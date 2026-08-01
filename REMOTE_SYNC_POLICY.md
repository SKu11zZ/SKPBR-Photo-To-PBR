# Remote Sync Policy

Target repository: `https://github.com/SKu11zZ/SKPBR-Photo-To-PBR.git`

Before the first upload:

1. Query remote branches and tags without writing.
2. Fetch the remote history.
3. Inspect and compare every remotely tracked file, especially the MIT License.
4. Preserve remote-only content and reconcile collisions explicitly.
5. Use a normal fast-forward or merge commit.
6. Never use force push, history rewriting, or an overwrite-oriented mirror push.

If the remote changes during packaging, fetch and inspect it again immediately before pushing.

Initial audit base: remote `main` commit `f04eab0`, containing only the remotely generated MIT License and initial README. The remote must be fetched again immediately before the eventual push.
