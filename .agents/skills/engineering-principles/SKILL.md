---
name: engineering-principles
description: Apply proven engineering heuristics for this toolkit. Use when designing fixes, attribution or rendering behavior, or weighing fidelity trade-offs. Do not use for platform API facts.
---

# Engineering principles

Design heuristics and anti-pattern lessons distilled from building and
maintaining this toolkit, generalized to be implementation-agnostic.

## Principles

### Mechanisms over special cases

When one instance breaks, first ask whether it is the first sighting of a
class of problems. A special-case patch fixes one instance; a general
mechanism covers future shapes you have not seen yet. Litmus test: can you
state the fix rule without naming any specific instance ID? Yes — mechanism;
no — special case, be wary.

### Deterministic resolution over heuristics

Prefer deterministic placement over "most likely" guesses. The
background-payload attribution waterfall (anchor → completion-stub window →
thread-appendix fallback) lands every payload in exactly one predictable
place instead of scoring "nearest" candidates. Wherever a guess would be
needed, fall back to a declared default plus faithful annotation.

### Raw data is the ultimate source of truth

Persist raw responses before any parsing; renderers may be buggy and may
evolve, but the raw archive never betrays you. Every "data fix" in this
project has actually been a render-layer fix — invest fidelity in the raw
layer and let the render layer iterate fast.

### Recompute offline before verifying online

For any "need to ask the platform" question, first squeeze the local raw
data dry. Online requests are a scarce, rate-limited resource; spend them
only on what offline analysis cannot yield: new data, freshness spot-checks,
and UI-layer behavior.

### Distinguish "no server-side data" from "fetch gap" — with evidence

Attribute a gap only with an evidence chain. "Probably missing" and "proven
absent" are separated by a re-fetch and a packet capture: empty
computer-mode answers were accepted as truth only after a re-fetch returned
data identical to the archive and UI expansion triggered zero data requests.

### A collapsed UI is not a data boundary

The UI's presentation is a product choice, not data truth. Content
boundaries always come from the API entries/blocks; "not visible on the
page" is never evidence of nonexistence — and vice versa.

### Terminal-state thinking: ledger permanent and transient separately

Error classification drives disposition: permanent states are recorded once
and never retried; transient states back off and retry; credential states
fail fast for a human. The two classic mistakes are upgrading a transient
to terminal (burying live data) and retrying a terminal state (burning
quota and tripping risk control).

### Idempotence is free insurance

Re-renders, backfills, incremental plans, and state writes are all
idempotent: interrupted runs resume, timeouts are safe to kill, errors
self-heal. Test: running the same command twice produces zero diff the
second time. Non-idempotent operations (migrations, deletions) are marked,
committed, and rollback-able separately.

### Single source of truth per semantic

One function owns one semantic (status classification, account table, mode
detection), consumed by every path that needs it. The moment a second
implementation of the same semantic appears, it is already drifting — or
will.

### Redundant signals; over-fetch on doubt

Platform fields change without notice, so mode detection keeps independent
signals and prefers the authoritative one. When classification is
uncertain, spend one extra fetch — the cost of one request is far below the
cost of a permanently missing raw artifact. Robustness to change means
assuming every field may vanish and asking "what do I have left?".

### Silent failure is the most dangerous failure

An unrecognized payload type once rendered silently as an empty string,
dropping hundreds of content segments unnoticed. Everything unrecognized
must leave a trace: a placeholder, a debug log, and a scannable registry
entry. Design default behavior so that losing things is loud and keeping
things is quiet.

### Limits are a defense line

Rate limiting is not an efficiency question but an account-survival
question: randomized human-like pacing, no API concurrency, jittered
backoff. Red-line values come from respect for the account holder's assets,
not from technical estimates.

### Review quality is capped by the brief

The same reviewer produced a handful of findings from a coarse brief and 17
zero-hallucination findings from a brief that fixed coverage manifests,
confidence tiers, and verification methods. Define "what counts as a valid
finding" before asking anyone — human or agent — to review.

### Tests are the renderer's lock

Byte-exact snapshot regression that reuses the production render path turns
any rendering change red immediately. The lock's value is not catching bugs
but making refactoring safe. Fixtures are trimmed from realistic archives,
and goldens interlock with them.

### Documentation is the next maintainer's context

Write docs for a zero-context successor: can someone safely onboard from
this document alone? Sync docs in the same batch as any fact change —
stale docs are worse than none.

### A rejected design is a review signal

Behind a "this is wrong" there is usually an unstated principle. Surface
the principle before redesigning; patching the surface keeps the wrong
shape. The best mechanisms in this codebase were born from rejections of
one-off fixes.

### Cross-check numbers across documents

When memory, docs, and code disagree on a number, trust the currently
recomputable data and unify every document to it. Any number verifiable
from two independent sources must not exist in a third value.

### Handoff mindset: today's work is tomorrow's archaeology

Clearly classified commits, synced docs, and behavior locked by tests let a
successor continue without a briefing. Write every commit message for a
stranger three months from now: the "why" matters more than the "what".

## Anti-pattern lessons

| # | Pitfall | Lesson |
|---|---|---|
| 1 | A comment claimed "model X is common in mode Y (121 samples)" — the 121 were the classifier's own misjudgments | Your classifier's output is not platform fact; verify against the authoritative field before recording statistics |
| 2 | A missing `completed_at` field treated as an interruption signal | It is noise — most normal completions leave it empty too; trust only explicit reason/status enums |
| 3 | Table cells truncated to 80 characters, citations to 20 | Every truncation eats fidelity, and at the time it always feels "good enough" |
| 4 | Answer extraction handled only the plain-FINAL shape | Shapes outside the guard condition are the norm — computer-mode FINAL is usually a dict without an answer key |
| 5 | Batch and transport layers each held their own throttle | Shared-resource ownership must be explicit; split counters plus no reset on success pins backoff at maximum |
| 6 | The "deleted" assumption: 404 mapped straight to a terminal expired state | A transient (propagation delay right after creation) gets buried forever; keep 404 retryable |
| 7 | Subagent result items dropped when no background match existed | Fallback branches must still render placeholder content, or whole step groups vanish silently |
| 8 | The first external review brief was too coarse | Report quality is capped by the brief (3 findings vs 17 from the same reviewer) |
| 9 | Stale wording left in the README after the detection mechanism changed | Docs drift silently; sweep for stale statements in every change batch |
| 10 | A backfill path downloaded inline, bypassing magic-number sniffing | Two code paths for the same need: one always does less (a PNG ended up saved as .bin) |
| 11 | Names containing spaces broke whitespace-split path parsing | Any code that splits paths on whitespace must pass a space-containing sample first |
| 12 | Subagent citations were missed by the conversation-level aggregate until render time | Aggregation rules must be fixed in the data-model layer, or every consumer leaks a little |
