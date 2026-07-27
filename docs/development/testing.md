# Testing

The test suite lives in `tests/`, outside the `pplx_export` package, and runs
fully offline. Its API-shaped inputs are deterministic simulated data committed
under `tests/fixtures/`; tests do not depend on live services or a real
user-level configuration.

This page owns the current test-module inventory and the contributor workflow.
For the regression design, see
[Test system architecture](testing-architecture.md). For the input
data contract, see [Test fixtures](fixtures.md).

## Running the tests

```bash
uv run pytest tests
```

pytest is a declared development dependency. The suite guarantees:

- **Zero network** — simulated inputs are checked in; network-facing paths are
  covered with fakes, `tmp_path`, and `monkeypatch`.
- **No real user configuration** — before importing any production module,
  `tests/conftest.py` creates a process-local temporary configuration and
  overrides `PPLX_EXPORT_CONFIG`. Each test then receives its own placeholder
  `alice` / `bob` configuration and restores the process-local placeholder
  afterward. Subprocess regressions verify that a missing or broken caller
  configuration cannot break test collection.
- **Fast feedback** — on 2026-07-25 the project observed 435 tests collected
  from 32 `test_*.py` modules and ran the full suite in roughly 13–25 seconds
  across local verification runs.
  Counts are a dated repository snapshot and will grow.

Useful selections:

| Command | Effect |
|---|---|
| `uv run pytest tests` | full suite |
| `uv run pytest tests/test_units.py` | one module |
| `uv run pytest tests -k snapshot` | tests whose node id matches `snapshot` |
| `uv run pytest tests -x -q` | stop at the first failure, quiet output |
| `uv run pytest --collect-only -q` | refresh the collected-case count |

## Current module inventory

Inventory synchronized with the repository on **2026-07-27**:

<!-- audit:inventory test-modules -->

| Functional family | Modules | Purpose |
|---|---|---|
| Render snapshots | `test_render_snapshots.py` | re-render all simulated full-mode and reduced-scenario fixtures, then compare committed products byte-for-byte |
| Core and shared utilities | `test_units.py` | state, throttling, planning, normalization, asset naming, mode detection, safe paths, and cross-cutting regressions |
| Documentation contracts, skills, and localization | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | repository-local skill contracts plus isolated miniature-repository tests for the read-only documentation auditor and machine-translation pipeline |
| Configuration, authentication, and bootstrap | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | external configuration isolation, cookie-source profiles, credential selection, and initialization |
| Rendering and workflow semantics | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | workflow attribution, interruption states, answer variants, audit logging, and relation edges |
| Offline archive and index maintenance | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | enrichment, resume/idempotency behavior, cross-account deletion detection, terminal states, and the offline state-account/change report tiers |
| Review regressions | 16 `test_fix_*.py` modules listed below | fixes derived from review findings; module names retain review lineage |

### Review-regression lineage

Review identifiers explain why a regression exists; they are not the test
suite's primary architecture. The mapping is deliberately many-to-many: one
module may cover several findings, and a finding may also add cases to an
existing topical module.

| Lineage | Dedicated modules |
|---|---|
| N review | `test_fix_n01_inline_assets.py`, `test_fix_n02_spaces_link.py`, `test_fix_n03_n12.py`, `test_fix_n04_cookies.py`, `test_fix_n05_n06_n09.py`, `test_fix_n07_usage_checkpoint.py`, `test_fix_n08_throttle_overflow.py`, `test_fix_n10_table_header.py`, `test_fix_n11_batch_total.py` |
| V3 review | `test_fix_v301_nested_sources_text.py`, `test_fix_v305_export_products.py` |
| V4 review | `test_fix_v401_thread_dir_migration.py`, `test_fix_v402_manifest_count.py`, `test_fix_v403_handle_assets_idempotency.py`, `test_fix_v405_ask_post_steps.py` |
| V5 review | `test_fix_v5_review.py`, plus focused additions to existing topical modules |
| V6 review | `test_fix_v6_atomic_writes.py` |

<!-- /audit:inventory test-modules -->

The module docstrings remain the authoritative explanation of each finding's
old behavior, corrected behavior, and regression boundary.

## How snapshot tests reuse the production re-render path

Snapshot tests do not implement a parallel renderer:

1. `render_fixture` in `tests/conftest.py` copies a fixture's simulated
   `raw_entries.json`, optional `raw_blocks.json`, and `thread.json` into a
   temporary directory.
2. It calls `pplx_export.commands.rerender_cmd.rerender`, the same function
   used by `pplx-export re-render`.
3. The `rendered` fixture factory returns the fresh output and the fixture's
   committed `golden/` directory.
4. Tests compare `conversation.md` and every `turns/turn_*.md` byte-for-byte.

Content invariants supplement byte equality: answers must not collapse to the
empty `(无)` placeholder, and dict-repr residue such as `{'type': ...` must not
leak into rendered text.

## Adding a test

- **Existing logic** — add a test to the matching topical module. Use
  `tmp_path`, fakes, and `monkeypatch`; never access the network or real
  `~/.config`.
- **Bug regression** — prefer the matching topical module. Create a
  `test_fix_<lineage>_<slug>.py` module when retaining review lineage materially
  improves traceability; do not assume one module per finding.
- **Render regression** — add or reduce a simulated fixture, regenerate its
  golden products with the maintenance tool, then register it in
  `test_render_snapshots.py` or add scenario-specific assertions.

Follow the neighboring style: type annotations,
`from __future__ import annotations`, and bilingual module docstrings.

## See also

- [Test fixtures](fixtures.md) — simulated inputs, golden products, and the
  maintenance contract
- [Test system architecture](testing-architecture.md) — test layers
  and regression guarantees
- [Offline operations](../architecture/offline-operations.md) — the production
  re-render path used by snapshot tests
