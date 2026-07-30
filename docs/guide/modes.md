# Conversation modes

Perplexity conversations come in five modes: `search` / `deep-research` / `computer` /
`council` / `study`. The mode is detected per thread during export; it decides which API
responses are fetched, what lands in the thread directory, and which
[archive path](archive-layout.md) the thread gets (`<account>/<mode>/…`). The detected mode is
recorded in `thread.json` (`mode` key) and used by `pplx-export batch --mode` filtering.
`pplx-ask` can also *create* new threads in four of the five modes (all but
`computer`) — see [pplx-ask](pplx-ask.md).

## The five modes at a glance

| Mode | UI name / model | Turn content | Citations | Products | Schematized blocks fetched |
|---|---|---|---|---|---|
| `search` | "Best" (`pplx_pro`; labs `STUDIO`/`pplx_beta` also maps here) | Query + Answer, text steps | turn-level + thread-wide `sources.*` | — | No (`raw_blocks.json` absent) |
| `deep-research` | "Deep research" (`pplx_alpha`, fixed, no selector) | research steps incl. `RESEARCH_ANSWER` | yes | `report.md` (full report) | Yes |
| `computer` | Computer (`pplx_asi_opus`, `pplx_asi_opus_thinking`) | full `workflow_block`: narration, tool calls, sub-agent prompts/steps, per-step citations | per-step + turn + thread | versioned files in `assets/` + sub-agent runs | Yes |
| `council` | model council (`pplx_agentic_research`; three models by default) | `COUNCIL_RESEARCH` step; each model's nested `LLM_COUNCIL` workflow folded into `<details>` (search rounds, all sources, full per-model answer) | per-model + aggregated | per-model answers compared side by side | Yes |
| `study` | Study (`pplx_study`) | steps/citations via blocks (verified to also contain assets) | yes | assets when present | Yes |

## How the mode is decided

The detection authority is the platform's own field **`entry.search_mode`**
(`SEARCH_MODE_MAP`, `normalize.py:50-59`), collected across all entries
(`normalize.py:106-115`). It was verified against the official model config
(`GET /rest/models/config/v2`): `default_models.search=pplx_pro` (UI "Best"),
`default_models.research=pplx_alpha` (UI "Deep research"), and the values map one-to-one to
conversation modes:

| `search_mode` value | Mode |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`, `STUDIO` | `search` |

Conflict rules (`detect_mode`, `normalize.py:66-128`):

- **Mode switching inside one thread** (entries disagree): take the highest by specificity —
  **computer > council > study > deep-research > search** (`_MODE_SPECIFICITY`,
  `normalize.py:63`) — and `log.warning`.
- **Conflict with downstream signals** (step names / `display_model`): `search_mode` wins,
  `log.warning` (`normalize.py:120-123`).
- **`search_mode` entirely absent** → the original chain: URL contains `/computer/tasks/` or
  `metadata.mode == '4'` or index mode ∈ `ASI`/`COMPUTER` → `computer`; a `COUNCIL_RESEARCH`
  step → `council`; a `RESEARCH_ANSWER` step → `deep-research`; redundant `display_model`
  signal (`DISPLAY_MODEL_MODE`, `normalize.py:32-37`) wins on conflict; nothing hits →
  `search` by default.
- **All signals missing doesn't conclude search**: the pipeline still fetches the schematized
  blocks (`adapter.py:83-89`) so a platform field drift can't silently drop `raw_blocks.json`.

!!! note "Why `pplx_alpha` is not a detection cue"
    `pplx_alpha` is the RESEARCH-dedicated model — it is the *target* the classifier must
    detect, not evidence for detection, so it is deliberately excluded from the mapping table
    (`normalize.py:15-31` comment).

The full decision tree with every branch: [Export pipeline — mode detection](../architecture/export-pipeline.md).

## Where sub-agent payloads land

Computer/council runs spawn background sub-agent workflows. Each background
`workflow_payload` is rendered in **exactly one place, never twice**; at the user level the
three possible landing spots are:

1. **Anchored — inside the initiating turn**: the turn that started the sub-agent carries a
   matching payload id, so the run renders inline in that turn's work process
   (`turns/turn_NNNN.md`), with prompt, steps, answer, and sources.
2. **Stub turn — "子代理工作" (Subagent work) section**: a `subagent_result` stub turn within a
   10-second completion window absorbs the payload; the answer is not backfilled.
3. **Thread appendix — end of `conversation.md`**: everything left over (interrupted runs
   produce no completion notification, so the first two levels necessarily miss) is archived
   verbatim under "## 后台任务（未归入轮次）" (Background tasks (unassigned to turns)) — no
   time-attribution guessing, any status accepted.

Matching rules, data structures, and the single-consumption guarantees:
[Sub-agents & interruptions](../architecture/subagents-interruptions.md).

## Interruptions: non-COMPLETED workflows

Workflows that did not complete are annotated inline wherever they render — in work-process
headings, sub-agent headings, and nested `<details>` summaries. The three annotations
(`parsers.classify_wf_status`, `parsers.py:262-283`):

| Annotation | Condition | Meaning |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` (limit-interrupted — content stops at the interruption point) | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | spending limit exhausted; the workflow halted mid-run |
| `⏸ 中断待续` (interrupted, pending continuation) | `WORKFLOW_AWAITING_NEXT_STEPS` without `locked_reason` | interrupted, can be continued on the platform |
| `⛔ 已取消` (canceled) | `WORKFLOW_CANCELED` | canceled by user or platform |

- `COMPLETED` is never annotated (healthy threads get zero diff); unknown future status values
  stay silent.
- Every annotated case is also registered in `thread.json.interruptions` as
  `{location, kind, headline, status}` — locations look like `turn_0007`,
  `turn_0011/subagent`, `turn_0024/subagent_stub`, `background_unassigned`
  (`parsers.py:534-582`; key absent on healthy threads).
- **Resumption needs no special case**: when you continue an interrupted thread on the
  platform, its `lastUpdated` changes, the next incremental export re-fetches it, and the
  annotations simply disappear once the workflow completes. See
  [Incremental sync](incremental-sync.md).

Observed status values and distribution: [API responses & errors](../reference/api/api-responses-errors.md);
state machine: [Sub-agents & interruptions](../architecture/subagents-interruptions.md).

## Answer-rewrite variants (answer_variants)

When the platform rewrites an answer (A/B experiments), the replaced variant is invisible in
the API — only the selected answer is returned, while the losing sibling leaves a trace in
`entries[].side_by_side_metadata` and may later be purged (dead sibling links confirmed:
403 `VIEW_THREAD_NOT_ALLOWED`). The tool makes "a rewrite happened" observable:

- **Registration**: narrowed-criteria hits are written to `thread.json.answer_variants`
  (`fs_writer.py:247-252`; key absent without hits) and appended to the central registry
  `index/answer_variants_log.jsonl`, deduplicated by (thread, entry) and idempotent
  (`variant_log.py:76`).
- **Alerts**: a single grep-able WARNING line `ANSWER_VARIANT_DETECTED` with full locating
  fields (thread uuid/uuid8, entry_uuid, sibling_uuid, selection_status, experiment_role) on
  every online hit; `re-render` re-registers offline and warns only when content is added or
  changed, so library-wide reruns stay quiet; the batch summary appends a ⚠ hit count.
- **Manual re-archive**: sibling variants are empirically dead links, so the alternate answer
  usually **cannot be recovered via the API**. On a hit, promptly confirm the alternate answer
  by hand (platform UI, your own records, screenshots); if you get it, record it as
  `rewritten_answer_variant.md` inside the thread directory. If not,
  `thread.json.answer_variants` plus the jsonl registry are the final traceable record.

Detection chain and offline re-registration: [Offline operations](../architecture/offline-operations.md);
field semantics and dead-link evidence: [API responses & errors](../reference/api/api-responses-errors.md).

## Rendering fidelity principles

Regardless of mode, rendering follows the same fidelity contract:

- **Answers in full, never truncated** — the old `[:4000]` cap was removed because it cut
  sentences mid-way (`render.py:645-647`).
- **Tables never truncated** — `WORKFLOW_ITEM_TABLE` renders every row and column, escaping
  `|` and newlines in headers and cells so the Markdown structure survives
  (`render.py:211-243`).
- **Full citations** — three collection channels (`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`), deduplicated by URL into `sources.*`; nothing cited is dropped.
- **The API raw JSON is the content boundary** — everything rendered comes from
  `raw_entries.json` / `raw_blocks.json`; what the API does not return (e.g. a replaced answer
  variant) cannot be rendered, and is surfaced through registries instead of being invented.
- **UI folds, the archive expands** — detail the web UI hides behind folds and clicks
  (computer workflow narration and tool I/O, council per-model runs, sub-agent steps) is
  rendered in full; `<details>` blocks keep the document outline readable without losing
  information (`render.py:46`, `render.py:404-413`).
- **Structural robustness** — code fences are sized to their content (`_fence_for`,
  `render.py:28-43`) so tool output containing its own fences can't flip the pairing, and
  LaTeX delimiters are normalized to `$$` / `$` with code segments protected
  (`normalize_math_delims`).

How retained raw responses make all of this offline-regenerable:
[Export pipeline](../architecture/export-pipeline.md) and [Offline operations](../architecture/offline-operations.md).

## See also

- [Archive layout](archive-layout.md) — where each mode's files land
- [pplx-ask](pplx-ask.md) — creating new threads in each mode
- [Incremental sync](incremental-sync.md) — re-fetching continued threads
- [Export pipeline](../architecture/export-pipeline.md) — full mode-detection decision tree
- [Sub-agents & interruptions](../architecture/subagents-interruptions.md) — attribution waterfall and state machine
- [API responses & errors](../reference/api/api-responses-errors.md) — observed field values
