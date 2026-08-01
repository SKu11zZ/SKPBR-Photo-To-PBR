# Changelog

## 0.2.0 - 2026-08-01

- Replaced the public BaseColor-only head with the 4,042,230-parameter D41 planar dual-mode checkpoint.
- Added aligned image + bilingual Prompt reconstruction that writes six 512px PBR maps.
- Added deterministic Prompt + seed generation and clearly marked it experimental after the 6/12 Fresh-12B failure.
- Published frozen D10 metrics, Fresh-12B and same-material-color sheets, and the D38-D41 technical report.
- Added circular padding, full-resolution image transport, tile/seam support, and Prompt color/texture adapters.
- Updated tests for bilingual parsing, checkpoint integrity, both forward modes, deterministic seeds, and six-map output.
- Changed the current repository license from MIT to Apache License 2.0 and added NOTICE.

## 0.1.0 - 2026-08-01

- Initial SKPBR research-preview release.
- Added the 266,241-parameter BaseColor calibration head.
- Added deterministic English Prompt conditioning and a source-free CLI.
- Exported a tensor-only checkpoint.
- Published aggregate one-shot shadow metrics, including failed gates.
- Added bilingual documentation, MIT License, tests, and privacy audit tooling.
- Added four from-scratch procedural examples with input renders, exact Prompts, output renders, and six-map PBR results.
- Added a 12-material bilingual coverage audit with full-resolution inputs, output renders, six-map predictions, and an explicit failure analysis.
- Rewrote the root READMEs in a more direct project-author voice and moved supporting documents into `docs/`.
