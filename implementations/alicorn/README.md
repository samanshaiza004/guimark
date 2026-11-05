# Alicorn adapter

The adapter imports alicorn:runtime from a separate Alicorn checkout and uses
the fixed shared font included in assets/fonts. Set ALICORN_ROOT to the
checkout root and run scripts/build_alicorn.sh.

It describes all 10,000 rows on each update. Validation inspects the retained
row nodes, keyed identity/order, actual row text, and renderer-facing text paint
runs. Its timer starts before root invalidation and stops after end_frame.
It does not include SDL, the GPU, or native event-loop scheduling.
