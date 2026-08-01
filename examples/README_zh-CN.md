# 公开示例

[English](README.md) | **简体中文**

这四组示例均为冻结 SKPBR 研究管线未经美化的输出。每个输入都由全新的确定性程序化配方生成，并以 Blender Cycles 在 Suzanne 上进行 1024 x 1024 渲染。推理只读取输入渲染图和下列 Prompt，没有读取源贴图、训练/评估样本、商业素材或近邻素材库。

完整研究管线生成了这些六贴图结果；可安装的公开包只包含最终 S12 BaseColor 校准头，无法单独完成上游父 PBR 预测。

## 深色橡胶

Prompt：`dark rubber, rough matte finish`

<table>
  <tr><th>输入</th><th>输出渲染</th></tr>
  <tr><td><img alt="深色橡胶输入" src="public/dark-rubber/input.png" width="430"></td><td><img alt="深色橡胶输出渲染" src="public/dark-rubber/output_render.png" width="430"></td></tr>
</table>

| BaseColor | Roughness | Metallic |
|---|---|---|
| ![深色橡胶 BaseColor](public/dark-rubber/maps/basecolor.png) | ![深色橡胶 Roughness](public/dark-rubber/maps/roughness.png) | ![深色橡胶 Metallic](public/dark-rubber/maps/metallic.png) |

| Normal | Height | AO |
|---|---|---|
| ![深色橡胶 Normal](public/dark-rubber/maps/normal.png) | ![深色橡胶 Height](public/dark-rubber/maps/height.png) | ![深色橡胶 AO](public/dark-rubber/maps/ao.png) |

## 粗钢

Prompt：`rough coarse steel`

<table>
  <tr><th>输入</th><th>输出渲染</th></tr>
  <tr><td><img alt="粗钢输入" src="public/rough-steel/input.png" width="430"></td><td><img alt="粗钢输出渲染" src="public/rough-steel/output_render.png" width="430"></td></tr>
</table>

| BaseColor | Roughness | Metallic |
|---|---|---|
| ![粗钢 BaseColor](public/rough-steel/maps/basecolor.png) | ![粗钢 Roughness](public/rough-steel/maps/roughness.png) | ![粗钢 Metallic](public/rough-steel/maps/metallic.png) |

| Normal | Height | AO |
|---|---|---|
| ![粗钢 Normal](public/rough-steel/maps/normal.png) | ![粗钢 Height](public/rough-steel/maps/height.png) | ![粗钢 AO](public/rough-steel/maps/ao.png) |

## 白色大理石

Prompt：`white marble with subtle gray veins, polished finish`

<table>
  <tr><th>输入</th><th>输出渲染</th></tr>
  <tr><td><img alt="白色大理石输入" src="public/white-marble/input.png" width="430"></td><td><img alt="白色大理石输出渲染" src="public/white-marble/output_render.png" width="430"></td></tr>
</table>

| BaseColor | Roughness | Metallic |
|---|---|---|
| ![白色大理石 BaseColor](public/white-marble/maps/basecolor.png) | ![白色大理石 Roughness](public/white-marble/maps/roughness.png) | ![白色大理石 Metallic](public/white-marble/maps/metallic.png) |

| Normal | Height | AO |
|---|---|---|
| ![白色大理石 Normal](public/white-marble/maps/normal.png) | ![白色大理石 Height](public/white-marble/maps/height.png) | ![白色大理石 AO](public/white-marble/maps/ao.png) |

## 青蓝色汽车清漆

Prompt：`cyan blue automotive clearcoat, glossy metallic finish`

<table>
  <tr><th>输入</th><th>输出渲染</th></tr>
  <tr><td><img alt="青蓝车漆输入" src="public/cyan-automotive-clearcoat/input.png" width="430"></td><td><img alt="青蓝车漆输出渲染" src="public/cyan-automotive-clearcoat/output_render.png" width="430"></td></tr>
</table>

| BaseColor | Roughness | Metallic |
|---|---|---|
| ![青蓝车漆 BaseColor](public/cyan-automotive-clearcoat/maps/basecolor.png) | ![青蓝车漆 Roughness](public/cyan-automotive-clearcoat/maps/roughness.png) | ![青蓝车漆 Metallic](public/cyan-automotive-clearcoat/maps/metallic.png) |

| Normal | Height | AO |
|---|---|---|
| ![青蓝车漆 Normal](public/cyan-automotive-clearcoat/maps/normal.png) | ![青蓝车漆 Height](public/cyan-automotive-clearcoat/maps/height.png) | ![青蓝车漆 AO](public/cyan-automotive-clearcoat/maps/ao.png) |

## 当前可见问题

- 多张输出贴图存在周期性 UV/投影点阵；
- 白色大理石细脉恢复不足；
- 粗钢颜色偏浅并略微偏绿；
- 青蓝车漆向更高饱和度的蓝色偏移。

这些是定性演示，不代表精度承诺；没有使用后处理或人工替换贴图来掩盖问题。

## 公开 CLI 输入约定

运行公开校准头时，需要提供受控 RGB 参考图、父 PBR 预测和可见 UV 置信度图。父目录必须包含 `basecolor.png`、`roughness.png`、`metallic.png`、`normal.png`、`height.png` 和 `ao.png`。输出包含校准后的 BaseColor、逐文件不变的其余五张贴图和 `metadata.json`。
