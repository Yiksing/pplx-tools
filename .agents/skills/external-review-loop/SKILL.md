---
name: external-review-loop
description: Run closed-loop external code reviews. Use when drafting review briefs, adjudicating findings, or landing fixes. Do not use for direct unreviewed fixes.
---

# External review loop

## Origin

Battle-tested across five consecutive external review rounds on this codebase;
the patterns below are what made later rounds measurably better than earlier ones.

## Loop overview

```text
write brief -> independent read-only review -> REPORT.md + COVERAGE.md
  -> maintainer re-reads the cited code, item by item -> EVALUATION.md
  -> classified commits (fix: / data: / docs:) -> artifacts archived
  -> next round's brief (prior changes re-reviewed, past lessons baked in)
```

Two iron rules: (1) the reviewer is read-only and the maintainer personally
re-reads the cited code before any finding enters a verdict or a fix; (2) every
round's outputs land as new `_vN`-suffixed files, never overwritten — archived
rounds are the next round's review index.

## Brief design patterns

1. **Read-only and no-network discipline first; violation voids the review.**
   Only the round's own outputs may be written. Name every command that secretly
   hits the network — implicit startup requests included, reason in parentheses —
   not a generic "no network". Allow-list: read files, grep/glob, offline tests,
   `--help`, read-only scripts, git log/show. No git writes.
2. **Fixed reading order.** Repo manual, design docs, API reference, tool README
   before code, plus orientation: what the object is, file/line counts, pipeline.
3. **Per-file COVERAGE manifest, a hard deliverable.** Every source file listed
   with path, line count, "fully read" mark, one duty comment. State the expected
   count (with the `find` self-check) so sampling cannot pass as coverage; any
   unread file means the review is incomplete. The single largest quality jump.
4. **Five-element findings.** Exact `file:line`, short code excerpt, trigger
   scenario, suggested fix, verification method — an unverifiable finding is
   invalid. For top findings, attach a rerunnable read-only forensic script.
5. **Confidence tiers with a cap.** confirmed (full logic chain verified) /
   likely (strong signs) / suspected (guess — at most 20% of findings).
   "Nothing found, paths checked: ..." is a valid result.
6. **Exclusion list.** Require a "checked but not a problem" section with
   reasons, so the adjudicator never wonders whether an area was missed.
7. **Known intentional decisions list.** Documented deliberate designs and
   proven facts go into the brief, each with its source document; when unsure,
   the docs win.
8. **Subagent conclusions must be personally verified.** Parallel module
   reviewers are allowed; forwarding conclusions unverified is not. Record a
   test baseline first ("expect N passed; if not, record, then review").

## Why the brief is the ceiling

Same reviewer capability, two rounds: a minimal brief produced 3 findings with
missing mandated sections and thin, unverifiable coverage; an upgraded brief
produced 17 findings with zero hallucinations (9 confirmed / 7 likely /
1 suspected = 5.9%), a complete coverage manifest, and correct verification of
the previous round's dispositions. The quality ceiling of a review report lives
in the brief, not in the reviewer.

## Adjudication patterns (maintainer side)

- Re-read the **current** code at each cited `file:line` — report excerpts may
  have drifted. Never batch-adopt.
- Four verdicts, each with a written reason: **accept** (true, fix sound — land
  it, noting fix point and new tests); **partially accept** (observation true,
  advice wrong — take one, reject the other, justify both); **reject** (record
  why, so the next round does not re-report); **accept as confirmation** (no action).
- Default-reject proposals that escalate a transient error into a terminal
  state: terminal means never retry, and a misjudgment buries live data forever.
  Mapping 404 to "expired" would bury threads only briefly invisible right after
  creation; keeping 404 retryable is the safe behavior. Accept a terminal state
  only from an explicit server error body; fail-fast only on repeated auth errors.
- Reserved modules reported as dead code: do not delete; annotate the intent more
  visibly, or — when the same item keeps being re-reported — simply fix the
  underlying smell. Drive the cost of a false positive to zero.

## EVALUATION.md skeleton

```markdown
# EVALUATION — adjudication of <report> (<date>)
Adjudicator: <role>. All N findings re-verified against current code.
## Report quality   # form compliance vs content trust, separately
<coverage/summary/confidence/exclusions? suspected share? zero hallucinations? vs previous round>
## Item-by-item verdicts
| ID | verdict | action / reason |
**Exclusion-list review**: <were the reviewer's exclusions correct?>
## Disposition record
- fix: <files, tests N->M, new regression cases>
- data: <re-render/backfill scope; blast radius>
- docs: <behavior sync; review artifacts archived>
```

## Fix-landing discipline

1. Fix and regression tests land in the same commit — never fix now, test later.
2. A fix that alters stored artifacts gets a separate `data:` commit stating the
   affected scope, proving the blast radius is known.
3. Behavior changes sync the docs in the same round as a separate `docs:` commit;
   otherwise the next round reports doc drift as new findings.
4. Review artifacts are committed apart from fixes — reports are evidence.
   Classify commits `fix:` / `data:` / `docs:` / `test:` and book dispositions to them.
5. The next brief must contain a "verify prior dispositions" section; a fix is
   not closed until verified.
6. Content-loss claims need full-library forensics: the decisive test is a
   whole-library raw-vs-product comparison plus a zero-diff re-render, not
   single-point code reading — a redundant channel may already render the
   content. Medium severity and above requires a rerunnable evidence script.
7. External output contract changes must first grep consumers for backward
   compatibility; failure semantics stay falsy; new information goes into new
   keys — never reshape existing keys' shape or semantics.

## Appendix A — compact brief template (small-scope read-only review)

```markdown
# Task: read-only review of <repo/dir>
## Discipline (violation voids the review)
1. Read-only; the only allowed write is <out>/REPORT.md.
2. No network: do not run <name each networked command, incl. implicit entry
   points, with reasons>. Allowed: read, grep/glob, <offline tests>, git log/show.
3. No git writes.
## Onboarding: read <manual> -> <design docs> -> <README>. Object: <dir>
(<N> files, ~<M> lines) — one-sentence role and pipeline.
## REPORT.md sections: scope & method; summary table (ID/severity/confidence/
location/one-liner); finding details; unverified & excluded list; overall
assessment. Five elements per finding: file:line, excerpt, scenario, fix,
verification method. Confidence: confirmed/likely/suspected (<=20%).
## Known intentional decisions (do not report): <each with source doc>
```

## Appendix B — full brief template (exhaustive review, round <N>)

```markdown
# Task: exhaustive review of <dir> in <repo> (round <N>)
## Background: <reading order>; <N-1> prior rounds archived at <dir> — verify
each prior fix holds with no regressions; do not re-report fixed items.
## Lessons from prior rounds (from round 3 onward)
1. Data findings need full-library forensics; a redundant channel may already
   render the content — the test is a whole-library diff, not code reading.
2. External contract changes: grep consumers, falsy failure semantics, new keys.
3. Severity and data impact scored separately: "path exists, zero library
   instances" caps at low; medium+ needs a rerunnable evidence script.
## Iron discipline: read-only except own _vN outputs; no network (name every
entry point); no git writes.
## Scope: every source file fully read — no sampling. COVERAGE_<vN>.md lists
path/lines/read-mark/duty per file; self-check the count (<N> files) via find.
## Dimensions: correctness and edge cases; regression risk in the last round's
new code; coupling and duplicated responsibilities; error-path semantics;
dead/duplicated code; test gaps and silently stale goldens; doc drift.
## Known intentional decisions (do not report): <list, each with source doc>.
## Method: record the test baseline first; subagents allowed but every finding
personally re-verified; five-element findings; forensic scripts for top
findings; confirmed/likely/suspected, suspected <=20%; "found nothing" with
paths checked is a valid result.
## Outputs (all _<vN>): REPORT (scope / summary / details / exclusions /
assessment / prior-disposition verification), COVERAGE, findings/ scripts.
```
