# 12 类材质覆盖审计

[English](README.md) | **简体中文**

这里放的是 v0.1 Suzanne 历史覆盖审计，不是“最好看结果集”。12 套输入都由新的程序化配方生成，输出来自当时的冻结研究管线，没有修图或人工替换贴图。当前 v0.2 平面评估见 `examples/plane-d41`。

- [打开中英双语长图](contact_sheet_long.png)
- [查看完整中文报告](../../docs/COVERAGE_AUDIT_12_zh-CN.md)
- [查看交付审计](../../docs/release/coverage_12_delivery_audit.json)

`materials/` 下每个目录都包含 1024px 输入渲染、输出渲染、BaseColor、Roughness、Metallic、Normal、Height、AO、实际输入模型的英文 Prompt，以及仅用于展示的中文译文。当前模型没有读取中文 Prompt。

结果好坏差别很大：蓝色釉面陶瓷和红砖相对接近，另外多项在颜色、材质身份、路由或物理通道上明显失败。这里没有为了展示效果把失败藏起来。
