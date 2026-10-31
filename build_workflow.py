#!/usr/bin/env python3
"""Builds the Frankenstein workflows from ComfyUI's Qwen Image 2.1 edit templates.

Writes editable UI workflows (ComfyUI/user/default/workflows and ./workflows) and flat API
graphs (./workflows/api) used by run_test.py. Re-run after editing frankenstein_enhancer.md.
"""
import copy, json, pathlib
HERE = pathlib.Path(__file__).parent
COMFY = pathlib.Path.home() / "Repositories/ComfyUI"
TPL = COMFY / ".venv/lib/python3.12/site-packages/comfyui_workflow_templates_json/templates"
SYSTEM = (HERE / "frankenstein_enhancer.md").read_text()
DEFAULT_SCENE = "The figure stands perfectly frontal and symmetrical in a T-pose like the Vitruvian Man, both arms straight out to the sides horizontally at shoulder height with open palms facing forward, legs straight with feet slightly apart, facing the camera with a neutral expression. The figure is small in the frame: the fingertips reach only about 70 percent of the frame width, the arms are near the vertical center, and there is wide empty space on every side of the hands, head and feet. Plain dark charcoal backdrop, in one soft even light."
PROMPT = (HERE / "direct_prompt.txt").read_text().strip().replace("{{SCENE}}", DEFAULT_SCENE)  # Local enhancer is off; prompts will come from an external LLM.
REFS = [("FACE", "face_lincoln.jpg"), ("ARMS", "arms_houdini.jpg"), ("TORSO", "torso_roosevelt.jpg"), ("LEGS", "legs_keaton.jpg")]
W, H, REF_RES, MAX_LEN, SEED = 1024, 1024, 512, 8192, 42
REF_MP = 0.26  # about 512x512: fast path on M5 Pro (about 7 s per step, against 60+ at 768)
PE = "qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors"
TE = "qwen3vl_8b_int8_convrot.safetensors"
VAE = "qwen_image_2.1_vae_bf16.safetensors"

def ui(tpl, out, overrides):
    w = json.load(open(TPL / tpl))
    sub = w["definitions"]["subgraphs"][0]
    next(n for n in sub["nodes"] if n["id"] == 479)["widgets_values"][0] = SYSTEM
    g = next(n for n in w["nodes"] if n["id"] == 459)
    names = [i["name"] for i in sub["inputs"]]
    vals = dict(resolution=REF_RES, prompt=PROMPT, switch_1=False, thinking=True, max_length=MAX_LEN,
                switch=True, width=W, height=H, seed=SEED, **overrides)
    for k, v in vals.items():
        g["widgets_values"][names.index(k)] = v
    g["title"] = "Frankenstein Edit (Qwen Image 2.1)"
    # Template load-image nodes become slots 1-2; the turbo template only ships slot 1.
    by = {n["id"]: n for n in w["nodes"]}
    a = by[470]
    ids, link = [470, 475, 510, 511], max(l[0] for l in w["links"]) + 1
    w["links"] = [l for l in w["links"] if not (l[3] == 459 and l[1] in (470, 475))]
    a["outputs"][0]["links"] = [l for l in a["outputs"][0]["links"] if any(x[0] == l for x in w["links"])]
    if 475 in by:
        by[475]["outputs"][0]["links"] = []
    for slot, nid in enumerate(ids):
        n = by.get(nid)
        if n is None:
            n = copy.deepcopy(a); n["id"] = nid; n["outputs"][0]["links"] = []
            w["nodes"].append(n); by[nid] = n
        n["pos"] = [a["pos"][0], a["pos"][1] + 390 * slot]
        n["title"] = f"image_{slot + 1}: {REFS[slot][0]}"
        n["widgets_values"][0] = REFS[slot][1]
        sid = 520 + slot
        n["outputs"][0]["links"].append(link)
        w["nodes"].append({"id": sid, "type": "ImageScaleToTotalPixels", "pos": [n["pos"][0] + 170, n["pos"][1]], "size": [240, 110], "flags": {}, "order": 0, "mode": 0,
            "inputs": [{"name": "image", "type": "IMAGE", "link": link}],
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [link + 1]}],
            "properties": {"Node name for S&R": "ImageScaleToTotalPixels"}, "widgets_values": ["lanczos", REF_MP, 32]})
        w["links"].append([link, nid, 0, sid, 0, "IMAGE"])
        inp = next(i for i in g["inputs"] if i["name"] == f"images.image_{slot + 1}")
        inp["link"] = link + 1
        w["links"].append([link + 1, sid, 0, 459, g["inputs"].index(inp), "IMAGE"])
        link += 2
    w["last_node_id"], w["last_link_id"] = max(w["last_node_id"], 523), link
    for d in (HERE / "workflows", COMFY / "user/default/workflows"):
        d.mkdir(parents=True, exist_ok=True)
        json.dump(w, open(d / out, "w"), indent=1)

def api(unet, turbo, out, steps=25):
    i = lambda n, c, **k: {"class_type": c, "inputs": k}
    g = {
     "1": i(1, "LoadImage", image=REFS[0][1]), "2": i(2, "LoadImage", image=REFS[1][1]),
     "3": i(3, "LoadImage", image=REFS[2][1]), "4": i(4, "LoadImage", image=REFS[3][1]),
     **{str(10 + n): i(0, "ImageScaleToTotalPixels", image=[str(n), 0], upscale_method="lanczos", megapixels=REF_MP, resolution_steps=32) for n in (1, 2, 3, 4)},
     "451": i(0, "UNETLoader", unet_name=unet, weight_dtype="default"),
     "453": i(0, "CLIPLoader", clip_name=TE, type="qwen_image", device="default"),
     "454": i(0, "VAELoader", vae_name=VAE),
     "456": i(0, "EmptyLatentImage", width=W, height=H, batch_size=1),
     "469": i(0, "QwenImage21Cache", model=["451", 0], device="auto", dtype="default"),
     "474": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["453", 0], "vae": ["454", 0], "prompt": PROMPT, "negative_prompt": "", "resolution": REF_RES,
             "images.image_1": ["11", 0], "images.image_2": ["12", 0], "images.image_3": ["13", 0], "images.image_4": ["14", 0]}},
     "457": i(0, "VAEDecode", vae=["454", 0], samples=["505", 0] if turbo else ["458", 0]),
     "461": i(0, "SaveImage", images=["457", 0], filename_prefix="frankenstein/" + out),
    }
    if turbo:
        g |= {"502": i(0, "ManualSigmas", sigmas="1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0"),
              "503": i(0, "KSamplerSelect", sampler_name="euler"), "504": i(0, "RandomNoise", noise_seed=SEED),
              "507": i(0, "CFGGuider", model=["469", 0], positive=["474", 0], negative=["474", 1], cfg=1.0),
              "505": i(0, "SamplerCustomAdvanced", noise=["504", 0], guider=["507", 0], sampler=["503", 0], sigmas=["502", 0], latent_image=["456", 0])}
    else:
        g["458"] = i(0, "KSampler", model=["469", 0], positive=["474", 0], negative=["474", 1], latent_image=["456", 0], seed=SEED, steps=steps, cfg=1.0, sampler_name="euler", scheduler="simple", denoise=1.0)
    d = HERE / "workflows/api"; d.mkdir(parents=True, exist_ok=True)
    json.dump(g, open(d / f"{out}.json", "w"), indent=1)

ui("image_qwen_image_2_1_image_edit.json", "frankenstein_qwen21_edit.json", {})
ui("image_qwen_image_2_1_turbo_image_edit.json", "frankenstein_qwen21_turbo_edit.json", {})
api("qwen_image_2.1_int8_convrot.safetensors", False, "frankenstein_qwen21_edit")
api("qwen_image_2.1_turbo_int8_convrot.safetensors", True, "frankenstein_qwen21_turbo_edit")
print("built")
