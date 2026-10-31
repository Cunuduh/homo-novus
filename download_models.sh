#!/bin/zsh
# Downloads Qwen Image 2.1 int8-convrot models into ComfyUI's model folders. Safe to re-run (resumes).
cd ~/Repositories/ComfyUI/models || exit 1
B=https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main
for p in vae/qwen_image_2.1_vae_bf16.safetensors \
         diffusion_models/qwen_image_2.1_turbo_int8_convrot.safetensors \
         text_encoders/qwen3vl_8b_int8_convrot.safetensors \
         text_encoders/qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors \
         diffusion_models/qwen_image_2.1_int8_convrot.safetensors; do
  echo "START $p"
  curl -L --fail -C - --retry 10 --retry-delay 10 --retry-all-errors -sS -o "$p" "$B/$p" && echo "DONE $p" || echo "FAILED $p"
done
echo ALL_FINISHED
