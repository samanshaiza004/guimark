# Dear ImGui adapter

This adapter submits all 10,000 labels with TextUnformatted, creates draw data
with ImGui::Render, and reports actual draw vertices, indices, and commands.
It uses plain text rows without persistent interactive row identity. The
text-order swap tests submission order only; it makes no selection or focus
claim.

The adapter has no SDL platform or renderer backend, so it cannot produce
native idle, GPU, presentation, or input-latency results. Its timer covers
NewFrame through Render, which emits draw data for a separate renderer.

The dependency is pinned to the upstream v1.92.9b release tag and commit
f1cc2ae15e53a861a874c3034aae6798fde194ab in dependencies.lock.json.
make deps clones it into this directory's ignored third_party; make builds an
optimized C++17 executable.
