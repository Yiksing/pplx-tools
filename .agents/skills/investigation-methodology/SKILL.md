---
name: investigation-methodology
description: Investigate archive anomalies with evidence chains. Use when attributing data gaps, overturning suspected misjudgments, or planning verification. Do not use for routine fixes with known causes.
---

# Investigation methodology

Reusable investigation principles distilled from three real investigations
carried out while building this toolkit's archive pipeline: case 1, the
empty-answer investigation; case 2, the model-attribution misjudgment;
case 3, the orphaned background payload.

## Cross-case principles

1. **Recompute offline first, verify online after.** The raw archive is
   already on disk; do not spend rate-limited online budget on questions
   local data can answer. (Case 2 ran a full-library census before any
   request; case 1's payload survey and case 3's distribution recount were
   purely local.)
2. **Raw data over inference.** Raw responses are the highest truth;
   renders, statistics, and code comments are derivatives. (Case 1 judged
   the empty turns from raw; case 2's old comment was overturned by a raw
   recount.)
3. **Packet-capture falsification.** When UI and API behavior must be
   compared, count requests instead of guessing at hidden channels: zero
   data requests on expansion means the UI and the API share one source.
   (Case 1's decisive experiment.)
4. **Mechanism over special case.** Prove the causal chain of "why this
   must miss" before designing the general fallback. (Case 3's third
   waterfall level; case 2 rewrote the whole detection chain on the
   authoritative field instead of adding patch rules.)
5. **Cheapest falsifiable hypothesis first.** (Case 1 re-fetched a few
   threads before running browser experiments; case 2 did the local census
   before the triple online checks.)
6. **Overturning an old conclusion requires existing-data migration plus
   records.** Fixing only the logic leaves the archive half right and half
   wrong; migrate with a per-item report so every change stays traceable.
   (Case 2's thread migration report; case 3's registry backfill.)
7. **"Unrecoverable" is also a conclusion; faithful annotation beats
   backfill.** The goal of an investigation is to establish the truth, not
   to make the numbers look complete. (Case 1's answers kept empty; case
   3's orphaned payload displayed as "no conclusion".)
8. **Single source of truth; healthy paths stay zero-diff.** One
   classification function feeds every consumer, and normal cases get no
   annotation at all. (Case 3's shared status classifier; case 2's
   re-render produced zero diff outside the migrated threads.)

## References

- Read [references/case-studies.md](references/case-studies.md) only when a
  cited case's full narrative is needed — its symptom, hypotheses,
  verification steps, conclusion, migration record, and lessons — to model a
  new investigation on or to challenge a principle's evidence.
