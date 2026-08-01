# Security Policy

The bundled checkpoint is a tensor-only PyTorch state dictionary. The runtime loads it with `weights_only=True`.

Do not replace the checkpoint with an untrusted pickle-based file. Report suspected model-file tampering or unsafe loading behavior through a private GitHub security advisory after the repository is published.
