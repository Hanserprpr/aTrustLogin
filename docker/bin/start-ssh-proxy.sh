#!/bin/bash
# Maintains an outbound SSH dynamic-forward proxy after aTrust is authenticated.

set -u

if [ -z "${SSH_PROXY_HOST:-}" ]; then
    echo "[SSH proxy] SSH_PROXY_HOST is not set; outbound SSH SOCKS5 proxy is disabled."
    exit 0
fi

if [ -z "${SSH_PROXY_USER:-}" ]; then
    echo "[SSH proxy] ERROR: SSH_PROXY_USER is required when SSH_PROXY_HOST is set."
    exit 1
fi

SSH_PROXY_PORT="${SSH_PROXY_PORT:-22}"
SSH_PROXY_LOCAL_PORT="${SSH_PROXY_LOCAL_PORT:-1081}"
SSH_PROXY_IDENTITY_FILE="${SSH_PROXY_IDENTITY_FILE:-/root/.ssh/id_ed25519}"
SSH_PROXY_PASSWORD_FILE="${SSH_PROXY_PASSWORD_FILE:-}"
SSH_PROXY_KNOWN_HOSTS_FILE="${SSH_PROXY_KNOWN_HOSTS_FILE:-/root/.ssh/known_hosts}"
SSH_PROXY_STRICT_HOST_KEY_CHECKING="${SSH_PROXY_STRICT_HOST_KEY_CHECKING:-accept-new}"
SSH_PROXY_RETRY_INTERVAL="${SSH_PROXY_RETRY_INTERVAL:-5}"
SSH_PROXY_PUBLISHED_HOST="${SSH_PROXY_PUBLISHED_HOST:-127.0.0.1}"
SSH_PROXY_PUBLISHED_PORT="${SSH_PROXY_PUBLISHED_PORT:-1080}"
ATRUST_READY_FILE="${ATRUST_READY_FILE:-/tmp/atrust-login-ready}"

for value_name in SSH_PROXY_PORT SSH_PROXY_LOCAL_PORT SSH_PROXY_RETRY_INTERVAL SSH_PROXY_PUBLISHED_PORT; do
    value="${!value_name}"
    if ! [[ "$value" =~ ^[0-9]+$ ]] || [ "$value" -lt 1 ] || [ "$value" -gt 65535 ]; then
        echo "[SSH proxy] ERROR: $value_name must be an integer between 1 and 65535."
        exit 1
    fi
done

ssh_prefix=()
ssh_auth_args=()

if [ -r "$SSH_PROXY_IDENTITY_FILE" ]; then
    ssh_auth_args=(-i "$SSH_PROXY_IDENTITY_FILE" -o BatchMode=yes)
    auth_description="private key $SSH_PROXY_IDENTITY_FILE"
elif [ -n "$SSH_PROXY_PASSWORD_FILE" ]; then
    if [ ! -r "$SSH_PROXY_PASSWORD_FILE" ]; then
        echo "[SSH proxy] ERROR: password file is not readable: $SSH_PROXY_PASSWORD_FILE"
        exit 1
    fi
    ssh_prefix=(sshpass -f "$SSH_PROXY_PASSWORD_FILE")
    ssh_auth_args=(-o BatchMode=no -o PreferredAuthentications=password -o PubkeyAuthentication=no)
    auth_description="password file $SSH_PROXY_PASSWORD_FILE"
elif [ -n "${SSH_PROXY_PASSWORD:-}" ]; then
    export SSHPASS="$SSH_PROXY_PASSWORD"
    ssh_prefix=(sshpass -e)
    ssh_auth_args=(-o BatchMode=no -o PreferredAuthentications=password -o PubkeyAuthentication=no)
    auth_description="password environment variable"
else
    echo "[SSH proxy] ERROR: no authentication configured. Provide a readable SSH_PROXY_IDENTITY_FILE, SSH_PROXY_PASSWORD_FILE, or SSH_PROXY_PASSWORD."
    exit 1
fi

if [ "${#ssh_prefix[@]}" -gt 0 ] && ! command -v sshpass >/dev/null 2>&1; then
    echo "[SSH proxy] ERROR: sshpass is required for password authentication."
    exit 1
fi

docker_gateway="$(ip route show default | awk 'NR == 1 {print $3}')"
docker_interface="$(ip route show default | awk 'NR == 1 {print $5}')"
container_ip=""
if [ -n "$docker_interface" ]; then
    container_ip="$(ip -4 addr show dev "$docker_interface" | awk '/inet / {sub(/\/.*/, "", $2); print $2; exit}')"
fi

repair_docker_return_route() {
    if [ -z "$docker_gateway" ] || [ -z "$docker_interface" ] || [ -z "$container_ip" ]; then
        echo "[SSH proxy] WARNING: unable to determine Docker gateway route; published ports may be affected by aTrust routes."
        return
    fi

    if ip route replace "$docker_gateway/32" dev "$docker_interface" src "$container_ip"; then
        echo "[SSH proxy] Docker return route protected: $docker_gateway via $docker_interface"
    else
        echo "[SSH proxy] WARNING: failed to protect Docker gateway return route."
    fi
}

is_socks_listening() {
    ss -lntH 2>/dev/null | awk -v endpoint=":$SSH_PROXY_LOCAL_PORT" \
        '$4 ~ endpoint "$" {found = 1} END {exit !found}'
}

announce_proxy_ready() {
    echo "============================================================"
    echo "[SSH proxy] READY"
    echo "[SSH proxy] Protocol       : SOCKS5"
    echo "[SSH proxy] Connect address: $SSH_PROXY_PUBLISHED_HOST"
    echo "[SSH proxy] Connect port   : $SSH_PROXY_PUBLISHED_PORT"
    echo "[SSH proxy] Proxy URL      : socks5h://$SSH_PROXY_PUBLISHED_HOST:$SSH_PROXY_PUBLISHED_PORT"
    echo "[SSH proxy] Browser config : SOCKS v5, enable proxy DNS"
    echo "[SSH proxy] Route          : aTrust -> SSH $SSH_PROXY_HOST:$SSH_PROXY_PORT -> destination"
    echo "============================================================"
}

mkdir -p "$(dirname "$SSH_PROXY_KNOWN_HOSTS_FILE")"
touch "$SSH_PROXY_KNOWN_HOSTS_FILE"

ssh_pid=""

stop_ssh() {
    if [ -n "$ssh_pid" ] && kill -0 "$ssh_pid" 2>/dev/null; then
        kill "$ssh_pid" 2>/dev/null || true
        wait "$ssh_pid" 2>/dev/null || true
    fi
    ssh_pid=""
}

trap 'stop_ssh; exit 0' INT TERM

echo "[SSH proxy] Waiting for aTrust authentication ..."

while true; do
    while [ ! -f "$ATRUST_READY_FILE" ]; do
        sleep 2
    done

    repair_docker_return_route
    echo "[SSH proxy] Starting SOCKS5 on 0.0.0.0:$SSH_PROXY_LOCAL_PORT via $SSH_PROXY_HOST:$SSH_PROXY_PORT using $auth_description"
    "${ssh_prefix[@]}" ssh -N \
        -D "0.0.0.0:$SSH_PROXY_LOCAL_PORT" \
        -p "$SSH_PROXY_PORT" \
        -l "$SSH_PROXY_USER" \
        "${ssh_auth_args[@]}" \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ConnectTimeout=15 \
        -o "StrictHostKeyChecking=$SSH_PROXY_STRICT_HOST_KEY_CHECKING" \
        -o "UserKnownHostsFile=$SSH_PROXY_KNOWN_HOSTS_FILE" \
        "$SSH_PROXY_HOST" &
    ssh_pid=$!

    for _ in $(seq 1 50); do
        if ! kill -0 "$ssh_pid" 2>/dev/null; then
            break
        fi
        if is_socks_listening; then
            announce_proxy_ready
            break
        fi
        sleep 0.1
    done

    while kill -0 "$ssh_pid" 2>/dev/null; do
        if [ ! -f "$ATRUST_READY_FILE" ]; then
            echo "[SSH proxy] aTrust session is unavailable; stopping SSH proxy."
            stop_ssh
            break
        fi
        sleep 2
    done

    if [ -n "$ssh_pid" ]; then
        wait "$ssh_pid" 2>/dev/null || true
        ssh_pid=""
        echo "[SSH proxy] SSH connection ended; retrying in ${SSH_PROXY_RETRY_INTERVAL}s."
        sleep "$SSH_PROXY_RETRY_INTERVAL"
    fi
done
