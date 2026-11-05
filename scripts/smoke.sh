#!/bin/sh
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd -P)
if [ -z "${ALICORN_ROOT:-}" ]; then
    echo "Set ALICORN_ROOT to an Alicorn checkout." >&2
    exit 2
fi
python3 -m unittest discover -s "$ROOT/tests" -v
if [ ! -d "$ROOT/implementations/dear-imgui/third_party/imgui" ]; then
    make -C "$ROOT/implementations/dear-imgui" deps
fi
make -C "$ROOT/implementations/dear-imgui"
"$ROOT/scripts/build_alicorn.sh"
python3 "$ROOT/scripts/run.py" \
    --alicorn-root "$ALICORN_ROOT" \
    --alicorn-bin "$ROOT/out/guimark-alicorn" \
    --imgui-bin "$ROOT/implementations/dear-imgui/guimark-imgui" \
    --runs 1 --allow-dirty
