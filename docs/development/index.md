# Maintainer guide

Contracts and workflows for changing pplx-tools without weakening archive
fidelity or test isolation.

## Choose the right document

- [Testing architecture](testing-architecture.md) — test layers, trust
  boundaries, and the guarantees provided by offline snapshots.
- [Testing practices](testing.md) — current test inventory and contributor
  workflow.
- [Fixtures and snapshots](fixtures.md) — simulated-data provenance,
  directory conventions, golden generation, and residue checks.

## Local quality loop

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Fixture inputs are deterministic simulated data. They are not copied from live
accounts, live API responses, `web_archive/`, or private archives.
