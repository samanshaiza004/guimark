# Benchmark contract v0.1

## Question

For a fixed, nonvirtualized tree of 10,000 text rows, what CPU time does each
framework spend on initial construction and on three controlled changes?

The first pass isolates the UI framework core. It ends at Alicorn's completed
runtime frame and Dear ImGui's completed draw-data generation. It does not
include process startup in `elapsed_ns`; the runner records process wall time
separately. A future native mode must measure the complete app and presentation
path with each framework's normal scheduling.

## Workloads

The exact workload IDs and intended state changes are in
[`workloads/manifest.json`](../workloads/manifest.json).

- **Construction:** create 10,000 rows with stable numeric identities.
- **One-row update:** change the label for row 5,000.
- **Ten-percent update:** change labels for every tenth row.
- **Reorder:** swap rows 0 and 1 while keeping row identity tied to the row.

Rows have fixed-width labels (`Row 00000`) so each update preserves string
length. The data and alternate labels are prepared before the timed operation.
The tree is nonvirtualized in this mode. Scroll virtualization will be its own
workload and must realize equivalent visible rows in every adapter.

## Fairness rules

1. Keep the logical rows, identity values, changed rows, viewport dimensions,
   and text inputs identical.
2. Use each toolkit's ordinary public API and recommended implementation.
   Do not force continuous redraw for a workload whose contract requests one
   update.
3. Validate the resulting row count, order checksum, and changed-item count
   before accepting timing data.
4. Report each framework's internal counters as diagnostics. They explain work
   avoided, but differing counters are not directly comparable.
5. Build optimized release binaries. Record framework revisions, compiler
   versions, OS, architecture, binary hashes, and all raw samples.
6. Alternate framework order across repeated process launches. Report the
   individual observations and summarize with median and spread; never publish
   only the fastest run.
7. Keep native app behavior separate from this core-pipeline mode. Idle CPU,
   wakeups, GPU submissions, input-to-submit, and input-to-display require a
   real host and a separately described measurement boundary.

## Result format

Each adapter writes exactly one JSON object to stdout matching
[`schema/adapter-result.schema.json`](../schema/adapter-result.schema.json). The
runner also checks logical row count, changed-item count, and independent FNV-1a
checksums of the row order and final label byte before accepting a sample.
The runner adds launch wall time, sample number, machine metadata, binary hash,
and source revisions to the capture. Keep both JSON and JSONL outputs.

## Known limits

This is an initial CPU-throughput probe, not a GUI leaderboard. It currently
uses framework defaults for layout and style, and the first Dear ImGui adapter
has no platform or renderer backend. A native follow-up should use the
upstream [SDL3 platform backend](https://github.com/ocornut/imgui/blob/master/backends/imgui_impl_sdl3.cpp)
and [SDL_GPU renderer backend](https://github.com/ocornut/imgui/blob/master/backends/imgui_impl_sdlgpu3.cpp)
without local patches. Equivalent pixels, accessibility
semantics, and native input behavior have not been validated. Those are
acceptance gates for the native application mode.
