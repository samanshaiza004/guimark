# Guimark

Guimark is a small, reproducible benchmark suite for comparing GUI libraries.
Its first experiment asks how much CPU work each library performs to build and
update the same large, nonvirtualized text tree.

This is a framework CPU-pipeline comparison. Alicorn measures through
end_frame; Dear ImGui measures NewFrame through Render. The adapters do not
create a native window, submit GPU work, measure idle wakeups, or claim
input-to-display latency. Those measurements need a native host and are a
later mode.

## First comparison

- Alicorn from a separate checkout supplied at build time.
- Dear ImGui v1.92.9b, fetched separately at build time.
- Five 10,000-row workloads: construction, visible update, offscreen update,
  ten-percent update, and a text-order swap.
- Twenty fresh-process runs per framework and workload by default.
- Full submitted-text checks, adapter-specific output validation, and raw JSON
  results.

The text-order swap does not claim interactive identity parity: Alicorn checks
its keyed node IDs, while Dear ImGui's TextUnformatted rows have no persistent
selection or focus state. Read the [benchmark contract](docs/benchmark-contract.md) and [workload manifest](workloads/manifest.json)
before interpreting results.

## Build and run

Requirements: Odin, a C++17 compiler, Python 3, and Git.

    ALICORN_ROOT=/path/to/alicorn ./scripts/smoke.sh

The smoke script runs the runner's unit tests, builds both adapters, and runs
one sample per framework and workload. For an experimental run while any source
checkout is dirty, it passes --allow-dirty; official captures reject dirty
Guimark, Alicorn, or Dear ImGui trees by default.

For a comparison run, build the adapters and run:

    ALICORN_ROOT=/path/to/alicorn ./scripts/build_alicorn.sh
    make -C implementations/dear-imgui deps
    make -C implementations/dear-imgui
    python3 scripts/run.py \
      --alicorn-root /path/to/alicorn \
      --alicorn-bin out/guimark-alicorn \
      --imgui-bin implementations/dear-imgui/guimark-imgui

The runner uses the shared Atkinson Hyperlegible Next font and writes a
timestamped directory under results/ containing capture.json and capture.jsonl.
Summarize a capture with python3 scripts/summarize.py
results/<capture>/capture.json. Keep output checksums framework-local; they
are not cross-framework pixel comparisons.

## Current state

This repository is the home for cross-framework workloads, adapters,
methodology, and raw captures. Older Alicorn-only measurements remain
historical evidence in the Alicorn repository. Guimark does not yet publish a
cross-framework performance result.
