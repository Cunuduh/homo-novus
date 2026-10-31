#!/usr/bin/env python3
"""Runs one Qwen Image 2.1 Turbo job in MLX from a stdin line, then exits to free memory.

Runs in .mflux-venv. Writes `EVT <json>` lines to stdout; everything else goes to stderr.
SIGUSR1 cancels the current job at the next step.
"""
import json, os, signal, sys, tempfile, time

_out = os.fdopen(os.dup(1), "w", buffering=1)
os.dup2(2, 1)
def emit(**k): _out.write("EVT " + json.dumps(k) + "\n"); _out.flush()

import mlx.core as mx
import numpy as np
from mflux.models.common.config.model_config import ModelConfig
from mflux.models.qwen21.latent_creator.qwen_image21_latent_creator import QwenImage21LatentCreator
from mflux.models.qwen21.variants.edit.qwen_image_21_edit import QwenImage21Edit
from mflux.utils.exceptions import StopImageGenerationException

TURBO_SIGMAS = [1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0.0]
cancel = False
def on_cancel(*_):
    global cancel
    cancel = True
signal.signal(signal.SIGUSR1, on_cancel)


class Reporter:
    def __init__(self, job): self.job, self.prev = job, None
    def call_before_loop(self, seed, prompt, latents, config, canny_image=None, depth_image=None, control_images=None):
        self.prev = latents
        emit(type="sampling", id=self.job["id"])
    def call_in_loop(self, t, seed, prompt, latents, config, time_steps, denoised=None):
        j = self.job
        if cancel: raise StopImageGenerationException("Cancelled")
        path = None
        # mflux doesn't expose the prediction here, so recover it from the Euler step: x0 = x - sigma * v.
        v = (latents - self.prev) / (TURBO_SIGMAS[t + 1] - TURBO_SIGMAS[t])
        src = latents - TURBO_SIGMAS[t + 1] * v
        self.prev = latents
        try:
            x = QwenImage21LatentCreator.unpack_latents(src, j["height"], j["width"]).astype(mx.float32)
            mx.eval(x)
            fd, path = tempfile.mkstemp(suffix=".npy", dir=j["tmp"]); os.close(fd)
            np.save(path, np.array(x))
        except Exception as e:
            print("preview failed", repr(e), file=sys.stderr); path = None
        emit(type="step", id=j["id"], value=t + 1, max=j["steps"], latent=path)
    def call_after_loop(self, seed, prompt, latents, config):
        emit(type="decoding", id=self.job["id"])


t = time.time()
model = QwenImage21Edit(quantize=8, model_config=ModelConfig.qwen_image_21_turbo())
emit(type="ready", load_seconds=round(time.time() - t, 1))

current = {}
rep = Reporter(current)
model.callbacks.register(rep)

for line in sys.stdin:
    job = json.loads(line)
    current.clear(); current.update(job)
    cancel = False
    t = time.time()
    emit(type="encoding", id=job["id"])
    try:
        img = model.generate_image(seed=job["seed"], prompt=job["prompt"], width=job["width"], height=job["height"],
                                   num_inference_steps=job["steps"], image_paths=job["images"], output_resolution=job["ref_res"], strength=job.get("strength", 1.0))
        img.save(job["output"])
        emit(type="done", id=job["id"], seconds=round(time.time() - t, 1), peak_gb=round(mx.get_peak_memory() / 2**30, 1))
    except StopImageGenerationException:
        emit(type="cancelled", id=job["id"])
    except Exception as e:
        import traceback; traceback.print_exc()
        emit(type="error", id=job["id"], message=repr(e)[:400])
    # Exit after each job: a held model pushes a 24 GB Mac into swap (about 56 s per run fresh, 105 s after).
    # The server starts a new worker straight away, and loading is lazy and quick.
    break
