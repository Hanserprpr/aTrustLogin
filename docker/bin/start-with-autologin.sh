#!/bin/bash

echo "Starting aTrustLogin Docker Image ..."
echo "Built at $(cat /etc/build-date.txt)"

start.sh > $HOME/atrust-startup.log 2>&1 &
start-port-forwarding.sh
exec start-with-autologin-actual.sh