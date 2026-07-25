# Incremental Sync

`pplx-export batch` is built to run often: each run exports only what is new or
changed, heals gaps left by interrupted runs, and never retouches threads the
platform has already retired. The single source of truth for "what has been
exported" is `index/batch_state.json` (`BatchState`,
`pplx_export/core/state.py:63`), updated after every thread — there is no
separate shadow copy.

## Prerequisites and basic usage

```bash
pplx-export index --account alice   # refresh index/library_alice.json first
pplx-export batch --account alice   # incremental export (early stop, resumable)
```

`batch` refuses to run without the index
(`pplx_export/commands/batch_cmd.py:79-81`). `--limit N` and `--mode <mode>`
filter the index rows before planning; rows missing `entryUUID` are skipped
with a warning instead of crashing the run (`batch_cmd.py:95-100`).

## How the incremental plan works

1. **Sort.** Index rows are sorted by `lastUpdated`, newest first
   (`batch_cmd.py:89`). Brand-new conversations and resumed old ones (whose
   `lastUpdated` just moved them upward) both sit at the top — this ordering is
   what makes early stop safe.
2. **Classify.** `plan_incremental`
   (`pplx_export/hooks/incremental.py:36-87`) — a pure function shared by
   `batch` and `schedule` — assigns each row exactly one action:

   | action | condition | what batch does |
   |---|---|---|
   | `new` | uuid never seen in `batch_state` | export |
   | `updated` | `lastUpdated` differs from the recorded value, or `--force` | re-export |
   | `done` | status `ok` and `lastUpdated` unchanged | skip |
   | `expired` | the platform returned `ENTRY_EXPIRED` on an earlier attempt | skip — terminal, never retried |
   | `deleted` | `sync-deleted` confirmed a remote deletion | skip — terminal, never retried |

3. **Early stop.** By default (neither `--full` nor `--force`) the longest
   trailing run of terminal entries (`done` / `expired` / `deleted`) is trimmed
   wholesale and counted as `n_stopped` (`incremental.py:83-87`). Because the
   list is newest-first, everything below an unchanged entry is necessarily
   older and unchanged too — scanning further would only burn time.

   ```mermaid
   flowchart TD
       IDX["library index rows<br/>sorted by lastUpdated, newest first"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → export"]
       PLAN --> UPD["updated → re-export"]
       PLAN --> DONE["done → skip"]
       PLAN --> TERM["expired / deleted → skip (terminal)"]
       DONE --> STOP["early stop:<br/>trailing terminal run trimmed"]
       TERM --> STOP
   ```

4. **Execute.** Every exported thread is marked immediately (`mark_ok` /
   `mark_error` / `mark_expired` / `mark_deleted`) and the state file is saved
   after each item (`batch_cmd.py:154-201`); a `KeyboardInterrupt` also saves
   before propagating (`batch_cmd.py:158-161`). Writes are atomic — temp file
   plus `os.replace` (`state.py:145-152`) — so an interrupted run never leaves
   truncated JSON.

## Gap healing after interrupted runs

Early stop never buries a gap. Threads that failed (status `error`) or were
never reached sit **above** the terminal suffix, so the next run re-plans them
as `updated` / `new` and exports them before the early-stop point is reached
(`incremental.py:12-14`, `batch_cmd.py:206-208`). Combined with per-item state
saves, a batch run can be interrupted at any point and simply re-run.

If `batch_state.json` itself is corrupted, it is not silently blanked: the
original is renamed to `batch_state.json.corrupt-<timestamp>` so recorded
terminal states are not lost and needlessly retried (`state.py:68-81`).

## `--full` and `--force`

| flag | effect | terminal states | when to use |
|---|---|---|---|
| *(default)* | early stop over the trailing terminal run | skipped | every regular / scheduled run |
| `--full` | full scan, no early stop; unchanged threads are still skipped as `done` | skipped | periodic backstop, or when archive gaps are suspected |
| `--force` | re-export everything, even unchanged threads | still excluded — never retried | after pipeline fixes that must re-fetch raw data |

Terminal states are excluded from `--force` by design: retrying an expired or
remotely deleted thread only wastes requests and backoff budget
(`batch_cmd.py:120-127`).

See also [`status`](maintenance-commands.md#status): a zero-network report of the
state account and the change plan computed with the same `plan_incremental`
semantics (`new`/`updated`/early-stop count).

The `lastUpdated` comparison normalizes trailing zeros in the
fractional-seconds part (`.18033Z` equals `.180330Z`; `state.py:23-55`),
because the platform occasionally drops them — an exact string compare would
misjudge "changed" and cause duplicate exports.

## Terminal states: `expired` and `deleted`

| | `expired` | `deleted` |
|---|---|---|
| meaning | the platform purged the thread (~3-month retention window); the export attempt returned `ENTRY_EXPIRED` | user/remote deletion, confirmed by `sync-deleted` |
| recorded by | `batch` itself (`mark_expired`, `state.py:131-134`) | `pplx-export sync-deleted --online` (`mark_deleted`, `state.py:136-143`) |
| retried? | never — not even with `--force` | never — not even with `--force` |
| evidence | the `ENTRY_EXPIRED` response | `note` field: index absence + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

### sync-deleted: confirming remote deletions

```bash
pplx-export sync-deleted --account alice            # offline dry-run: list candidates only
pplx-export sync-deleted --account alice --online   # confirm each candidate online
```

1. **Candidates (offline, zero network).** Any thread with status `ok` in
   `batch_state` that is missing from the `entryUUID` union of **all**
   `index/library_*.json` account indexes is a suspected remote-deletion
   candidate (`pplx_export/commands/sync_deleted_cmd.py:148-212`). The union
   across accounts is required: a thread owned by `bob` but exported by `alice`
   through a shared space never appears in `alice`'s own index — a
   single-account diff would false-positive that whole set. When no usable
   index exists at all, every candidate is safely skipped with the reason
   recorded.
2. **Dry-run by default.** Without `--online` the command only lists
   candidates — no network, no file changes.
3. **`--online` confirmation.** Each candidate is verified with
   `GET /rest/thread/<uuid>`, using the candidate's `export_via` account from
   `thread.json` (the cookie switches automatically):

   | result | outcome |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | confirmed: `batch_state` marks terminal `deleted` (the `note` records the reason), and every `thread.json` of that thread gets a `remote_deleted` timestamp in place |
   | thread still exists | false positive: reported as-is (the index may not be fully refreshed — re-run `index` and check again), nothing changed |
   | 5xx / network error | no state change; the candidate is left for the next round |
   | 3 consecutive 401/403 | fail-fast abort — an expired cookie cannot heal itself, and spinning on would mis-mark live threads (`sync_deleted_cmd.py:333-337`) |

   Confirmed marks are persisted per item, so an interrupted `--online` run
   loses nothing and reruns are idempotent (`sync_deleted_cmd.py:254-256`).

## The tombstone principle

!!! warning "Local archives are never deleted"
    This archive is the backup of record for the exported conversations.
    `sync-deleted` only *identifies and marks* (tombstone): it **never deletes
    or moves any archive file**. Confirmation changes exactly two things — the
    `batch_state` status and one marker key in `thread.json`:

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    The stamp is idempotent: an existing `remote_deleted` key is neither
    rewritten nor overwritten (`sync_deleted_cmd.py:215-244`).

## Idempotence and offline re-render

- Re-running `batch` against an unchanged index exports nothing: every row
  classifies as `done` and the run stops at the early-stop point. State writes
  are atomic, marks are per-thread, and re-confirmed deletions never duplicate
  the `remote_deleted` stamp.
- The archive keeps the raw API payloads (`raw_entries.json` /
  `raw_blocks.json`), so the rendered files can be regenerated at any time
  with zero network access:

  ```bash
  pplx-export re-render                 # rebuild conversation.md + turns/ everywhere
  pplx-export re-render --dry-run       # only list the thread directories
  pplx-export re-render --thread-json   # also sync interruptions / answer_variants keys
  ```

  `re-render` re-parses the raw JSON with the current renderer
  (`pplx_export/commands/rerender_cmd.py:105-190`): `conversation.md` and
  `turns/turn_*.md` are rewritten, stale turn files numbered above the current
  turn count are removed, and sources, assets, `report.md` and `thread.json`
  are left untouched. That is how renderer fixes roll out over the whole
  archive without a single request.

## See also

- [pplx-export.md](pplx-export.md) — full `batch` command reference (`--mode`, `--limit`, delays)
- [maintenance-commands.md](maintenance-commands.md) — `sync-deleted`, `re-render` and the backfill commands
- [archive-layout.md](archive-layout.md) — where `batch_state.json` and `thread.json` live
- [rate-limiting.md](rate-limiting.md) — pacing between threads, backoff, auth fail-fast
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) — the full export pipeline
- [../architecture/offline-operations.md](../architecture/offline-operations.md) — the offline rebuild pipeline in depth
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — error taxonomy and terminal-state handling
