# Benchmark contract v0.1.1

## Question

For a fixed, nonvirtualized tree of 10,000 text rows, how much CPU time does
each framework spend on initial construction and on four controlled changes?
This is a framework CPU-pipeline comparison. It is not a complete application,
renderer, GPU, idle, or latency benchmark.

The adapters use a fixed 1280 × 900 logical viewport at display scale 1. Rows
have 20 logical units of pitch and a 16-unit Atkinson Hyperlegible Next regular
font. Alicorn assigns each row a 20-unit extent with no container gap; Dear
ImGui uses zero padding and four units of item spacing after its 16-unit text
line. Both adapters clip after 45 full rows and submit all 10,000 rows.
The Dear ImGui adapter disables scrolling and scrollbars for this workload;
Alicorn uses a fixed clipped container. The top of the tree remains at row 0.

## Workloads

The exact IDs and state changes are in the [workload manifest](../workloads/manifest.json).

- **Construction:** create 10,000 rows with stable Alicorn row identities.
- **Visible one-row update:** change zero-based item 10, which is in the initial viewport.
- **Offscreen one-row update:** change zero-based item 5,000, outside the viewport.
- **Ten-percent update:** change every tenth row, including visible and offscreen rows.
- **Text-order swap:** put rows 1 and 0 in the first two positions.

Labels retain their byte length. A changed label uses Row %04dX; all labels and
the full order are prepared before timing. No list is virtualized.

The text-order swap tests submitted order. Alicorn additionally checks that its
baseline row node IDs follow their keyed logical rows through the swap. Dear
ImGui uses TextUnformatted, which has no persistent interactive row identity;
this workload makes no selection, focus, or state-preservation claim. An
interactive keyed-row comparison is a separate future workload.

## Fairness and validation

1. Use the same logical labels, initial order, changed rows, viewport, font,
   row pitch, and display scale. Adapter-specific differences in retained nodes
   and draw data remain visible in diagnostics and output kinds.
2. Each adapter checks that it submitted all rows and hashes the full label
   bytes in display order. The runner independently calculates expected full
   text and order hashes from the manifest.
3. Alicorn verifies the actual retained child count, text kind, order, labels,
   and stable node IDs against the baseline. It resolves renderer-facing
   Text_Paint commands back to their live text runs, checks the visible
   clipped rows, and hashes their text and geometry.
4. Dear ImGui hashes text at the TextUnformatted calls, counts row calls that
   add visible glyph vertices, and hashes ImDrawData vertices, indices, and
   commands after Render.
5. Output hashes validate each framework against its own baseline. They are
   different representations and must not be compared across frameworks.
   These structural checks are not pixel or visual-equivalence tests. Native
   mode must add reference-frame or sampled-pixel checks before claiming
   visually equivalent results.
6. The runner reads the checked-in [adapter-result JSON Schema](../schema/adapter-result.schema.json) and enforces the schema keywords used by it (type, required, const, enum, minimum, pattern, and additionalProperties), then performs workload semantics. It rejects schema keywords that its small dependency-free validator does not implement.
   retained_row_nodes is an optional framework-specific diagnostic.
7. Build optimized release binaries. Record source revisions, compiler
   versions, OS, architecture, binary hashes, manifest hash, geometry, and raw
   samples. Dirty Guimark, Alicorn, or Dear ImGui checkouts are rejected by
   default. Pass --allow-dirty to mark an experimental capture explicitly.
8. Each sample runs in a fresh process. Framework order alternates per
   workload and run. The default is 20 paired runs; publish all observations and
   report medians and spread. This sample count does not support meaningful
   p95/p99 claims.
9. Keep native application behavior separate. Idle CPU, wakeups, GPU
   submissions, input-to-submit, and input-to-display require a real host and
   a separately described timing boundary.

## Timing boundaries

- **Alicorn:** starts immediately before invalidate_root, then ends after
  end_frame returns. This includes root description, retained reconciliation,
  layout, paint, and runtime frame work.
- **Dear ImGui:** starts before NewFrame and ends after Render returns. It
  includes submitting 10,000 TextUnformatted calls and generating draw lists.
  Render produces draw data for a separate renderer to consume.

Neither boundary includes process startup in elapsed_ns; the runner records
process launch wall time separately. Dear ImGui runs a second, unmeasured frame
after the timed frame to inspect actual draw data and validate text submissions.
Alicorn inspects the retained tree and paint output after its timed frame. Neither
boundary includes native GPU encoding or presentation. The boundaries include
different internal obligations, so publish them as framework CPU-pipeline
timings, not interchangeable measures of total UI work.

Every update currently invalidates and describes all 10,000 Alicorn rows.
That is a valid full-description baseline, but it does not exercise a retained
region that avoids describing unchanged content. A retained-region
implementation and Update Amplification report should be added as a separately
labeled scenario, while this baseline remains intact.

## Result format

Each adapter writes exactly one JSON result matching the checked-in schema.
The runner validates the schema and checks row count, full-text checksum,
order checksum, visible row count, and baseline output behavior. For the
offscreen update, actual renderer-facing output must match the base frame; for
visible edits and reorder it must change. Hashes are framework-local diagnostics,
not a cross-framework visual comparison.

Captures include JSON and JSONL, plus binary/source hashes and environment
metadata. Use the raw captures for analysis; do not publish only a summary.

## Known limits and next gates

This is an initial CPU-throughput probe with no native host or renderer.
Dear ImGui's child layout and Alicorn's clipped container have explicit matched
viewport and row geometry, but their actual pixels have not been compared.
Accessibility, native input behavior, scrolling, idle scheduling, text
shaping cost under large documents, and GPU presentation are outside this
contract. Do not claim them from these results.

A native follow-up should use Dear ImGui's upstream SDL3 platform backend and
SDL_GPU renderer backend without local patches. Before publishing that mode,
add pixel validation, startup boundaries, working set, idle behavior, frame
pacing, and input latency.
