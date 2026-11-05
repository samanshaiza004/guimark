# Alicorn adapter

The adapter imports `alicorn:runtime` from a separate Alicorn checkout and uses
the fixed shared font included in `assets/fonts/`. Set `ALICORN_ROOT` to the
checkout root and run `scripts/build_alicorn.sh` from Guimark's root. The
runner records the Alicorn commit and whether that checkout has uncommitted
changes.

This adapter measures through `end_frame`; it does not include SDL, the GPU,
or native event-loop scheduling.
