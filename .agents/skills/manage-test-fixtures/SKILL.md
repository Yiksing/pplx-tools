---
name: manage-test-fixtures
description: Create, scrub, regenerate, and validate simulated fixtures and golden rendering snapshots. Use when committed fixture JSON changes, a render regression needs API-shaped input, or golden Markdown must be regenerated. Do not use for pytest-only changes without fixture data changes.
---

# Manage test fixtures

Read [references/fixture-contract.md](references/fixture-contract.md) only when
touching committed files under `tests/fixtures/`.

## Workflow

1. Model only the minimum fields and relationships needed by the scenario.
   Construct deterministic simulated data; never copy from `web_archive/`, a
   live API response, an account, or a private archive.
2. Treat committed `raw_entries.json`, optional `raw_blocks.json`, and
   `thread.json` as the scenario truth.
3. Change simulated raw JSON rather than independently editing files under
   `golden/`.
4. Normalize inputs and regenerate derived products through the production
   offline renderer:

   ```bash
   uv run python tests/scrub_fixtures.py
   ```

5. Run the non-mutating residue gate and relevant snapshot tests:

   ```bash
   uv run python tests/scrub_fixtures.py --check
   uv run pytest tests/test_render_snapshots.py -q
   ```

6. Inspect the diff for unintended content changes, identifiers, paths, signed
   URL credentials, and turn-count changes.

## Boundaries

- Never commit private replacement mappings, credentials, real identities, or
  reverse mappings from placeholders to live objects.
- Do not describe committed fixtures as captures, sanitized captures, or
  derivatives of real threads. Their source contract is simulated data.
- Preserve intentional cross-record relationships while using the repository's
  deterministic placeholder conventions.
- When adding, renaming, or deleting a fixture directory, update the
  audit-delimited fixture inventories in both canonical languages.
- Treat ordinary test design and full repository validation as separate later
  phases; do not load their instructions merely to change fixture data.
