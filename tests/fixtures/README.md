# Test fixtures

> [中文文档](README.zh-CN.md)

This directory contains deterministic, API-shaped **simulated data** plus
golden Markdown generated from it. It is self-contained and requires neither
network access nor private account data.

For the full maintenance and trust-boundary documentation, see
[`docs/development/fixtures.md`](../../docs/development/fixtures.md).

## Source contract

<!-- audit:contract fixture-source=simulated -->

All committed fixtures are simulated data:

- no file is copied from `web_archive/`, a user account, a live API response,
  or a private archive;
- identities, identifiers, prompts, answers, workflow payloads, paths, and URLs
  are placeholders created for tests;
- production-shaped fields and relationships exist only to exercise code
  behavior; and
- no original thread id or private reverse mapping is part of the fixture
  contract.

“Full-mode” and “reduced scenario” describe coverage and input size, not
provenance.

## Files

| Path | Role |
|---|---|
| `raw_entries.json` | simulated thread entries in production response shape |
| `raw_blocks.json` | simulated workflow blocks, when relevant |
| `thread.json` | simulated archived-thread metadata |
| `golden/conversation.md` + `golden/turns/turn_*.md` | generated expectations for byte-level comparison |

The placeholder account, uuid5/`5cbeef00`, `toolu_`/`5crub0`, token, text, and
URL conventions are deterministic. They preserve intentional relationships
inside the simulated dataset without implying any live-object origin.

## Inventory

<!-- audit:inventory fixture-directories -->

### Full-mode simulated conversations

| Fixture | Coverage |
|---|---|
| `search_demo` | search, one turn; R code fence and inline code |
| `deep_research_demo` | deep research; math-delimiter conversion |
| `computer_demo` | computer, seven-turn workflow rendering |
| `council_demo` | council model-committee rendering with a large nested payload |
| `study_demo` | study-mode rendering |

### Reduced simulated scenarios

| Fixture | Coverage |
|---|---|
| `scenario_computer_answer_fallback` | answer recovery from a schematized workflow block |
| `scenario_subagent_fallback` | sub-agent fallback without a background match |
| `scenario_user_response` | `WORKFLOW_ITEM_USER_RESPONSE` rendering |
| `scenario_subagent_stub` | unanchored subagent-result stub association |
| `scenario_workflow_item_nested` | nested workflow-item rendering |
| `scenario_limit_interrupted` | limit interruption and attribution-waterfall behavior |
| `scenario_canceled` | canceled-workflow annotation |

<!-- /audit:inventory fixture-directories -->

## Regenerating golden products

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

The first command normalizes simulated inputs and regenerates `golden/` through
the production offline `rerender` path. The second performs only the residue
gate and does not write files.

User-level configuration and an optional local
`tests/scrub_pairs.local.json` are safety inputs for replacement/residue
checks, not fixture sources. They do not contribute scenario semantics or make
the committed simulated data a derivative of local account data.

Golden Markdown is derived output. Change simulated raw JSON when the test
scenario changes; regenerate rather than independently editing golden files.
