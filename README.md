# SKPBR

**English** | [简体中文](README_zh-CN.md)

> **SKPBR is a 266,241-parameter single-image + Prompt BaseColor calibrator that produces a 1024px BaseColor from a controlled Suzanne/Light-Stage input and a frozen parent PBR, while preserving Roughness, Metallic, Normal, Height, and AO bit-for-bit; it is not a general solution for arbitrary photos, arbitrary geometry, or production-ready PBR reconstruction.**

SKPBR v0.1 is a transparent research preview of the final calibration head developed in a larger single-image material-reconstruction experiment. This repository intentionally contains only the small, source-free calibration component whose weights and runtime can be audited independently.

The project was originally developed as an experimental material tool for the author's own game project.

## What this release does

The command-line runtime accepts:

- one RGB reference render;
- one English material Prompt;
- a frozen parent PBR prediction containing BaseColor, Roughness, Metallic, Normal, Height, and AO;
- a visible-confidence map for the known UV projection.

It creates a new BaseColor and copies the other five parent maps without modification. The saved output is object-UV-specific, not a guaranteed seamless material for arbitrary meshes.

## What this release does not do

- It does not contain the upstream RGB-to-parent-PBR stack.
- It does not infer a complete PBR material from an arbitrary photograph by itself.
- It is not validated for arbitrary geometry, cameras, lighting, backgrounds, or UV layouts.
- It is not intended for SSS, transmission, opacity, hair, skin, fluids, or volumetric materials.
- It is not a production release. The frozen external shadow failed 3 of 11 release gates.

## Install

```bash
python -m venv .venv
python -m pip install -e .
```

CUDA is optional. CPU inference is supported but slower.

## Run

The parent directory must contain `basecolor.png`, `roughness.png`, `metallic.png`, `normal.png`, `height.png`, and `ao.png`.

```bash
skpbr \
  --image reference.png \
  --prompt "dark rough cast iron" \
  --parent-dir parent_pbr \
  --visible-confidence visible_confidence.png \
  --output outputs/cast_iron
```

The runtime refuses to overwrite an existing output directory. Use `--device cpu`, `--device cuda`, or the default `--device auto`.

## Four honest examples

The following examples use four newly created procedural materials, rendered on Suzanne with Blender Cycles at 1024px. Inference received only the rendered RGB image and the exact English Prompt. The examples were run through the complete frozen research pipeline; the public package in this repository contains only its final 266,241-parameter S12 calibration head and therefore still requires a parent PBR input.

![Four SKPBR procedural examples: input, output render, and six output maps](examples/public/contact_sheet.png)

[Open the full-resolution inputs, Prompts, output renders, and all six PBR maps.](examples/README.md)

These are unedited model results, not selected ground truth or post-processed artwork. Known problems remain visible: periodic UV/projection dots, weak fine-vein recovery in white marble, a pale/green cast in rough steel, and a saturated-blue shift in cyan automotive clearcoat.

## Public evaluation

The frozen one-shot external shadow used 81 examples from 59 source-disjoint identities. Only aggregate metrics are published here.

| Metric | SKPBR v0.1 | Result |
|---|---:|---|
| Parent BaseColor MAE | 0.19143 | reference |
| Frozen D36 BaseColor MAE | 0.07272 | stronger color baseline |
| SKPBR BaseColor MAE | 0.08935 | 53.3% better than parent |
| SKPBR / parent MAE | 0.46676 | pass |
| SKPBR / D36 MAE | 1.22873 | fail |
| Item non-regression rate | 92.59% | fail |
| Catastrophic item rate | 4.94% | fail |
| Screen-substitution consistency MAE | 0.0 | pass |
| Parent-detail correlation | 0.96742 | pass |
| Identity overlap | 0 | pass |

The result is reported as-is. The held-out targets were not used to change weights, thresholds, or the published metrics after evaluation.

## Repository privacy

Apart from the four newly generated procedural public examples above, this repository does not include training or evaluation images, source PBR maps, material-library assets, training caches, optimizer states, local filesystem paths, per-example evaluation records, or nearest-neighbor catalogs. The checkpoint is a tensor-only state dictionary and should be loaded with `weights_only=True`.

See the [model card](docs/MODEL_CARD.md), [data policy](docs/DATA_POLICY.md), and [release checklist](docs/RELEASE_CHECKLIST.md) before publishing or redistributing the weights. The remaining technical and release documents are collected in the [documentation index](docs/README.md).

## License

Repository-authored code and the exported SKPBR weight file are provided under the [MIT License](LICENSE). This license does not grant rights to any third-party training or reference assets, none of which are included here.
