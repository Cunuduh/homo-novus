#!/usr/bin/env python3
"""Runs each ComfyUI configuration from a fresh server and records encode and per-step sampling times.
Step 1 includes building the reference-prefix KV cache; later steps show the sustained rate."""
import asyncio, json, os, pathlib, signal, subprocess, sys, time, uuid
import aiohttp
HERE = pathlib.Path(__file__).parent; ROOT = HERE.parent; COMFY = pathlib.Path.home() / "Repositories/ComfyUI"
URL = "http://127.0.0.1:8188"
AGGRESSIVE = ["--disable-smart-memory", "--cache-none", "--reserve-vram", "4"]
FP8, MI8, FAST = "ComfyUI-AppleSilicon-FP8", "ComfyUI-MPS-INT8", "ComfyUI-AppleSilicon-int8-Fast"
BOTH = [FP8, MI8]
# ref = reference resolution, None drops references; size = output w, h.
C = lambda name, ref=512, size=(832, 1248), nodes=BOTH, args=(), env=None, cache=("auto", "default"), mem=True: dict(name=name, ref=ref, size=size, nodes=nodes, args=list(args), env=env or {}, cache=cache, mem=mem)
CASES = [
 C("A1_refs768_output1MP", ref=768), C("A2_refs512", ref=512), C("A3_refs384", ref=384), C("A4_no_refs", ref=None),
 C("B1_refs512_output0.6MP", size=(640, 960)),
 C("C1_pytorch_attention", args=["--use-pytorch-cross-attention"]),
 C("D1_int8_kernel_off", env={"ASFP8_INT8_EXT": "off"}), C("D2_fp8_node_only", nodes=[FP8]), C("D3_mps_int8_only", nodes=[MI8]), C("D4_no_nodes", nodes=[]),
 C("D5_int8_fast_with_fp8", nodes=[FP8, FAST]), C("D6_int8_fast_only", nodes=[FAST]),
 C("E1_cache_cpu", cache=("cpu", "default")), C("E2_cache_int8", cache=("auto", "int8")), C("E3_cache_off", cache=("off", "default")),
 C("F1_default_memory", mem=False),
]
OUT = HERE / "results.jsonl"

def graph(c):
    g = json.loads((ROOT / "workflows/api/frankenstein_qwen21_turbo_edit.json").read_text())
    g["502"]["inputs"]["sigmas"] = "1.0, 0.978453, 0.95418, 0.926626"  # first 3 of the 8 Turbo steps
    g["456"]["inputs"].update(width=c["size"][0], height=c["size"][1])
    g["469"]["inputs"].update(device=c["cache"][0], dtype=c["cache"][1])
    e = g["474"]["inputs"]
    if c["ref"] is None:
        for k in list(e):
            if k.startswith("images."): del e[k]
        for k in ("1", "2", "3", "4", "11", "12", "13", "14"): del g[k]
    else:
        e["resolution"] = c["ref"]
        for k in ("11", "12", "13", "14"): g[k]["inputs"]["megapixels"] = round(c["ref"] ** 2 / 1e6, 3)
    return g

async def run(c):
    args = [".venv/bin/python", "main.py", "--listen", "127.0.0.1", "--port", "8188", "--disable-all-custom-nodes"]
    if c["nodes"]: args += ["--whitelist-custom-nodes", *c["nodes"]]
    args += c["args"] + (AGGRESSIVE if c["mem"] else [])
    log = open(HERE / f"{c['name']}.log", "w")
    p = subprocess.Popen(args, cwd=COMFY, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, **c["env"]})
    out = dict(name=c["name"])
    try:
        async with aiohttp.ClientSession() as s:
            for _ in range(240):
                try:
                    async with s.get(URL + "/system_stats") as r:
                        if r.status == 200: break
                except aiohttp.ClientError: pass
                await asyncio.sleep(1)
            cid = uuid.uuid4().hex
            async with s.ws_connect(f"ws://127.0.0.1:8188/ws?clientId={cid}") as ws:
                async with s.post(URL + "/prompt", json={"prompt": graph(c), "client_id": cid}) as r:
                    j = await r.json()
                    if r.status != 200: out["error"] = str(j)[:800]; return out
                t0, steps = time.time(), []
                while True:
                    m = await asyncio.wait_for(ws.receive(), timeout=1500)
                    if m.type != aiohttp.WSMsgType.TEXT:
                        if m.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR): out["error"] = "socket closed"; break
                        continue
                    d = json.loads(m.data)
                    if d["type"] == "progress" and d["data"].get("max") == 3: steps.append(round(time.time() - t0, 1))
                    elif d["type"] == "execution_success": break
                    elif d["type"] in ("execution_error", "execution_interrupted"): out["error"] = str(d["data"].get("exception_message"))[:500]; break
                out["to_step1_end_s"] = steps[0] if steps else None
                out["step_s"] = [round(b - a, 1) for a, b in zip(steps, steps[1:])]
                out["total_s"] = round(time.time() - t0, 1)
                out["swap"] = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout.strip()
    except Exception as e:
        out["error"] = repr(e)[:500]
    finally:
        p.send_signal(signal.SIGINT)
        try: p.wait(25)
        except subprocess.TimeoutExpired: p.kill(); p.wait()
    return out

async def main():
    only = sys.argv[1:]
    for c in CASES:
        if only and not any(c["name"].startswith(o) for o in only): continue
        r = await run(c)
        with open(OUT, "a") as f: f.write(json.dumps(r) + "\n")
        print(json.dumps(r), flush=True)
    print("BENCH_DONE", flush=True)
asyncio.run(main())
