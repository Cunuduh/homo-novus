#!/usr/bin/env python3
"""Queues an API workflow on a local ComfyUI, waits, and prints timing, the enhanced prompt and outputs."""
import json, sys, time, urllib.request as u, urllib.error
S = "http://127.0.0.1:8188"
g = json.load(open(sys.argv[1]))
try:
    pid = json.load(u.urlopen(u.Request(S + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})))["prompt_id"]
except urllib.error.HTTPError as e:
    sys.exit("REJECTED " + e.read().decode()[:3000])
t = time.time(); print("queued", pid, flush=True)
while True:
    time.sleep(10)
    h = json.load(u.urlopen(f"{S}/history/{pid}")).get(pid)
    if h: break
print("status", h["status"]["status_str"], "elapsed", round(time.time() - t), "s")
for m in h["status"]["messages"]:
    if m[0] == "execution_error": print("ERROR", m[1]["node_type"], m[1]["exception_message"][:1500])
for k, o in h["outputs"].items():
    print(k, json.dumps(o, ensure_ascii=False)[:6000])
