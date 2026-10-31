#!/bin/zsh
# Uses hf (Xet), which is far faster here than plain curl. Files land directly in ComfyUI's model folders.
cd ~/Repositories/hack-or-treat
for p in vae/flux2-vae.safetensors text_encoders/qwen3vl_4b_int8_convrot.safetensors diffusion_models/fibo2_edit_turbo_int8_convrot.safetensors; do
  echo "START $p"; .mflux-venv/bin/hf download Comfy-Org/Fibo-2.0 "$p" --local-dir ~/Repositories/ComfyUI/models >/dev/null 2>&1 && echo "DONE $p" || echo "FAILED $p"
done
echo ALL_FINISHED
