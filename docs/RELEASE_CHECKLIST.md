# Public Release Checklist

- [x] Repository name changed to SKPBR.
- [x] MIT License added.
- [x] Model described as a 266,241-parameter calibration head, not as the full upstream stack.
- [x] External-shadow failure disclosed in the README and model card.
- [x] Tensor-only checkpoint exported.
- [x] Training/evaluation images, source maps, caches, resume states, and private per-example records excluded.
- [x] Public examples are newly generated procedural assets, visually reviewed, and clearly labeled as unedited qualitative results.
- [x] Local absolute-path scan passes.
- [x] Private-workspace token scan passes.
- [x] CPU inference and screen-invariance tests pass.
- [ ] Publisher confirms authorization to distribute learned weights under MIT.
- [x] GitHub HTTP remote supplied.
- [x] Fetch and inspect every remote branch, tag, and existing file before push.
- [x] Preserve the remotely generated MIT License and copyright owner.
- [ ] Use a normal fast-forward/merge workflow; never force-push or overwrite an unreviewed remote file.
- [ ] Public repository description and topics reviewed.
