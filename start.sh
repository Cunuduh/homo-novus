#!/bin/zsh
# Starts the app, then opens the page. Default engine is mflux (MLX). `./start.sh comfy` falls back to ComfyUI.
ROOT=${0:A:h}; COMFY=~/Repositories/ComfyUI; mkdir -p "$ROOT/logs"
ENGINE=${1:-mflux}; export PROMETHEUS_BACKEND=$ENGINE
pkill -f "$ROOT/server.py" 2>/dev/null; pkill -f mflux_worker.py 2>/dev/null
if [[ $ENGINE == comfy ]]; then
  if ! curl -sf http://127.0.0.1:8188/system_stats >/dev/null; then
    (cd "$COMFY" && nohup .venv/bin/python main.py --listen 127.0.0.1 --port 8188 --disable-smart-memory --cache-none --reserve-vram 4 --preview-method taesd --preview-size 512 > "$ROOT/logs/comfy.log" 2>&1 &)
    until curl -sf http://127.0.0.1:8188/system_stats >/dev/null; do sleep 1; done
  fi
else
  pkill -f "main.py --listen" 2>/dev/null  # mflux needs the memory
fi
open http://127.0.0.1:8420
exec "$COMFY/.venv/bin/python" "$ROOT/server.py"
