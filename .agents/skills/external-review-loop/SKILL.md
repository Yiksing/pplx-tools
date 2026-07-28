---
name: external-review-loop
description: Run closed-loop external code reviews. Use when drafting review briefs, adjudicating findings, or landing fixes. Do not use for direct unreviewed fixes.
---

# External review loop

Battle-tested across five consecutive external review rounds on this codebase;
these patterns are what made later rounds measurably better than earlier ones.

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

## Core rules

- The quality ceiling of a review report lives in the brief, not in the
  reviewer: the same reviewer produced 3 findings from a minimal brief and 17
  zero-hallucination findings from an upgraded one.
- A brief mandates: read-only/no-network discipline (named commands), a fixed
  reading order, a per-file COVERAGE manifest, five-element findings
  (`file:line`, excerpt, scenario, fix, verification), confidence tiers with a
  suspected cap of 20%, an exclusion list, known intentional decisions, and
  personal verification of any subagent conclusion.
- Adjudication issues one of four verdicts per finding — accept, partially
  accept, reject, accept as confirmation — each with a written reason;
  default-reject proposals that escalate a transient error into a terminal
  state.
- Fixes land with regression tests in the same commit; `data:` and `docs:`
  changes get separate classified commits; a fix is not closed until the next
  brief verifies its disposition.

## References

- Read [references/brief-design.md](references/brief-design.md) only when
  writing or upgrading a review brief; it holds the eight brief design
  patterns, the quality-ceiling evidence, and the compact and full brief
  templates.
- Read [references/adjudication-and-landing.md](references/adjudication-and-landing.md)
  only when adjudicating a delivered report or landing accepted fixes; it
  holds the maintainer-side verdict patterns, the EVALUATION.md skeleton, and
  the seven fix-landing rules.
