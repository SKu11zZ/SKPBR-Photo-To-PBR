# Public examples

**English** | [简体中文](README_zh-CN.md)

These four examples are unedited outputs from the frozen SKPBR research pipeline. Each input was created from a new deterministic procedural recipe and rendered on Suzanne with Blender Cycles at 1024 x 1024. Inference read only the input render and the listed Prompt; it did not read source maps, training or evaluation samples, commercial assets, or a nearest-neighbor catalog.

The complete research pipeline generated these six-map outputs. The installable public package contains only the final S12 BaseColor calibration head and cannot reproduce the upstream parent-PBR prediction by itself.

For the wider and much less flattering test, see the [12-material coverage audit](coverage-12/README.md).

## Dark rubber

Prompt: `dark rubber, rough matte finish`

<table>
  <tr><th>Input</th><th>Output render</th></tr>
  <tr><td><img alt="Dark rubber input" src="public/dark-rubber/input.png" width="430"></td><td><img alt="Dark rubber output render" src="public/dark-rubber/output_render.png" width="430"></td></tr>
</table>

| BaseColor | Roughness | Metallic |
|---|---|---|
| ![Dark rubber BaseColor](public/dark-rubber/maps/basecolor.png) | ![Dark rubber Roughness](public/dark-rubber/maps/roughness.png) | ![Dark rubber Metallic](public/dark-rubber/maps/metallic.png) |

| Normal | Height | AO |
|---|---|---|
| ![Dark rubber Normal](public/dark-rubber/maps/normal.png) | ![Dark rubber Height](public/dark-rubber/maps/height.png) | ![Dark rubber AO](public/dark-rubber/maps/ao.png) |

## Rough coarse steel

Prompt: `rough coarse steel`

<table>
  <tr><th>Input</th><th>Output render</th></tr>
  <tr><td><img alt="Rough steel input" src="public/rough-steel/input.png" width="430"></td><td><img alt="Rough steel output render" src="public/rough-steel/output_render.png" width="430"></td></tr>
</table>

| BaseColor | Roughness | Metallic |
|---|---|---|
| ![Rough steel BaseColor](public/rough-steel/maps/basecolor.png) | ![Rough steel Roughness](public/rough-steel/maps/roughness.png) | ![Rough steel Metallic](public/rough-steel/maps/metallic.png) |

| Normal | Height | AO |
|---|---|---|
| ![Rough steel Normal](public/rough-steel/maps/normal.png) | ![Rough steel Height](public/rough-steel/maps/height.png) | ![Rough steel AO](public/rough-steel/maps/ao.png) |

## White marble

Prompt: `white marble with subtle gray veins, polished finish`

<table>
  <tr><th>Input</th><th>Output render</th></tr>
  <tr><td><img alt="White marble input" src="public/white-marble/input.png" width="430"></td><td><img alt="White marble output render" src="public/white-marble/output_render.png" width="430"></td></tr>
</table>

| BaseColor | Roughness | Metallic |
|---|---|---|
| ![White marble BaseColor](public/white-marble/maps/basecolor.png) | ![White marble Roughness](public/white-marble/maps/roughness.png) | ![White marble Metallic](public/white-marble/maps/metallic.png) |

| Normal | Height | AO |
|---|---|---|
| ![White marble Normal](public/white-marble/maps/normal.png) | ![White marble Height](public/white-marble/maps/height.png) | ![White marble AO](public/white-marble/maps/ao.png) |

## Cyan automotive clearcoat

Prompt: `cyan blue automotive clearcoat, glossy metallic finish`

<table>
  <tr><th>Input</th><th>Output render</th></tr>
  <tr><td><img alt="Cyan automotive clearcoat input" src="public/cyan-automotive-clearcoat/input.png" width="430"></td><td><img alt="Cyan automotive clearcoat output render" src="public/cyan-automotive-clearcoat/output_render.png" width="430"></td></tr>
</table>

| BaseColor | Roughness | Metallic |
|---|---|---|
| ![Cyan clearcoat BaseColor](public/cyan-automotive-clearcoat/maps/basecolor.png) | ![Cyan clearcoat Roughness](public/cyan-automotive-clearcoat/maps/roughness.png) | ![Cyan clearcoat Metallic](public/cyan-automotive-clearcoat/maps/metallic.png) |

| Normal | Height | AO |
|---|---|---|
| ![Cyan clearcoat Normal](public/cyan-automotive-clearcoat/maps/normal.png) | ![Cyan clearcoat Height](public/cyan-automotive-clearcoat/maps/height.png) | ![Cyan clearcoat AO](public/cyan-automotive-clearcoat/maps/ao.png) |

## Visible limitations

- Periodic UV/projection dots appear in multiple output maps.
- Fine marble veins are recovered weakly.
- Rough steel becomes too pale and slightly green.
- Cyan clearcoat shifts toward a more saturated blue.

These examples are qualitative demonstrations, not accuracy claims. No post-processing or manual texture replacement was used to hide failures.

## CLI input contract

To run the released calibration head, provide a controlled RGB reference, parent PBR prediction, and visible-confidence map. The parent directory must contain `basecolor.png`, `roughness.png`, `metallic.png`, `normal.png`, `height.png`, and `ao.png`. The output contains a corrected BaseColor, the five bit-identical non-color maps, and `metadata.json`.
