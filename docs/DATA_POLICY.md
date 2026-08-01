# Data and Privacy Policy

SKPBR's public repository is intentionally separated from its private research workspace.

## Included

- Standalone model architecture.
- Deterministic English Prompt encoder.
- Source-free inference CLI.
- Tensor-only model state dictionary.
- Aggregate model-card metrics.
- Tests and release-audit tooling.
- Four newly generated, deterministic procedural example inputs and their unedited frozen-pipeline outputs.

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

The public weight file contains only named tensors required by `SKPBRBaseColorCalibrator.load_state_dict`. It contains no training metadata or local path strings.

The files under `examples/public` were generated from scratch for this release. They are not members of the training, validation, or external-shadow sets and do not contain third-party material-library content.

## Third-party rights

The MIT License covers repository-authored code and the exported SKPBR weight file. It does not grant rights to third-party assets that may have been used in private experiments. No such assets are included in this repository. The publisher is responsible for confirming that publishing the learned weights is compatible with every applicable source-data agreement.
