# pplx-export

`pplx-export` is the archiver CLI: it pulls conversation indexes from Perplexity, exports threads into the local archive, and maintains the derived views (space index, cron snippet). This page covers the capture-side subcommands — `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule` — plus the one-time setup command `init`. The backfill/repair subcommands live in [maintenance-commands.md](maintenance-commands.md); the query CLI is covered in [pplx-ask.md](pplx-ask.md).

## Common options

Every subcommand accepts these flags (defined once in `pplx_export/commands/common.py`):

| Flag | Meaning | Default |
|---|---|---|
| `--account NAME` | Target account. When the cookie's email doesn't match the registered email, per-account browser session tokens are enumerated to switch automatically | `default_account` from the user-level config |
| `--config PATH` | User-level config file (account registry). Priority: `--config` > env `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | default lookup chain |
| `--skip-auth-check` | Skip the startup account-attribution session probe and trust the current login, avoiding a long startup wait on a poor network; `batch` runs a deferred account check if errors accumulate — see [Configuration](configuration.md) | off |
| `--site NAME` | Site adapter | `perplexity` |
| `--out DIR` | Archive output root | `--out` > config `archive_root` > `./web_archive` |
| `--cookies-from BROWSER` | Import cookies from a browser (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | Netscape cookie file or JSON cookie file | — |
| `--transport MODE` | `cookie` = cookie-direct requests; `webbridge` = fetch inside the browser page context | `cookie` |
| `-v`, `--verbose` | DEBUG output (request traces, internal decisions); repeatable | off |
| `--log-file [PATH]` | Write the full log to disk; without a value, auto path `<out>/index/logs/<cmd>-<timestamp>.log` | off |

- `--cookies-from` / `--cookies` are mutually exclusive with `--transport webbridge` — the bridge runs in the page context and already carries the browser's cookies.
- `pplx-export --version` prints the package version and exits (top-level only, not a subcommand flag).
- Account registration, cookie sources and multi-account switching: [configuration.md](configuration.md). Where everything lands on disk: [archive-layout.md](archive-layout.md).

## init

Discover accounts from browser cookies and write the user-level config — the automatic alternative to hand-copying `config.example.toml` (see [configuration.md](configuration.md)).

| Flag | Meaning | Default |
|---|---|---|
| `--force` | Overwrite an existing config file | off (refuses to overwrite) |
| `--create-bot-space [TITLE]` | Create the BOT space via the API when no space title matches (a write operation on the account); an explicit TITLE drives both matching and creation, otherwise the title comes from `--bot-title`; without this flag `[bot_space]` is written empty | off |
| `--bot-title TITLE` | Space title used both to match an existing space and to name a created one | `BOT` |
| *(common options apply)* | Cookie-source flags pick where accounts are discovered; for `init` only, `--config` is the **write** path (the strict config load is skipped) | |

Key behaviors:

- Token enumeration: per-account session cookies (`__Secure-pplx.session.<uid>`) are collected from the browser stores — or, with `--cookies FILE`, scanned from the cookie file (a full export may carry several accounts). With no enumerable tokens, only the currently active session is probed.
- Session probe: each token is tried against `GET /api/auth/session` to learn the account's email / display name; tokens that fail or return no email are skipped with a warning.
- Registry assembly: each account key is derived from the email local part (collisions get `-2`/`-3`… suffixes); `default_account` is set to the currently active account, else the first one discovered.
- BOT space: a space is matched by exact title (case-insensitive) via `list_user_collections`; when nothing matches, `--create-bot-space [TITLE]` creates it on the spot (an explicit TITLE overrides `--bot-title` for both matching and creation), otherwise `[bot_space]` is left empty.
- The TOML is written atomically (temp file + rename) with 0600 permissions, and an existing file is never overwritten without `--force`. The command ends with a summary JSON line: config path, account keys, default account, BOT space uuid/slug.
- Model seeding (best-effort): after writing the config, `init` fetches `models/config/v2` and seeds the machine-managed `[models]` table so a fresh config already carries the current model defaults/catalog; on failure it is skipped with a warning (refresh later with `pplx-ask models --refresh`). See [Configuration](configuration.md).
- `--transport webbridge` is rejected — the page-context channel cannot enumerate per-account tokens.

```bash
pplx-export init                          # write the default ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --config /path/to/config.toml --force   # custom path, overwrite allowed
```

## index

Refresh the account's conversation list index `index/library_<account>.json` — the baseline every other command diffs against.

| Flag | Meaning | Default |
|---|---|---|
| `--full` | Page the entire library and rewrite the index; resets the incremental counter | incremental |

Key behaviors:

- **Incremental by default.** It pages newest-first and stops once a full page (`_STOP_RUN`) of consecutive rows is already known and unchanged, then merges the fetched head onto the existing index — older rows are carried over verbatim (no loss). The first run, or any run with no existing index, is a full sweep.
- **`--full`** pages everything and rewrites the index; use it as the periodic reconciliation front-end.
- **Blind spot of the incremental path:** remote *deletions* and *space changes* of older threads never appear in the fetched head, so they are not observed. Deletion authority stays with `sync-deleted --online`. The per-account refresh state (`extracted_at` / `last_full_index_at` / `incremental_runs_since_full`) lives in the machine-managed `[index_state]` table of the user-level config (see [configuration.md](configuration.md)); the index document keeps only stable fields, so a no-change refresh is a git no-op. After enough incremental runs it warns you to run `--full` (and `sync-deleted --online`).
- Preserves the `search_mode` enrichment written by `search-mode-backfill`, merged back by `entryUUID`.
- Run it before `batch`, `sync-space` and `sync-deleted` — their diffs are only as fresh as this index.

```bash
pplx-export index --account alice          # incremental refresh
pplx-export index --account alice --full   # full sweep + reconciliation front-end
```

## sync

High-frequency convenience entry: **incremental `index` + incremental `batch`**, focused on conversations only.

| Flag | Meaning | Default |
|---|---|---|
| `--full` | Full reconciliation: full `index` + full `batch` sweep (and runs the deletion/space steps below) | off |
| `--check-deleted` | Also run `sync-deleted --online` to verify and mark remotely-deleted threads | off |
| `--refresh-spaces` | Also rebuild `spaces --fetch-meta` and run `sync-space` | off |
| `--limit N` / `--mode X` / `--delay-min` / `--delay-max` | Passed through to the `batch` phase | — |

Key behaviors:

- Default run fetches only new/updated conversations and **skips deletion detection and space refresh** — the cheapest shape for frequent syncing.
- Deletion/space reconciliation is opt-in (`--check-deleted` / `--refresh-spaces`) or bundled by `--full`. The `incremental_runs_since_full` counter in the config's `[index_state]` table is the backstop: it reminds you when a `--full` reconciliation is overdue.

```bash
pplx-export sync --account alice                     # conversations only (fast)
pplx-export sync --account alice --full              # periodic full reconciliation
pplx-export sync --account alice --check-deleted     # also mark remote deletions
```

## space-index

Extract one space's "All" conversation list — including threads shared by other members — into `index/space_<slug>.json`.

| Flag | Meaning | Default |
|---|---|---|
| `SPACE_URL` (positional) | Space page URL | required |
| `--transport webbridge` | Use the legacy browser-rendering path instead of REST | `cookie` (REST direct) |

Key behaviors:

- Default path is REST direct: `list_collection_threads` over the cookie transport with offset pagination; rows include `context_uuid` and `answer_preview`.
- With `--transport webbridge` it falls back to scrolling the rendered space page and scraping row props — a backup in case the REST structure changes.
- Rows are written newest-first by `lastUpdated`.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

Export a single thread (URL or bare UUID) into its archive directory `<out>/<account-folder>/<mode>/<thread-dir>/`.

| Flag | Meaning | Default |
|---|---|---|
| `THREAD` (positional) | Thread URL or UUID | required |
| `--force` | Re-export even when `lastUpdated` is unchanged | off |

Key behaviors:

- If the archived copy is already up to date, the export is skipped with no writes; `--force` overrides the check.
- `lastUpdated` is taken from the local library index when the thread is listed there (same semantics and format as `batch`), falling back to the platform value otherwise.
- Terminal states are registered gracefully, without a traceback: `ENTRY_DELETED` marks `deleted` in `batch_state.json`, `ENTRY_EXPIRED` marks `expired` — the existing local archive is kept untouched either way.
- A successful export writes `ok` into `index/batch_state.json`, so the incremental plan counts the thread as "exported and unchanged".
- When an ancestor of the archive root is a git repository, a successful export auto-commits the archive subtree (config `auto_commit`, default on) and optionally pushes (`auto_push`, default off; a rejected/conflicting push aborts with a non-zero exit) — see [configuration.md](configuration.md).
- What lands in the thread directory: [archive-layout.md](archive-layout.md); the export pipeline itself: [../architecture/export-pipeline.md](../architecture/export-pipeline.md).

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

Bulk-export an account's threads — the daily driver, with incremental early stop and resumable checkpoints.

| Flag | Meaning | Default |
|---|---|---|
| `--force` | Re-export all threads (terminal states excluded) | off |
| `--full` | Full scan: unchanged threads are still skipped, but no early stop | off |
| `--limit N` | Process only the first N rows of the list (newest first) | all |
| `--mode MODE` | Export only `search` / `deep-research` / `computer` / `council` / `study` threads | all modes |
| `--delay-min SEC` | Lower bound of the random interval between threads | `10` |
| `--delay-max SEC` | Upper bound of the random interval between threads | `20` |

Key behaviors:

- Requires `index/library_<account>.json` — run `index` first.
- Default **incremental early stop**: the list is sorted newest-first and the trailing run of "exported and unchanged" threads is trimmed wholesale; gaps left by interrupted runs (error/never-exported) sit above that suffix and are still repaired. `--full` disables early stop (periodic backstop, or when archive gaps are suspected); `--force` re-exports everything except terminal states, which are never retried. Full semantics: [incremental-sync.md](incremental-sync.md).
- `--mode` filtering: rows carrying `search_mode` (the platform-authoritative field enriched by `search-mode-backfill`) match exactly via `SEARCH_MODE_MAP` — on that path `--mode search` no longer pulls in deep-research/council/study threads. Rows without `search_mode` fall back to index heuristics: `computer` = mode `COMPUTER`; `deep-research` = displayModel `pplx_alpha`; `council` = `pplx_agentic_research`; `study` = `pplx_study`; `search` = the remaining mode-`SEARCH` rows (including those three kinds — filter them out precisely by exporting the specific modes separately).
- State is saved to `index/batch_state.json` after every thread — interrupt and rerun freely.
- Auth fail-fast: 3 consecutive 401/403 responses abort the run (an expired cookie cannot self-heal, and spinning on would fail hundreds of threads one by one).
- Pacing: a random `--delay-min`–`--delay-max` pause between threads; 429/5xx are backed off by the transport layer. Details: [rate-limiting.md](rate-limiting.md).
- Threads hitting rewritten-answer variants are registered in `index/answer_variants_log.jsonl` with a warning to handle them manually as soon as possible (see [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md)).
- After the run, the archive subtree is auto-committed unconditionally when the archive lives inside a git repository — even an `ok=0` run leaves index refresh metadata worth committing; with no changes it is a no-op. Controlled by config `auto_commit` / `auto_push` — see [configuration.md](configuration.md).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

Rebuild the space-view index — one Markdown page per space plus a `spaces.json` registry — from the local library indexes.

| Flag | Meaning | Default |
|---|---|---|
| `--fetch-meta` | Refresh owner/member metadata before rebuilding | off |

Key behaviors:

- Without `--fetch-meta` the command is purely local (zero network): it aggregates threads per space slug across all `library_*.json` files, with participating-account stats and backlinks to the exported thread directories.
- Output goes to `./spaces/` relative to the current working directory — run it from the directory containing `web_archive/` so the backlinks in the space pages resolve.
- `--fetch-meta` first refreshes each space's owner/member cache via `get_collection` (1 request per space, 3s interval) into `index/space_meta.json`; when the current account cannot see a space, an account that can is retried automatically (cookies switch on their own).

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

Sync the `space` field of already-archived `thread.json` files with the current index — purely local, zero network.

| Flag | Meaning | Default |
|---|---|---|
| *(common options only; only `--out` matters)* | | |

Key behaviors:

- Prerequisite: run `index` first — the refreshed `library_*.json` is the source of truth for current space ownership.
- Compares space slugs per thread and patches `thread.json` in place on divergence; the first 30 changes are logged.
- After any change, the `spaces/` index is rebuilt automatically alongside.

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

Compute this round's incremental export plan and write a cron snippet the system cron can call directly.

| Flag | Meaning | Default |
|---|---|---|
| *(common options only)* | | |

Key behaviors:

- Fetches a live index and reports the plan as total/new/updated counts, using the same early-stop pure function (`plan_incremental`) as `batch` — see [incremental-sync.md](incremental-sync.md).
- Writes `<out>/index/cron_snippet.txt` containing one `17 3 * * *` line of the form `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'` — paths are absolute and quoted because cron's cwd and PATH are unpredictable. The executable path is resolved via `shutil.which`; when that fails the snippet falls back to the bare `pplx-export` name.
- Scheduled runs are incremental-only by design; run `batch --full` manually as a periodic backstop.

```bash
pplx-export schedule --account alice
```
