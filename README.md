# SKPBR

**English** | [简体中文](README_zh-CN.md)

SKPBR started as a small material experiment for one of my own game projects. The part released here has **266,241 parameters**. Given a controlled Suzanne/Light-Stage render, an English material Prompt, and a parent PBR prediction, it corrects the BaseColor at up to 1024px and passes Roughness, Metallic, Normal, Height, and AO through unchanged.

One thing should be clear up front: this is not yet a “drop in any photo and get a finished PBR material” model. The public package is the final BaseColor calibration head, not the complete private RGB-to-PBR research stack. It still needs a parent PBR input and a known visible-UV confidence map.

## Where it works today

The current model is useful when the setup is controlled:

- one Suzanne render using the known camera, UV layout, and Light-Stage-style lighting;
- one short English Prompt such as `dark rough cast iron`;
- six parent PBR maps: BaseColor, Roughness, Metallic, Normal, Height, and AO;
- one visible-confidence map for the projected UV region.

It produces a corrected BaseColor. The other five maps are copied bit-for-bit, so the head cannot quietly change geometry detail or surface response behind your back. The result is tied to the known UV layout; it is not guaranteed to tile cleanly on another mesh.

## A few honest examples

These four inputs were made from new procedural recipes and rendered in Blender Cycles at 1024px. The frozen research pipeline saw only the RGB render and the exact Prompt. None of the results below were cleaned up afterward.

![Four SKPBR procedural examples: input, output render, and six output maps](examples/public/contact_sheet.png)

[Open the full-resolution inputs, Prompts, output renders, and all six maps.](examples/README.md)

The failures are left in the image on purpose. You can see periodic UV/projection dots, weak fine marble veins, rough steel becoming too pale and slightly green, and cyan clearcoat shifting toward saturated blue. This is a progress snapshot, not a polished demo reel.

## Then I tried twelve broader material types

This second run was meant to find the boundary, not to make the model look good. Blue glazed ceramic and red brick came out relatively close. Oxidized copper, cork, and denim caught only part of the material. Brushed aluminum, powder-coated steel, black ABS, granite, concrete, carbon fiber, and leather all had obvious identity or color failures.

So the 73 active material families in the research directory should not be read as 73 materials the model can already reconstruct reliably. Sand is still reference-only and is not included here.

<details>
  <summary>Open the 12-material bilingual long sheet</summary>
  <p><img alt="SKPBR 12-material coverage audit" src="examples/coverage-12/contact_sheet_long.png"></p>
</details>

[Read the full report and per-channel numbers.](docs/COVERAGE_AUDIT_12.md) The full-resolution input, output render, and six maps for every case are under [examples/coverage-12](examples/coverage-12/README.md).

## Running the public head

```bash
python -m venv .venv
python -m pip install -e .
```

The parent directory must contain `basecolor.png`, `roughness.png`, `metallic.png`, `normal.png`, `height.png`, and `ao.png`.

```bash
skpbr \
  --image reference.png \
  --prompt "dark rough cast iron" \
  --parent-dir parent_pbr \
  --visible-confidence visible_confidence.png \
  --output outputs/cast_iron
```

The command refuses to overwrite an existing output directory. CPU and CUDA inference are both supported through `--device cpu`, `--device cuda`, or the default `--device auto`.

## The numbers, without dressing them up

The frozen external shadow contained 81 examples from 59 source-disjoint identities. SKPBR improved BaseColor MAE over the uncalibrated parent by about **53.3%**, but it was still **22.9% worse** than the stronger frozen D36 color baseline. It passed 8 of 11 release gates, so v0.1 remains a research preview.

| Metric | Result |
|---|---:|
| Parent BaseColor MAE | 0.19143 |
| Frozen D36 BaseColor MAE | 0.07272 |
| SKPBR BaseColor MAE | 0.08935 |
| Item non-regression rate | 92.59% — fail |
| Catastrophic item rate | 4.94% — fail |
| Screen-substitution consistency MAE | 0.0 — pass |
| Parent-detail correlation | 0.96742 — pass |
| Development/shadow identity overlap | 0 — pass |

No weight, threshold, or published metric was changed after that one-shot evaluation.

## Current boundary

The main unresolved problem is color: the final head is deliberately very stable under lighting changes, but that stability also makes it throw away some useful evidence from the input image. Fine, high-density patterns such as marble veins, patina, and irregular gravel structure are also weaker than they should be.

The model has not been validated for arbitrary phone photos, arbitrary geometry, unknown cameras, unknown UVs, SSS, transmission, opacity, hair, skin, fluids, or volumetric materials. If your use case depends on any of those, assume it is unsupported until it is tested.

## What is actually published

The repository contains the small inference package, a tensor-only checkpoint, tests, four focused examples, the 12-material coverage audit, and aggregate evaluation numbers. It does not contain training/evaluation images, private source PBR maps, commercial material assets, caches, optimizer states, local paths, sample identities, or nearest-neighbor catalogs.

The more formal material is kept out of the front page: [model card](docs/MODEL_CARD.md), [data policy](docs/DATA_POLICY.md), [release checklist](docs/RELEASE_CHECKLIST.md), and [documentation index](docs/README.md).

## License

Repository-authored code and the exported SKPBR weight file are released under the [MIT License](LICENSE). MIT does not grant redistribution rights for third-party source assets; none of those assets are included here.
