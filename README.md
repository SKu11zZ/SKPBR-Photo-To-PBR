# SKPBR

[English](#english) · [简体中文](#简体中文)

## English

SKPBR started as a small material experiment for one of my own game projects. The part released here has **266,241 parameters**. Given a controlled Suzanne/Light-Stage render, an English material Prompt, and a parent PBR prediction, it corrects the BaseColor at up to 1024px and passes Roughness, Metallic, Normal, Height, and AO through unchanged.

One thing should be clear up front: this is not yet a “drop in any photo and get a finished PBR material” model. The public package is the final BaseColor calibration head, not the complete private RGB-to-PBR research stack. It still needs a parent PBR input and a known visible-UV confidence map.

### Where it works today

The current model is useful when the setup is controlled:

- one Suzanne render using the known camera, UV layout, and Light-Stage-style lighting;
- one short English Prompt such as `dark rough cast iron`;
- six parent PBR maps: BaseColor, Roughness, Metallic, Normal, Height, and AO;
- one visible-confidence map for the projected UV region.

It produces a corrected BaseColor. The other five maps are copied bit-for-bit, so the head cannot quietly change geometry detail or surface response behind your back. The result is tied to the known UV layout; it is not guaranteed to tile cleanly on another mesh.

### Twelve broader material types

This second run was meant to find the boundary, not to make the model look good. Blue glazed ceramic and red brick came out relatively close. Oxidized copper, cork, and denim caught only part of the material. Brushed aluminum, powder-coated steel, black ABS, granite, concrete, carbon fiber, and leather all had obvious identity or color failures.

So the 73 active material families in the research directory should not be read as 73 materials the model can already reconstruct reliably. Sand is still reference-only and is not included here.

![SKPBR 12-material bilingual coverage audit](examples/coverage-12/contact_sheet_long.png)

[Read the full report and per-channel numbers.](docs/COVERAGE_AUDIT_12.md) The full-resolution input, output render, and six maps for every case are under [examples/coverage-12](examples/coverage-12/README.md).

### Running the public head

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

### The numbers, without dressing them up

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

### Current boundary

The main unresolved problem is color: the final head is deliberately very stable under lighting changes, but that stability also makes it throw away some useful evidence from the input image. Fine, high-density patterns such as marble veins, patina, and irregular gravel structure are also weaker than they should be.

The model has not been validated for arbitrary phone photos, arbitrary geometry, unknown cameras, unknown UVs, SSS, transmission, opacity, hair, skin, fluids, or volumetric materials. If your use case depends on any of those, assume it is unsupported until it is tested.

### What is actually published

The repository contains the small inference package, a tensor-only checkpoint, tests, four focused examples, the 12-material coverage audit, and aggregate evaluation numbers. It does not contain training/evaluation images, private source PBR maps, commercial material assets, caches, optimizer states, local paths, sample identities, or nearest-neighbor catalogs.

The more formal material is kept out of the front page: [model card](docs/MODEL_CARD.md), [data policy](docs/DATA_POLICY.md), [release checklist](docs/RELEASE_CHECKLIST.md), and [documentation index](docs/README.md).

### License

Repository-authored code and the exported SKPBR weight file are released under the [MIT License](LICENSE). MIT does not grant redistribution rights for third-party source assets; none of those assets are included here.

<p align="right"><a href="#skpbr">Back to top</a></p>

---

## 简体中文

SKPBR 是我给自己的一个游戏项目做的材质实验。现在公开的这部分一共 **266,241 个参数**：输入一张受控的 Suzanne/Light-Stage 渲染图、一句英文材质 Prompt 和一套父 PBR，它负责把 BaseColor 校准到最高 1024px；Roughness、Metallic、Normal、Height 和 AO 则原样保留。

先把话说在前面：它还不是“随手扔一张照片进去，就能自动吐出完整 PBR”的模型。GitHub 里放出来的是最后的 BaseColor 校准头，不是私有研究管线的全部上游。当前公开版仍然需要父 PBR 和已知 UV 的可见置信度图。

### 它现在能干什么

在输入条件受控时，它可以完成下面这件事：

- 输入一张固定相机、固定 UV、Light-Stage 风格光照下的 Suzanne 渲染图；
- 再给一句类似 `dark rough cast iron` 的英文描述；
- 提供 BaseColor、Roughness、Metallic、Normal、Height、AO 六张父 PBR；
- 提供可见 UV 区域的置信度图；
- 输出一张校准后的 BaseColor，其余五张贴图逐文件不变。

这样做的好处是校准头不会顺手篡改表面细节；代价是它只能处理已知 UV 下的结果，不能保证贴到别的模型上仍然无缝。

### 12 类材质覆盖测试

这一轮不是为了挑最好看的结果，而是想看看边界到底在哪。蓝色釉面陶瓷和红砖相对接近；氧化铜、软木和牛仔布只抓到一部分；拉丝铝、粉末涂层钢、黑色 ABS、花岗岩、混凝土、碳纤维和皮革都有明显的材质身份或颜色失败。

所以研究目录里的 73 个活跃家族，不能理解成模型已经可靠支持 73 类材质。沙子目前仍然是 `reference_only`，这次没有把它硬算成会做。

![SKPBR 12 类材质中英双语覆盖测试](examples/coverage-12/contact_sheet_long.png)

[完整分析和逐通道数字在这里。](docs/COVERAGE_AUDIT_12_zh-CN.md) 每项 1024px 输入、输出渲染和六张贴图都放在 [examples/coverage-12](examples/coverage-12/README_zh-CN.md)。

### 怎么跑

```bash
python -m venv .venv
python -m pip install -e .
```

父 PBR 文件夹需要包含 `basecolor.png`、`roughness.png`、`metallic.png`、`normal.png`、`height.png` 和 `ao.png`。

```bash
skpbr \
  --image reference.png \
  --prompt "dark rough cast iron" \
  --parent-dir parent_pbr \
  --visible-confidence visible_confidence.png \
  --output outputs/cast_iron
```

CLI 默认不会覆盖已有输出目录。推理可以用 CPU，也可以通过 `--device cuda` 使用显卡。

### 成绩就直接说

一次性冻结外部盲测共有 81 个样本，来自 59 个与开发集不重叠的材质身份。SKPBR 相比未校准父输出把 BaseColor MAE 降低了约 **53.3%**，但仍然比更强的冻结 D36 颜色基线差 **22.9%**。11 个发布门槛里通过了 8 个，所以 v0.1 只能算研究预览版。

| 指标 | 结果 |
|---|---:|
| 未校准父输出 BaseColor MAE | 0.19143 |
| 冻结 D36 BaseColor MAE | 0.07272 |
| SKPBR BaseColor MAE | 0.08935 |
| 单项不退化率 | 92.59%——未通过 |
| 灾难性样本率 | 4.94%——未通过 |
| 屏幕替换一致性 MAE | 0.0——通过 |
| 父输出高频细节相关性 | 0.96742——通过 |
| 开发集/盲测身份重叠 | 0——通过 |

这次一次性评估结束后，没有为了让数字好看再改权重、阈值或已公布指标。

### 目前最大的短板

最明显的问题还是颜色。最终校准头为了抵抗光照变化做得比较保守，但保守过头以后，也会把输入图里本来有用的颜色证据一起丢掉。大理石细脉、铜锈和不规则砾石这类高信息密度纹理，目前也还原得不够好。

任意手机照片、任意模型、未知相机、未知 UV，以及 SSS、透明、毛发、皮肤、流体和体积材质，都不在当前已验证范围内。没有测过的能力，这里就不先吹成支持。

### 仓库里到底放了什么

仓库里有可独立运行的小型校准包、纯张量权重、测试、四组重点示例、12 类覆盖审计和聚合评估数据。训练/评估图片、私有原始 PBR、商业材质、缓存、优化器状态、本机路径、逐样本身份和近邻素材库都没有上传。

模型卡、数据政策、发布审计等偏学术和工程的内容统一放在 [文档目录](docs/README.md)，首页不再堆一排说明文件。

### License

仓库代码和导出的 SKPBR 权重使用 [MIT License](LICENSE)。MIT 不会自动授予第三方原始素材的再分发权；这类素材没有放进仓库。

<p align="right"><a href="#skpbr">返回顶部</a></p>
