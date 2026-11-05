#!/bin/sh
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd -P)
ALICORN_ROOT=${ALICORN_ROOT:-}
ODIN=${ODIN:-odin}
if [ -z "$ALICORN_ROOT" ]; then
    echo "Set ALICORN_ROOT to an Alicorn checkout." >&2
    exit 2
fi
if ! command -v "$ODIN" >/dev/null 2>&1 && [ ! -x "$ODIN" ]; then
    echo "Odin compiler not found: $ODIN (set ODIN to its executable path)." >&2
    exit 2
fi
mkdir -p "$ROOT/out"
"$ODIN" build "$ROOT/implementations/alicorn" \
    "-collection:alicorn=$ALICORN_ROOT" \
    -o:speed \
    "-out:$ROOT/out/guimark-alicorn"
