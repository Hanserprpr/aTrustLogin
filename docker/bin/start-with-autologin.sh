#!/bin/bash

echo "[Environment Init] Starting aTrustLogin Docker Image ..."
echo "[Environment Init] Built at $(cat /etc/build-date.txt)"

rm -f /tmp/atrust-login-ready

start.sh > $HOME/atrust-startup.log 2>&1 &
echo "[Environment Init] aTrust started in background, log at $HOME/atrust-startup.log"

/bin/start-ssh.sh
start-port-forwarding.sh
/bin/start-ssh-proxy.sh &
exec start-with-autologin-actual.sh
