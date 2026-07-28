---
name: engineering-principles
description: Apply proven engineering heuristics for this toolkit. Use when designing fixes, attribution or rendering behavior, or weighing fidelity trade-offs. Do not use for platform API facts.
---

# Engineering principles

Design heuristics and anti-pattern lessons distilled from building and
maintaining this toolkit, generalized to be implementation-agnostic.

## Core rules

- **Mechanisms over special cases.** If the fix rule cannot be stated without
  naming a specific instance ID, it is a special case — be wary.
- **Deterministic resolution over heuristics.** Prefer predictable placement;
  where a guess would be needed, use a declared default plus faithful
  annotation.
- **Raw data is the ultimate source of truth.** Persist raw responses before
  parsing; fix fidelity in the raw layer, iterate fast in the render layer.
- **Recompute offline before verifying online.** Spend rate-limited requests
  only on what local raw data cannot answer.
- **Distinguish "no server-side data" from "fetch gap" — with evidence.**
  Attribute a gap only after a re-fetch comparison and packet-capture proof.
- **A collapsed UI is not a data boundary.** Content boundaries come from the
  API entries/blocks, never from what the page shows.
- **Terminal-state thinking.** Ledger permanent and transient errors
  separately; never upgrade a transient to terminal or retry a terminal state.
- **Idempotence is free insurance.** Running the same command twice must
  produce zero diff the second time; mark non-idempotent operations apart.
- **Single source of truth per semantic.** One function owns each semantic;
  a second implementation is already drifting.
- **Redundant signals; over-fetch on doubt.** Assume every platform field may
  vanish; one extra fetch is cheaper than a missing raw artifact.
- **Silent failure is the most dangerous failure.** Everything unrecognized
  leaves a trace: placeholder, debug log, registry entry.
- **Limits are a defense line.** Rate limits protect the account, not
  efficiency: human-like pacing, no API concurrency, jittered backoff.
- **Review quality is capped by the brief.** Define what counts as a valid
  finding before asking anyone to review.
- **Tests are the renderer's lock.** Byte-exact snapshots on the production
  render path make refactoring safe.
- **Documentation is the next maintainer's context.** Sync docs in the same
  batch as any fact change.
- **A rejected design is a review signal.** Surface the unstated principle
  behind "this is wrong" before redesigning.
- **Cross-check numbers across documents.** Trust the currently recomputable
  data and unify every document to it.
- **Handoff mindset.** Write commits, docs, and tests for a zero-context
  successor; the "why" matters more than the "what".

## References

- Read [references/principles.md](references/principles.md) only when a core
  rule above needs its full rationale, litmus test, or the project evidence
  behind it before you apply or challenge it.
- Read [references/anti-pattern-lessons.md](references/anti-pattern-lessons.md)
  only when checking a planned change against the twelve recorded pitfalls,
  or when a new failure resembles a past one.
