#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Copy this file to docker/run-sdu-ssh-proxy.sh, then replace every CHANGE_ME
# value. The copied file is ignored by Git so credentials are not committed.
ATRUST_CONTAINER_NAME="atrust"
ATRUST_IMAGE="koishikiss/docker-sdu-atrust-autologin:custom"
ATRUST_OPTS='--cas=True --username="CHANGE_ME" --password="CHANGE_ME" --fingerprint="CHANGE_ME" --keepalive=100'
ATRUST_VNC_PASSWORD="CHANGE_ME"
ATRUST_PING_ADDR="CHANGE_ME"
ATRUST_PING_URL="http://CHANGE_ME/ping"

SSH_PROXY_HOST="CHANGE_ME"
SSH_PROXY_PORT="22"
SSH_PROXY_USER="CHANGE_ME"
# For a shared environment, prefer SSH_PROXY_PASSWORD_FILE instead.
SSH_PROXY_PASSWORD="CHANGE_ME"

if docker container inspect "$ATRUST_CONTAINER_NAME" >/dev/null 2>&1; then
  echo "[Runner] Reusing existing container: $ATRUST_CONTAINER_NAME"

  if [ "$(docker inspect -f '{{.State.Running}}' "$ATRUST_CONTAINER_NAME")" = "true" ]; then
    echo "[Runner] Container is already running; following logs."
    exec docker logs -f "$ATRUST_CONTAINER_NAME"
  fi

  chmod +x "$SCRIPT_DIR/bin/start-ssh-proxy.sh"
  docker cp "$SCRIPT_DIR/bin/start-ssh-proxy.sh" \
    "$ATRUST_CONTAINER_NAME:/bin/start-ssh-proxy.sh"
  docker cp "$SCRIPT_DIR/../src/." \
    "$ATRUST_CONTAINER_NAME:/opt/atrust-autologin/"
  echo "[Runner] Updated SSH proxy and login code without recreating the container."
  exec docker start -ai "$ATRUST_CONTAINER_NAME"
fi

docker run -it \
  --name "$ATRUST_CONTAINER_NAME" \
  --shm-size 256m \
  --device /dev/net/tun \
  --cap-add NET_ADMIN \
  --sysctl net.ipv4.conf.default.route_localnet=1 \
  -e "ATRUST_OPTS=$ATRUST_OPTS" \
  -e "PING_ADDR=$ATRUST_PING_ADDR" \
  -e "PING_ADDR_URL=$ATRUST_PING_URL" \
  -e "PASSWORD=$ATRUST_VNC_PASSWORD" \
  -e NODANTED=1 \
  -e "SSH_PROXY_HOST=$SSH_PROXY_HOST" \
  -e "SSH_PROXY_PORT=$SSH_PROXY_PORT" \
  -e "SSH_PROXY_USER=$SSH_PROXY_USER" \
  -e "SSH_PROXY_PASSWORD=$SSH_PROXY_PASSWORD" \
  -e SSH_PROXY_LOCAL_PORT=1081 \
  -e SSH_PROXY_PUBLISHED_HOST=127.0.0.1 \
  -e SSH_PROXY_PUBLISHED_PORT=1080 \
  -v "$HOME/.atrust-data:/root" \
  -p 10022:22 \
  -p 127.0.0.1:1080:1081 \
  "$ATRUST_IMAGE"
