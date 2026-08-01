# 12-material coverage audit

**English** | [简体中文](README_zh-CN.md)

This folder is the historical v0.1 Suzanne audit, not a best-of gallery. It contains 12 procedural inputs and the unedited outputs from that frozen research pipeline. The current v0.2 planar evaluation is under `examples/plane-d41`.

- [Open the bilingual long sheet](contact_sheet_long.png)
- [Read the full report](../../docs/COVERAGE_AUDIT_12.md)
- [Read the delivery audit](../../docs/release/coverage_12_delivery_audit.json)

Each folder under `materials/` contains a 1024px input render, output render, BaseColor, Roughness, Metallic, Normal, Height, AO, the English Prompt actually fed to the model, and a Chinese display translation. The Chinese text was not fed to the current model.

The results are mixed. Blue glazed ceramic and red brick are relatively close; several other cases fail visibly in color, material identity, routing, or physical channels. Nothing in this folder was manually retouched to hide that.
