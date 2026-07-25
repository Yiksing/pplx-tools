# Testing contract

## Sources of truth

- `docs/development/testing.md` owns contributor practice and the audited test
  module inventory.
- `docs/development/testing-architecture.md` owns test layers and isolation
  boundaries.
- `tests/conftest.py` owns the placeholder user configuration and production
  re-render fixture.
- `.github/workflows/quality.yml` owns the complete CI command sequence.

## Stable rules

- Keep every test deterministic and offline.
- Exercise network-facing code through fakes; keep filesystem and configuration
  behavior under temporary paths.
- Prefer behavior assertions over implementation-detail assertions. Repository
  contract tests may intentionally lock configuration, navigation, workflow, or
  public-title requirements.
- Add regressions at the lowest useful layer: pure unit, component behavior,
  offline command/state behavior, then byte-level render snapshot.
- Supplement snapshots with semantic invariants when identical bytes alone
  would not expose data loss.
- Treat review identifiers as traceability metadata, not a one-finding-per-file
  architecture.

## Common commands

```bash
uv run pytest tests/path/to/test_module.py -q
uv run pytest tests -q
uv run pytest --collect-only -q
```

Use current command output for test counts; do not preserve counts or timings as
timeless repository facts.
