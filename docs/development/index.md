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

## Commit convention

- Each commit addresses one concern. The commit message describes exactly what
  the diff changes — no more, no less.
- Split cross-concern work into independent commits. For example, quality-gate
  changes, agent-boundary changes (skills, `AGENTS.md`), and bulk documentation
  updates each land as their own commit.
- A canonical page and its `.zh-CN.md` counterpart are one concern and stay in
  the same commit, as required by the documentation pairing contract.
- Every commit passes `uv run pytest -q` on its own, so history remains
  reviewable and bisectable.

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
