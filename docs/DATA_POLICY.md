# Data and Privacy Policy

SKPBR's public repository is intentionally separated from its private research workspace.

## Included

- Standalone model architecture.
- Deterministic English and Chinese Prompt encoder.
- Source-free inference CLI.
- Restricted-load checkpoint containing model tensors and bounded release metadata.
- Aggregate model-card metrics.
- Tests and release-audit tooling.
- Two compact D41 evaluation sheets made from post-freeze procedural recipes.

## Excluded

- Training, validation, and shadow-evaluation images.
- Source and target PBR textures.
- Third-party material-library files.
- Render caches and tensor caches.
- Optimizer, scheduler, scaler, and RNG state.
- Resume checkpoints.
- Local filesystem paths and workstation identifiers.
- Material sample identities and split manifests.
- Per-example predictions, metrics, or target references.
- Nearest-neighbor catalogs and source lookup tables.

The public v0.2 checkpoint contains the named tensors required by `PromptRemediatedPBRNet.load_state_dict` plus the selected epoch, aggregate validation values, model-shape metadata, and target-read counters. It is loaded through PyTorch's restricted `weights_only=True` path. It contains no optimizer state, sample identity, source path, local path, or target texture.

The two sheets under `examples/plane-d41` were created from numeric procedural recipes after the corresponding weights were frozen. They are not members of the training or validation sets and contain no third-party material-library content. Larger internal reports and per-sample exports are deliberately excluded from the current public tree.

## Third-party rights

The Apache License 2.0 covers repository-authored code and the exported SKPBR weight file. It does not grant rights to third-party assets that may have been used in private experiments. No such assets are included in this repository. The publisher is responsible for confirming that publishing the learned weights is compatible with every applicable source-data agreement.
