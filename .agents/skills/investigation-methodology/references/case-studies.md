# Investigation case studies

The three real investigations behind the cross-case principles in SKILL.md,
with the case narratives generalized to their decision-relevant shape.

## Case 1: the empty-answer investigation

**Symptom.** A library-wide check found a set of computer-mode turns,
spread over several threads, whose rendered answer was empty — the archive
holds no final answer text for those turns.

**Hypothesis H1: fetch gap.** The export pipeline dropped data; the answers
exist server-side but never reached the archive. Suspecting yourself first
is also the cheapest hypothesis to falsify.

**Step 1 — API re-fetch comparison.** Several affected threads were
re-fetched in full through the same API and compared field by field against
the archived raw files: identical, and the empty positions stayed empty.
H1 was essentially excluded — unless the UI reads a different data channel.

**Step 2 — browser packet capture.** A real browser opened the same thread
and a human expanded the collapsed "N steps completed" bars and subagent
chips while all network traffic was recorded: zero content requests — only
static assets and analytics events. Every piece of collapsed content had
been delivered with the initial thread load, so the UI and the API share
one source, and the UI simply has no answer text to show either.

**Conclusion.** The server has no answer for these turns; they are
unrecoverable, and the archive is complete. Disposition shifted from "data
recovery" to "faithful presentation": render the answer as empty, never
backfill invented text. Precision matters: only a subset of these turns
sits in threads whose entries carry `locked_reason=spending_limit_exceeded`;
the rest carry no server-side marker at all — the spending limit is the
largest single identified cause, not the only one.

**Side discovery.** Surveying the raw files during the investigation
surfaced roughly 300 nested subagent workflow payloads — about half with
complete steps and around 140 with embedded answers — that the renderer had
never displayed. The "unrecoverable" investigation thus spawned a pure
render-layer fix that needed no re-fetching at all.

## Case 2: the model-attribution misjudgment

**Old claim.** A code comment stated that a certain model id was "commonly
used in ordinary sessions (121 samples versus 93)", and deliberately
excluded it from the mode-detection mapping to avoid "mass
misclassification".

**The doubt: circular reasoning.** The 121/93 statistic's denominator was
the old classifier's own output. If some premium-mode sessions lacked the
step the old chain relied on, they were judged ordinary and then counted as
evidence that the model is common in ordinary sessions. Using a
classifier's output to argue about the distribution of its input features
proves nothing.

**Step 1 — offline census.** Every entry carries the platform's
authoritative session-mode field. A full-library census on local raw data
(zero network) showed that 100% of the threads using that model id were
actually the premium research mode. The old statistic collapsed.

**Steps 2–4 — triple independent online verification.** The official
model-config endpoint mapped the default models to their modes; API
re-fetches of suspected misclassified threads reproduced the misjudgment
and exposed the root cause (a premium session missing the relied-upon step
fell back to ordinary); and the UI model picker did not offer that model in
ordinary mode at all. Three mutually independent sources, one conclusion.

**Fix and migration.** The detection chain now takes the authoritative
field as its highest-priority signal, with a specificity ordering for
mixed-mode threads and the old chain kept as fallback. Because overturning
a conclusion without migrating existing data would leave the archive half
right and half wrong, every archived thread was re-judged: about 124
misfiled threads were moved, each change recorded in a per-thread migration
report, and the missing raw artifacts of the affected threads were
backfilled. Re-rendering produced the previously hidden workflow output in
migrated threads and zero diff everywhere else.

**Lessons.** A classifier's output cannot serve as evidence about the
classifier — anchor platform-authoritative fields or official
configuration, never your own inference chain's intermediate products. And
comments that carry statistics are debt: a confidently written "measured
121 versus 93" hid the misjudgment for months, so always state the
determination basis alongside the numbers.

## Case 3: the orphaned background payload

**Symptom.** In one computer-mode thread, a background workflow payload —
38 steps, no conclusion — matched no anchor in the main entries and no
completion-stub turn, so both levels of the attribution waterfall
necessarily missed it.

**Mechanism analysis before solution.** A completion-stub turn is the
notification the server emits when a subagent finishes; an interrupted
background task never produces one, so the time-window stub matching can
never fire for it. The orphan was not a bug but an inevitable product of
the interruption semantics — and any one-off special path for this payload
would only patch the mechanism gap, leaving the next interrupted thread to
leak again.

**Decision.** The one-off fix was rejected in favor of a general mechanism:
a third waterfall level, the thread appendix. Every payload left unconsumed
by the first two levels — any status, present or future — is rendered
faithfully at the end of the conversation document, with no time-attribution
guessing, and lands in exactly one place. Supporting pieces: one
status-classification function feeds the renderer, the machine-readable
registry, and the warning path (healthy threads get zero annotations and
zero diff); interruption entries live in `thread.json` and can be added or
removed offline in place without re-fetching; threads continued after an
interruption are picked up by incremental sync with no special code.

**Lessons.** When a special case is rejected, write down the causal chain
of "why it must miss" first — with that proof, the general solution sells
itself. And the fallback level's job is fidelity, not reconstructing the
scene: show everything, guess nothing.
