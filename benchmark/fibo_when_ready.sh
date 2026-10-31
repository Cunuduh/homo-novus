#!/bin/zsh
cd ~/Repositories/hack-or-treat
until grep -q ALL_FINISHED logs/download_fibo.log; do sleep 20; done
grep -q FAILED logs/download_fibo.log && { echo DOWNLOAD_FAILED; cat logs/download_fibo.log; exit 1; }
date '+start %H:%M:%S'; python3 run_test.py benchmark/fibo_turbo.json | cut -c1-700; date '+end %H:%M:%S'
tr '\r' '\n' < logs/comfy.log | grep -E "/4 \[|executed|rror" | tail -4 | cut -c1-140
ls -t ~/Repositories/ComfyUI/output/fibo/ | head -1
