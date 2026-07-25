# Fixture contract

## Authority and layout

All committed fixture inputs are deterministic simulated data.

| Path | Role |
|---|---|
| `raw_entries.json` | Simulated thread entries in API response shape |
| `raw_blocks.json` | Optional simulated workflow blocks |
| `thread.json` | Simulated archived-thread metadata |
| `golden/` | Derived Markdown generated through the production re-render path |

The raw JSON defines scenario semantics. Golden files are generated
expectations and are never an independent source of truth.

## Trust boundary

- Do not copy or transform data from a user account, live API response,
  `web_archive/`, or a private archive.
- Use generic placeholder identities, deterministic identifiers, synthetic
  prompts and answers, and URLs without signed credentials.
- Local config and `tests/scrub_pairs.local.json` are optional safety inputs for
  replacement and residue detection. They are private, uncommitted, and do not
  provide fixture semantics or provenance.

## Maintenance

`tests/scrub_fixtures.py` normalizes simulated inputs, regenerates goldens via
`pplx_export.commands.rerender_cmd.rerender`, and checks residue. Its `--check`
mode must remain non-mutating.

Fixture directories and their provenance statement are audited in:

- `docs/development/fixtures.md`
- `docs/development/fixtures.zh-CN.md`
- `tests/fixtures/README.md`
- `tests/fixtures/README.zh-CN.md`
