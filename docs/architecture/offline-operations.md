# Offline operations

The zero-network side of `pplx_export`: offline regeneration from raw JSON, the relations
rebuild pipeline, index enrichment backfills, the remote-deletion state machine, and the
answer_variants detection chain. Sections keep their original numbering from the
[architecture overview](overview.md).

---

## Offline regeneration (re-render)

After render-layer fixes, regenerate all artifacts from raw JSON **with zero network**, idempotently.
Implementation: `commands/rerender_cmd.py` (single-thread `rerender` rerender_cmd.py:105-190;
batch `cmd_rerender` rerender_cmd.py:193-212).

```mermaid
flowchart TD
    IN[("&lt;out&gt;/*/*/*/raw_entries.json<br/>glob all thread directories (rerender_cmd.py:199)")] --> CHK{"raw_entries.json exists?"}
    CHK -->|"no"| SKIP["skip (counted as skipped)"]
    CHK -->|"yes"| P1["parse_turn per entry (parsers.py:172)<br/>sort by created_us, re-number index<br/>(rerender_cmd.py:57-60)"]
    P1 --> P2["Conversation rebuilt<br/>metadata = thread_metadata (rerender_cmd.py:65-70)<br/>conv._plain = doc"]
    P2 --> P3{"raw_blocks.json exists?"}
    P3 -->|"yes"| P4["conv._blocks loaded (rerender_cmd.py:91)<br/>PerplexityAdapter(None).sub_agents builds sub_map<br/>(None-transport pure data assembly, rerender_cmd.py:84-88, 138)"]
    P3 -->|"no"| P5["sub_map = {}"]
    P4 --> P6{"mode in computer/council?"}
    P6 -->|"yes"| P7["attach_workflow_blocks (rerender_cmd.py:93)<br/>attach_stub_workflows (rerender_cmd.py:97)<br/>collect_unconsumed_background (rerender_cmd.py:101)"]
    P6 -->|"no"| P8
    P5 --> P8["render_conversation → conversation.md<br/>render_turn × N → turns/turn_NNNN.md<br/>(rerender_cmd.py:170, 189)"]
    P7 --> P8
    P8 --> TJ{"--thread-json?"}
    TJ -->|"no"| OUT(("done: other files untouched"))
    TJ -->|"yes"| TJ1["collect_interruptions(conv, sub_map) (rerender_cmd.py:150)<br/>answer_variants rebuilt with load_archived's same implementation (rerender_cmd.py:83)"]
    TJ1 --> TJ2{"compare the two keys<br/>interruptions / answer_variants<br/>against existing thread.json"}
    TJ2 -->|"content changed"| TJ3["add/remove the two keys in place, then write; all other fields kept as-is (round-trip indent=1)<br/>(rerender_cmd.py:141-169)<br/>warn + append jsonl registration when variants are added/changed<br/>(rerender_cmd.py:163-166, see §18)"]
    TJ2 -->|"no change"| TJ4["no write — avoids library-wide mtime/diff noise"]
```

Discipline:

- **Zero network**: `PerplexityAdapter(None)` only reuses pure data-assembly methods; no online
  method (get_thread etc.) is ever called.
- **Idempotent**: artifacts depend only on raw + renderer; reruns are byte-identical
  (guaranteed by the snapshot regression tests, [§13](../development/testing-architecture.md)).
- **Other files untouched**: sources, report.md, assets stay as-is; thread.json is untouched by default —
  with `--thread-json` only the two keys interruptions / answer_variants are added or removed.
- `--dry-run` only lists directories without writing files (rerender_cmd.py:204-206); `--limit N` takes the first N.

---

## relations offline rebuild pipeline

`cmd_relations` (misc_cmd.py:16) rebuilds the library-wide conversation relations graph from
archived raw data **with zero network**: it reuses re-render's offline rebuild pipeline
`load_archived_conversation` (rerender_cmd.py:34) to restore each Conversation (turn parsing/
sorting/numbering, _plain/_blocks attachment), fills conversation-level `conv.sub_agents` via
`adapter.sub_agents` thread by thread (misc_cmd.py:70-73; the export pipeline does not backfill
this field, models.py:178-182); the computer answer fallback (`wf_block_answer`) backfills
`turn.answer` at this layer, widening the references scan surface (misc_cmd.py:74-79). Threads
without raw data degrade to a thread.json + conversation.md shell (only same_space / bare-uuid
edges can be detected, misc_cmd.py:61-66).

```mermaid
flowchart LR
    RAW["web_archive/*/*/*/raw_entries.json<br/>+ raw_blocks.json"] --> LA["load_archived_conversation<br/>(rerender_cmd.py:34, zero network)"]
    LA --> SUB["adapter.sub_agents → conv.sub_agents<br/>(misc_cmd.py:70-73)"]
    LA --> FB["wf_block_answer backfills turn.answer<br/>(misc_cmd.py:74-79)"]
    SUB --> BE["build_edges (relations.py:200)"]
    FB --> BE
    BE --> SS["same_space: same space<br/>dst = space:&lt;slug&gt;"]
    BE --> SP["same_prompt: first-query normalized equality<br/>(normalize_query, relations.py:111)<br/>in-cluster chaining by created_us (not cliques)<br/>query_source distinguishes scheduled-task reruns<br/>from manual resends (parsers.py:208-214)"]
    BE --> RF["references: answer text / citation URLs<br/>referencing other archived threads (incl. bare uuids)"]
    BE --> SA["subagent_of: main thread → subagent run<br/>dst = toolu_X run id (not a thread uuid)<br/>archived subagent threads recorded in evidence"]
    SS --> OUT[("web_archive/relations/<br/>edges.jsonl + graph.md")]
    SP --> OUT
    RF --> OUT
    SA --> OUT
```

Decision discipline (2026-07-23): the `branch_of` mechanism is confirmed but has no instance
in the archive — no edges built; `related_query` cannot be parsed from existing data — no edges
built either: rather miss an edge than build a guessed one.
Observed scale: 772 edges / 21 clusters across the archive (same_space 559 / subagent_of 154 /
same_prompt 49 / references 10).

---

## search-mode-backfill (index search_mode enrichment)

`cmd_search_mode_backfill` (search_mode_backfill_cmd.py:81) enriches the platform-authoritative
field `search_mode` into `index/library_<account>.json`: **local raw first** (for archived
threads, extracted from `entries[].search_mode` of raw_entries.json, zero network); only threads
without local raw fall back to an online thread fetch. Writing merges and preserves existing
index fields (refresh semantics: enrichment keys overwrite, everything else kept), idempotent
and resumable, with `--limit` for subsets.
Enriched index rows make batch's `--mode` filter authoritative:
`index_row_matches_mode` (batch_cmd.py:46) judges by index search_mode first
(SEARCH_MODE_MAP, normalize.py:50), falling back to heuristics only when it is missing.

---

## sync-deleted remote-deletion state machine

`cmd_sync_deleted` (sync_deleted_cmd.py:262) identifies threads "deleted by the user/remotely
on the platform side" and records a terminal state, alongside expired. Candidate determination
is a **union-of-all-account-indexes diff**: an archived ok thread counts as a candidate only
when it has disappeared from **all** `index/library_*.json` files (a cross-account export_via
thread appears only in its owner's index, so a single-account diff would false-positive;
find_candidates, sync_deleted_cmd.py:148); missing/unreadable indexes are safely skipped with
the reason recorded. The default offline dry-run only lists candidates (no network, no file
changes); `--online` verifies thread by thread with GET: `ENTRY_DELETED` / `ENTRY_EXPIRED` /
404 → deletion confirmed, `state.mark_deleted` (state.py:136) + a thread.json tombstone
(mark_thread_json_remote_deleted, sync_deleted_cmd.py:215).

```mermaid
stateDiagram-v2
    [*] --> ok : archived (batch_state = ok)
    ok --> candidate : gone from the union of all account indexes<br/>(find_candidates, sync_deleted_cmd.py:148)
    candidate --> skipped : index missing/unreadable<br/>safely skipped, reason recorded
    candidate --> listed : offline dry-run lists only<br/>(no network, no file changes)
    listed --> deleted : --online verifies one by one<br/>ENTRY_DELETED / ENTRY_EXPIRED / 404<br/>(_confirm_deleted, sync_deleted_cmd.py:247)
    deleted --> [*] : terminal mark_deleted (state.py:136) + thread.json tombstone<br/>plan_incremental trims it like expired<br/>(incremental.py:74-75, 84)
```

Error-type layering: `EntryDeletedError` inherits `EntryExpiredError` (the check for 400 with a
body containing ENTRY_DELETED comes before ENTRY_EXPIRED, cookie_transport.py:93-98); batch
must catch the subclass before the parent (batch_cmd.py:163-174 before 175-183), or deleted
would be misrecorded as expired. The deletion API itself:
`DELETE /rest/thread/delete_thread_by_entry_uuid`
(read_write_token taken from the first non-empty `entries[].read_write_token`;
verified in practice 10/10 deletions succeeded on self-created test threads and BOT-space threads).

---

## The answer_variants answer-rewrite variant detection chain

Variants replaced in the platform's "answer rewrite / A-B experiments" are invisible on the API
side — the selected answer is visible, while the losing sibling leaves only a trace in
`entries[].side_by_side_metadata`, and may be purged by the platform (dead sibling links are
proven: 403 VIEW_THREAD_NOT_ALLOWED + an SPA redirect to the home page; see
[the API reference §5.2](../reference/api/api-responses-errors.md)). The detection chain makes "a rewrite happened" observable
and traceable:

```mermaid
flowchart LR
    E["entries[].side_by_side_metadata<br/>narrowed criteria"] --> CAV["parsers.collect_answer_variants<br/>(parsers.py:588)"]
    CAV --> AD["adapter.get_thread warns on online hits<br/>(adapter.py:141-147)"]
    CAV --> RR["re-render offline rebuild<br/>warns only on additions/changes (rerender_cmd.py:163-166)"]
    AD --> LOG["variant_log.warn_detections (variant_log.py:65)<br/>single WARNING line ANSWER_VARIANT_DETECTED (variant_log.py:45)<br/>full locating fields + handling guidance, grep-able"]
    RR --> LOG
    AD --> TJ["thread.json.answer_variants registration<br/>(fs_writer.py:247-252)"]
    RR --> TJ
    TJ --> JSONL[("index/answer_variants_log.jsonl<br/>append_registry (variant_log.py:76)<br/>dedup by (web_uuid, entry_uuid), idempotent")]
    LOG --> B["batch summary surfaces ⚠ hit-thread count<br/>(batch_cmd.py:214-223)"]
    JSONL --> B
```

- **Narrowed criteria**: only the authoritative signals of side_by_side_metadata are accepted;
  full locating fields are recorded (full thread uuid + uuid8, title, entry_uuid, sibling_uuid,
  selection_status, experiment_role) plus handling guidance; the format is in
  `format_detection` (variant_log.py:53).
- **Idempotent**: the jsonl dedups by (web_uuid, entry_uuid); duplicate registrations from the
  online (source=online) and offline (source=offline) paths produce no duplicate rows; rerender
  warns only when variant content changes, so library-wide reruns don't spam.
- **Handling flow**: on a hit, manually confirm the alternate answer as soon as possible and
  record it (the alternate may be purged by the platform and cannot be recovered via the API);
  the full flow is in [the API reference §5.2](../reference/api/api-responses-errors.md).
