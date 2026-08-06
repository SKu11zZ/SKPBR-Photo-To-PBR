# Security Policy

The bundled checkpoint is a restricted-load PyTorch payload containing model tensors and bounded release metadata. The runtime loads it with `weights_only=True` and verifies the bundled file's SHA-256 digest before use.

Do not replace the checkpoint with an untrusted pickle-based file. Report suspected model-file tampering or unsafe loading behavior through a private GitHub security advisory after the repository is published.
