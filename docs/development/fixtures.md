# Test fixtures

`tests/fixtures/` contains deterministic, API-shaped **simulated data** for the
[test suite](testing.md). The inputs model representative thread and workflow
structures; their rendered products are committed as golden snapshots.

## Source contract

<!-- audit:contract fixture-source=simulated -->

The current committed fixture content is simulated:

- New or updated fixtures must be constructed as simulated data; contributors
  must not populate them by importing `web_archive/`, user-account data, live
  API responses, or private archives.
- Names, identities, identifiers, prompts, answers, workflow payloads, paths,
  and URLs in the committed files are testing placeholders.
- The JSON mirrors production response and archive schemas only to exercise
  parser, renderer, state, and relation behavior.
- The repository does not commit a reverse mapping from placeholders to
  private identifiers.

The terms **full-mode fixture** and **reduced scenario fixture** describe test
coverage and input shape, not provenance. Both are simulated data.

## Directory contract

Each fixture directory contains simulated raw-response-shaped inputs and,
where snapshot comparison is needed, a `golden/` tree:

| Path | Role |
|---|---|
| `raw_entries.json` | simulated thread entries in the production response shape |
| `raw_blocks.json` | simulated workflow blocks; absent where the mode has no block response |
| `thread.json` | simulated archived-thread metadata |
| `golden/conversation.md` + `golden/turns/turn_*.md` | products generated from the simulated inputs and compared byte-for-byte |

The current deterministic conventions include:

- placeholder accounts `alice` / `bob`, example identities, a placeholder BOT
  space, and a fixed placeholder `read_write_token`;
- uuid5-derived identifiers tagged with `5cbeef00`, preserving intentional
  cross-references between simulated records;
- fixed-length simulated `toolu_` identifiers tagged with `5crub0`;
- generic prompts, titles, workflow text, and file paths; and
- signed-URL query strings removed.

These conventions make accidental environment-specific residue easy to detect;
they do not imply that the simulated identifiers were derived from live
objects.

## Inventory

<!-- audit:inventory fixture-directories -->

### Full-mode fixtures

These are complete simulated conversations for each supported mode:

| Fixture | Coverage |
|---|---|
| `search_demo` | search, one turn; R code fence and inline code |
| `deep_research_demo` | deep research; end-to-end math-delimiter conversion |
| `computer_demo` | computer, seven-turn workflow rendering |
| `council_demo` | council model-committee rendering with a large nested payload |
| `study_demo` | study-mode rendering |

### Reduced scenario fixtures

These are focused simulated payloads containing only the entries and
relationships needed by a regression. “Reduced” does not mean extracted from a
real thread.

| Fixture | Coverage |
|---|---|
| `scenario_computer_answer_fallback` | recover the answer from a schematized workflow block when the plain FINAL path is unavailable |
| `scenario_subagent_fallback` | render a sub-agent headline and its own items when no background match exists |
| `scenario_user_response` | `WORKFLOW_ITEM_USER_RESPONSE` question/answer rendering |
| `scenario_subagent_stub` | ten-second association window for an unanchored subagent-result stub |
| `scenario_workflow_item_nested` | nested `WORKFLOW_ITEM_WORKFLOW` collapsed-block rendering |
| `scenario_limit_interrupted` | spending-limit interruption, attribution waterfall, appendix placement, and no double-rendering |
| `scenario_canceled` | `WORKFLOW_CANCELED` annotation |

<!-- /audit:inventory fixture-directories -->

## Maintaining fixtures

`tests/scrub_fixtures.py` normalizes the simulated data, regenerates golden
products through the production offline renderer, and enforces a residue gate:

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **Regeneration** — every fixture is rendered in a temporary directory through
  `pplx_export.commands.rerender_cmd.rerender`; turn-count mismatches abort.
- **Deterministic normalization** — placeholder text, UUIDs, `toolu_` values,
  tokens, and signed URLs are normalized idempotently.
- **Safety inputs are not provenance** — the optional local
  `tests/scrub_pairs.local.json` and user-level account configuration only
  extend replacement and residue checks. They must not be used as inputs for
  constructing fixture scenarios.
- **Check mode** — `--check` performs no writes and fails on configured residue,
  local absolute paths, or signed-URL credentials.

Run the maintenance tool after changing simulated input JSON or renderer output,
and run `--check` before committing fixture changes.

## Golden snapshot authority

Committed simulated JSON is the input authority. Golden Markdown is derived
output: it is regenerated from that JSON with the current production re-render
path and then committed for byte-level regression comparison. It must not be
edited as an independent source of truth.

## See also

- [Testing](testing.md) — how the suite consumes the fixtures
- [Test system architecture](testing-architecture.md) — regression
  layers and guarantees
- `tests/fixtures/README.md` — repository-local fixture inventory
