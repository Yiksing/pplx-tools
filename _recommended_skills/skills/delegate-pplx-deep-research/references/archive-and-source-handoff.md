# Archive and source handoff

Treat the automatically exported archive as part of the research deliverable.
Do not reduce it to the console summary.

## Contents

- [Run contract](#run-contract)
- [Locate and verify the archive](#locate-and-verify-the-archive)
- [Read the artifacts](#read-the-artifacts)
- [Return to the parent](#return-to-the-parent)
- [Verification language](#verification-language)

## Run contract

Use a private output root and keep automatic export enabled:

```bash
pplx-ask --out "$PPLX_ARCHIVE_ROOT" ask "$PPLX_RESEARCH_PROMPT" \
  --mode deep-research --no-telemetry
```

The global `--out` option appears before `ask`. Deep-research mode has a fixed
platform model, so do not pass `--models`. Add `--timeout` only when needed.

The CLI writes progress to stderr and emits one machine-readable JSON object
on stdout. Require exit status zero. Treat a missing or failed export as an
incomplete research package even if an answer appeared in the stream.

## Locate and verify the archive

The result identifies the new thread but does not provide a dependable archive
directory path. Search beneath the configured output root for `thread.json`
and accept a directory only when `thread.json.web_uuid` exactly equals the
returned thread identity.

Do not infer identity from:

- the title;
- a date;
- a shortened identifier;
- the directory name alone.

## Read the artifacts

Inspect these files as applicable:

- `report.md` — the full deep-research report and primary deliverable when
  present.
- `conversation.md` — the rendered query and answer; use as the primary answer
  artifact when no separate report was produced.
- `sources.json` — the complete deduplicated inventory of sources returned by
  the platform. Entries preserve `name`, `url`, `snippet`, and `timestamp`
  when those fields were supplied.
- `sources.md` — a readable link index for the returned-source inventory.
- `raw_entries.json` and `raw_blocks.json` — source material for resolving
  exact structured metadata, workflow detail, or a rendering ambiguity.
- `thread.json` — identity, mode, report metadata, status, and archive summary.
- `assets/` and its manifest — downloadable report or file artifacts when the
  thread produced them.

Read `report.md` completely before summarizing it. Do not assume that the
report's references section and `sources.json` contain the same set:

- the report references identify sources materially presented in the report;
- `sources.json` preserves the broader set of sources returned by the
  platform.

The returned-source inventory is not proof that every entry was read by the
agent, relied upon by the report, or independently verified.

## Return to the parent

Return a compact control message that points to the complete package:

1. verified archive directory;
2. primary report or answer path;
3. `sources.json` and `sources.md` paths;
4. returned-source count;
5. concise synthesis of the strongest findings;
6. a small mapping from decision-critical claims to their best sources;
7. contradictions, weak evidence, inaccessible primary sources, and
   unresolved questions;
8. relevant assets.

Do not paste a long report or a very large source list into the control
message unless the parent requests it. Do not discard, rewrite, or replace the
complete archive with the compact handoff.

## Verification language

Use precise labels:

- **Returned** — present in the platform's exported source inventory.
- **Cited** — materially referenced in the report.
- **Opened** — accessed by the agent.
- **Verified** — inspected closely enough to support the specific claim,
  including the relevant location or data.
- **Unresolved** — inaccessible, contradictory, or insufficient for the
  claim.

Never say that all sources were verified when only the report or a selected
subset was inspected.
