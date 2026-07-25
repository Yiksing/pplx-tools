---
name: test-pplx-tools
description: Design, add, run, and diagnose offline pytest coverage. Use when changing Python behavior, adding a regression, choosing test scope, or investigating a failure. Do not use for creating or regenerating committed fixture datasets and golden snapshots.
---

# Test pplx-tools

Read [references/testing-contract.md](references/testing-contract.md) only when
adding, reorganizing, or changing the architecture of tests.

## Workflow

1. Inspect the changed production path, neighboring tests, and relevant module
   docstrings. Identify the smallest observable contract that should fail
   before the change and pass after it.
2. Place coverage in the existing topical module whenever possible. Create a
   `test_fix_<lineage>_<slug>.py` module only when retaining review lineage
   materially improves traceability.
3. Keep tests offline and isolated. Use `tmp_path`, fakes, and `monkeypatch`;
   never use live Perplexity services, real user configuration, or a user
   archive.
4. Run the narrowest relevant test first, then the complete offline suite.
   Treat interrupted collection or execution as incomplete verification.
5. Report the exact commands and outcomes. Treat full repository validation as
   a separate later phase; do not load another skill merely to run tests.

## Boundaries

- Use the production offline re-render path for rendering behavior; do not
  build a second renderer inside tests.
- If committed simulated JSON or golden snapshots must change, stop and route
  that work as a separate fixture phase.
- If a test module is added, renamed, or removed, record the bilingual test
  inventory update as a later documentation phase.
- Preserve neighboring style, including type annotations,
  `from __future__ import annotations`, and bilingual module docstrings.
