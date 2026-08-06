# SKPBR v0.6 Model Card

[中文](#简体中文) · [English](#english) · [返回 README](../README.md)

## 简体中文

### 模型概览

SKPBR v0.6 / D72 是一个 **5,652,218 参数**的平面 PBR 材质研究模型。

- **图片 + Prompt**：从一张接近平面的 RGB 材质参考图重建六张 512px PBR 贴图。这是当前主路径。
- **Prompt + Seed**：生成确定性、可复现的材质候选。v0.6 仍沿用 D57 分支，属于实验功能。

输出顺序固定为 BaseColor、Roughness、Metallic、OpenGL +Y Normal、Height 和 AO。模型不恢复不可见 UV，也不支持透明、SSS、皮肤、毛发、液体或体积材质。

### 结构

| 组成 | 参数量 | 作用 |
|---|---:|---|
| D57 基础网络 | 4,586,975 | 双分辨率图像编码、Prompt 条件和六通道基础预测；保留纯文字路径 |
| D69 intrinsic 分解 | 65,635 | 预测无光照 BaseColor、RGB 光照、高光、颜色边缘、几何边缘与门控残差 |
| D70–D71 物理分支 | 984,278 | 共享多尺度特征下恢复 Roughness、Metallic、Normal、Height，并由 Height/Normal 派生 AO |
| D72 安全门 | 15,330 | 对 BaseColor 和 AO 做全局置信度融合，不改写 Roughness、Metallic、Normal、Height |
| **总计** | **5,652,218** | 发布推理时全部冻结 |

这次的关键不是“再加一个纹理 Adapter”，而是先拆开材质反射率、光照、高光和几何证据。高分辨率 RGB 仍用于保留细节，但必须通过颜色/几何/高光门控，不能无条件抄进 BaseColor 与 Height。AO 也不再完全从输入暗部独立猜测，而是以 Height 和 Normal 的派生结果为主。

### D69–D72 冻结验证

下面是 128 项、双域、固定验证集上的 D72 宏平均；该验证集参与模型选择，因此只能作为开发指标。

| 指标 | D72 |
|---|---:|
| BaseColor 线性 MAE | 0.065240 |
| 跨光照 BaseColor MAE | 0.054892 |
| Roughness MAE | 0.067777 |
| Roughness 梯度 MAE | 0.019596 |
| Metallic MAE | 0.039923 |
| Metallic F1 | 0.900338 |
| Normal 角度误差 | 10.106° |
| Normal 梯度 MAE | 0.116721 |
| Height 梯度 MAE | 0.020136 |
| Height Laplacian MAE | 0.004293 |
| AO MAE | 0.166373 |
| 重渲染线性 MAE | 0.060059 |

D72 相对 D71 把 AO MAE 从 0.188138 降到 0.166373，改善约 **11.6%**；重渲染 MAE 回退约 **0.88%**。D72 的 Roughness、Metallic、Normal 和 Height 与 D71 位级一致。BaseColor 保留 D69 的开发集成绩，同时通过 D57 锚点降低高风险样本的整体偏移。

### MatSynth Blind-6：冻结后诊断

六个测试材质在 D72 冻结后才按元数据选定，选题时没有读取像素。它们覆盖沥青、皮革、花岗岩、金属箔、草缝铺路石和涂漆木材。每题统一在 Blender 中渲染，推理只获得一张 512px RGB 图和一条 Prompt；目标 PBR 贴图只用于评分。

| 指标 | 六题宏平均 |
|---|---:|
| BaseColor 线性 MAE | 0.191157 |
| Roughness MAE | 0.239864 |
| Roughness 梯度 MAE | 0.069260 |
| Metallic MAE | 0.007646 |
| Normal 角度误差 | 12.825° |
| Normal 梯度 MAE | 0.280886 |
| Height 梯度 MAE | 0.018202 |
| AO MAE | 0.151794 |
| 重渲染线性 MAE | 0.132930 |

这组诊断没有通过生产级验收。花岗岩和涂漆木材的几何较稳，金属/非金属判断也稳定；金属箔在 BaseColor、Roughness、AO 上明显失败，草缝铺路石的结构和 Roughness 也较差。结果与逐项来源见 [MatSynth Blind-6](../examples/matsynth-blind6/README.md)。这六题已经被看过，之后不能再用于训练、调参或选择检查点。

### 适用范围

适合：

- 对齐、接近平面的材质局部；
- 一张图片加中英文材质描述；
- 常见非 SSS 金属、涂层、石材、混凝土、砖石、陶瓷、塑料、复合材料、木材、皮革与织物；
- 给美术提供可继续编辑的六贴图候选。

不承诺：

- 任意手机照片中的未知透视、遮挡、极端曝光与混合光源；
- 绝对物理反射率测量或唯一正确的逆渲染解；
- 高反射金属箔、复杂铺装结构、细密裂纹和高信息密度花纹的稳定重建；
- 纯文字生成准确的空间布局；
- 透明、SSS、皮肤、毛发、液体和体积材质。

### 数据与发布

公开仓库不包含训练图、目标贴图、MatSynth 原始 PBR 文件、商业材质、缓存、优化器状态、样本身份或数据划分。发布检查点通过 `torch.load(..., weights_only=True)` 加载，只含模型张量和有限的发布元数据。模型权重不能直接还原训练集，但不能从理论上排除记忆或成员推断风险。

公开的 MatSynth 展示只使用元数据标为 CC0 的条目；第三方说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。

### 资源与状态

- 权重大小：约 22.9MB。
- 本机 RTX 3060：冷启动约 9.09 秒；模型加载后的单材质推理约 0.60 秒；峰值 reserved 显存约 1.094 GiB。
- 训练显存约束：常态不超过 8GB，允许不常态的 10% 瞬时容差。
- 发布状态：**图片 + Prompt 为研究预览；纯 Prompt 为实验功能；尚未达到生产级材质扫描器标准。**

## English

### Model summary

SKPBR v0.6 / D72 is a **5,652,218-parameter** research model for planar PBR materials.

- **Image + prompt** reconstructs six 512px PBR maps from one approximately planar RGB reference. This is the primary path.
- **Prompt + seed** produces a deterministic material candidate. v0.6 retains the D57 branch and treats this mode as experimental.

The fixed outputs are BaseColor, Roughness, Metallic, OpenGL +Y Normal, Height, and AO. The model does not recover unseen UV regions and does not support transparency, SSS, skin, hair, liquids, or volumes.

### Architecture

| Component | Parameters | Role |
|---|---:|---|
| D57 base network | 4,586,975 | dual-resolution image encoding, prompt conditioning, baseline six-map prediction, and the text-only path |
| D69 intrinsic decomposition | 65,635 | de-lit BaseColor, RGB illumination, specular/color/geometry masks, and gated residual prediction |
| D70–D71 physical branch | 984,278 | shared multiscale Roughness, Metallic, Normal, and Height recovery; AO derived from Height and Normal |
| D72 safety gate | 15,330 | global confidence blends for BaseColor and AO; leaves Roughness, Metallic, Normal, and Height unchanged |
| **Total** | **5,652,218** | all parameters frozen for release inference |

The main change is an explicit appearance decomposition rather than another spatial texture adapter. High-resolution RGB still preserves detail, but it must pass specular and color/geometry gates before affecting BaseColor. AO is primarily derived from reconstructed Height and Normal instead of being guessed independently from dark input pixels.

### Frozen D69–D72 validation

The following are D72 macro results on a frozen 128-row dual-domain validation set. This set was used for model selection, so these are development metrics.

| Metric | D72 |
|---|---:|
| Linear BaseColor MAE | 0.065240 |
| Cross-light BaseColor MAE | 0.054892 |
| Roughness MAE | 0.067777 |
| Roughness gradient MAE | 0.019596 |
| Metallic MAE | 0.039923 |
| Metallic F1 | 0.900338 |
| Normal angular error | 10.106° |
| Normal gradient MAE | 0.116721 |
| Height gradient MAE | 0.020136 |
| Height Laplacian MAE | 0.004293 |
| AO MAE | 0.166373 |
| Linear rerender MAE | 0.060059 |

D72 reduces AO MAE from 0.188138 at D71 to 0.166373, an improvement of about **11.6%**, while rerender MAE moves backward by about **0.88%**. Roughness, Metallic, Normal, and Height are bitwise identical to D71. BaseColor retains the D69 development score while a D57 anchor limits large global failures.

### Post-freeze MatSynth Blind-6

Six materials were locked from metadata only after D72 was frozen, before their pixels were inspected. They cover asphalt, leather, granite, foil, paving stones with grass, and painted wood. Each was rendered under a common Blender setup. Inference received one 512px RGB image and one prompt; target maps were used only for scoring.

| Metric | Six-case macro |
|---|---:|
| Linear BaseColor MAE | 0.191157 |
| Roughness MAE | 0.239864 |
| Roughness gradient MAE | 0.069260 |
| Metallic MAE | 0.007646 |
| Normal angular error | 12.825° |
| Normal gradient MAE | 0.280886 |
| Height gradient MAE | 0.018202 |
| AO MAE | 0.151794 |
| Linear rerender MAE | 0.132930 |

This diagnostic does not meet a production acceptance bar. Granite and painted wood retain geometry comparatively well, and metal/non-metal classification is stable. Foil fails badly in BaseColor, Roughness, and AO; paving stones also lose structure and roughness. See [MatSynth Blind-6](../examples/matsynth-blind6/README.md) for every output and source. These six cases are now diagnostic-only and cannot be used for further training, tuning, or checkpoint selection.

### Intended use and limits

Suitable uses include aligned planar crops, one image plus a Chinese or English material description, common non-SSS material families, and artist-reviewed editable map candidates.

The release does not claim arbitrary handheld-photo recovery, absolute reflectance measurement, a unique inverse-rendering solution, reliable high-density foil or paving reconstruction, accurate text-only spatial layouts, unseen UV recovery, or support for transparent, SSS, skin, hair, liquid, and volumetric materials.

### Data and release disclosure

The public repository contains no training images, target maps, original MatSynth PBR files, commercial materials, caches, optimizer state, sample identities, or data splits. The checkpoint loads through `torch.load(..., weights_only=True)` and contains model tensors plus bounded release metadata. The weights do not directly expose the training set, although memorization and membership inference cannot be ruled out in principle.

Public MatSynth displays use entries whose metadata reports CC0. See [THIRD_PARTY.md](THIRD_PARTY.md) for provenance.

### Resource envelope and status

- Checkpoint size: about 22.9MB.
- Local RTX 3060: about 9.09 seconds for the first cold request, 0.60 seconds for warm single-material inference, and 1.094 GiB peak reserved VRAM.
- Training constraint: 8GB steady-state cap with up to 10% non-persistent transient tolerance.
- Release status: **image + prompt is a research preview; prompt-only is experimental; this is not yet a production material scanner.**
