# Remote Sync Policy

Target repository: `https://github.com/SKu11zZ/SKPBR-Photo-To-PBR.git`

Before the first upload:

1. Query remote branches and tags without writing.
2. Fetch the remote history.
3. Inspect and compare every remotely tracked file, especially the repository license.
4. Preserve remote-only content and reconcile collisions explicitly.
5. Use a normal fast-forward or merge commit.
6. Never use force push, history rewriting, or an overwrite-oriented mirror push.

If the remote changes during packaging, fetch and inspect it again immediately before pushing.

The v0.2 packaging run started with local and remote `main` both at `9c2f8c4`. The requested license change from MIT to Apache-2.0 is made as a normal reviewed commit. The remote must be fetched and compared again immediately before each push.
