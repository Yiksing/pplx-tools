---
name: delegate-pplx-deep-research
description: "Delegate an evidence-heavy investigation to a subagent that runs pplx-ask in deep-research mode, then integrate the archived report and complete returned-source inventory. Use for literature reviews, research-gap audits, source audits, multi-source synthesis, or consequential fact verification. Do not use for narrow lookups, local-only analysis, or context that cannot be sent to an external service."
---

# Delegate PPLX deep research

Assign one subagent clear ownership of the research workstream. Require a
detailed research brief, automatic `pplx-ask` archiving, and an evidence-aware
handoff to the parent agent.

## Load the supporting references

- Read [research-prompt-patterns.md](references/research-prompt-patterns.md)
  before composing the subagent objective or the Perplexity-facing prompt.
- Read
  [archive-and-source-handoff.md](references/archive-and-source-handoff.md)
  before running the command or accepting the subagent result.

## 1. Confirm that delegation fits

Delegate when the task needs substantial evidence collection, reconciliation
of conflicting sources, a literature synthesis, or a defensible audit trail.

Do not delegate merely because the request contains the word "research." Use a
focused direct search for a small number of facts or sources. Keep local-only
questions local.

If no subagent mechanism is available, do not pretend that delegation
occurred. Apply the same research and archive contract directly, and disclose
that the work ran in the main agent.

## 2. Apply the external-transmission boundary

Before delegation, identify which local materials the subagent may read and
which information may be sent to Perplexity.

Never send credentials, cookies, account identifiers, private conversation
text, unnecessary local paths, or unrelated personal information. Do not send
unpublished or confidential material unless the user has authorized that
external transmission. Replace local implementation detail with the minimum
semantic context needed to answer the research question.

If essential evidence cannot cross this boundary, stop the external call and
report the limitation.

## 3. Write a detailed subagent objective

Give the subagent a self-contained, read-only research workstream. Include:

- the mission and intended downstream decision;
- background, known facts, and genuine disagreements;
- local materials to inspect before constructing the external prompt;
- prioritized questions when priorities are useful;
- primary-source and verification standards;
- the expected report shape and language;
- hard requirements, exclusions, and uncertainty rules;
- the command and archive-verification contract;
- the exact completion handoff expected by the parent.

Do not constrain the objective to a minimal answer, a small table, or a fixed
number of searches. Scope it around evidence quality and clear work ownership.
Do not impose a publication-date window unless the question is explicitly
current, time-sensitive, or historically bounded.

Use the delegation template in
[research-prompt-patterns.md](references/research-prompt-patterns.md), adapting
its sections rather than forwarding the user's request verbatim.

## 4. Require the subagent to run `pplx-ask`

The subagent must:

1. Confirm that `pplx-ask` is available and inspect `pplx-ask ask --help` when
   the installed CLI contract is uncertain.
2. Confirm the user-level config file exists before any network call: the
   explicit `--config` path when one is used, otherwise `$PPLX_EXPORT_CONFIG`,
   otherwise `~/.config/pplx-export/config.toml`. If none exists, pause and
   report to the user instead of proceeding in degraded mode.
3. Run `pplx-ask models` as the Perplexity connectivity-and-session probe and
   require the search-mode selectable-model table in its output. If the
   command fails or that table cannot be retrieved, pause and report to the
   user; do not launch the research run. This probe is needed once per
   conversation, before the first call only; repeat it only after a later
   call actually times out or fails with connectivity symptoms — backoff
   silence alone is not a trigger.
4. Construct a detailed Perplexity-facing prompt from the applicable reference
   pattern.
5. Pass the prompt as one process argument without re-evaluating its contents
   as shell syntax.
6. Use a private archive root outside any repository intended for publication.
7. Run deep-research mode with agent telemetry disabled and automatic export
   enabled, and always with the most verbose output — pass `-v` (and
   `--log-file` for unattended runs) so request traces and the "still waiting"
   heartbeats are visible and any failure is easy to locate:

   ```bash
   pplx-ask -v --out "$PPLX_ARCHIVE_ROOT" ask "$PPLX_RESEARCH_PROMPT" \
     --mode deep-research --no-telemetry
   ```

8. Increase `--timeout` only when the expected run needs it.
9. Budget wall-clock time for the whole run, not just `--timeout`: that flag
   only bounds the ask-side SSE stream, while the transport retries 429 / 5xx /
   network errors with backoff waits of up to 300 s each, so a long wait is
   normal, not a hang. At default verbosity these waits now print periodic INFO
   heartbeats (backoff countdown, in-flight request, and idle SSE stream), so a
   live run emits a "still waiting" line rather than going fully silent. Deep
   research alone can run tens of minutes — never wrap the command in a task
   manager with a short hard timeout (see [runtime budget for
   callers](https://pplx.iekseng.com/guide/rate-limiting/#runtime-budget-for-callers)).
   If a run is killed mid-stream anyway, the tool deliberately skips the
   export; the platform-side thread survives and can be archived afterwards
   with `pplx-export export <thread-uuid>`.
10. Never use `--no-export`.

Deep-research mode uses its platform-defined model. Do not pass `--models` or
hardcode a model identifier for this mode.

## 5. Wait for and verify the research package

Wait for the delegated workstream instead of treating launch acknowledgement
as completion. A successful CLI exit is necessary but not sufficient.

Require the subagent to locate the archive by the returned thread identity and
verify the exact `thread.json` identity. Require it to read the complete
`report.md` when present, use `conversation.md` as the fallback answer
artifact, and inspect the source and raw artifacts described in
[archive-and-source-handoff.md](references/archive-and-source-handoff.md).

Do not accept a handoff that contains only a short summary when the archived
report or returned-source inventory has not been inspected.

## 6. Integrate without overstating verification

Use the subagent's concise synthesis to orient the parent work, then consult
the archived report for detail. Preserve the complete returned-source
inventory by path and count; use a smaller claim-to-source map only for the
conclusions that drive the parent decision.

Distinguish:

- sources returned by Perplexity;
- sources materially cited in the report;
- sources independently opened and verified by the subagent or parent.

Never claim that all returned sources were independently checked unless that
work was actually performed. Surface conflicting evidence, inaccessible
primary sources, weak support, and unresolved questions in the final answer.
