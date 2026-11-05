# GUI framework comparison: <workload suite and date>

## Scope

- Guimark commit: <sha>
- Mode: <core pipeline or native application>
- Workloads: <IDs from the checked-in manifest>
- Correctness checks: <retained tree, full submitted text, draw output, pixels, interaction>
- Dirty-source override: <yes/no>

## Environment

| Item | Value |
| --- | --- |
| Machine / CPU / RAM | |
| OS and build | |
| Logical viewport / display scale / refresh | |
| Row pitch / font file / font size | |
| Compiler versions and flags | |
| GPU / driver / backend | |
| Framework commits | |

## Results

| Workload | Framework | Median | Min–max | Samples | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| | | | | | |

Link the complete capture.json and capture.jsonl here and preserve the
environment manifest. Report work counters as architecture-specific
diagnostics. Framework-local rendered-output hashes validate each adapter's
own frame behavior and are not cross-framework image comparisons.

## Interpretation and limits

State which stages each timer includes and excludes. Describe differences in
virtualization, text, identity, interaction, and native scheduling. Do not
compare measurements captured on different machines as if they were one
experiment. The core pipeline has no pixel validation, GPU renderer, native
idle behavior, or input-to-display latency.
