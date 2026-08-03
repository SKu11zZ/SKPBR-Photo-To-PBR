# SKPBR v0.4 Model Card

[English](#english) | [简体中文](#简体中文)

## English

### Model summary

SKPBR v0.4 is a 4,586,975-parameter planar PBR model with two runtime modes:

- aligned RGB image + Prompt → reconstruction of the visible flat material patch;
- Prompt + deterministic seed → a plausible material candidate.

Both modes write BaseColor, Roughness, Metallic, OpenGL +Y Normal, Height, and AO. Image + Prompt remains a research preview; text-only generation remains experimental. Only 2 of the 12 frozen Blind-G materials met all consistency checks, so this release is not a production-ready material scanner.

### Inputs and outputs

- Optional aligned planar RGB material image, evaluated at 512 × 512.
- English or Chinese material description.
- Integer seed for text-only generation.
- Six square PBR maps at the requested resolution.

The network receives a 93-dimensional condition vector and a separate 55-dimensional structured Prompt vector. The structured vector covers material class, physical regime, primary and secondary colors, confidence, Roughness, Metallic, relief, finish, effects, and light/dark modifiers.

### Architecture

| Component | Parameters |
|---|---:|
| Frozen circular-padding reconstruction core | 3,409,232 |
| Prompt, texture, relief, property, spatial, photometric, and disentanglement adapters | 1,177,743 |
| Total | 4,586,975 |

The image path keeps a full-resolution RGB carrier. The text path starts from twelve channels of deterministic, isotropic, multiscale filtered noise. v0.4 adds two image-side components above the v0.3 parent:

- a full-resolution photometric BaseColor refiner using local image evidence, low-frequency color, and Prompt context;
- a conservative color/geometry separator that looks for reflectance-only edges before changing Normal or Height.

The original 3.41M-parameter reconstruction core remains frozen.

### D52–D54 development result

| Stage | Main change | Frozen development result |
|---|---|---|
| D52 | photometric BaseColor refiner | BaseColor MAE 0.06855 → 0.05920 |
| D53 | color/geometry disentangler | leakage 0.06985 → 0.06614; Normal 14.23° → 13.55° |
| D54 | three-mode joint adapter tuning | objective 0.70650 → 0.69374 |

At the selected D54 checkpoint, development BaseColor MAE is 0.05878 and color-to-geometry leakage is 0.06158. The training mix was 60% image + Prompt, 15% image-only, and 25% text-only. D10 test, Fresh12, Blind-C/D, Blind-E/F pixels, and Blind-G pixels were not read during these stages.

### Frozen Blind-G evaluation

Blind-G contains twelve procedural targets first generated after the v0.4 weights were frozen. Image mode receives one rendered RGB image and its Prompt. Text mode receives only the Prompt and deterministic seed. Target PBR maps are never supplied to inference.

| Blind-G check | Result | Acceptance threshold |
|---|---:|---|
| Materials meeting all consistency checks | 2 / 12 | Does not meet threshold; at least 9 required |
| Acceptance thresholds met | 12 / 20 | Overall result does not meet threshold |
| Image BaseColor MAE | 0.112868 | Does not meet threshold ≤ 0.065 |
| Image BaseColor mean MAE | 0.111026 | Does not meet threshold ≤ 0.050 |
| Image Roughness MAE | 0.074689 | Meets threshold |
| Image Metallic MAE | 0.023755 | Meets threshold |
| Image Normal angular error | 10.054° | Meets threshold |
| Image micro-normal log MAE | 0.623825 | Does not meet threshold ≤ 0.550 |
| Image rerender MAE | 0.068899 | Does not meet threshold ≤ 0.060 |
| Color-to-geometry leakage | 0.068370 | Does not meet threshold ≤ 0.030 |
| Text mean-color MAE | 0.156367 | Meets threshold |
| Text Roughness mean MAE | 0.078915 | Meets threshold |
| Text Metallic mean MAE | 0.020429 | Meets threshold |
| Text spectrum-amplitude MAE | 0.073241 | Meets threshold |
| Text autocorrelation MAE | 0.219831 | Does not meet threshold ≤ 0.205 |
| Text stripe-peak MAE | 0.285967 | Does not meet threshold ≤ 0.130 |
| Text relief log MAE | 0.251228 | Meets threshold |
| Text relief overshoot rate | 20.83% | Meets threshold |
| Catastrophic physical-regime failures | 0 | Meets threshold |

Bead-blasted aluminum and black-aggregate concrete met every per-material consistency check. Copper patina is close in image mode but does not preserve text-only structure. ABS, limestone, basalt, marble, and terracotta show the largest image-side color and low-frequency material-characteristic errors. Blind-G has now been used for diagnosis and must not be reused for further training, hyperparameter tuning, or checkpoint selection.

### Intended use

- Research on flat single-image material reconstruction.
- Artist-reviewed candidate extraction from aligned scans, crops, or controlled renders.
- Prompt-guided material family, color, finish, and relief control.
- Reproducible text-only material ideation using an integer seed.

### Known limits

- BaseColor can shift in brightness, saturation, and hue outside the development distribution.
- Color-only edges can still leak into Normal and Height.
- Fine cracks, veins, layers, chips, weave, and other high-information structures are not reliably reconstructed.
- Text-only structure often collapses to generic stochastic texture.
- Arbitrary handheld photos, hidden UV recovery, absolute reflectance measurement, transparency, SSS, hair, skin, liquids, and volumes are outside the established boundary.

### Training-data disclosure

Training data is not distributed. The repository contains no private source textures, commercial material assets, training images, target maps, cache tensors, optimizer states, sample identities, or split manifests. The checkpoint is loaded through PyTorch's restricted `weights_only=True` path and contains model state plus compact release metadata; it is not a browsable copy of the training set. Memorization and membership inference cannot be ruled out in principle.

### Resource envelope

The conservative whole-device peak estimate during D52–D54 was 4.280 GiB under an 8 GiB limit. This is a development-machine measurement, not a guaranteed inference requirement for every resolution, driver, or PyTorch build.

### Release status

**Image + Prompt: research preview. Prompt only: experimental. The Blind-G release threshold was not met.**

## 简体中文

### 模型概览

SKPBR v0.4 是一个拥有 4,586,975 个参数的平面 PBR 模型，支持两种运行模式：

- 对齐的 RGB 图片 + 提示词（Prompt）→ 重建图片中可见的平面材质局部；
- 提示词 + 固定随机种子 → 生成一套可复现的材质候选。

两种模式都会输出 BaseColor、Roughness、Metallic、OpenGL +Y Normal、Height 和 AO。图片 + 提示词模式属于研究预览，纯文字生成仍是实验功能。冻结后的 Blind-G 测试中，12 种材质只有 2 种通过了全部一致性检查，因此这一版还不能当作生产级材质扫描器。

### 输入与输出

- 可选的对齐平面 RGB 材质图片，正式评估分辨率为 512 × 512；
- 中文或英文材质描述；
- 纯文字生成使用的整数随机种子；
- 按指定分辨率输出六张方形 PBR 贴图。

网络接收一个 93 维条件向量，以及一个独立的 55 维结构化提示词向量。结构化向量描述材质类别、物理类型、主色与辅色、置信度、Roughness、Metallic、表面起伏、表面效果和明暗修饰词。

### 模型结构

| 组成部分 | 参数量 |
|---|---:|
| 冻结的环形填充重建核心 | 3,409,232 |
| 提示词、纹理、起伏、物理属性、空间、光度和解耦适配器 | 1,177,743 |
| 总计 | 4,586,975 |

图片路径会保留全分辨率 RGB 信息。纯文字路径从 12 通道确定性、各向同性、多尺度滤波噪声开始。与 v0.3 相比，v0.4 新增了两个图片侧模块：

- 全分辨率 BaseColor 光度修正模块，结合局部图像信息、低频颜色和提示词上下文；
- 保守的颜色/几何分离模块，先判断边缘是否只来自反射率变化，再决定是否修改 Normal 或 Height。

原有的 341 万参数重建核心保持冻结。

### D52–D54 开发集结果

| 阶段 | 主要改动 | 冻结开发集结果 |
|---|---|---|
| D52 | BaseColor 光度修正模块 | BaseColor MAE 0.06855 → 0.05920 |
| D53 | 颜色/几何分离模块 | 泄漏 0.06985 → 0.06614；Normal 14.23° → 13.55° |
| D54 | 三种模式联合调整适配器 | 目标函数 0.70650 → 0.69374 |

最终选择的 D54 检查点在开发集上的 BaseColor MAE 为 0.05878，颜色到几何泄漏为 0.06158。训练批次由 60% 图片 + 提示词、15% 只输入图片和 25% 只输入文字组成。这些阶段没有读取 D10 测试集、Fresh12、Blind-C/D、Blind-E/F 或 Blind-G 的像素。

### 冻结 Blind-G 评估

Blind-G 包含 12 个程序化目标，它们是在 v0.4 权重冻结后才首次生成的。图片模式只接收一张渲染 RGB 图片和对应提示词；纯文字模式只接收提示词和固定随机种子。推理阶段不会向模型提供目标 PBR 贴图。

| Blind-G 检查项 | 结果 | 验收阈值结果 |
|---|---:|---|
| 通过全部一致性检查的材质 | 2 / 12 | 未通过；验收要求至少 9 种 |
| 已达到的验收阈值 | 12 / 20 | 总体未通过 |
| 图片 BaseColor MAE | 0.112868 | 未通过；阈值 ≤ 0.065 |
| 图片 BaseColor 均值 MAE | 0.111026 | 未通过；阈值 ≤ 0.050 |
| 图片 Roughness MAE | 0.074689 | 通过 |
| 图片 Metallic MAE | 0.023755 | 通过 |
| 图片 Normal 角度误差 | 10.054° | 通过 |
| 图片微法线对数 MAE | 0.623825 | 未通过；阈值 ≤ 0.550 |
| 图片重渲染 MAE | 0.068899 | 未通过；阈值 ≤ 0.060 |
| 颜色到几何泄漏 | 0.068370 | 未通过；阈值 ≤ 0.030 |
| 纯文字平均颜色 MAE | 0.156367 | 通过 |
| 纯文字 Roughness 均值 MAE | 0.078915 | 通过 |
| 纯文字 Metallic 均值 MAE | 0.020429 | 通过 |
| 纯文字频谱幅度 MAE | 0.073241 | 通过 |
| 纯文字自相关 MAE | 0.219831 | 未通过；阈值 ≤ 0.205 |
| 纯文字条纹峰值 MAE | 0.285967 | 未通过；阈值 ≤ 0.130 |
| 纯文字表面起伏对数 MAE | 0.251228 | 通过 |
| 纯文字表面起伏过冲率 | 20.83% | 通过 |
| 灾难性物理类型错误 | 0 | 通过 |

喷砂铝和黑骨料混凝土通过了全部逐材质一致性检查。铜锈在图片模式下比较接近输入，但纯文字模式没有保住纹理结构。ABS、石灰岩、玄武岩、大理石和赤陶的图片重建存在最明显的颜色与低频材质特征误差。Blind-G 已经用于本轮诊断，之后不能再用于训练、调整超参数或选择检查点。

### 适用范围

- 研究平面材质的单图重建；
- 从对齐扫描、材质裁剪图或受控渲染中提取供美术人员复核的候选材质；
- 使用提示词控制材质类别、颜色、表面效果和起伏；
- 使用整数随机种子复现纯文字材质候选。

### 已知限制

- 遇到开发集分布之外的输入时，BaseColor 的亮度、饱和度和色相可能偏移；
- 只存在于颜色中的边缘仍可能泄漏到 Normal 和 Height；
- 细裂纹、纹脉、分层、缺口、编织等高信息密度结构还不能稳定重建；
- 纯文字生成的结构经常退化成通用随机纹理；
- 任意手持照片、不可见 UV 恢复、绝对反射率测量、透明、SSS、毛发、皮肤、液体和体积材质不在当前已验证范围内。

### 训练数据说明

训练数据不随仓库发布。仓库不包含私有源贴图、商业材质资产、训练图片、目标贴图、张量缓存、优化器状态、样本标识或数据划分清单。检查点通过 PyTorch 的受限 `weights_only=True` 模式加载，只包含模型状态和精简的发布元数据，不是可浏览的训练集副本。原则上仍不能完全排除记忆或成员推断风险。

### 资源占用

D52–D54 阶段估算的整卡显存峰值为 4.280 GiB，低于 8 GiB 限制。这是开发机上的测量结果，不代表所有分辨率、驱动版本或 PyTorch 版本都具有相同的推理显存需求。

### 发布状态

**图片 + 提示词：研究预览。纯提示词：实验功能。Blind-G 发布验收阈值未达到。**
