# Vendoring Reference Code

The reference Python code is intentionally small and stdlib-only. Consuming
projects should vendor it into their own repositories instead of installing it
at runtime.

Recommended consuming layout:

```text
vendor/docchain/
  VERSION
  abi.py
  model.py

indexer/
  project_index.py
  project_profile.py
```

The project indexer imports local vendored helpers and applies its own profile:

```python
from vendor.docchain.model import normalize_doc_attested
from indexer.project_profile import score_branches
```

This keeps node operation dependency-free:

```bash
python3 indexer/project_index.py
```

## Update Process

Vendored updates should be manual and reviewable:

1. Tag or identify a commit in this repository.
2. Copy `reference/docchain/` into the consuming repo's `vendor/docchain/`.
3. Update `vendor/docchain/VERSION`.
4. Open a PR with tests and generated-index diff where appropriate.

The reference layer should change infrequently after the ABI and event model
stabilize.
