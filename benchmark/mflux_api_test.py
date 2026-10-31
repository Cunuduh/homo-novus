#!/usr/bin/env python3
"""Runs N generations through the app's API, recording timing, events and preview frames."""
import asyncio, aiohttp, json, sys, time, pathlib
R = pathlib.Path("refs"); N = int(sys.argv[1]); PREV = pathlib.Path(sys.argv[2])
SC = ["Hunched over a cluttered wooden desk in a candlelit study at night, glaring at the camera", "Standing on a foggy moonlit moor at night, arms raised toward the sky, roaring", "Walking through a neon-lit city street in the rain at night"]
async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None)) as s:
        async with s.ws_connect("http://127.0.0.1:8420/api/ws?clientId=t") as ws:
            for r in range(N):
                f = aiohttp.FormData()
                for k, n in [("face","face_lincoln"),("arms","arms_houdini"),("torso","torso_roosevelt"),("legs","legs_keaton")]:
                    f.add_field(k, (R/f"{n}.jpg").read_bytes(), filename=n+".jpg", content_type="image/jpeg")
                f.add_field("instruction", SC[r % len(SC)])
                t = time.time()
                async with s.post("http://127.0.0.1:8420/api/generate", data=f) as x:
                    if x.status != 200: print("REJECT", x.status, await x.text()); return
                frames, steps = 0, []
                while True:
                    m = await ws.receive()
                    if m.type == aiohttp.WSMsgType.BINARY:
                        frames += 1; (PREV/f"run{r}_frame{frames}.jpg").write_bytes(m.data[8:])
                    elif m.type == aiohttp.WSMsgType.TEXT:
                        d = json.loads(m.data)
                        if d["type"] == "progress": steps.append(round(time.time()-t,1))
                        if d["type"].startswith("execution"): print(d["type"], flush=True); break
                    else: print("socket", m.type); return
                await asyncio.sleep(8)
                print(f"run {r}: total {round(time.time()-t-8,1)}s first step {steps[0] if steps else None}s steps {len(steps)} previews {frames}", flush=True)
asyncio.run(main())
