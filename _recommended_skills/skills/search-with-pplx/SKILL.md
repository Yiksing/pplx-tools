---
name: search-with-pplx
description: "Run targeted Perplexity searches directly with pplx-ask and integrate the automatically archived answer and returned sources. Use when the main agent needs a focused fact lookup, source discovery, current-state check, or bounded claim verification. Do not use for exhaustive literature reviews, broad multi-source synthesis, or questions answerable from authoritative local files."
---

# Search with PPLX

Run a focused search in the main agent, preserve the automatically exported
thread, and ground the resulting answer in the archived sources.

Read [focused-search-prompts.md](references/focused-search-prompts.md) when the
query needs more structure than a direct question.

## 1. Keep the task focused

Use this skill for:

- a small set of factual questions;
- locating primary or authoritative sources;
- checking one bounded claim;
- discovering papers before local analysis;
- current-state checks that genuinely require current information.

Switch to `delegate-pplx-deep-research` when the work expands into a literature
review, research-gap audit, consequential multi-source verification, or a
substantial report.

Do not make a network call when authoritative local material already answers
the question.

## 2. Apply the external-transmission boundary

Minimize context before sending the prompt. Never transmit credentials,
cookies, account identifiers, private conversation text, unnecessary local
paths, or unrelated personal information. Do not transmit unpublished or
confidential material without user authorization.

If the lookup depends on material that cannot be sent, keep the task local or
ask the user for direction.

## 3. Write the search prompt

State:

- the exact question or claim;
- the intended use of the answer;
- the preferred evidence class;
- any definitions needed to avoid ambiguity;
- the requested citation or bibliographic detail;
- how to handle uncertainty or disagreement.

Prefer authority and relevance over an arbitrary date range. Add recency or a
date boundary only when the question is time-sensitive or historically
bounded.

Ask for direct links and exact evidence locations when the claim warrants
them. Do not request an exhaustive report from search mode.

## 4. Run and archive

Before the first search call, run two preflight checks:

1. Confirm the user-level config file exists: the explicit `--config` path
   when one is used, otherwise `$PPLX_EXPORT_CONFIG`, otherwise
   `~/.config/pplx-export/config.toml`.
2. Run `pplx-ask models` as the Perplexity connectivity-and-session probe and
   require the search-mode selectable-model table in its output.

If the config file is missing, or the model table cannot be retrieved, pause
and report to the user instead of proceeding.

Run this preflight once per conversation, before the first call only. Do not
re-probe between subsequent calls; repeat the connectivity probe only after a
later call actually times out or fails with connectivity symptoms — backoff
silence alone is not a trigger.

Confirm the installed contract with `pplx-ask ask --help` when uncertain. Pass
the prompt as one process argument without re-evaluating its contents as shell
syntax.

Run:

```bash
pplx-ask --out "$PPLX_ARCHIVE_ROOT" ask "$PPLX_SEARCH_PROMPT" \
  --mode search --no-telemetry
```

Keep automatic export enabled. Never use `--no-export`.

Search mode uses the platform's default "Best" choice when `--models` is
omitted. If the user asks for a specific selectable model, take a live model
identifier from the preflight `pplx-ask models` output; do not hardcode an
identifier in the skill.

Every `ask` command creates a new thread. Use separate calls only for genuinely
distinct questions, and keep them sequential unless the surrounding
environment explicitly establishes a safe concurrency policy.

Budget wall-clock time generously: the transport retries 429 / 5xx / network
errors with backoff waits of up to 300 s each, so even a search-mode call that
normally finishes in minutes can legitimately stay silent much longer — give
any wrapping task a budget of at least 15 minutes rather than a short hard
timeout, and treat silence as a backoff wait, not a hang (see [runtime budget
for
callers](https://pplx.iekseng.com/guide/rate-limiting/#runtime-budget-for-callers)).

## 5. Verify the archive

Require exit status zero. Capture the final JSON result, then locate the
archive under the configured output root by matching the returned thread
identity exactly against `thread.json.web_uuid`.

Read:

- `conversation.md` for the rendered answer;
- `sources.json` for the complete deduplicated returned-source inventory;
- `sources.md` for the readable link index;
- raw JSON only when exact metadata or rendering needs verification.

If `report.md` or assets exist unexpectedly, include them in the handoff.

## 6. Integrate the result

Answer the user's question directly and cite the strongest sources actually
supporting the answer. Preserve the archive path and returned-source count
when they are useful to the larger task.

Distinguish sources returned by the platform from sources the main agent
independently opened and verified. State uncertainty, conflicting evidence,
and access limitations. Do not claim comprehensive coverage from a focused
search.
