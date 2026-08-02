# SKPBR v0.3 Model Card

## Model summary

SKPBR v0.3 is a 4,443,261-parameter planar PBR model with two runtime modes:

- aligned RGB image + Prompt → reconstruction of the visible flat material patch;
- Prompt + deterministic seed → a plausible material candidate.

Both modes run and write six maps. Image + Prompt remains a research preview; text-only generation remains experimental. The frozen Blind-F suite passed only 2 of 12 per-material identity checks, so neither mode should be described as production-ready material recovery.

## Inputs

- Optional aligned planar RGB material image, evaluated at 512 × 512.
- English or Chinese material description.
- Integer seed for text-only generation.

The frozen reconstruction core still receives a 93-dimensional condition vector. v0.3 adds a separate 55-dimensional structured Prompt vector containing material class, physical regime, primary and secondary colors, confidence values, Roughness, Metallic and relief hints, finish, effect flags, and light/dark modifiers.

## Outputs

- BaseColor RGB.
- Roughness.
- Metallic.
- OpenGL +Y tangent-space Normal RGB.
- Height.
- Ambient Occlusion.

All maps are written at the requested square resolution. Only 512px has been used for the current frozen release evaluation.

## Architecture

| Component | Parameters |
|---|---:|
| Frozen circular-padding reconstruction core | 3,409,232 |
| Prompt, texture, relief, property and spatial adapters | 1,034,029 |
| Total | 4,443,261 |

The image path keeps a full-resolution RGB carrier. The text path uses twelve channels of deterministic, isotropic, multiscale filtered noise; the first six channels also feed the frozen core. v0.3 adds structured global calibration and an exact zero-relief path for explicitly flat materials.

A 31,392-parameter 512px spatial separator was trained during D51, but neither trained epoch beat the frozen zero-residual baseline. The released checkpoint therefore keeps that head at its epoch-0 zero-residual state. Its parameters are included in the total count, but it does not contribute a learned spatial correction in this release.

## Intended use

- Research on flat single-image material reconstruction.
- Artist-reviewed PBR candidate extraction from aligned scans, crops, or controlled renders.
- Prompt-guided material family, color, finish and relief control.
- Reproducible text-only material ideation using an integer seed.

## Out-of-scope use

- Arbitrary handheld photographs with unknown camera response, perspective, exposure, illumination, occlusion, or cast shadows.
- Recovery of hidden or unobserved UV regions.
- Certified physical material measurement.
- Transparency, subsurface scattering, hair, skin, liquids, or volumetric materials.
- Unreviewed production use of generated maps.

## D49–D51 development result

| Stage | Change | Frozen development objective | Result |
|---|---|---:|---|
| D49 | 55-D structured Prompt calibrator | 0.306307 → 0.270900 | improved 11.6% |
| D50 | exact-zero relief limiter and flat hard negatives | 0.981784 → 0.966645 | improved 1.54% |
| D51 | 512px spatial property separator | 0.454305 → 0.454305 | trained residual rejected |

D49–D51 used development train data for optimization and development validation data for checkpoint selection. D10 test, Fresh12, Blind-C/D, Blind-E pixels and Blind-F pixels were not read during these stages.

## Frozen Blind-F evaluation

Blind-F contains twelve procedural targets first generated after both the v0.3 weights and evaluator were frozen. The evaluator runs once and refuses to overwrite a completed result. Image mode receives one rendered RGB image plus the Prompt; text mode receives only the Prompt and deterministic seed. Target maps are never supplied to inference.

| Blind-F metric | Value | Gate |
|---|---:|---|
| Per-material identities | 2 / 12 | fail, required 9 |
| Aggregate gates | 13 / 20 | fail |
| Image BaseColor MAE | 0.104172 | fail, ≤0.065 |
| Image BaseColor mean MAE | 0.102702 | fail, ≤0.050 |
| Image Roughness MAE | 0.075988 | pass |
| Image Metallic MAE | 0.030611 | pass |
| Image Normal angular error | 11.729° | pass |
| Image micro-normal log MAE | 0.789289 | fail, ≤0.550 |
| Image rerender MAE | 0.065479 | fail, ≤0.060 |
| Color-to-geometry leakage | 0.088739 | fail, ≤0.030 |
| Text mean-color MAE | 0.152954 | pass |
| Text Roughness mean MAE | 0.053674 | pass |
| Text Metallic mean MAE | 0.042363 | pass |
| Text relief log MAE | 0.290870 | pass |
| Text relief overshoot rate | 18.75% | pass |
| Catastrophic physical-regime failures | 0 | pass |

The two full per-material passes were brushed titanium and forest-green powder-coated aluminum. Blind-F is now a consumed diagnostic suite and must not be used for further training, hyperparameter tuning, or checkpoint selection.

## Known weaknesses

- BaseColor can shift in brightness, saturation and hue, especially for sand, terrazzo, brick, ceramic and concrete.
- Color-only edges are often copied into Normal and Height.
- Fine cracks, veins, layers, chips and other high-information structures are not reliably reconstructed.
- Text-only structure is often generic stochastic texture rather than the requested topology.
- Multi-color Prompts are parsed more reliably than their secondary pattern is generated.
- Most development inputs are controlled or synthetic; a dedicated cross-camera, cross-exposure real-photo set is still missing.

## Training-data disclosure

Training data is not distributed. The repository contains no private source textures, commercial material assets, training images, target maps, cache tensors, optimizer states, sample identities, or split manifests. The checkpoint is loaded through PyTorch's restricted `weights_only=True` path and contains model state plus bounded release metadata; it is not a browsable copy of the training set. Memorization and membership inference cannot be ruled out in principle.

## Resource envelope

The highest conservative whole-device estimate in D49–D51 was 2.411 GiB under an 8 GiB limit. This is a development-machine training measurement, not a guaranteed inference requirement for every resolution, driver or PyTorch build.

## Release status

**Image + Prompt: research preview. Prompt only: experimental. Blind-F release gate: failed.**
