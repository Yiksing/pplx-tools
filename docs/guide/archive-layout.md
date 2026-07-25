# Archive layout

Everything `pplx-export` downloads lands in a single output tree — `./web_archive/` by default
(override with `--out`). This page is a reading guide to that tree: what each directory and file
is, which keys `thread.json` carries, and how the tool keeps one directory per thread when a
conversation continues across days. All of it is tool-generated; the mechanism depth lives in
[Data model & directory contract](../architecture/data-model.md) and
[Export pipeline](../architecture/export-pipeline.md).

## The output tree

```
web_archive/
├── alice/                                # one folder per account (author display name)
│   ├── search/                           # mode: search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # one directory per thread
│   │       ├── thread.json               # metadata + optional registries
│   │       ├── conversation.md           # compact read: per-turn Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # full read: complete work-process detail
│   │       │   └── ...
│   │       ├── sources.json              # thread-wide citations (deduped by url)
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research report (only when one exists)
│   │       ├── raw_entries.json          # plain API response, verbatim (always present)
│   │       ├── raw_blocks.json           # schematized API response (absent for search)
│   │       └── assets/
│   │           ├── assets_manifest.json  # versioned manifest
│   │           └── files/                # downloaded asset bodies
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # state files and indexes (see below)
├── relations/                            # edges.jsonl + graph.md (rebuilt by `pplx-export relations`)
├── crosscheck/                           # cross-validation reports (manual/review artifacts)
└── bob/ ...
```

## The thread directory

Each thread gets exactly one directory, computed by `thread_dir_for` (`fs_writer.py:58-72`):

```
<account display name>/<mode>/<YYYY-MM-DD>_<title-slug>_<uuid8>/
```

| Component | Source | Notes |
|---|---|---|
| `<account display name>` | thread author, via `author_folder` → `_safe_folder` (`fs_writer.py:40-51`) | path separators and Windows-illegal characters (`:*?"<>\|`) become `_`; `.`/`..` rejected (path-traversal guard for shared spaces); everything else — including spaces — is kept |
| `<mode>` | `detect_mode` | one of the five modes; see [Conversation modes](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` `lastUpdated` date prefix | the platform's last-update date, **not** the export date — it moves when a continued thread is updated (see migration below) |
| `<title-slug>` | `slugify(title)` (`normalize.py:261-263`) | max 40 chars, non-word characters → `-`, empty → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | first 8 characters of the thread UUID — the directory's identity anchor |

## Files in a thread directory

### thread.json — metadata and registries

Written by `write_thread` (`fs_writer.py:224-253`). Always-present keys:

| Key | Content |
|---|---|
| `web_uuid` | web entryUUID — the UUID in the thread URL; the thread's identity |
| `psc_uuid` | platform `context_uuid` (nullable; from the first non-empty turn) — the dual ID used by space indexes |
| `url` | canonical thread URL |
| `title` | thread title |
| `mode` | detected mode (`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | author account display name |
| `export_via` | account username that performed the export — matters for shared-space threads exported through another account |
| `space` | `{"uuid", "title", "slug"}` or `null` |
| `lastUpdated` | platform last-update timestamp (machine-comparison contract for incremental sync) |
| `threadAccess` | platform access flag |
| `n_turns` | turn count |
| `n_sources` | thread-wide citation count |
| `metadata` | `thread_metadata` from the API response, verbatim |
| `report_info` | `{"title", "file_name", "url"}` or `null` |
| `exported_at` | export time (UTC ISO 8601) |

Optional keys — absent when there is nothing to record:

| Key | Added when | Content |
|---|---|---|
| `interruptions` | any non-completed workflow (`fs_writer.py:242-244`) | list of `{location, kind, headline, status}`; see [Conversation modes — Interruptions](modes.md#interruptions-non-completed-workflows) |
| `answer_variants` | an answer-rewrite variant is detected (`fs_writer.py:247-252`) | narrowed `side_by_side_metadata` locating fields; see [Conversation modes — Answer-rewrite variants](modes.md#answer-rewrite-variants-answer_variants) |
| `remote_deleted` | `pplx-export sync-deleted --online` confirms remote deletion | tombstone timestamp, written in place, idempotent (existing value never overwritten; `sync_deleted_cmd.py:215-244`) — the local archive itself is kept |

### conversation.md — the compact read

`render_conversation` (`render.py:641`): title header (mode / author / turns / citation count),
then per turn a `### Query` + `### Answer` pair with answers in full, and — when present — the
thread-level background-task appendix at the end. This is the file to open first; per-turn work
processes are in `turns/`.

### turns/turn_NNNN.md — the full read

`render_turn` (`render.py:596`): one file per turn (`turn_0001.md` …), each with the complete
work process — steps, tool calls, sub-agent runs, tables, per-turn citations. When a thread's
turn count shrinks, stale high-numbered `turn_*.md` files are deleted but untouched files keep
their mtime (`fs_writer.py:287-301`).

### sources.json / sources.md

Thread-wide citations, deduplicated by URL (`fs_writer.py:270-278`). `sources.json` is
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`; `sources.md` is the same
list as a numbered Markdown link list.

### report.md

The deep-research report product, written only when the thread carries one
(`fs_writer.py:308-316`): report title, the original product file name, then the full report
Markdown.

### raw_entries.json / raw_blocks.json — raw fidelity

The API responses, persisted verbatim **before** any parsing (`fs_writer.py:257-266`):

- `raw_entries.json` — the plain response: `{"thread_metadata", "entries", "background_entries"}`.
  Always present.
- `raw_blocks.json` — the schematized response, same shape. Absent for `search` threads
  (no blocks fetch); fetched for the other four modes, and also as a fallback when every
  mode-detection signal is missing.

These two files are the fidelity anchor of the archive: parsing, rendering, and registries can
all be rebuilt from them offline, with zero network. See
[Offline operations](../architecture/offline-operations.md).

### assets/ — products and their manifest

Downloadable products (computer-mode files, and any other assets the API lists) are fetched
from CloudFront signed URLs into `assets/files/`; the extension is decided at download time
from URL path, content magic bytes, or asset type. `assets/assets_manifest.json`
(`fs_writer.py:320-330`) records every version:

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` is always the **total number of versions** (Σ `len(versions)`), not the number of file
groups — use `len(files)` for that.

## The index/ layer

`web_archive/index/` holds tool-managed state and indexes — do not hand-edit:

| File | Written by | Semantics |
|---|---|---|
| `library_<account>.json` | `pplx-export index` (`index_cmd.py:17-43`) | full account thread index (GraphQL); input for batch / scheduling / space indexes |
| `batch_state.json` | `BatchState` (`state.py`) | resumable checkpoint: uuid → status (ok/error/expired/deleted) + lastUpdated; atomic writes; corrupt files auto-backed up as `.corrupt-<ts>` |
| `.cookies.json` | cookie cache (`common.py:111`, `common.py:150`) | 12h-freshness cookie cache with source and account email; written `0o600` then atomically replaced (session credentials, owner-readable only) |
| `space_<slug>.json` | `pplx-export space-index` (`spaces_cmd.py:106-167`) | per-space thread list, incl. the `context_uuid` dual-ID mapping |
| `space_meta.json` | `pplx-export spaces --fetch-meta` (`spaces_cmd.py:299-330`) | space owner/member cache reused on rebuilds |
| `credit_usage_<account>.json` | `pplx-export usage-backfill` (`usage_backfill_cmd.py:17`) | per-thread credit usage (idempotent, resumable, flushed every 25 entries) |
| `cron_snippet.txt` | `pplx-export schedule` (`scheduler.py:48-78`) | cron invocation snippet (absolute paths) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (`variant_log.py:76`) | central answer-rewrite variant registry, deduped by (thread, entry), idempotent |
| `logs/` | `--log-file` (`common.py:218-229`) | full DEBUG logs |

## The spaces/ layer

`pplx-export spaces` aggregates `index/library_*.json` into a space index (`spaces_cmd.py:259-389`):
one `<slug>.md` per space (participating accounts, owner/member header, thread table,
export-location backlinks) plus a `spaces.json` registry.

!!! note "Output location"
    `spaces/` is written relative to the current working directory (`spaces_cmd.py:332`) — it
    does **not** follow `--out`. Do not hand-edit: the next rebuild overwrites.

## Cross-day continuation: directory migration by UUID identity

The directory name embeds the `lastUpdated` date, so when you continue a thread on a later day
the naive computation yields a *new* directory. The writer prevents duplicates by UUID identity
(`thread_dir_for`, `fs_writer.py:58-72`):

1. **Find**: `find_thread_dirs` (`fs_writer.py:74-105`) searches the whole archive for
   directories ending in `_<uuid8>` — cross-account and cross-mode. A candidate is accepted only
   if its `thread.json` exists, parses, and its `web_uuid` matches exactly; missing, corrupt, or
   mismatched directories are never touched (better to skip a migration than to mis-merge).
2. **Merge**: `_merge_into` (`fs_writer.py:107-178`) merges the old directory into the new one —
   union of files (nothing unique to the old directory is lost); same name + same content → skip;
   same-name conflicts **always keep the target side** (the semantically newer one), with each
   conflict logged. Every copied file is sha256-verified before the old directory is deleted; any
   failure leaves the old directory intact and retries are idempotent.
3. **Clean up historical duplicates**: `consolidate_uuid` (`fs_writer.py:180-209`) merges
   duplicate date directories of one UUID archive-wide, keeping the one with the max
   `lastUpdated` — the backstop for duplicates left behind by older versions.

The same UUID-strictness protects the space index backlinks: candidate directories with a
missing/corrupt/mismatched `thread.json` are never linked.

## Hand-editable vs tool-managed

- **Tool-managed (do not hand-edit)**: everything inside thread directories, plus `index/`,
  `spaces/`, and `relations/`. If content is wrong, fix the tool and regenerate — rendering
  fixes go through `pplx-export re-render`, data fixes through the matching backfill command
  (see [Maintenance commands](maintenance-commands.md)) — so every artifact stays reproducible
  from raw.
- **Hand-editable**: the documentation and the `web_archive/crosscheck/` review reports.
  One user-level exception: a manually rescued alternate answer may be recorded as
  `rewritten_answer_variant.md` inside the thread directory — see
  [Conversation modes — Answer-rewrite variants](modes.md#answer-rewrite-variants-answer_variants).

## See also

- [Conversation modes](modes.md) — the five modes and what each one produces
- [Incremental sync](incremental-sync.md) — how `lastUpdated` drives re-exports
- [Maintenance commands](maintenance-commands.md) — re-render, backfills, sync-deleted
- [Data model & directory contract](../architecture/data-model.md) — the underlying dataclasses
- [Export pipeline](../architecture/export-pipeline.md) — how these files get written
- [Offline operations](../architecture/offline-operations.md) — rebuilding everything from `raw_*.json`
