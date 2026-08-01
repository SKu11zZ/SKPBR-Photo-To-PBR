# Public Release Checklist

- [x] Repository name and author identity use SKPBR and SKu11zZ.
- [x] Apache License 2.0 and NOTICE added; package and citation metadata updated.
- [x] v0.2 described as a 4,042,230-parameter planar dual-mode model.
- [x] Image + Prompt is identified as the MVP path.
- [x] Prompt-only is identified as experimental and its 6/12 blind failure is disclosed.
- [x] Frozen D10 and one-shot Fresh-12B results are separated.
- [x] Public checkpoint loads through `weights_only=True` and matches the recorded SHA-256.
- [x] Training/evaluation source images, commercial assets, source maps, caches, optimizer states, and private per-example records are excluded.
- [x] D41 public sheets use post-freeze numeric procedural recipes.
- [x] Local absolute-path and private-workspace-token scans pass.
- [x] CPU model load, bilingual Prompt, both forward modes, deterministic seed, and six-map CLI tests pass.
- [x] GitHub remote fetched and compared before packaging; local and remote `main` started at the same commit.
- [x] Fetch and compare the remote once more immediately before push.
- [x] Push through a normal fast-forward update; never force-push.
- [ ] Public repository description and topics reviewed by the owner.
