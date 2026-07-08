#!/bin/bash
# start-ssh.sh — 配置并启动 SSH 服务

if [ -z "$SSH_PASSWORD" ]; then
    echo "[SSH] SSH_PASSWORD not set, SSH server will not start."
    exit 0
fi

SSH_USER="${SSH_USER:-atrust}"
useradd -m -s /bin/bash "$SSH_USER" 2>/dev/null || true
echo "$SSH_USER:$SSH_PASSWORD" | chpasswd
echo "[SSH] User '$SSH_USER' password set."

sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

mkdir -p /var/run/sshd

/usr/sbin/sshd > $HOME/ssh-server.log 2>&1 &
echo "[SSH] SSH server started on port 22, log at $HOME/ssh-server.log"
