# Guimark

Guimark is a small, reproducible benchmark suite for comparing GUI libraries.
Its first experiment asks how much CPU work each library performs to build and
update the same large, nonvirtualized row tree.

The repository is intentionally early. The first adapters measure the
framework-side CPU pipeline through Alicorn's `end_frame` and Dear ImGui's
`Render`. They do not create a window, submit GPU work, measure idle wakeups,
or claim input-to-display latency. Those measurements need a native host and
are a later mode.

## First comparison

- Alicorn, from a separate checkout supplied at build time.
- Dear ImGui v1.92.9b, fetched separately at build time.
- Four 10,000-row workloads: initial construction, one-row update, ten-percent
  update, and adjacent-row reorder.
- Five fresh process launches per framework and workload by default.
- One JSON result per process, plus a machine and binary manifest.

See [the benchmark contract](docs/benchmark-contract.md) and
[workload manifest](workloads/manifest.json) before interpreting results.

## Build and run

Requirements: Odin, a C++17 compiler, Python 3, and Git.

```sh
ALICORN_ROOT=/path/to/alicorn ./scripts/build_alicorn.sh
make -C implementations/dear-imgui deps
make -C implementations/dear-imgui
python3 scripts/run.py \
  --alicorn-root /path/to/alicorn \
  --alicorn-bin out/guimark-alicorn \
  --imgui-bin implementations/dear-imgui/guimark-imgui
```

On Windows, build the Alicorn adapter with the same Odin command in
`scripts/build_alicorn.sh` and pass the resulting `.exe` paths to `run.py`.
The current Dear ImGui adapter is a CPU-only core-pipeline probe and builds
without SDL. It deliberately does not stand in for the planned native
SDL3 + SDL_GPU comparison.

The runner sets `GUIMARK_FONT` to the shared font for both adapters and writes a
timestamped directory under `results/` containing `capture.json` and
`capture.jsonl`. Summarize a capture with `python3 scripts/summarize.py
results/<capture>/capture.json`. Use [`docs/report-template.md`](docs/report-template.md)
for published comparisons and preserve the full raw directory. The adapter reports work-specific counters; these are
diagnostics and are not scores that can be compared across architectures.

## Current state

This repository is the home for new cross-framework workload definitions,
adapters, methodology, and raw captures. Older Alicorn-only measurements
remain historical evidence in the Alicorn repository. Guimark does not yet
publish a cross-framework performance result.
