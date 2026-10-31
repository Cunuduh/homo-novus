# Homo Novus

*Create a New Man.* A Hack or Treat project: a preview tool for Victor Frankenstein, so he can see his creation before robbing any graves. Measure twice, exhume once.

Lay photos on Leonardo's Vitruvian Man for the face, arms, torso and legs. Homo Novus isolates each body part and generates one stitched-together figure inside Leonardo's circle, running locally on Apple Silicon in about a minute.

## How it works

- `web/`: the single-page interface
- `server.py`: local server, relays progress and live previews to the page
- `mflux_worker.py`: Qwen Image 2.1 Turbo (8-bit) on MLX through [mflux](https://github.com/mflux-community/mflux)
- `preprocess.py`: human-parsing masks for each body part, background cut-out, ghost filter
- `strict_prompt.txt`: the generation prompt

## Run

Needs an Apple Silicon Mac (tested on an M5 Pro with 24 GB), `uv`, and a ComfyUI checkout at `~/Repositories/ComfyUI` with its `.venv`: the server uses that environment and its tiny preview decoder.

```sh
uv venv --python 3.12 .mflux-venv && uv pip install --python .mflux-venv/bin/python mflux
./start.sh
```

The first run downloads about 30 GB of model weights.

## Credits

Artwork and photos are public domain, CC0 or similarly unrestricted, listed in `refs/CREDITS.md` and `web/assets/CREDITS.md`. Model licenses apply separately: check Qwen Image 2.1's terms before commercial use.
