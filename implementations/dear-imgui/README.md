# Dear ImGui adapter

This is the core-pipeline CPU adapter. It submits the same 10,000 fixed-width
row labels, creates draw data with `ImGui::Render`, and reports draw vertices
and commands. It has no SDL platform or renderer backend, so it cannot produce
native idle, GPU, presentation, or input-latency results.

The dependency is pinned to the upstream `v1.92.9b` release tag and commit
`f1cc2ae15e53a861a874c3034aae6798fde194ab` in `dependencies.lock.json`. `make deps`
clones it into this directory's ignored `third_party/`; `make` builds an
optimized C++17 executable. The exact ImGui version is included in each adapter
result. For the later native mode, use the upstream SDL3 platform backend and
SDL_GPU renderer backend without patching their sources.
