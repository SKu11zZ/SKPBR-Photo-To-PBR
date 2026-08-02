# SKPBR v0.4 Model Card

## Model summary

SKPBR v0.4 is a 4,586,975-parameter planar PBR model with two runtime modes:

- aligned RGB image + Prompt → reconstruction of the visible flat material patch;
- Prompt + deterministic seed → a plausible material candidate.

Both modes write BaseColor, Roughness, Metallic, OpenGL +Y Normal, Height, and AO. Image + Prompt remains a research preview; text-only generation remains experimental. The frozen Blind-G suite passed only 2 of 12 per-material identity checks, so this release is not a production-ready material scanner.

## Inputs and outputs

- Optional aligned planar RGB material image, evaluated at 512 × 512.
- English or Chinese material description.
- Integer seed for text-only generation.
- Six square PBR maps at the requested resolution.

The network receives a 93-dimensional condition vector and a separate 55-dimensional structured Prompt vector. The structured vector covers material class, physical regime, primary and secondary colors, confidence, Roughness, Metallic, relief, finish, effects, and light/dark modifiers.

## Architecture

| Component | Parameters |
|---|---:|
| Frozen circular-padding reconstruction core | 3,409,232 |
| Prompt, texture, relief, property, spatial, photometric, and disentanglement adapters | 1,177,743 |
| Total | 4,586,975 |

The image path keeps a full-resolution RGB carrier. The text path starts from twelve channels of deterministic, isotropic, multiscale filtered noise. v0.4 adds two image-side components above the v0.3 parent:

- a full-resolution photometric BaseColor refiner using local image evidence, low-frequency color, and Prompt context;
- a conservative color/geometry separator that looks for reflectance-only edges before changing Normal or Height.

The original 3.41M-parameter reconstruction core remains frozen.

## D52–D54 development result

| Stage | Main change | Frozen development result |
|---|---|---|
| D52 | photometric BaseColor refiner | BaseColor MAE 0.06855 → 0.05920 |
| D53 | color/geometry disentangler | leakage 0.06985 → 0.06614; Normal 14.23° → 13.55° |
| D54 | three-mode joint adapter tuning | objective 0.70650 → 0.69374 |

At the selected D54 checkpoint, development BaseColor MAE is 0.05878 and color-to-geometry leakage is 0.06158. The training mix was 60% image + Prompt, 15% image-only, and 25% text-only. D10 test, Fresh12, Blind-C/D, Blind-E/F pixels, and Blind-G pixels were not read during these stages.

## Frozen Blind-G evaluation

Blind-G contains twelve procedural targets first generated after the v0.4 weights were frozen. Image mode receives one rendered RGB image and its Prompt. Text mode receives only the Prompt and deterministic seed. Target PBR maps are never supplied to inference.

| Blind-G metric | Value | Gate |
|---|---:|---|
| Per-material identities | 2 / 12 | fail, required 9 |
| Aggregate gates | 12 / 20 | fail |
| Image BaseColor MAE | 0.112868 | fail, ≤0.065 |
| Image BaseColor mean MAE | 0.111026 | fail, ≤0.050 |
| Image Roughness MAE | 0.074689 | pass |
| Image Metallic MAE | 0.023755 | pass |
| Image Normal angular error | 10.054° | pass |
| Image micro-normal log MAE | 0.623825 | fail, ≤0.550 |
| Image rerender MAE | 0.068899 | fail, ≤0.060 |
| Color-to-geometry leakage | 0.068370 | fail, ≤0.030 |
| Text mean-color MAE | 0.156367 | pass |
| Text Roughness mean MAE | 0.078915 | pass |
| Text Metallic mean MAE | 0.020429 | pass |
| Text spectrum-amplitude MAE | 0.073241 | pass |
| Text autocorrelation MAE | 0.219831 | fail, ≤0.205 |
| Text stripe-peak MAE | 0.285967 | fail, ≤0.130 |
| Text relief log MAE | 0.251228 | pass |
| Text relief overshoot rate | 20.83% | pass |
| Catastrophic physical-regime failures | 0 | pass |

Bead-blasted aluminum and black-aggregate concrete passed every per-material identity check. Copper patina is close in image mode but fails text structure. ABS, limestone, basalt, marble, and terracotta show the largest image-side color and low-frequency identity errors. Blind-G is now a consumed diagnostic suite and must not be used for further training, hyperparameter tuning, or checkpoint selection.

## Intended use

- Research on flat single-image material reconstruction.
- Artist-reviewed candidate extraction from aligned scans, crops, or controlled renders.
- Prompt-guided material family, color, finish, and relief control.
- Reproducible text-only material ideation using an integer seed.

## Known limits

- BaseColor can shift in brightness, saturation, and hue outside the development distribution.
- Color-only edges can still leak into Normal and Height.
- Fine cracks, veins, layers, chips, weave, and other high-information structures are not reliably reconstructed.
- Text-only structure often collapses to generic stochastic texture.
- Arbitrary handheld photos, hidden UV recovery, absolute reflectance measurement, transparency, SSS, hair, skin, liquids, and volumes are outside the established boundary.

## Training-data disclosure

Training data is not distributed. The repository contains no private source textures, commercial material assets, training images, target maps, cache tensors, optimizer states, sample identities, or split manifests. The checkpoint is loaded through PyTorch's restricted `weights_only=True` path and contains model state plus compact release metadata; it is not a browsable copy of the training set. Memorization and membership inference cannot be ruled out in principle.

## Resource envelope

The conservative whole-device peak estimate during D52–D54 was 4.280 GiB under an 8 GiB limit. This is a development-machine measurement, not a guaranteed inference requirement for every resolution, driver, or PyTorch build.

## Release status

**Image + Prompt: research preview. Prompt only: experimental. Blind-G release gate: failed.**
