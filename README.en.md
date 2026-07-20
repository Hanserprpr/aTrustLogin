# aTrustLogin

[中文版本](/README.md)

This project provides an automated solution for logging into Sangfor aTrust, enabling VPN connectivity without manual intervention. The main features of the project are:

- Automatically opens the aTrust Web login page
- Auto-fills username and password
- Automatically derives and inputs TOTP two-factor authentication codes
- Bypasses CAPTCHA using cookie state
- KeepAlive connection for session persistence and auto-reconnection on logout or disconnection
- Supports Windows, Linux, x86-64, and ARM64

## Usage Instructions
The project provides two methods: Docker and General.

The **Docker method** is Linux-specific and requires no dependency installation or configuration, making it ideal for headless environments like soft routers or industrial PCs.

The **General method** works on all platforms but requires manual installation of Python 3.8+ and Selenium. If possible, use the Docker method.

### General Method

#### Browser Setup
- **Windows:** Uses the default Microsoft Edge browser for Windows 10 1903+ and Windows 11. No additional browser or driver installation is typically required. For other browsers, refer to the [Selenium Documentation](https://www.selenium.dev/documentation/en/webdriver/driver_requirements/) for driver installation.
- **Linux:** Requires Chromium. Install it on Debian/Ubuntu using:
  ```bash
  apt-get install -y chromium chromium-driver chromium-l10n
  ```

#### Project Setup
Download the project and install dependencies. Both domestic and international download options are provided. If international downloads are slow, use the domestic option.

**International Option:**
```bash
git clone --depth=1 https://github.com/kenvix/aTrustLogin.git aTrustLogin
cd aTrustLogin/src
pip install -r requirements.txt
```

Run the program with the parameters outlined in the "Program Parameters" section.

### Program Parameters

The following parameters are supported:

- `--portal_address`: VPN portal address (URL), e.g., `https://atrust.moe.edu.cn/`
- `--username`: VPN username
- `--password`: VPN password
- `--totp_key`: TOTP secret for two-factor authentication (optional)
- `--cookie_tid`: Cookie ID for session tracking (optional, to bypass CAPTCHA)
- `--cookie_sig`: Cookie signature for session tracking (optional, to bypass CAPTCHA)
- `--keepalive`: Optional. Session keep-alive interval in seconds. `0` disables it.
- `--data_dir`: Optional. Path to store cookies and session data.
- `--driver_type`: Optional. WebDriver type (e.g., "chrome", "edge").
- `--driver_path`: Optional. Path to the WebDriver executable.
- `--browser_path`: Optional. Path to the browser executable.
- `--interactive`: Optional. Enables interactive mode.
- `--wait_atrust`: Optional. Waits for aTrust to listen on the specified port.

**Example Command:**
```bash
python main.py --portal_address "https://example.com" --username "your_username" --password "your_password" --totp_key "your_totp_key" --cookie_tid "your_cookie_tid" --cookie_sig "your_cookie_sig" --keepalive 300 --interactive True --wait_atrust True
```

### Docker Method

Pull the Docker image using:
```bash
docker pull kenvix/atrust-autologin:latest
```

If downloads are slow, use the domestic address:
```bash
wget https://modelscope.cn/models/kenvix/aTrustLoginRepo/resolve/master/docker-atrust-autologin-amd64.tar.xz -O - | xz -dc | docker load
docker tag kenvix/docker-atrust-autologin:amd64 kenvix/docker-atrust-autologin:latest
```

Set program parameters in the `ATRUST_OPTS` environment variable and run the Docker container:
```bash
docker run -it --rm -e ATRUST_OPTS='--portal_address="your_portal" --username="your_username" --password="your_password"' kenvix/atrust-autologin:latest
```

### SSH SOCKS5 proxy over aTrust

Set `SSH_PROXY_HOST` and `SSH_PROXY_USER` to create an outbound SSH dynamic-forward proxy after aTrust authentication succeeds. The SSH server should be reachable through the aTrust network. Authentication can use a private key, password file, or password environment variable; a readable private key takes precedence.

```shell
docker run -it --rm \
  --device /dev/net/tun --cap-add NET_ADMIN \
  -e NODANTED=1 \
  -e ATRUST_OPTS='--cas=True --username="student_id" --password="password"' \
  -e SSH_PROXY_HOST='vpn-internal-ssh-host' \
  -e SSH_PROXY_USER='ssh-user' \
  -e SSH_PROXY_IDENTITY_FILE=/run/secrets/ssh_proxy_key \
  -v "$HOME/.atrust-data:/root" \
  -v "$HOME/.ssh/atrust_proxy:/run/secrets/ssh_proxy_key:ro" \
  -p 127.0.0.1:1080:1081 \
  atrust-login-sdu:latest
```

Use `socks5h://127.0.0.1:1080` in the browser or application. The proxy stops when the aTrust session is lost and reconnects automatically after authentication is restored. Optional settings include `SSH_PROXY_PORT` (default `22`), `SSH_PROXY_LOCAL_PORT` (default `1081`), `SSH_PROXY_KNOWN_HOSTS_FILE`, `SSH_PROXY_STRICT_HOST_KEY_CHECKING` (default `accept-new`), and `SSH_PROXY_RETRY_INTERVAL` (default `5`).

The startup script protects the Docker gateway return route from more-specific routes installed by aTrust. After the SSH forward is listening, it prints a `READY` block with the SOCKS5 protocol, published address, port, URL, and browser DNS guidance. Override the displayed endpoint with `SSH_PROXY_PUBLISHED_HOST` and `SSH_PROXY_PUBLISHED_PORT` when the Docker publish mapping differs from `127.0.0.1:1080`.

A credential-free runner template is available at [`docker/run-sdu-ssh-proxy.example.sh`](docker/run-sdu-ssh-proxy.example.sh). Copy it to the Git-ignored local runner, replace all `CHANGE_ME` values, and start it:

```shell
cp docker/run-sdu-ssh-proxy.example.sh docker/run-sdu-ssh-proxy.sh
chmod 700 docker/run-sdu-ssh-proxy.sh
./docker/run-sdu-ssh-proxy.sh
```

If the `atrust` container already exists, the runner reuses it. A running container is left untouched and its logs are followed; a stopped container receives the latest proxy and login code before being restarted in place, preserving its saved device identity.

For password authentication, replace the private-key setting and mount with `SSH_PROXY_PASSWORD_FILE=/run/secrets/ssh_proxy_password` and a read-only password-file mount. `SSH_PROXY_PASSWORD` is also supported but is less secure because container administrators can inspect environment variables. It is distinct from `SSH_PASSWORD`, which configures inbound SSH access to the container.

To avoid CAPTCHA during the first login:
1. Log in via the aTrust webpage and input the CAPTCHA manually.
2. Save `tid` and `tid.sig` cookies from your browser's developer tools.
3. Add these values to `--cookie_tid` and `--cookie_sig`.

**Note:** By default, containers are temporary. For persistent data and auto-start on boot, replace `--rm` with `--restart unless-stopped`.

### CAPTCHA Bypass

To bypass the CAPTCHA:
1. Open the aTrust login webpage, log in, and input the CAPTCHA manually.
2. Open browser developer tools (F12) and go to the Application tab.
3. Find the `tid` and `tid.sig` cookies, copy their values, and use them in `--cookie_tid` and `--cookie_sig`.

![Cookie Example](doc/cookie.webp)

### Integration with FRP

FRP (Fast Reverse Proxy) is an intranet penetration tool. You can use FRP to map local aTrust services to a public server.

1. Edit the `run.sh` script in the `frpc` directory.
2. Download the FRP binary and place it in the `frpc/frp` directory.
3. Run `run.sh` to automatically create and start the Docker image with port mapping.
4. Use `run.sh` for future starts, not `docker start`.

For further options and environment variables (e.g., `PING_ADDR`, `PING_INTERVAL`), refer to the [docker-easyconnect documentation](https://github.com/docker-easyconnect/docker-easyconnect/blob/master/doc/usage.md).
