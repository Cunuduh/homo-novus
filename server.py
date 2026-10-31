#!/usr/bin/env python3
"""Local bridge between the Modern Prometheus front end and ComfyUI. Binds to 127.0.0.1 only.

Run with ComfyUI's environment: ~/Repositories/ComfyUI/.venv/bin/python server.py
"""
import asyncio, io, json, os, pathlib, random, signal, struct, sys, uuid
import aiohttp
from aiohttp import web
from PIL import Image, ImageOps
import preprocess

HERE = pathlib.Path(__file__).parent
COMFY = "http://127.0.0.1:8188"
MODELS_DIR = pathlib.Path.home() / "Repositories/ComfyUI/models"
SLOTS = {"face": "1", "arms": "2", "torso": "3", "legs": "4"}
GRAPHS = {"turbo": "frankenstein_qwen21_turbo_edit.json", "full": "frankenstein_qwen21_edit.json"}
# Minimum bytes, so a file that is still downloading does not count as installed.
SHARED = {"vae/qwen_image_2.1_vae_bf16.safetensors": 0.6e9,
          "text_encoders/qwen3vl_8b_int8_convrot.safetensors": 9.3e9,
          }
UNETS = {"turbo": "diffusion_models/qwen_image_2.1_turbo_int8_convrot.safetensors",
         "full": "diffusion_models/qwen_image_2.1_int8_convrot.safetensors"}
UNET_MIN = 7.2e9
DEFAULT_SCENE = "The figure stands perfectly frontal and symmetrical in a T-pose like the Vitruvian Man, both arms straight out to the sides horizontally at shoulder height with open palms facing forward, legs straight with feet slightly apart, facing the camera with a neutral expression. The figure is small in the frame: the fingertips reach only about 70 percent of the frame width, the arms are near the vertical center, and there is wide empty space on every side of the hands, head and feet. Plain dark charcoal backdrop, in one soft even light."
BACKEND = os.environ.get("PROMETHEUS_BACKEND", "mflux")  # "mflux" or "comfy"
OUT = HERE / "output"
WIDTH, HEIGHT, REF_RES, STEPS = 1024, 1024, 512, 8
STRENGTH = 0.85  # lower follows the drawing more closely, higher keeps the donors more
MAX_UPLOAD = 40 * 1024 * 1024


def installed(rel, minimum):
    p = MODELS_DIR / rel
    return p.exists() and p.stat().st_size >= minimum


class Mflux:
    """Owns the MLX worker process and relays its events to every open page."""

    def __init__(self, app):
        self.app, self.proc, self.ready, self.busy = app, None, False, None
        self.jobs, self.tae = {}, None

    async def start(self):
        (OUT / "tmp").mkdir(parents=True, exist_ok=True)
        log = open(HERE / "logs/mflux_worker.log", "a")
        self.ready = False
        self.proc = await asyncio.create_subprocess_exec(str(HERE / ".mflux-venv/bin/python"), str(HERE / "mflux_worker.py"),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=log, cwd=HERE)
        self.task = asyncio.create_task(self.read())

    async def broadcast(self, **msg):
        for ws in list(self.app["sockets"]):
            try: await ws.send_str(json.dumps(msg))
            except Exception: self.app["sockets"].discard(ws)

    def decode_preview(self, path):
        """Decodes a latent with the tiny autoencoder to a ComfyUI-style binary preview frame."""
        import numpy as np, torch
        if self.tae is None:
            comfy_dir = pathlib.Path.home() / "Repositories/ComfyUI"
            if str(comfy_dir) not in sys.path: sys.path.insert(0, str(comfy_dir))
            from comfy.taesd.taesd import TAESD
            self.tae = TAESD(None, str(comfy_dir / "models/vae_approx/taeqi2_1_decoder.safetensors"), latent_channels=64).eval()
        x = torch.from_numpy(np.load(path))
        if x.ndim == 5: x = x[:, :, 0]
        with torch.inference_mode():
            rgba = self.tae.decode(x)[0, :4].clamp(-1, 1).add(1).mul(127.5).byte().permute(1, 2, 0).numpy()
        buf = io.BytesIO(); Image.fromarray(rgba, "RGBA").save(buf, "PNG", compress_level=1)
        return struct.pack(">II", 1, 2) + buf.getvalue()

    async def read(self):
        while True:
            line = await self.proc.stdout.readline()
            if not line: break
            if not line.startswith(b"EVT "): continue
            e = json.loads(line[4:])
            kind, pid = e["type"], e.get("id")
            if kind == "ready":
                self.ready = True; print("mflux ready, loaded in", e["load_seconds"], "s", flush=True)
            elif kind == "encoding":
                await self.broadcast(type="executing", data={"node": "474", "prompt_id": pid})
            elif kind == "sampling":
                await self.broadcast(type="executing", data={"node": "505", "prompt_id": pid})
            elif kind == "step":
                await self.broadcast(type="progress", data={"value": e["value"], "max": e["max"], "prompt_id": pid})
                if e.get("latent"):
                    asyncio.create_task(self.preview(e["latent"]))
            elif kind == "decoding":
                await self.broadcast(type="executing", data={"node": "457", "prompt_id": pid})
            elif kind in ("done", "error", "cancelled"):
                job = self.jobs[pid]; self.busy = None
                for f in (OUT / "tmp").glob(f"{pid}_*"): f.unlink(missing_ok=True)
                if kind == "done":
                    print("mflux job", e["seconds"], "s, peak", e["peak_gb"], "GB", flush=True)
                    try:
                        await asyncio.to_thread(preprocess.ghost, str(OUT / job["file"]), str(OUT / job["file"].replace(".png", "_ghost.png")))
                    except Exception as err:
                        print("ghost failed:", repr(err), flush=True)
                    try:
                        kept = await asyncio.to_thread(preprocess.cut_out, str(OUT / job["file"]))
                        print("cut out, kept", round(kept * 100, 1), "%", flush=True)
                    except Exception as err:
                        print("cut-out failed, keeping the background:", repr(err), flush=True)
                    job.update(state="done", images=[{"filename": job["file"], "subfolder": ""}])
                    await self.broadcast(type="execution_success", data={"prompt_id": pid})
                elif kind == "error":
                    job.update(state="error", message=e["message"])
                    await self.broadcast(type="execution_error", data={"prompt_id": pid})
                else:
                    job.update(state="cancelled")
                    await self.broadcast(type="execution_interrupted", data={"prompt_id": pid})
        # The worker died: fail any running job, then bring it back.
        if self.busy:
            self.jobs[self.busy].update(state="error", message="The image engine crashed, probably out of memory. It is restarting.")
            await self.broadcast(type="execution_error", data={"prompt_id": self.busy}); self.busy = None
        self.ready = False
        await asyncio.sleep(.2)
        await self.start()

    async def preview(self, path):
        try:
            frame = await asyncio.to_thread(self.decode_preview, path)
            for ws in list(self.app["sockets"]):
                try: await ws.send_bytes(frame)
                except Exception: self.app["sockets"].discard(ws)
        except Exception as e:
            print("preview failed", repr(e), flush=True)
        finally:
            try: os.unlink(path)
            except OSError: pass

    async def submit(self, images, prompt, seed):
        pid = uuid.uuid4().hex
        paths = [str(HERE / "refs/isolated/pose_vitruvian.jpg")]  # <image1>: the starting point that fixes the outline
        for slot, (data, _) in images.items():
            p = OUT / "tmp" / f"{pid}_{slot}.jpg"
            p.write_bytes(data); paths.append(str(p))
        file = f"homo_novus_{pid[:10]}.png"
        self.jobs[pid] = {"state": "running", "file": file}
        self.busy = pid
        job = dict(id=pid, seed=seed, prompt=prompt, width=WIDTH, height=HEIGHT, steps=STEPS, ref_res=REF_RES, strength=STRENGTH, images=paths, output=str(OUT / file), tmp=str(OUT / "tmp"))
        self.proc.stdin.write((json.dumps(job) + "\n").encode()); await self.proc.stdin.drain()
        return pid


async def status(req):
    if BACKEND == "mflux":
        return web.json_response({"comfy": True, "modes": {"turbo": req.app["engine"].ready, "full": False}})
    s = req.app["http"]
    try:
        async with s.get(f"{COMFY}/system_stats", timeout=aiohttp.ClientTimeout(total=3)) as r:
            online = r.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        online = False
    shared = all(installed(k, v) for k, v in SHARED.items())
    modes = {m: shared and installed(p, UNET_MIN) for m, p in UNETS.items()}
    return web.json_response({"comfy": online, "modes": modes})


async def upload(s, name, data, ctype):
    form = aiohttp.FormData()
    form.add_field("image", data, filename=name, content_type=ctype)
    form.add_field("overwrite", "true")
    async with s.post(f"{COMFY}/upload/image", data=form) as r:
        if r.status != 200:
            raise web.HTTPBadGateway(text=f"ComfyUI refused the image: {await r.text()}")
        return (await r.json())["name"]


def isolate_part(data, ctype, part):
    """Masks and crops a photo to one body part; keeps the original if that fails or finds nothing."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
        out = preprocess.isolate(img, part)
        if out is None:
            print(f"isolate: no {part} found, using the whole photo", flush=True)
            return data, ctype
        buf = io.BytesIO()
        out.save(buf, "JPEG", quality=95)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        print(f"isolate: {part} failed ({e!r}), using the whole photo", flush=True)
        return data, ctype


async def generate(req):
    s = req.app["http"]
    fields, files = {}, {}
    reader = await req.multipart()
    while (part := await reader.next()) is not None:
        data = await part.read()
        if part.name in SLOTS:
            if not (part.headers.get("Content-Type") or "").startswith("image/"):
                raise web.HTTPBadRequest(text=f"{part.name} is not an image")
            files[part.name] = (data, part.headers["Content-Type"])
        else:
            fields[part.name] = data.decode()
    missing = [k for k in SLOTS if k not in files]
    if missing:
        raise web.HTTPBadRequest(text="Missing parts: " + ", ".join(missing))
    if BACKEND == "mflux":
        engine = req.app["engine"]
        if not engine.ready or engine.busy:
            raise web.HTTPConflict(text="The image engine is busy or still loading.")
        isolated = {}
        for slot in SLOTS:
            isolated[slot] = await asyncio.to_thread(isolate_part, *files[slot], slot)
        seed = int(fields.get("seed") or random.randrange(2**31))
        prompt = (HERE / "strict_prompt.txt").read_text().strip()
        pid = await engine.submit(isolated, prompt, seed)
        return web.json_response({"id": pid, "seed": seed, "prompt": prompt})
    mode = fields.get("mode", "turbo")
    if mode not in GRAPHS:
        raise web.HTTPBadRequest(text="Unknown mode")

    g = json.loads((HERE / "workflows/api" / GRAPHS[mode]).read_text())
    run = uuid.uuid4().hex[:10]
    for slot, nid in SLOTS.items():
        data, ctype = await asyncio.to_thread(isolate_part, *files[slot], slot)
        ext = {"image/png": "png", "image/webp": "webp"}.get(ctype, "jpg")
        g[nid]["inputs"]["image"] = await upload(s, f"prometheus_{run}_{slot}.{ext}", data, ctype)

    seed = int(fields.get("seed") or random.randrange(2**48))
    note = fields.get("instruction", "").strip()
    template = (HERE / "direct_prompt.txt").read_text().strip()
    scene = f"Setting, pose and mood: {note}." if note else DEFAULT_SCENE
    g["474"]["inputs"]["prompt"] = template.replace("{{SCENE}}", scene)
    if "458" in g:
        g["458"]["inputs"]["seed"] = seed
    else:
        g["504"]["inputs"]["noise_seed"] = seed

    body = {"prompt": g, "client_id": fields.get("client_id", "")}
    async with s.post(f"{COMFY}/prompt", json=body) as r:
        out = await r.json()
        if r.status != 200:
            return web.json_response({"error": out}, status=502)
    return web.json_response({"id": out["prompt_id"], "seed": seed, "prompt": g["474"]["inputs"]["prompt"]})


async def job(req):
    pid = req.match_info["id"]
    if BACKEND == "mflux":
        job = req.app["engine"].jobs.get(pid)
        if not job: return web.json_response({"state": "error", "message": "Unknown job."})
        if job["state"] == "done": return web.json_response({"state": "done", "images": job["images"], "prompt": ""})
        if job["state"] == "running": return web.json_response({"state": "running"})
        return web.json_response({"state": "error", "message": job.get("message", "Cancelled.")})
    async with req.app["http"].get(f"{COMFY}/history/{pid}") as r:
        h = (await r.json()).get(pid)
    if not h:
        return web.json_response({"state": "running"})
    st = h["status"]
    if st.get("status_str") != "success":
        msg = next((m[1].get("exception_message", "") for m in st.get("messages", []) if m[0] == "execution_error"), "")
        return web.json_response({"state": "error", "message": msg or "The run failed."})
    out = h["outputs"]
    images = [{"filename": i["filename"], "subfolder": i.get("subfolder", "")} for i in out.get("461", {}).get("images", [])]
    text = out.get("480", {}).get("text", [""])
    return web.json_response({"state": "done", "images": images, "prompt": text[0] if text else ""})


async def view(req):
    if BACKEND == "mflux":
        p = OUT / pathlib.Path(req.query.get("filename", "")).name
        if not p.is_file(): raise web.HTTPNotFound()
        return web.FileResponse(p)
    q = {"filename": req.query.get("filename", ""), "subfolder": req.query.get("subfolder", ""), "type": "output"}
    async with req.app["http"].get(f"{COMFY}/view", params=q) as r:
        if r.status != 200:
            raise web.HTTPNotFound()
        return web.Response(body=await r.read(), content_type=r.content_type)


async def interrupt(req):
    if BACKEND == "mflux":
        engine = req.app["engine"]
        if engine.busy and engine.proc: engine.proc.send_signal(signal.SIGUSR1)
        return web.json_response({"ok": True})
    async with req.app["http"].post(f"{COMFY}/interrupt"):
        return web.json_response({"ok": True})


async def relay(req):
    """Relays ComfyUI's progress messages and live preview frames to the browser."""
    browser = web.WebSocketResponse(heartbeat=30)
    await browser.prepare(req)
    if BACKEND == "mflux":
        req.app["sockets"].add(browser)
        async for _ in browser: pass
        req.app["sockets"].discard(browser)
        return browser
    try:
        async with req.app["http"].ws_connect(f"{COMFY.replace('http', 'ws')}/ws?clientId={req.query.get('clientId', '')}") as comfy:
            async def up():
                async for _ in browser:
                    pass
                await comfy.close()
            task = asyncio.create_task(up())
            async for m in comfy:
                if m.type == aiohttp.WSMsgType.TEXT:
                    await browser.send_str(m.data)
                elif m.type == aiohttp.WSMsgType.BINARY:
                    await browser.send_bytes(m.data)
            task.cancel()
    except aiohttp.ClientError:
        pass
    await browser.close()
    return browser


async def index(_):
    return web.FileResponse(HERE / "web/index.html")


async def on_start(app):
    app["http"] = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None))
    # Load the parsing model now so the first Generate isn't slowed by it.
    await asyncio.to_thread(preprocess._load)
    app["sockets"] = set()
    if BACKEND == "mflux":
        app["engine"] = Mflux(app)
        await app["engine"].start()


async def on_stop(app):
    if BACKEND == "mflux" and app["engine"].proc and app["engine"].proc.returncode is None:
        app["engine"].task.cancel(); app["engine"].proc.kill()
    await app["http"].close()


app = web.Application(client_max_size=4 * MAX_UPLOAD + 1024 * 1024)
app.on_startup.append(on_start)
app.on_cleanup.append(on_stop)
app.router.add_get("/", index)
app.router.add_get("/api/status", status)
app.router.add_post("/api/generate", generate)
app.router.add_get("/api/job/{id}", job)
app.router.add_get("/api/view", view)
app.router.add_post("/api/interrupt", interrupt)
app.router.add_get("/api/ws", relay)
app.router.add_static("/refs", HERE / "refs")
app.router.add_static("/output", HERE / "output")
app.router.add_static("/", HERE / "web")

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=8420, print=lambda *_: print("Prometheus: http://127.0.0.1:8420", flush=True))
