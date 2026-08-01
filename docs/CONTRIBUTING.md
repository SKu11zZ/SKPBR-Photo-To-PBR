# Contributing

Contributions are welcome when they preserve the published capability boundary and data-isolation rules.

1. Do not add private datasets, local paths, caches, or third-party textures.
2. Add tests for behavior changes.
3. Report evaluation changes with frozen aggregate protocols.
4. Do not describe the calibration head as a standalone end-to-end RGB-to-PBR system.
5. Run `python tools/release_audit.py` before opening a pull request.
