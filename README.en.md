# aTrustLogin SDU SSH Proxy

[中文版本](README.md)

This is the SDU-focused edition hosted at [Hanserprpr/aTrustLogin](https://github.com/Hanserprpr/aTrustLogin). It automatically authenticates to SDU aTrust in Docker, creates an SSH dynamic forward through the VPN, and publishes a SOCKS5 endpoint on the host.

```text
Browser / Shadowrocket / application
  -> SOCKS5 127.0.0.1:1080
  -> Docker 0.0.0.0:1081
  -> aTrust VPN
  -> SSH dynamic-forward server
  -> intranet website or another TCP destination
```

## Features

- Automated SDU CAS authentication and session keepalive.
- Persistent aTrust device identity and login data.
- Explicit Chromium/ChromeDriver discovery inside Docker.
- Cookie-only fallback when an aTrust page blocks `localStorage` access.
- SSH private-key, password-file, and password-environment authentication.
- Automatic SSH reconnection.
- Docker gateway return-route protection after aTrust installs its routes.
- In-place updates of stopped containers without deleting the saved device identity.
- A clear `READY` block containing the SOCKS5 address, port, and URL.

## Quick start

```shell
git clone -b sdu-adapter https://github.com/Hanserprpr/aTrustLogin.git
cd aTrustLogin
docker build -t koishikiss/docker-sdu-atrust-autologin:custom .

cp docker/run-sdu-ssh-proxy.example.sh docker/run-sdu-ssh-proxy.sh
chmod 700 docker/run-sdu-ssh-proxy.sh
```

Replace every `CHANGE_ME` value in `docker/run-sdu-ssh-proxy.sh`, then start it:

```shell
./docker/run-sdu-ssh-proxy.sh
```

The proxy is ready when the console prints:

```text
[SSH proxy] READY
[SSH proxy] Protocol       : SOCKS5
[SSH proxy] Connect address: 127.0.0.1
[SSH proxy] Connect port   : 1080
[SSH proxy] Proxy URL      : socks5h://127.0.0.1:1080
```

The local runner is Git-ignored, so its real credentials are not committed.

## Configuration

The public template is [`docker/run-sdu-ssh-proxy.example.sh`](docker/run-sdu-ssh-proxy.example.sh).

| Variable | Purpose |
| --- | --- |
| `ATRUST_CONTAINER_NAME` | Docker container name; defaults to `atrust` |
| `ATRUST_IMAGE` | Locally built image |
| `ATRUST_OPTS` | CAS credentials, fingerprint, and keepalive options |
| `ATRUST_VNC_PASSWORD` | VNC console password |
| `ATRUST_PING_ADDR` | VPN-side ping keepalive target |
| `ATRUST_PING_URL` | VPN-side HTTP keepalive URL |
| `SSH_PROXY_HOST` | SSH server reachable through aTrust |
| `SSH_PROXY_PORT` | SSH server port; defaults to `22` |
| `SSH_PROXY_USER` | SSH user |
| `SSH_PROXY_PASSWORD` | SSH password for personal environments |

`SSH_PASSWORD` configures inbound SSH access to the container itself. `SSH_PROXY_PASSWORD` authenticates to the outbound SSH proxy server; they are different settings.

## SSH authentication

Authentication priority is private key, then password file, then password environment variable.

Private key:

```shell
-e SSH_PROXY_IDENTITY_FILE=/run/secrets/ssh_proxy_key \
-v "$HOME/.ssh/atrust_proxy:/run/secrets/ssh_proxy_key:ro"
```

Password file:

```shell
-e SSH_PROXY_PASSWORD_FILE=/run/secrets/ssh_proxy_password \
-v "$HOME/.ssh/atrust_proxy_password:/run/secrets/ssh_proxy_password:ro"
```

Password environment variable:

```shell
-e SSH_PROXY_PASSWORD='remote-ssh-password'
```

Prefer a private key or read-only password file in shared environments because container administrators can inspect environment variables.

## Client configuration

- Protocol: SOCKS5
- Host: `127.0.0.1`
- Port: `1080`
- DNS: resolve through the proxy (`socks5h`)

Test a TCP destination with:

```shell
curl --proxy socks5h://127.0.0.1:1080 -I http://destination/
```

HTTP, HTTPS, WebSocket, and other TCP traffic are supported. Standard UDP/QUIC forwarding is not supported by SSH dynamic forwarding.

## Shadowrocket routing

Create a SOCKS5 node for `127.0.0.1:1080` and route selected intranet IPs to it. Keep the outbound SSH server port on `DIRECT`; otherwise, the SSH connection can loop back into its own SOCKS5 proxy.

```ini
[Proxy]
Local = socks5, 127.0.0.1, 1080

[Rule]
DEST-PORT,actual-ssh-port,DIRECT
IP-CIDR,target-address/32,Local,no-resolve
FINAL,DIRECT
```

If enabling Shadowrocket disrupts aTrust/CAS, bypass the aTrust portal, CAS addresses, and Docker-related subnets in Shadowrocket or its TUN routes.

## Reusing the container

Do not remove the `atrust` container just to update scripts:

- Running container: the runner follows its logs without changing it.
- Stopped container: the runner copies in the latest proxy and login code, then starts it in place.
- Missing container: the runner creates it from the local configuration.

To load the latest code into an existing container:

```shell
docker stop atrust
./docker/run-sdu-ssh-proxy.sh
```

This preserves both the container and the data mounted at `$HOME/.atrust-data`.

## Troubleshooting

- `Unable to obtain driver for chrome`: rebuild the image from this repository so Chromium and its matching driver are installed and explicitly selected.
- `Failed to read the localStorage property`: this edition records the warning, saves cookies, and continues login.
- Web session check fails while SOCKS5 still works: the live SSH SOCKS5 data plane is treated as authoritative, avoiding disruptive repeated CAS authentication.
- `READY` is shown but the host times out: confirm the publish mapping is `127.0.0.1:1080:1081` and look for `Docker return route protected` in the logs.

## Security

- Never commit `docker/run-sdu-ssh-proxy.sh`, SSH keys, password files, or persisted aTrust data.
- Keep the host SOCKS5 listener bound to `127.0.0.1`; do not expose it directly to the public internet.
- For production, pre-populate `known_hosts` and set `SSH_PROXY_STRICT_HOST_KEY_CHECKING=yes`.
- The SSH server must allow TCP forwarding with `AllowTcpForwarding yes`.

## Credits

This edition builds on [kenvix/aTrustLogin](https://github.com/kenvix/aTrustLogin) and [docker-easyconnect](https://github.com/docker-easyconnect/docker-easyconnect).
