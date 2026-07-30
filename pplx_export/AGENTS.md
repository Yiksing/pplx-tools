# Production package boundary

These instructions apply to `pplx_export/**`.

- Treat this tree as production export, archive, and ask implementation, not as
  generated documentation or sample code.
- Preserve the raw-first archive contract: capture `raw_entries.json` and
  `raw_blocks.json` before parsing derived views, and keep offline re-rendering
  able to rebuild from archived raw data without network access.
- Keep CLI flags, configuration shape, archive layout, and fixture contracts
  backward-compatible unless the user explicitly authorizes a breaking change.
- Do not use live Perplexity services, real browser profiles, real cookies, user
  archives, or user configuration while testing unless the user explicitly asks
  for live validation. Prefer fakes, `tmp_path`, and `monkeypatch`.
- User identity, account registry, cookies, tokens, cache files, and output roots
  must stay outside the repository unless they are scrubbed test fixtures.
- When a change crosses `commands/`, `sites/`, `core/`, `writers/`, or `hooks/`,
  inspect the callers and tests for each touched boundary before editing.
- Before publishing this package to the public remote, follow the repository
  privacy release gate from the root `AGENTS.md`.
