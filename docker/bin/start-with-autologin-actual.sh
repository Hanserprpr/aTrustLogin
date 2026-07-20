#!/bin/bash

# 设置要等待的 X11 显示环境
DISPLAY=":1"
export DISPLAY

# Parse the option string without eval so quoted credentials remain a single
# argument and shell metacharacters are not executed.
mapfile -d '' -t ATRUST_ARGS < <(
  python3 -c 'import os, shlex, sys; sys.stdout.write("\0".join(shlex.split(os.environ.get("ATRUST_OPTS", ""))) + "\0")'
)

# 检查 X11 是否已启动
while ! xset q >/dev/null 2>&1; do
    echo "[Environment Init] Waiting for X11 to start..."
    sleep 3
done

# 无限循环直到成功
while true; do
  # 执行命令
  python3 /opt/atrust-autologin/main.py --interactive=True --wait_atrust=True --driver_type=chrome \
  --data_dir="$HOME/.atrust-data" \
  --driver_path=/usr/bin/chromedriver --browser_path=/usr/bin/chromium "${ATRUST_ARGS[@]}"

  # 检查退出状态码
  if [ $? -eq 0 ]; then
      echo "[Program Exit] Autologin Command executed successfully."
      break
  elif [ $? -eq 1 ]; then
      echo "[Program Exit] Autologin Command executed unsuccessfully."
      break
  else
      echo "[Program Restart] Autologin Command crashed. Restarting..."
      sleep 3  # 添加一个短暂的等待时间，以避免立即重试，增加稳定性
  fi
done
