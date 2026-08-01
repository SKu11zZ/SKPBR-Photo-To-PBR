# SKPBR v0.2 Model Card

## Model summary

SKPBR v0.2 is a 4,042,230-parameter planar PBR model with two runtime modes:

- aligned RGB image + Prompt → reconstruction of the visible flat material patch;
- Prompt + deterministic seed → a plausible material candidate.

The first mode is the release MVP. The second mode is experimental and failed the final Fresh-12B identity gate.

## Inputs

- Optional aligned planar RGB material image, evaluated at 512 × 512.
- English or Chinese material description encoded into a fixed 93-dimensional vector.
- Integer seed for text-only generation.

The Prompt vector contains material family, physical regime, named color and RGB hint, finish, effect flags, roughness/metallic hints, color confidence, and deterministic hashed tokens.

## Outputs

- BaseColor RGB.
- Roughness.
- Metallic.
- OpenGL +Y tangent-space Normal RGB.
- Height.
- Ambient Occlusion.

All six maps are written at the requested square resolution; 512px is the evaluated release setting.

## Architecture

| Component | Parameters |
|---|---:|
| Circular-padding reconstruction core | 3,409,232 |
| Prompt color and texture adapters | 632,998 |
| Total | 4,042,230 |

The core is a fully convolutional Prompt-conditioned U-Net with a full-resolution RGB carrier, so visible color and texture do not pass through a small global latent bottleneck. Text-only mode replaces the image with six periodic core seed channels and twelve multi-harmonic adapter seed channels. The released adapter checkpoint keeps the reconstruction core frozen.

## Intended use

- Research on flat single-image material reconstruction.
- Artist-reviewed PBR candidate extraction from aligned scans, crops, or controlled renders.
- Prompt-guided color, material-family, and finish control.
- Reproducible text-only material ideation using an integer seed.

## Out-of-scope use

- Arbitrary handheld photographs with unknown camera response, perspective, exposure, illumination, occlusion, or cast shadows.
- Recovery of hidden or unobserved UV regions.
- Certified physical material measurement.
- Transparency, subsurface scattering, hair, skin, liquids, or volumetric materials.
- Unreviewed production use of text-only outputs.

## Frozen evaluation

The reconstruction core was frozen before the first target read from the 81-row, source-identity-disjoint D10 test set.

| D10 metric | Value |
|---|---:|
| BaseColor MAE | 0.049674 |
| Roughness MAE | 0.061454 |
| Metallic MAE | 0.004553 |
| Normal angular error | 13.681° |
| Fixed novel-light rerender MAE | 0.037021 |
| Tile seam error | 0.005068 |
| Seed difference | 0.059572 |
| Catastrophic metal/non-metal regime rate | 0 |

All frozen D10 gates passed.

Fresh-12A was generated after core freeze and exposed text-only texture collapse. The reconstruction core was then kept frozen while 632,998 Prompt-adapter parameters were trained using only development train/validation data. Fresh-12B seeds were fixed before remediation, its targets were generated after adapter freeze, and the failed result was not used for another tuning round.

| Fresh-12B metric | Value |
|---|---:|
| Combined material identities passed | 6 / 12 |
| Required | 8 / 12 |
| Mean image BaseColor MAE | 0.072964 |
| Mean image rerender MAE | 0.039460 |
| Mean text spectrum MAE | 0.226900 |
| Mean text color MAE | 0.117239 |
| Catastrophic physical-regime rate | 0 |

Text-only generation therefore remains experimental. Same-material color control passed red, blue, and orange but failed white at 0.146667 mean-color MAE.

## Known weaknesses

- Dark fibrous materials, especially denim and leather, can lose their true BaseColor.
- Cork is near the current color threshold.
- Red brick and black ABS can miss Roughness even when BaseColor looks reasonable.
- White Prompt control is biased dark.
- A shallow periodic-seed CNN does not reliably reproduce class-specific texture distributions for every material family.
- Most development inputs are controlled or synthetic; a dedicated cross-camera, cross-exposure real-photo set is still missing.

## Training-data disclosure

Training data is not distributed. The repository contains no private source textures, commercial material assets, training images, target maps, cache tensors, optimizer states, sample identities, or split manifests. The checkpoint is loaded through PyTorch's restricted `weights_only=True` path and contains the model state plus bounded training metadata; it is not a browsable copy of the training set. Memorization and membership inference cannot be ruled out in principle.

## Resource envelope

The conservative whole-device peak estimate during D41 Prompt remediation was 5.0687 GiB under an 8 GiB limit. This is a training measurement from the development machine, not a guaranteed inference requirement for every resolution or driver stack.

## Release status

**Image + Prompt: research-preview MVP. Prompt only: experimental. Not production ready.**
