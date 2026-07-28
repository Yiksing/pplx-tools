# Anti-pattern lessons

Twelve recorded pitfalls from this toolkit's history and the lesson each one
taught.

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
