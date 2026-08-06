# MatSynth 六材质冻结后盲测 / Post-freeze MatSynth Blind-6

[中文](#中文) · [English](#english) · [返回项目首页](../../README.md)

## 中文

这是 SKPBR v0.6 / D72 权重冻结后的诊断题，不是训练集成绩。六个材质先按 MatSynth 元数据锁定，覆盖沥青、皮革、花岗岩、金属箔、草缝铺路石和涂漆木材；选题阶段没有读取像素。随后统一导入 Blender 渲染，模型推理时只拿到一张 512px RGB 图和一条英文 Prompt。

目标 PBR 贴图只用于出分，既没有进入模型，也没有参与选权重。冻结后才看到的这六题今后也不会用于训练、调参或检查点选择。

[![六道盲测题](questions_2x3.png)](questions_2x3.png)

结果并不全好：花岗岩和涂漆木材的几何较稳，非金属判定也稳定；金属箔的 BaseColor、Roughness 与 AO 明显失败，草缝铺路石的结构和 Roughness 也没有还原好。六题宏平均为 BaseColor 线性 MAE 0.1912、Roughness MAE 0.2399、Metallic MAE 0.0076、Normal 角度误差 12.83°、AO MAE 0.1518、重渲染线性 MAE 0.1329。这组结果更适合说明下一轮训练该修什么，而不是拿来证明模型已经成熟。

- [结果 01–02：沥青、皮革](results_01_02.png)
- [结果 03–04：花岗岩、金属箔](results_03_04.png)
- [结果 05–06：草缝铺路石、涂漆木材](results_05_06.png)
- [机器可读指标与来源](benchmark.json)

## English

This is a post-freeze diagnostic for the SKPBR v0.6 / D72 checkpoint, not a training-set score. Six materials were locked from MatSynth metadata before any pixels were read, covering asphalt, leather, granite, foil, paving stones with grass, and painted wood. Each material was then rendered under a common Blender setup. Inference received only one 512px RGB image and one English prompt.

The target PBR maps were used only for scoring. They were not available to the model and were not used to select the checkpoint. Now that these six cases have been inspected, they will not be used for training, tuning, or checkpoint selection.

Granite and painted wood retain geometry comparatively well, and non-metal classification is stable. Foil fails badly in BaseColor, Roughness, and AO; the paving-stone case also loses structure and roughness. Macro results are 0.1912 linear BaseColor MAE, 0.2399 Roughness MAE, 0.0076 Metallic MAE, 12.83° Normal angular error, 0.1518 AO MAE, and 0.1329 linear rerender MAE. The set is useful as a map of the next training problems, not as evidence of production maturity.

- [Results 01–02: asphalt and leather](results_01_02.png)
- [Results 03–04: granite and foil](results_03_04.png)
- [Results 05–06: paving stones with grass and painted wood](results_05_06.png)
- [Machine-readable metrics and provenance](benchmark.json)

All six source materials report CC0 in their MatSynth metadata. Upstream provenance is recorded in `benchmark.json`; MatSynth is described in the repository [third-party notice](../../docs/THIRD_PARTY.md).
