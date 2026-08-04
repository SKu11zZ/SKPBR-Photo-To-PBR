# SKPBR v0.5 Model Card

[简体中文](#简体中文) | [English](#english)

## 简体中文

### 模型概览

SKPBR v0.5 是一个 4,586,975 参数的平面 PBR 研究模型，支持两种模式：

- 对齐的 RGB 图片 + Prompt → 重建图片中可见的平面材质局部；
- Prompt + 固定整数 Seed → 生成一套可复现的材质候选。

两种模式都输出 BaseColor、Roughness、Metallic、OpenGL +Y Normal、Height 和 AO。正式评估分辨率为 512 × 512。图片模式属于研究预览，纯文字模式仍是实验功能。

v0.5 使用冻结的 D57 检查点，选择 epoch 4。网络结构与 v0.4 相同，变化来自固定数据上的权重优化，而不是增加参数。

### 输入与输出

- 可选的对齐平面 RGB 材质图片；
- 中文或英文材质描述；
- 纯文字模式使用的整数 Seed；
- 六张方形 PBR 贴图。

Prompt 编码由 93 维条件向量和独立的 55 维结构化属性向量组成，描述材质类别、物理类型、主色与辅色、置信度、Roughness、Metallic、起伏、表面效果及明暗修饰。图片路径保留全分辨率 RGB 信息；纯文字路径从 12 通道确定性、各向同性、多尺度滤波噪声开始。

### 结构与参数

| 组成部分 | 参数量 |
|---|---:|
| 冻结的环形填充重建核心 | 3,409,232 |
| Prompt、纹理、起伏、物理属性、空间、光度和解耦适配器 | 1,177,743 |
| 总计 | 4,586,975 |

D57 训练时只开放了其中 786,274 个适配器参数；发布后的推理模型全部冻结。网络包含全分辨率 BaseColor 光度修正、保守的颜色/几何分离、结构化 Prompt 校准、表面起伏限制、物理属性校准与空间残差模块。

### D55–D57 固定数据训练

本轮没有增加材质库、外部训练素材或监督目标文件。训练数据合同保持为 604 个训练样本和 67 个验证样本。

| 检查点 | BaseColor MAE | BaseColor 均值 MAE | Normal 误差 | 重渲染 MAE | 颜色→几何泄漏 |
|---|---:|---:|---:|---:|---:|
| v0.4 / D54 父模型 | 0.058779 | 0.050700 | 13.325° | 0.042615 | 0.061577 |
| D55 | 0.056220 | 0.047876 | 13.324° | 0.042378 | 0.061517 |
| D56 | 0.056220 | 0.047876 | 13.324° | 0.042378 | 0.061517 |
| v0.5 / D57 | 0.055771 | 0.047491 | 13.288° | 0.040768 | 0.061982 |

- **D55** 专项训练 BaseColor 光度模块，加入在线曝光、白平衡、传感器串扰、暗电平、渐变光照及只改变 BaseColor 的反事实扰动。
- **D56** 尝试父模型锚定的几何修复。训练 epoch 没有改善验证目标，因此选择器保留 epoch 0，没有发布退化权重。
- **D57** 联合调整纹理、空间、BaseColor 与几何适配器，训练批次比例为 65% 图片 + Prompt、15% 只输入图片、20% 纯文字。

D57 改善了开发集颜色、Normal、重渲染与部分高频指标，但颜色到几何泄漏轻微变差；不能把开发集进步解释为跨分布问题已解决。

### 冻结 Blind-H6 评估

Blind-H6 的六种程序化目标是在 D57 权重冻结之后才生成的。图片模式只获得一张渲染 RGB 图和 Prompt；纯文字模式只获得 Prompt 和固定 Seed。目标贴图不提供给推理，训练与检查点选择对 H6 像素的读取次数为 0，也没有源贴图查询或复制。

| Blind-H6 检查项 | 结果 | 验收阈值 | 状态 |
|---|---:|---:|---|
| 图片 BaseColor MAE | 0.094459 | ≤ 0.090 | 未通过 |
| 图片 BaseColor 均值 MAE | 0.084404 | ≤ 0.075 | 未通过 |
| 图片 Roughness MAE | 0.085367 | ≤ 0.120 | 通过 |
| 图片 Metallic MAE | 0.035444 | ≤ 0.140 | 通过 |
| 图片 Normal 角度误差 | 12.090° | ≤ 22.0° | 通过 |
| 图片微法线对数 MAE | 0.499788 | ≤ 0.750 | 通过 |
| 图片重渲染 MAE | 0.046990 | ≤ 0.080 | 通过 |
| 颜色到几何泄漏 | 0.074515 | ≤ 0.075 | 通过，接近阈值 |
| 纯文字平均颜色 MAE | 0.134103 | ≤ 0.200 | 通过 |
| 纯文字 Roughness 均值 MAE | 0.088250 | ≤ 0.180 | 通过 |
| 纯文字 Metallic 均值 MAE | 0.031752 | ≤ 0.180 | 通过 |
| 纯文字频谱幅度 MAE | 0.067781 | ≤ 0.160 | 通过 |
| 纯文字自相关 MAE | 0.241775 | ≤ 0.200 | 未通过 |
| 纯文字条纹峰值 MAE | 0.284714 | ≤ 0.240 | 未通过 |
| 纯文字起伏对数 MAE | 0.305519 | ≤ 0.900 | 通过 |
| 纯文字起伏过冲率 | 16.67% | ≤ 25% | 通过 |
| 平铺接缝 MAE | 0.007477 | ≤ 0.020 | 通过 |
| 通过全部身份检查的材质 | 2 / 6 | ≥ 4 / 6 | 未通过 |
| 灾难性物理类型错误 | 0 | ≤ 0 | 通过 |

汇总为 **14 / 19 个阈值通过**，整体未通过。主要失败仍是图片 BaseColor 泛化、纯文字空间结构，以及逐材质身份一致性。Blind-H6 已用于诊断，之后不能用于继续训练、调参或选择检查点。

### 适用范围

- 平面对齐材质的单图重建研究；
- 从受控扫描、裁剪图或渲染中生成供美术复核的候选贴图；
- 用 Prompt 控制材质类别、颜色、表面效果和起伏；
- 用整数 Seed 复现纯文字候选。

### 已知限制

- 跨出开发分布后，BaseColor 的亮度、饱和度和色相仍可能偏移；
- 颜色边缘仍可能泄漏到 Normal 和 Height；
- 细裂纹、纹脉、分层、缺口、编织和砖块布局不能稳定恢复；
- 纯文字结果常退化为通用随机纹理；
- 任意手持照片、不可见 UV 恢复、绝对反射率、透明、SSS、毛发、皮肤、液体和体积材质不在已验证范围内。

### 训练数据说明

训练数据不随仓库发布。仓库不包含私有源贴图、商业材质资产、训练图片、目标贴图、缓存张量、优化器状态、样本身份或数据划分清单。检查点通过 PyTorch 的 `weights_only=True` 路径加载，只包含模型状态和精简的发布元数据；它不是训练集副本。原则上仍不能完全排除记忆或成员推断风险。

### 资源占用

估算整卡显存峰值：D55 为 5.479 GiB，D56 为 4.434 GiB，D57 为 4.188 GiB，均低于 8 GiB 训练限制。这些是开发机记录，不是所有驱动、PyTorch 版本和分辨率下的保证值。

### 发布状态

**图片 + Prompt：研究预览。纯 Prompt：实验功能。Blind-H6 总体验收未通过。**

## English

### Model summary

SKPBR v0.5 is a 4,586,975-parameter planar PBR research model with two modes:

- aligned RGB image + Prompt → reconstruction of the visible planar material patch;
- Prompt + deterministic integer seed → a repeatable material candidate.

Both modes write BaseColor, Roughness, Metallic, OpenGL +Y Normal, Height, and AO. The evaluated release resolution is 512 × 512. Image mode is a research preview; text-only mode remains experimental.

v0.5 uses the frozen D57 checkpoint selected at epoch 4. Its architecture is unchanged from v0.4; this release changes fixed-data weights, not parameter count.

### Inputs and outputs

- Optional aligned planar RGB material image.
- English or Chinese material description.
- Integer seed for text-only generation.
- Six square PBR maps.

Prompt encoding uses a 93-dimensional condition vector plus a separate 55-dimensional structured-attribute vector. They cover material class, physical regime, primary and secondary color, confidence, Roughness, Metallic, relief, finish, effects, and light/dark modifiers. The image path retains full-resolution RGB evidence. The text path starts from twelve channels of deterministic isotropic multiscale filtered noise.

### Architecture and parameters

| Component | Parameters |
|---|---:|
| Frozen circular-padding reconstruction core | 3,409,232 |
| Prompt, texture, relief, property, spatial, photometric, and disentanglement adapters | 1,177,743 |
| Total | 4,586,975 |

D57 opened 786,274 adapter parameters during training; every parameter is frozen for released inference. The network includes full-resolution photometric BaseColor recovery, conservative color/geometry separation, structured Prompt calibration, relief limiting, property calibration, and spatial residual modules.

### D55–D57 fixed-data training

No material libraries, external training assets, or supervised target files were added. The data contract remained fixed at 604 training rows and 67 validation rows.

| Checkpoint | BaseColor MAE | BaseColor mean MAE | Normal error | Rerender MAE | Color→geometry leakage |
|---|---:|---:|---:|---:|---:|
| v0.4 / D54 parent | 0.058779 | 0.050700 | 13.325° | 0.042615 | 0.061577 |
| D55 | 0.056220 | 0.047876 | 13.324° | 0.042378 | 0.061517 |
| D56 | 0.056220 | 0.047876 | 13.324° | 0.042378 | 0.061517 |
| v0.5 / D57 | 0.055771 | 0.047491 | 13.288° | 0.040768 | 0.061982 |

- **D55** specialized the photometric BaseColor path with online exposure, white-balance, sensor-cross-talk, black-level, smooth-lighting, and BaseColor-only counterfactual perturbations.
- **D56** attempted parent-anchored geometry remediation. Trained epochs did not improve validation, so checkpoint selection retained epoch 0 instead of publishing a regression.
- **D57** jointly tuned texture, spatial, BaseColor, and geometry adapters with 65% image + Prompt, 15% image-only, and 20% text-only batches.

D57 improves development color, Normal, rerendering, and selected high-frequency measures. Color-to-geometry leakage moves slightly backward, so development progress must not be read as a solved out-of-distribution problem.

### Frozen Blind-H6 evaluation

The six procedural H6 targets were generated only after D57 was frozen. Image mode received one rendered RGB image plus Prompt. Text mode received Prompt plus fixed seed. Target maps were unavailable to inference, training and checkpoint selection read zero H6 pixels, and no source-map lookup or copy occurred.

| Blind-H6 check | Result | Threshold | Status |
|---|---:|---:|---|
| Image BaseColor MAE | 0.094459 | ≤ 0.090 | Not passed |
| Image BaseColor mean MAE | 0.084404 | ≤ 0.075 | Not passed |
| Image Roughness MAE | 0.085367 | ≤ 0.120 | Passed |
| Image Metallic MAE | 0.035444 | ≤ 0.140 | Passed |
| Image Normal angular error | 12.090° | ≤ 22.0° | Passed |
| Image micro-normal log MAE | 0.499788 | ≤ 0.750 | Passed |
| Image rerender MAE | 0.046990 | ≤ 0.080 | Passed |
| Color-to-geometry leakage | 0.074515 | ≤ 0.075 | Passed, close to threshold |
| Text mean-color MAE | 0.134103 | ≤ 0.200 | Passed |
| Text Roughness mean MAE | 0.088250 | ≤ 0.180 | Passed |
| Text Metallic mean MAE | 0.031752 | ≤ 0.180 | Passed |
| Text spectrum-amplitude MAE | 0.067781 | ≤ 0.160 | Passed |
| Text autocorrelation MAE | 0.241775 | ≤ 0.200 | Not passed |
| Text stripe-peak MAE | 0.284714 | ≤ 0.240 | Not passed |
| Text relief log MAE | 0.305519 | ≤ 0.900 | Passed |
| Text relief overshoot rate | 16.67% | ≤ 25% | Passed |
| Tile-seam MAE | 0.007477 | ≤ 0.020 | Passed |
| Materials passing every identity check | 2 / 6 | ≥ 4 / 6 | Not passed |
| Catastrophic physical-regime failures | 0 | ≤ 0 | Passed |

The aggregate result is **14 / 19 thresholds passed**, so overall acceptance was not met. The main failures are image BaseColor generalization, text-only spatial structure, and per-material identity consistency. Blind-H6 has now been used for diagnosis and must not be used for further training, tuning, or checkpoint selection.

### Intended use

- Research on single-image planar material reconstruction.
- Artist-reviewed candidate extraction from controlled scans, crops, or renders.
- Prompt control over material family, color, finish, and relief.
- Reproducible text-only material ideation using an integer seed.

### Known limits

- BaseColor brightness, saturation, and hue can shift outside the development distribution.
- Color-only edges can still leak into Normal and Height.
- Fine cracks, veins, layers, chips, weave, and brick layouts are not reliably recovered.
- Text-only structure often collapses to generic stochastic texture.
- Arbitrary handheld photos, hidden UV recovery, absolute reflectance, transparency, SSS, hair, skin, liquids, and volumes remain outside the established boundary.

### Training-data disclosure

Training data is not distributed. The repository contains no private source textures, commercial material assets, training images, target maps, cache tensors, optimizer states, sample identities, or split manifests. The checkpoint loads through PyTorch's `weights_only=True` path and contains only model state plus compact release metadata; it is not a copy of the training set. Memorization and membership inference cannot be ruled out in principle.

### Resource envelope

Estimated whole-device training peaks were 5.479 GiB for D55, 4.434 GiB for D56, and 4.188 GiB for D57, all below the 8 GiB cap. These are development-machine measurements, not guarantees for every driver, PyTorch build, or resolution.

### Release status

**Image + Prompt: research preview. Prompt only: experimental. Blind-H6 overall acceptance was not met.**
