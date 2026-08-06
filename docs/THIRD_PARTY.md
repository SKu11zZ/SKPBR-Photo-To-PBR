# Third-Party Notice

SKPBR depends on PyTorch, NumPy, and Pillow. Those packages are not vendored and remain subject to their respective licenses.

## MatSynth 90-material capability check

`examples/matsynth-90` contains Blender preview images derived from 90 materials selected from the [MatSynth dataset](https://huggingface.co/datasets/gvecchio/MatSynth), together with SKPBR-generated maps and comparison boards.

- Every selected item reports `CC0` in its MatSynth metadata.
- The 90 item names, upstream sources, source URLs, and license values are recorded in [`examples/matsynth-90/materials.csv`](../examples/matsynth-90/materials.csv).
- Original MatSynth PBR map files are not redistributed in this repository.
- Source-derived portions of the preview and comparison images retain their CC0 provenance. Repository-authored code, layout, metadata, and SKPBR output portions are covered by the repository's Apache-2.0 license where applicable.

MatSynth was published by Giuseppe Vecchio and Valentin Deschaintre. See [MatSynth: A Modern PBR Materials Dataset](https://arxiv.org/abs/2401.06056), CVPR 2024.

## MatSynth six-material post-freeze diagnostic

`examples/matsynth-blind6` contains four compact boards derived from six additional MatSynth entries, plus sanitized metrics and provenance.

- Every selected item reports `CC0` in its MatSynth metadata.
- The selection was locked from metadata before pixel inspection. Target PBR maps were used only for scoring and are not redistributed.
- The six item identifiers, prompts, source URLs, license values, and metrics are recorded in [`examples/matsynth-blind6/benchmark.json`](../examples/matsynth-blind6/benchmark.json).
- Source-derived portions retain their CC0 provenance. Repository-authored layout, metadata, and SKPBR output portions use Apache-2.0 where applicable.

The compact sheets under `examples/plane-d41` were generated from post-freeze numeric procedural recipes specifically for this release and contain no third-party material assets.
