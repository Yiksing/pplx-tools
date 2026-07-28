# Adjudication and fix landing

Maintainer-side adjudication patterns, the EVALUATION.md skeleton, and the
fix-landing discipline.

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
