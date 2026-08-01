# D41 planar evaluation sheets / D41 平面材质评估图

[English](#english) · [简体中文](#简体中文)

## English

`fresh12b_contact_sheet.jpg` is the final one-shot 12-material suite. Its numeric procedural recipes and seeds were fixed before Prompt-remediation training; target images were generated only after the adapter checkpoint was frozen. The combined identity gate passed 6/12, below the required 8/12.

`same_material_color_b_contact_sheet.jpg` keeps one powder-coated-steel recipe fixed and requests red, blue, orange, and white. The first three passed the 0.08 per-case mean-color gate; white failed.

These sheets are evaluation evidence, not selected product renders. No training image, commercial material texture, or nearest-neighbor source is included.

## 简体中文

`fresh12b_contact_sheet.jpg` 是最后一次 12 材质一次性测试。它的程序化数字配方和 Seed 在 Prompt 修复训练前已经锁定，目标图只在适配器权重冻结后生成。综合身份门槛通过 6/12，低于要求的 8/12。

`same_material_color_b_contact_sheet.jpg` 固定同一套粉末涂层钢配方，只改变红、蓝、橙、白四种颜色。前三种通过 0.08 单例平均颜色门槛，白色失败。

这些图是评估证据，不是挑选过的产品展示。目录里不包含训练图片、商业材质贴图或近邻来源素材。
