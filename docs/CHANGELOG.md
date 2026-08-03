# Changelog

## 0.4.0 - 2026-08-02

- Released the 4,586,975-parameter D52–D54 albedo-disentangled checkpoint.
- Added a full-resolution photometric BaseColor refiner and a conservative color/geometry separation head.
- Jointly tuned lightweight adapters with image + Prompt, image-only, and text-only batches while keeping the 3.41M-parameter core frozen.
- Reduced the frozen development objective from 0.70650 to 0.69374 and color-to-geometry leakage from 0.06614 to 0.06158.
- Published three selected Blind-G boards covering six of the 12 materials after freezing the v0.4 weights.
- Reported the Blind-G result without retuning on it: 2/12 materials met all consistency checks, 12/20 acceptance thresholds were met, and there were zero catastrophic physical-regime failures. The overall acceptance threshold was not met.

## 0.3.0 - 2026-08-02

- Released the 4,443,261-parameter D49–D51 structured-relief checkpoint.
- Added 55-dimensional structured Prompt attributes for material regime, primary/secondary color, finish and relief.
- Restored explicit Chinese aliases for automotive metallic paint in the public Prompt parser.
- Replaced the directional text seed basis with deterministic isotropic multiscale noise.
- Added an exact zero-relief path for explicitly flat materials.
- Kept the D51 spatial separator at its zero-residual baseline because trained epochs did not improve the frozen objective.
- Published one combined Blind-F result board with input, image + Prompt, text-only, reconstructed render and six maps.
- Reported the Blind-F result without retuning on it: 2/12 materials met all consistency checks and 13/20 acceptance thresholds were met. The overall acceptance threshold was not met.

## 0.2.0 - 2026-08-01

- Replaced the public BaseColor-only head with the 4,042,230-parameter D41 planar dual-mode checkpoint.
- Added aligned image + bilingual Prompt reconstruction that writes six 512px PBR maps.
- Added deterministic Prompt + seed generation and clearly marked it experimental after the 6/12 Fresh-12B failure.
- Published frozen D10 metrics plus compact Fresh-12B and same-material-color evaluation sheets.
- Added circular padding, full-resolution image transport, tile/seam support, and Prompt color/texture adapters.
- Updated tests for bilingual parsing, checkpoint integrity, both forward modes, deterministic seeds, and six-map output.
- Changed the current repository license from MIT to Apache License 2.0 and added NOTICE.

## 0.1.0 - 2026-08-01

- Initial SKPBR research-preview release.
- Added the 266,241-parameter BaseColor calibration head.
- Added deterministic English Prompt conditioning and a source-free CLI.
- Exported a tensor-only checkpoint.
- Published aggregate one-shot shadow metrics, including acceptance thresholds that were not met.
- Added bilingual documentation, MIT License, tests, and privacy audit tooling.
- Added four from-scratch procedural examples with input renders, exact Prompts, output renders, and six-map PBR results.
- Added a 12-material bilingual coverage audit with full-resolution inputs, output renders, six-map predictions, and an explicit failure analysis.
- Rewrote the root READMEs in a more direct project-author voice and moved supporting documents into `docs/`.
