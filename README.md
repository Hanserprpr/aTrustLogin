# aTrustLogin SDU SSH Proxy

[English Version](README.en.md)

这是 [Hanserprpr/aTrustLogin](https://github.com/Hanserprpr/aTrustLogin) 的 SDU 定制版。它会在 Docker 中自动登录山东大学 aTrust，再通过指定 SSH 服务器建立动态转发，向宿主机提供一个 SOCKS5 代理端口。

```text
浏览器 / Shadowrocket / 其他应用
              -> SOCKS5 127.0.0.1:1080
              -> Docker 容器 0.0.0.0:1081
              -> aTrust VPN
              -> SSH 动态转发服务器
              -> 校内网页或其他 TCP 目标
```

## 功能

- 山东大学 CAS 自动认证和会话保活。
- 持久化 aTrust 数据和设备绑定信息。
- 修复 Docker 内 Chromium/ChromeDriver 自动发现失败。
- 兼容登录后无法读取 `localStorage` 的 aTrust 页面。
- 支持 SSH 密钥、密码文件或密码环境变量。
- SSH 断线自动重连。
- 保护 Docker 网关回程路由，避免 aTrust 下发路由后宿主机无法连接映射端口。
- 支持复用旧容器并热更新登录/代理代码，避免因删除容器而重新验证设备。
- 代理就绪后明确输出协议、连接地址、端口和 URL。

## 快速开始

### 1. 获取代码

```shell
git clone -b sdu-adapter https://github.com/Hanserprpr/aTrustLogin.git
cd aTrustLogin
```

### 2. 构建镜像

```shell
docker build -t koishikiss/docker-sdu-atrust-autologin:custom .
```

### 3. 生成本地启动脚本

macOS/Linux：

```shell
cp docker/run-sdu-ssh-proxy.example.sh docker/run-sdu-ssh-proxy.sh
chmod 700 docker/run-sdu-ssh-proxy.sh
```

Windows PowerShell：

```powershell
Copy-Item docker/run-sdu-ssh-proxy.example.ps1 docker/run-sdu-ssh-proxy.ps1
```

编辑复制出的 `.sh` 或 `.ps1` 脚本，将所有 `CHANGE_ME` 替换为实际配置。这两个本地脚本均已加入 `.gitignore`，其中的真实账号和密码不会被 Git 提交。

### 4. 启动

```shell
./docker/run-sdu-ssh-proxy.sh
```

Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\docker\run-sdu-ssh-proxy.ps1
```

看到以下内容即表示代理已就绪：

```text
============================================================
[SSH proxy] READY
[SSH proxy] Protocol       : SOCKS5
[SSH proxy] Connect address: 127.0.0.1
[SSH proxy] Connect port   : 1080
[SSH proxy] Proxy URL      : socks5h://127.0.0.1:1080
[SSH proxy] Browser config : SOCKS v5, enable proxy DNS
============================================================
```

## 启动脚本配置

[`docker/run-sdu-ssh-proxy.example.sh`](docker/run-sdu-ssh-proxy.example.sh) 和 [`docker/run-sdu-ssh-proxy.example.ps1`](docker/run-sdu-ssh-proxy.example.ps1) 是可公开提交的模板，不包含真实凭据。主要变量如下：

| 变量 | 用途 |
| --- | --- |
| `ATRUST_CONTAINER_NAME` | Docker 容器名，默认 `atrust` |
| `ATRUST_IMAGE` | 要启动的本地镜像 |
| `ATRUST_OPTS` | CAS 账号、密码、设备指纹和保活参数 |
| `ATRUST_VNC_PASSWORD` | 容器 VNC 控制台密码 |
| `ATRUST_PING_ADDR` | VPN 内用于发包保活的地址 |
| `ATRUST_PING_URL` | VPN 内用于 HTTP 保活的 URL |
| `SSH_PROXY_HOST` | aTrust 链路上可达的 SSH 服务器 |
| `SSH_PROXY_PORT` | SSH 服务器端口，默认 `22` |
| `SSH_PROXY_USER` | SSH 登录用户 |
| `SSH_PROXY_PASSWORD` | SSH 登录密码，仅建议用于个人环境 |

`SSH_PASSWORD` 和 `SSH_PROXY_PASSWORD` 不是同一个参数：前者用于登录容器自身的 SSH 服务，后者用于连接二级代理服务器。

## SSH 认证方式

优先级为：私钥 > 密码文件 > 密码环境变量。

### 私钥（推荐）

```shell
-e SSH_PROXY_IDENTITY_FILE=/run/secrets/ssh_proxy_key \
-v "$HOME/.ssh/atrust_proxy:/run/secrets/ssh_proxy_key:ro"
```

### 密码文件（推荐）

```shell
-e SSH_PROXY_PASSWORD_FILE=/run/secrets/ssh_proxy_password \
-v "$HOME/.ssh/atrust_proxy_password:/run/secrets/ssh_proxy_password:ro"
```

### 密码环境变量

```shell
-e SSH_PROXY_PASSWORD='远程SSH密码'
```

密码环境变量使用方便，但容器管理员可以读取，因此不建议用于共享环境。

## 客户端配置

浏览器或应用配置：

- 协议：SOCKS5
- 地址：`127.0.0.1`
- 端口：`1080`
- DNS：启用“通过代理解析 DNS”，即使用 `socks5h`

简单验证：

```shell
curl --proxy socks5h://127.0.0.1:1080 -I http://目标地址/
```

HTTP、HTTPS 和 WebSocket 等 TCP 流量均可以通过该代理。SSH 动态转发不支持普通 UDP/QUIC 流量。

## Shadowrocket 分流

建立一个指向 `127.0.0.1:1080` 的 SOCKS5 节点，再将指定校内 IP 分流到该节点。SSH 服务器的连接端口必须设为 `DIRECT`，否则会形成“SSH 连接继续走自己的 SOCKS5”的代理回环。

```ini
[Proxy]
本地节点 = socks5, 127.0.0.1, 1080

[Rule]
DEST-PORT,实际SSH端口,DIRECT
IP-CIDR,需要代理的IP/32,本地节点,no-resolve
FINAL,DIRECT
```

如果 Shadowrocket 开启后导致 aTrust/CAS 断线，还应将 aTrust 门户、CAS 地址和 Docker 相关网段设为直连或 TUN 旁路路由。

## 复用容器

不要为了更新脚本而删除 `atrust` 容器。直接运行启动脚本时：

- 容器正在运行：不修改容器，直接跟随日志。
- 容器已停止：把最新代理脚本和 Python 登录代码复制进旧容器，然后原地启动。
- 容器不存在：按照本地脚本中的配置新建容器。

如果需要将最新代码加载到已存在的容器：

```shell
docker stop atrust
./docker/run-sdu-ssh-proxy.sh
```

这不会删除容器，也不会删除挂载在 `$HOME/.atrust-data` 中的数据。

## Windows 支持

Windows 版需要 Docker Desktop 使用 WSL 2 后端和 Linux containers 模式。PowerShell 脚本会在启动前检查 Docker 是否可用以及容器操作系统是否为 Linux。Windows 应用仍然使用 SOCKS5 `127.0.0.1:1080`。

PowerShell 从 Windows 文件系统热更新已停止容器时，只复制不依赖 Unix 可执行权限的 Python 登录代码；SSH 代理 Shell 脚本由当前构建的镜像提供。如果修改了 `docker/bin/start-ssh-proxy.sh`，请先重新构建镜像。

如果 Docker 报告找不到 `/dev/net/tun`，请更新 WSL/Docker Desktop，确认已切换到 Linux containers，并检查：

```powershell
docker run --rm --device /dev/net/tun --entrypoint sh koishikiss/docker-sdu-atrust-autologin:custom -c "test -c /dev/net/tun && echo TUN-OK"
```

## 常见问题

### `Unable to obtain driver for chrome`

镜像需要同时包含 Chromium 和匹配的 `chromium-driver`。当前版本会显式寻找 `/usr/bin/chromedriver`，并传给 Selenium。请先用本仓库重新构建镜像。

### `Failed to read the localStorage property`

某些 aTrust 跳转页面禁止读取 `localStorage`。当前版本会记录警告并继续保存 Cookie，不再因此判定登录失败。

### CAS 保活检查失败，但 SOCKS5 仍然可用

当 Web 会话检查失败、但本地 SSH SOCKS5 监听器仍存活时，程序会以实际数据链路为准，保留现有 VPN/SSH 代理，避免反复 CAS 认证导致链路中断。

### 代理显示 `READY`，但宿主机连接超时

检查 Docker 端口映射是否为 `127.0.0.1:1080:1081`。启动脚本会自动添加 Docker 网关 `/32` 回程路由；日志中应该出现 `Docker return route protected`。

## 安全提示

- 不要提交 `docker/run-sdu-ssh-proxy.sh`、私钥、密码文件或 aTrust 持久化数据。
- 宿主机 SOCKS5 默认只绑定 `127.0.0.1`，请不要直接暴露到公网。
- 生产环境建议预先配置 SSH `known_hosts`，并把 `SSH_PROXY_STRICT_HOST_KEY_CHECKING` 设为 `yes`。
- SSH 服务器需要允许 TCP 转发：`AllowTcpForwarding yes`。

## 致谢

本项目基于 [kenvix/aTrustLogin](https://github.com/kenvix/aTrustLogin) 和 [docker-easyconnect](https://github.com/docker-easyconnect/docker-easyconnect) 的工作进行定制。
