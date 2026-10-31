#!/bin/zsh
# usage: mflux_run.sh <name> <ref budget> [extra mflux args]
cd ~/Repositories/hack-or-treat; N=$1; R=$2; shift 2
SCENE="Setting, pose and mood: Hunched over a cluttered wooden desk in a candlelit study at night, one hand gripping a quill, glaring at the camera with menace."
P=$(sed "s/{{SCENE}}/$SCENE/" direct_prompt.txt)
mkdir -p benchmark/mflux; S=$(date +%s)
/usr/bin/time -l .mflux-venv/bin/mflux-generate-qwen-2.1-edit --model qwen-image-2.1-turbo \
  --image-paths refs/face_lincoln.jpg refs/arms_houdini.jpg refs/torso_roosevelt.jpg refs/legs_keaton.jpg \
  --prompt "$P" --seed 42 --quantize 8 --width 832 --height 1248 --output-resolution $R \
  --output benchmark/mflux/$N.png "$@" > benchmark/mflux/$N.log 2>&1
echo "$N exit=$? seconds=$(( $(date +%s)-S ))"
tr '\r' '\n' < benchmark/mflux/$N.log | grep -E "s/it|it/s|Error|error|Killed|maximum resident|peak memory" | tail -5 | cut -c1-160
sysctl vm.swapusage
