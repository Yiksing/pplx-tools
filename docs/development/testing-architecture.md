# Testing architecture

The `pplx_export` test system is fully offline, uses checked-in simulated data,
and snapshot-locks renderer behavior. This page describes the architecture and
guarantees; the current module list belongs in
[Testing](../development/testing.md), and fixture details belong in
[Test fixtures](../development/fixtures.md).

The section keeps its numbering from the
[architecture overview](../architecture/overview.md).

---

## Test system

Run the suite with `uv run pytest tests`. Test counts are reported from the
current run rather than treated as an architectural constant.

### Layers

| Layer | Representative modules | Contract |
|---|---|---|
| Pure unit behavior | `test_units.py`, credential/cookie/config tests | isolate functions, classes, validation, and normalization with simulated inputs |
| Component semantics | interruption, stub-workflow, answer-variant, and relations tests | exercise cooperation between parser, renderer, state, and index code without network access |
| Offline command/state behavior | backfill, deletion sync, initialization, and review regressions | run command paths against temporary directories and faked transports |
| Render snapshots | `test_render_snapshots.py` | pass simulated API-shaped JSON through the production re-render path and compare all Markdown bytes with committed goldens |

Review identifiers such as N, V3, V4, and V5 are traceability metadata across
these layers. They do not define a separate runtime architecture, and their
relationship to test modules is not necessarily one-to-one.

### Snapshot data flow

1. A simulated fixture supplies `raw_entries.json`, optional
   `raw_blocks.json`, and `thread.json`.
2. `tests/conftest.py::render_fixture` copies those files into `tmp_path`.
3. The fixture calls `commands.rerender_cmd.rerender`, the production offline
   reconstruction path.
4. Fresh `conversation.md` and `turns/turn_*.md` files are compared
   byte-for-byte with committed `golden/` products.

Goldens are generated expectations, not an independent data source. Any
renderer change that alters artifact bytes turns the snapshot suite red until
the change is reviewed and the goldens are intentionally regenerated.

### Isolation and trust boundaries

- **Fixture origin** — all committed fixture inputs are simulated data. They
  are not copied from live accounts, live API responses, `web_archive/`, or
  private archives.
- **Network boundary** — tests use fakes and offline paths; checked-in fixtures
  require no credentials or network access.
- **Configuration boundary** — the autouse fixture installs placeholder account
  configuration, so a developer's real `~/.config` does not determine results.
- **Filesystem boundary** — command and migration behavior runs under
  `tmp_path`; user archives are not test targets.
- **Residue boundary** — `tests/scrub_fixtures.py --check` rejects configured
  environment-specific strings, local absolute paths, and signed-URL
  credentials without modifying files.

Together, unit assertions, component semantics, command-state tests, and
byte-level snapshots protect both local logic and the end-to-end re-render
contract.
