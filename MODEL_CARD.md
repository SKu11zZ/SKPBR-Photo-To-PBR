# SKPBR v0.1 Model Card

## Model summary

SKPBR v0.1 is a 266,241-parameter, dual-resolution convolutional BaseColor calibrator. It consumes a 128px RGB reference, a 512px 11-channel parent tensor, and a 72-dimensional deterministic Prompt vector. It predicts bounded RGB gain, bias, and a low-resolution UV residual that is applied to the original-resolution parent BaseColor.

The released checkpoint sets the direct screen-feature scale to zero at runtime. The final head therefore depends on the Prompt and reconstructed parent PBR, while the larger unreleased upstream system remains responsible for extracting image evidence.

## Inputs

- Controlled RGB reference render, resized to 128px for the head.
- English material description parsed into a fixed 72-dimensional vector.
- Parent PBR at 512px: BaseColor RGB, Roughness, Metallic, Normal RGB, Height, AO, and visible confidence.

## Outputs

- Corrected BaseColor at the parent map resolution, normally 1024px.
- Bit-identical parent Roughness, Metallic, Normal, Height, and AO files.

## Intended use

- Research on controlled single-image material reconstruction.
- Artist-reviewed BaseColor correction for a known object and UV layout.
- Reproducible comparison of color accuracy and illumination consistency.

## Out-of-scope use

- Arbitrary photographs or internet images.
- Arbitrary objects, UVs, cameras, or illumination distributions.
- Standalone end-to-end RGB-to-PBR inference.
- Safety-critical, scientific-measurement, or physically certified material capture.
- Organic, translucent, transparent, hairy, fluid, or volumetric materials.

## Architecture and parameters

| Component | Value |
|---|---:|
| Total parameters | 266,241 |
| State tensors | 104 |
| Screen input | 3 x 128 x 128 |
| Parent input | 11 x 512 x 512 |
| Prompt input | 72 values |
| Typical saved output | 3 x 1024 x 1024 BaseColor |
| Direct screen feature scale | 0.0 |

## Frozen external shadow

The one-shot evaluation used 81 examples from 59 identities that did not intersect development identities. The model passed 8 of 11 aggregate gates and failed the frozen release decision.

| Metric | Value |
|---|---:|
| Parent target MAE | 0.1914335 |
| D36 target MAE | 0.0727204 |
| SKPBR target MAE | 0.0893537 |
| SKPBR / parent target MAE | 0.4667610 |
| SKPBR / D36 target MAE | 1.2287298 |
| Item non-regression rate | 0.9259259 |
| Catastrophic item rate | 0.0493827 |
| Screen-substitution consistency MAE | 0.0 |
| High-frequency parent-detail correlation | 0.9674160 |
| Non-BaseColor file identity | exact |
| Development/shadow identity overlap | 0 |

Failed gates: target non-regression versus D36, item non-regression rate, and catastrophic item rate. No threshold or weight was changed after the one-shot result.

## Limitations and risks

- Strong consistency is partly achieved by removing the final head's direct screen dependence, which can discard useful color evidence.
- Single-image reconstruction is underdetermined; hidden UV areas and physical microstructure cannot be uniquely recovered.
- The published aggregate evaluation does not establish accuracy for every non-BaseColor channel.
- The deterministic English keyword parser is not a general language model.
- A tensor checkpoint is not a browsable copy of the training set, but memorization and membership inference cannot be ruled out in principle.

## Training-data disclosure

Training data is not distributed. Development used controlled synthetic renders and private source-derived material examples. This repository contains no source textures, training images, target maps, cache tensors, sample identities, or per-example scores.

## Release status

**Research preview / alpha. Not production ready.**
