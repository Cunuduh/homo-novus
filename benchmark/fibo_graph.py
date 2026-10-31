#!/usr/bin/env python3
"""Writes the FIBO 2.0 Edit Turbo API graph from the template's settings. FIBO names references <image_N>."""
import json, pathlib, re
H = pathlib.Path(__file__).parent; R = H.parent
scene = "Setting, pose and mood: Hunched over a cluttered wooden desk in a candlelit study at night, one hand gripping a quill, glaring at the camera with menace."
p = re.sub(r"<image(\d)>", r"<image_\1>", (R / "direct_prompt.txt").read_text().strip().replace("{{SCENE}}", scene))
i = lambda c, **k: {"class_type": c, "inputs": k}
g = {str(n + 1): i("LoadImage", image=f) for n, f in enumerate(["face_lincoln.jpg", "arms_houdini.jpg", "torso_roosevelt.jpg", "legs_keaton.jpg"])}
g |= {"10": i("UNETLoader", unet_name="fibo2_edit_turbo_int8_convrot.safetensors", weight_dtype="default"),
      "11": i("CLIPLoader", clip_name="qwen3vl_4b_int8_convrot.safetensors", type="fibo2", device="default"),
      "12": i("VAELoader", vae_name="flux2-vae.safetensors"),
      "13": {"class_type": "TextEncodeFibo2", "inputs": {"clip": ["11", 0], "vae": ["12", 0], "prompt": p, "negative_prompt": "", "width": 832, "height": 1248, "batch_size": 1,
             **{f"images.image_{n}": [str(n), 0] for n in (1, 2, 3, 4)}}},
      "14": i("KSampler", model=["10", 0], positive=["13", 0], negative=["13", 1], latent_image=["13", 2], seed=42, control_after_generate="fixed", steps=4, cfg=1.0, sampler_name="euler", scheduler="simple", denoise=1.0),
      "15": i("VAEDecode", vae=["12", 0], samples=["14", 0]),
      "16": i("SaveImage", images=["15", 0], filename_prefix="fibo/edit_turbo")}
del g["14"]["inputs"]["control_after_generate"]
json.dump(g, open(H / "fibo_turbo.json", "w"), indent=1)
