#!/bin/bash

echo "[Environment Init] Starting aTrustLogin Docker Image ..."
echo "[Environment Init] Built at $(cat /etc/build-date.txt)"

start.sh > $HOME/atrust-startup.log 2>&1 &
start-port-forwarding.sh
exec start-with-autologin-actual.sh