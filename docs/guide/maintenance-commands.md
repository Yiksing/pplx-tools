# Maintenance commands

`pplx-export`'s maintenance subcommands keep an existing archive healthy: re-render pages after renderer fixes, backfill assets / credit usage / mode metadata, tombstone remotely deleted threads, and rebuild the relation graph. Most are offline-first; their online phases follow the same pacing discipline as `batch` (see [rate-limiting.md](rate-limiting.md)). All of them accept the [common options](pplx-export.md) (`--account`, `--out`, `--cookies-from`, `--transport`, …).

- Local-archive retention principle: no maintenance command ever deletes or moves archived thread content — the archive is the backup.
- The offline commands (`re-render`, `relations`, `sync-space`, `spaces` without `--fetch-meta`, and the default phases below) need no transport at all; see [../architecture/offline-operations.md](../architecture/offline-operations.md).

## re-render

Regenerate `conversation.md` and `turns/` from the archived raw JSON (`raw_entries.json` / `raw_blocks.json`) after renderer fixes — zero network, and every other file is left untouched.

| Flag | Meaning | Default |
|---|---|---|
| `--limit N` | Process only the first N thread directories | all |
| `--dry-run` | List the directories that would be processed, write nothing | off |
| `--thread-json` | Also add/remove the `interruptions` and `answer_variants` keys in `thread.json` in place | off |

Key behaviors:

- Rebuilds turns offline with the same pipeline as export: parsing, ordering by `created_us`, citation dedup, and — for computer/council — workflow blocks, sub-agent mapping and the unconsumed-background appendix.
- Only `conversation.md` and `turns/turn_*.md` are (re)written; `sources*`, `assets/`, `report.md` and `thread.json` stay as-is. Stale `turn_*.md` files numbered above the current turn count are deleted — nothing else, so unchanged files keep their mtime.
- `--thread-json` writes only when the content actually changes; newly added/changed `answer_variants` raise an `ANSWER_VARIANT_DETECTED` warning and are appended to `index/answer_variants_log.jsonl` (idempotent reruns don't spam).
- Thread directories without `raw_entries.json` are skipped and counted.

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

Remediate assets that were archived without a signed URL — three staged remedies: re-fetch missing blocks, offline inline extraction, and optional online refresh.

| Flag | Meaning | Default |
|---|---|---|
| `--fetch-blocks` | First re-fetch missing `raw_blocks.json` and their signed-URL assets (online) | off |
| `--online` | Enable the online refresh of missing/stale assets | off (offline inline extraction only, zero requests) |
| `--limit N` | Process only the first N thread directories | all |

Key behaviors:

- Default phase (offline, zero requests): extract inline assets (`ASSET_DIFF` / `CODE_ASSET`) from `raw_blocks.json` into `assets/files/*.md`, and register cloud-workspace handle kinds (`DOC_FILE` / `CODE_FILE` / `UNKNOWN` — no download channel yet) in `assets/assets_manifest.json`. Idempotent: known records are deduped by uuid, then file_handle; multi-version same-name files get a uuid short-suffix so reruns don't collide.
- `--fetch-blocks` (online): re-fetch missing `raw_blocks.json` for deep-research/computer/council/study threads plus their downloadable assets; threads are grouped by account folder with a lazily-built adapter per account (cookies switch automatically), 3s between threads.
- `--online`: for manifest versions whose `downloaded_to` is missing/stale, fetch a fresh signed URL via `/rest/assets/<uuid>/data` (API calls serial, 3s apart), then re-download from the CDN (6 concurrent threads, no delay — CDN, not API). A 404 `ASSET_NOT_FOUND` sets the `asset_expired` terminal flag; a cross-account 403 is retried once with the account that owns the archive folder.
- The manifest `count` is recomputed as the total number of versions on every write-back.

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

Backfill per-thread credit usage (`credits/thread-usage`) for all of the account's archived threads into `index/credit_usage_<account>.json`.

| Flag | Meaning | Default |
|---|---|---|
| `--limit N` | Process only the first N threads | all |

Key behaviors:

- One GET per archived thread (`thread_id` = the thread's `psc_uuid`), 3s apart; idempotent — threads already present in the output file are skipped.
- A 403 (`thread_usage_forbidden`, i.e. a cross-account thread) is recorded as `error` and never retried; other failures are left for the next run. Progress is saved every 25 processed threads.
- Multi-account: run once per account with `--account` — the cookies switch automatically between runs.

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

Backfill the platform-authoritative `search_mode` field into each row of `index/library_<account>.json`, so `batch --mode` can filter exactly instead of relying on heuristics.

| Flag | Meaning | Default |
|---|---|---|
| `--limit N` | Process only the first N pending rows | all |
| `--offline` | Local extraction only — rows without local raw data wait for the next round, no online fallback | off |
| `--delay-min SEC` | Lower bound of the random interval between online-fallback threads | `10` |
| `--delay-max SEC` | Upper bound of the random interval between online-fallback threads | `20` |

Key behaviors:

- Stores the platform raw value (`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…); a thread carrying multiple values keeps the most specific one by computer > council > study > deep-research > search.
- Local-first: archived threads resolve from `raw_entries.json` with zero network — a fully local run never even builds a transport (not even a session probe).
- Online fallback only for rows without local raw data: `GET /rest/thread/<uuid>` with a 10–20s random interval; rows in `expired` terminal state are skipped and recorded; threads newly found expired/deleted online are marked in `batch_state.json` to spare future requests.
- Idempotent and resumable: rows that already have `search_mode` are skipped, progress is saved every 25 rows, and later `index` refreshes preserve the enrichment (merged back by `entryUUID`).

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

Identify threads that vanished from the remote library (deleted by the user or the platform) and tombstone them — it never deletes or moves any archive file.

| Flag | Meaning | Default |
|---|---|---|
| `--online` | Verify each candidate online | off (offline dry-run: list candidates only) |
| `--limit N` | Process only the first N candidates | all |
| `--delay-min SEC` | Lower bound of the random interval between candidates | `10` |
| `--delay-max SEC` | Upper bound of the random interval between candidates | `20` |

Key behaviors:

- Candidate detection is offline and cross-account: a thread with `batch_state` status `ok` that is missing from the `entryUUID` union of **all** `index/library_*.json` files becomes a candidate — any single index containing it counts as alive, so threads exported cross-account via shared spaces are not false-positived. When no usable index exists, everything is safely skipped with a hint to run `index` first.
- Default is an offline dry-run: it lists candidates and safe-skip reasons — zero network, zero writes.
- `--online` verifies each candidate with `GET /rest/thread/<uuid>` under the account recorded in `thread.json` `export_via` (cookies switch automatically per candidate).
- Confirmed by `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 → `batch_state` marks the terminal state `deleted` (same semantics as `expired`: never retried, `--force` does not re-export; see [incremental-sync.md](incremental-sync.md)) and each of the thread's `thread.json` files gets a `remote_deleted` timestamp in place (idempotent — an existing key is kept).
- Thread still exists → false positive: reported as-is with a hint to re-run `index`, nothing changed. Transport errors back off to the next round; 3 consecutive auth failures abort the run before anything gets mis-marked.

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

The first run lists candidates (offline dry-run); the second verifies them online and tombstones the confirmed ones.

## status

Print the archive state account and the incremental change plan — zero network, read-only. It answers "what does the archive look like right now, and what would the next `batch` run do" without touching the network.

| Flag | Meaning | Default |
|---|---|---|
| `--account X` | Report on one account only | all accounts that have an `index/library_*.json` file |
| `--json` | Full machine-readable report on stdout (ignores verbosity) | off (human log lines) |

Key behaviors:

- Data sources are purely local: `index/library_*.json` (per-account index rows) and `index/batch_state.json` (the single source of export states). Change classification reuses the same `plan_incremental` pure function as `batch`/`schedule`, so `new`/`updated`/`done`/`expired`/`deleted` semantics are identical to what `batch` would compute.
- The default INFO output prints one summary line per account (index count + freshness, `ok/expired/deleted/error` state counts, `new/updated` change counts, and the early-stop number) plus a global `batch_state` account line (e.g. `559 ok + 13 expired + 12 deleted`).
- Detail tiers ride the standard verbosity flag: `-v` adds the titles of `new`/`updated`/`error` threads (first line, truncated to 60 chars); `-vv` adds `done`/`expired`/`deleted` threads with `lastUpdated`/`exported_at`; `-vvv` prints everything untruncated with index `mode`/`search_mode` fields and the state-only list (records present in `batch_state` but missing from every account's index — remote-deletion candidates to reconcile with [sync-deleted](#sync-deleted)).
- Guardrails: a missing `index/` or missing library file exits with an error pointing at `pplx-export index`; a missing `batch_state.json` is treated as an empty state (everything counts as `new`). No user-level config is required — accounts are enumerated from the library file names.
- `--json` emits the full report (accounts, changes, threads, state-only, totals) as a single-line JSON on stdout — the same contract style as `pplx-ask`.

```bash
pplx-export status                 # summary for every account
pplx-export status -vv             # five-state thread details
pplx-export status --account alice --json
```

## relations

Rebuild the conversation relation graph from the exported threads → `relations/edges.jsonl` plus a human-readable `relations/graph.md` under the archive root.

| Flag | Meaning | Default |
|---|---|---|
| *(common options only; only `--out` matters)* | | |

Key behaviors:

- Purely offline, zero network, read-only against the archive: it reuses re-render's offline rebuild pipeline (`raw_entries.json` / `raw_blocks.json`), so `sub_agents`, `query_source` and citation signals are all available for edge detection.
- Threads without raw data degrade to a `thread.json` + `conversation.md` shell — only `same_space` and bare-uuid reference edges can fire for them.

```bash
pplx-export relations
```

## debug-js

Execute a JavaScript snippet in the current browser page context via the local WebBridge daemon (`127.0.0.1:10086`) and print the result as JSON — a debugging escape hatch.

| Flag | Meaning | Default |
|---|---|---|
| `JS代码` (positional) | JavaScript code to evaluate in the page context (the literal argparse metavar) | required |

Key behaviors:

- Requires the WebBridge daemon to be reachable and the target Perplexity page open in the browser; the snippet runs with the page's own session.
- The printed JSON is truncated at 5000 characters.

```bash
pplx-export debug-js 'document.title'
```
