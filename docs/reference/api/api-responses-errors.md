# API Response Structure and Error Semantics

*Part of the Perplexity web API reference — full map at the [API index](index.md).*

## Response structure essentials (parsing discipline)

- **Raw data retained in successful archives**: `raw_entries.json` (plain) and
  `raw_blocks.json` (schematized, when fetched) are stored alongside the rendered
  artifacts; parsing/rendering can be re-run offline (`pplx-export re-render`)
  without re-fetching.
- **Field extraction centralized** in `sites/perplexity/parsers.py` (schema drift only needs one place changed).
- Mode detection (`normalize.detect_mode`; decision tree in [export-pipeline.md](../../architecture/export-pipeline.md)): the highest-priority signal is the
  **`search_mode`** field of any entry (mapping at the end of [§3.9](api-rest-endpoints.md)); when all signals fail, fall back — computer = URL
  `/computer/tasks/` or metadata.mode=="4" or index mode ∈ {ASI,COMPUTER}; council = a
  COUNCIL_RESEARCH step exists; deep-research = a RESEARCH_ANSWER step exists (content-based, not relying on Chinese labels);
  otherwise search.
- The computer UI collapses everything — **always go by the API entries/blocks**; never use UI text as the content boundary.
- Subagent dual channel (discovered 2026-07-19): prompt in schematized `workflow_payload.objective_chunks`;
  steps/conclusion in plain `background_entries`; linked via `workflow_payload.id` (`toolu_X`).
- `WORKFLOW_ITEM_SOURCES` items often carry `text_payload`
  (subagent page-extraction text / comparison tables; 450 occurrences library-wide, 408 inside background nested payloads)
  in addition to `sources_payload.sources` (link list);
  the same content appears both in the plain background entry's `text` embedded step JSON and in the schematized nested payload —
  anchored subagents rendered via the plain path already preserve the text (library-wide check 2026-07-22: 408/408 present, none missing).
- **`related_queries` / `related_query_items` (settled 2026-07-23)**: each entry carries
  **next-question prompt recommendations** — follow-up suggestions the platform generates for a completed answer; `related_queries` is an array of recommendation texts,
  `related_query_items` the structured items (uuid/upsell_type, etc.). Forensic conclusion: an item's uuid
  **is not a thread uuid** (0/988 cross-match against library thread uuids), and recommendation texts have zero overlap with other threads' queries —
  **not resolvable into inter-thread relations for now**; the hypothesis of "pre-allocated thread uuids (materialized on click)" remains unverified.
  The data is naturally preserved in the archive `raw_entries.json` (hits in over half the threads of one archive library); no extra collection action needed;
  the relations graph builds no edges from it.

## Error and risk-control semantics

| Symptom | Meaning / handling |
|---|---|
| 403 (with cf challenge page) | Cloudflare block (TLS fingerprint / rate control) — back off; urllib + browser cookies generally don't trigger it |
| 401 / API-level 403 (no cf challenge page) | Session cookie expired/invalid — the tool raises immediately, no backoff; batch fail-fasts after 3 consecutive auth failures (update the cookie) |
| 429 | Rate limiting — exponential backoff (implemented in the tool) |
| 5xx (500/502/503/504) | Transient server errors (504 commonly a Cloudflare timeout) — back off and retry (implemented in the tool) |
| ENTRY_EXPIRED | Purged by the platform (~3 months) — terminal, do not retry |
| ENTRY_DELETED | Deleted by user/remote (also HTTP 400, different code) — terminal `deleted`, do not retry |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED` (HTTP 200) | Current account cannot view the space — retry with an account that can |
| `error_code: VIEW_THREAD_NOT_ALLOWED` (HTTP 403) | Current account cannot view the thread (tested 2026-07-23: sibling-variant uuid probing; the object exists but is inaccessible, not "nonexistent") |
| `status:"failed"` empty data | Same class (the get_collection failure form) |

**Rate-limit discipline (anti-ban, explicit user requirement)**: random 10–20s between batch threads, no concurrency, 429/403 backoff, 5xx backoff-retry;
pagination ≥3s; schematized re-fetch ≥4s; space metadata fetch ≥3s. Single-thread export = 1–2 requests ≈ opening the page once.

### Interruption semantics — observed values (2026-07-22; classification source of truth: `parsers.classify_wf_status`)

The `locked_reason` field: appears in `thread_metadata` / `entries[]` / `background_entries[]`
(on both the plain and schematized sides). Only observed value:

| locked_reason | Meaning | Observed distribution |
|---|---|---|
| `spending_limit_exceeded` | spending-limit interruption (quota exhausted; the workflow halts at the interruption point) | exactly one thread library-wide (markers in both raw_entries and raw_blocks) |

Workflow status field (`workflow_block.status` and nested `workflow_payload.status` share the same enum) observed values:

| status | Semantics | Render annotation (COMPLETED gets none) |
|---|---|---|
| `WORKFLOW_COMPLETED` | normal completion | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | awaiting next steps; with `locked_reason=spending_limit_exceeded` it is a **spending-limit interruption** (content stops at the interruption point); without locked_reason, interrupted pending continuation | `⏸ 限额中断（内容截至中断点）` (⏸ limit-interrupted — content stops at the interruption point) / `⏸ 中断待续` (⏸ interrupted, pending continuation) |
| `WORKFLOW_CANCELED` | canceled (user/platform abort) | `⛔ 已取消` (⛔ canceled) |

- `WORKFLOW_CANCELED` observed 19 times (16 main + 3 nested), across 7 computer threads
  (a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff).
- Note: the main-entry anchor payload's status may lag (observed anchor COMPLETED while the background was actually CANCELED) —
  a subagent's true status is the background-side `workflow_block.status`.
- Interrupted background tasks produce no subagent_result completion notification; unconsumed background payloads fall back to the thread appendix
  (see "attribution waterfall" in [subagents-interruptions.md](../../architecture/subagents-interruptions.md)).
- Empty answers in computer mode (double-verified 2026-07, unrecoverable): in computer mode, some turns have an
  empty answer because the server simply has none — an API re-fetch returns data identical to the archive, and
  expanding the UI's "N steps completed" bar triggers zero data requests (pure client-side rendering; the UI and
  the API share one source), so the API cannot recover them. Only a subset of such turns is linked to
  `locked_reason=spending_limit_exceeded`; the rest carry no server-side marker.

### `side_by_side_metadata`: answer-rewrite variant signal (settled 2026-07-23)

Field path: `entries[].side_by_side_metadata` (plain `/rest/thread/<uuid>` response).
When the platform generates multiple answer versions for the same query (A/B experiment or rewrite), this is the
only trace left on the currently active entry — **the replaced variant's body (text/steps/citations) is not in the thread API response** (real case
b2d2632b: the response has only 1 entry, 1 FINAL; variant 2 completely invisible).

Observed keys and values (evidence: b2d2632b raw; library-wide scan of 2442 entries):

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| Key | Semantics (observed/hypothesized) |
|---|---|
| `sibling_uuid` | Points to the **sibling answer variant** of the same query (another entry/context identifier). 7 threads hit library-wide; **online forensics (2026-07-23) confirm a dead link**: both accounts' `GET /rest/thread/<sibling_uuid>` return 403 `VIEW_THREAD_NOT_ALLOWED` (not 404/ENTRY_EXPIRED — the server recognizes it as an existing but unviewable object), and opening `/search/<sibling_uuid>` in the browser (owner account) gets SPA-redirected back to home — replaced variants cannot be recovered via sibling_uuid |
| `selection_status` | `SELECTED` = this entry's answer is the version chosen for display; control-group instances are all `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | Experiment role. The control group carries a `[control]` prefix (6 cases library-wide: `[control]default-model-class:gpt41`, etc.); the real case has no prefix (`override-default-model-class:qwen3_instruct-01f7f`, i.e. the treatment group of a model-override experiment) |
| `experiment_override` | Experiment override parameters (e.g. `override-default-model-class: qwen3_instruct`); observed only on treatment-group instances |
| `execution_log` | Observed as an empty object; semantics unknown |

**Narrowing criteria** (distinguishing "genuine rewrite keeping both versions" from "routine A/B control"):
`sibling_uuid` non-empty AND (`selection_status` non-empty and not `SELECTION_STATUS_UNSPECIFIED`,
OR `experiment_role` without the `[control]` prefix) → **only b2d2632b hits** among the 2442 entries library-wide
(the only confirmed real case; precision/recall are both 1 on this library, but n=1 cannot be extrapolated).

Tool behavior: `parsers.collect_answer_variants` extracts hits; `adapter.get_thread`
logs a warning + writes `thread.json.answer_variants` (key absent when no hits);
`re-render --thread-json` adds/removes in place (idempotent). Time evidence: the real case's entry `created→updated`
delta is 53.66 s (generated at 17:13, then rewritten/selected), and the rewrite advanced the thread-level `lastUpdated` (an incremental re-export
can trigger a re-fetch, but the re-fetched response still contains only the active answer; old variants are unrecoverable).

**Detection log and handling flow (2026-07-23, `sites/perplexity/variant_log.py`)**:

- **Log marker**: each hit emits a single WARNING line with the uniform greppable marker `ANSWER_VARIANT_DETECTED`,
  including all locating fields and handling guidance, shaped like:
  `ANSWER_VARIANT_DETECTED thread=<full uuid> uuid8=<8 chars> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | action: …`
  The online path (`adapter.get_thread`) outputs on every actual fetch hit; offline `re-render`
  **outputs only when registered content is added/changed** (idempotent re-runs don't spam); `batch` also passes through a one-line
  hit-count reminder at the end summary (without breaking the existing summary format).
- **Central registry**: `<out>/index/answer_variants_log.jsonl` (**a checked-in file**, not under the
  gitignored `logs/`) — one JSON per line (detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role), deduped by (web_uuid, entry_uuid); repeated exports/re-renders don't append endlessly;
  detected_at keeps the first-seen time.
- **Recommended action on hit**: siblings are empirically dead links (see the table above); the alternate answer usually
  **cannot be recovered via the API** — promptly confirm manually whether the alternate answer is still obtainable (platform conversation side / user memory / screenshots); if obtainable,
  record it manually as a `rewritten_answer_variant.md` file in the thread directory; if not, `thread.json.answer_variants` +
  the jsonl registry serve as the final traceable record.
