# Data and Privacy Policy

SKPBR's public repository is intentionally separated from its private research workspace.

## Included

- Standalone model architecture.
- Deterministic English and Chinese Prompt encoder.
- Source-free inference CLI.
- Restricted-load checkpoint containing model tensors and bounded release metadata.
- Aggregate model-card metrics.
- Tests and release-audit tooling.
- Two compact D41 evaluation sheets and one combined Blind-F board made from post-freeze procedural recipes.
- Compact MatSynth-90 and post-freeze Blind-6 packages containing CC0-derived Blender input previews, SKPBR outputs, comparison boards, sanitized provenance, and aggregate run metadata.

## Excluded

- Training, validation, and shadow-evaluation images.
- Source and target PBR textures.
- Original third-party PBR map files and non-CC0 material-library assets.
- Render caches and tensor caches.
- Optimizer, scheduler, scaler, and RNG state.
- Resume checkpoints.
- Local filesystem paths and workstation identifiers.
- Private training/validation sample identities and split manifests.
- Per-example predictions, metrics, or target references.
- Nearest-neighbor catalogs and source lookup tables.

The public v0.6 checkpoint contains model tensors plus bounded version, selection, and anti-cheating metadata. It is loaded through PyTorch's restricted `weights_only=True` path. It contains no optimizer state, sample identity, source path, local path, or target texture.

The sheets under `examples/plane-d41` and `examples/blind-g` were created from post-freeze evaluation recipes and are not members of the training or validation sets. MatSynth-90 is a historical inference-only capability check. The Blind-6 materials were locked only after D72 was frozen; their target maps were unavailable to inference and used only for scoring. Neither package publishes original PBR maps. Larger internal reports and raw per-sample exports remain excluded from the public tree.

## Third-party rights

The Apache License 2.0 covers repository-authored code and the exported SKPBR weight file. It does not replace upstream licenses for third-party material. The only public third-party-derived image packages are `examples/matsynth-90` and `examples/matsynth-blind6`; their selected items are individually recorded as CC0 in [`materials.csv`](../examples/matsynth-90/materials.csv) and [`benchmark.json`](../examples/matsynth-blind6/benchmark.json). Other private or commercial source assets are not included. The publisher remains responsible for confirming that learned-weight distribution is compatible with every applicable source-data agreement.
