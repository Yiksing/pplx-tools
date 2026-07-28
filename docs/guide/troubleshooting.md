# Troubleshooting

FAQ format: each entry is **problem → cause → fix**. For the full error-semantics
reference (status codes, terminal states, retry discipline) see
[Responses and errors](../reference/api/api-responses-errors.md) and
[Rate limiting and errors](../architecture/rate-limiting-errors.md).

## Bare requests to the API get a Cloudflare 403

**Problem**: a hand-rolled `curl` / script against `www.perplexity.ai` REST endpoints
returns 403 with a Cloudflare challenge page — even with cookies copied from the
browser — while the same endpoints work through the tool.

**Cause**: Cloudflare sits in front of the site, and `cf_clearance` / `__cf_bm` are
bound to the browser's TLS fingerprint. A bare client's fingerprint does not match, so
the challenge fires. The tool passes because it uses Python `urllib` with cookies
imported from the browser and a desktop-Chrome `User-Agent`
(`pplx_export/core/http/cookie_transport.py:29`). Cloudflare can also 403 under rate
control — in that case the response carries the same challenge shape.

**Fix**:

- Do not bypass the tool's transport; run your call through `pplx-export` / `pplx-ask`
  instead of ad-hoc scripts.
- Inside the tool, a 200 response with a non-JSON body (the Cloudflare interstitial) is
  classified as a transport error, not data (`pplx_export/core/http/cookie_transport.py:133`).
- If 403s start appearing inside the tool, slow down (see
  [Rate limiting](rate-limiting.md)) and refresh the cookies; a persistent challenge
  means re-login in the browser.
- Mind the two faces of 403: a Cloudflare risk-control challenge (clears once you slow
  down) versus an API-level 403 (dead cookie — raised immediately with no backoff; see
  the next section). The design page maps the latter
  ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

Background: [API authentication](../reference/api/api-authentication.md).

## 401 errors / expired cookies

**Problem**: commands fail with an auth error — `AuthTransportError: 鉴权失败 401`
from `pplx-export`, or `pplx-ask ask` exiting with an HTTP 401/403 hint to update the
cookie.

**Cause**: the session cookie has expired or been invalidated. `401`/`403` are treated
as authentication failures and raised immediately — no backoff, because backoff cannot
self-heal a dead session (`pplx_export/core/http/cookie_transport.py:82`;
`pplx_export/core/errors.py:68`). `batch` additionally fail-fasts after 3 consecutive
auth failures so a dead cookie does not burn through the queue.

**Fix**:

1. Re-login (or re-open the site) in the browser so the session cookies are renewed.
2. Refresh the tool's cookie cache. The cache at `<out>/index/.cookies.json` is reused
   within a 12-hour freshness window (`pplx_export/core/cookies/cache.py:22`), so after
   re-login either:
   - run once with `--cookies-from <browser>` to force a fresh browser import, or
   - delete `<out>/index/.cookies.json` and let the next run re-import automatically.
3. Every run that validates successfully re-saves the cache
   (`pplx_export/commands/common.py:150`), so day-to-day runs stay fresh on their own.

Setup details: [Getting started](getting-started.md) · [Configuration](configuration.md).

## Linux cookie decryption

**Problem**: on Linux, auto-detect (or `--cookies-from chrome` & co.) cannot read the
browser's cookie store even though the browser is logged in.

**Mechanism**: Chromium-family browsers on Linux encrypt the cookie database with a
key kept in the OS keyring, read at runtime through the Secret Service D-Bus API.
`browser_cookie3` talks D-Bus via pure-Python `jeepney` — already installed with the
tool on Linux, nothing extra to set up — and falls back to the legacy `peanuts`
password when no keyring answers, which only decrypts cookies that Chrome also wrote
without a keyring. When the keyring exists but the D-Bus lookup itself fails at the
transport level (e.g. a session bus rejecting anonymous auth), `browser_cookie3`'s
own fallback chain never engages; the tool detects that case and retries once with
the keyring bypassed, using Chromium's default password — the same key Chromium
itself uses when no keyring is available (`pplx_export/core/cookies/loaders.py:62-104`,
wired into the load path at `loaders.py:136-153`). Firefox needs none of this: its
`cookies.sqlite` is unencrypted.

**The matrix**:

| Layer | Case | What happens |
|---|---|---|
| Browser | Firefox | Zero friction — `cookies.sqlite` is not encrypted |
| Browser | Chromium + reachable keyring | Works — the key is fetched via Secret Service |
| Browser | Chromium + no keyring | `peanuts` path — works only if Chrome also wrote without a keyring |
| Browser | Chromium + keyring unreachable (D-Bus-level failure) | The tool auto-retries with Chromium's default password — same reach as the `peanuts` path |
| Install method | Native package | Auto-detected (browser_cookie3's built-in paths) |
| Install method | snap / flatpak | Auto-detected — the built-in profile registry covers profiles under `~/snap/<name>/...` resp. `~/.var/app/<app-id>/...` (`pplx_export/core/cookies/profiles.py:37-67`) |
| Desktop environment | GNOME | Usually works out of the box (gnome-keyring) |
| Desktop environment | KDE | Enable **Use KWallet for the Secret Service interface** in the KWallet settings |
| Desktop environment | Headless / minimal | No D-Bus session bus → `peanuts` path |
| Distro family | Debian / Ubuntu | Install `libsecret-1-0` + `gnome-keyring` |
| Distro family | Fedora / RHEL | Install `libsecret` + `gnome-keyring`; minimal / server installs often lack a keyring entirely — the most common failure |
| Distro family | Arch | Same mechanism, only the package names differ |

Sandbox installs need no extra flags: the native path is probed first, then the
registry's snap/flatpak cookie databases via an explicit `cookie_file=`
(`pplx_export/core/cookies/loaders.py:155-168`).

**Scenario → recommended channel**:

| Scenario | Recommended channel |
|---|---|
| Firefox installed | `--cookies-from firefox` — zero friction |
| Desktop GNOME / KDE | Auto-detect just works |
| snap / flatpak browser | Auto-detect — the registry covers it; otherwise `--cookies FILE` exported via a browser extension |
| Headless server | `--cookies FILE` — the universal fallback; `--transport webbridge` as last resort |

## An export ran under the wrong account (multi-account)

**Problem**: archived threads were fetched with the wrong account's session — e.g. an
`--account alice` run pulled data as `bob`, or the archive shows threads that do not
belong to the intended account.

**Cause**: with several accounts logged into the same browser, the active session token
(`__Secure-next-auth.session-token`) may belong to a different account than the one you
targeted. If the target account's `email` is not registered in the user-level config,
the tool cannot detect this and only logs a warning.

**How the tool prevents it** (`pplx_export/commands/common.py:93`): on startup the
transport calls `GET /api/auth/session` and compares the live email with the registered
one. On mismatch it automatically enumerates the browser's per-account session cookies
(`__Secure-pplx.session.<user_id>`), substitutes each into the active token, and probes
the session until the target email matches (`pplx_export/commands/common.py:190`;
`pplx_export/core/cookies/loaders.py:175`). If no token matches, the command aborts with a clear
error — it never silently proceeds as the wrong account.

**Fix**:

- Register every account's `email` under `[accounts.<name>]` (see
  [Configuration](configuration.md)) and pass `--account` explicitly.
- Check the startup log line `[auth] cookie 来源 …，当前账户: …` — it names the live
  session email before anything is fetched.
- To audit an existing archive, each thread's `thread.json` carries an `export_via`
  field recording which account performed the export
  (`pplx_export/sites/perplexity/fs_writer.py:229`). `pplx-export sync-deleted` uses the
  same field to pick the account for online verification.

Mechanism depth: [API authentication](../reference/api/api-authentication.md) ·
[Ask and accounts](../architecture/ask-and-accounts.md).

## "Config file not found" — degraded mode

**Problem**: a startup warning says no user-level config file was found and the command
runs in degraded mode; or an explicit `--account alice` fails with an error pointing at
`config.example.toml`.

**Cause**: no config file at any of the three lookup locations — `--config PATH`, the
`PPLX_EXPORT_CONFIG` environment variable, or the default
`~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). Two related but
distinct cases: an **explicitly specified** config path that does not exist raises
`ConfigError`; a corrupt (unparseable) config always raises `ConfigError` — a broken
config never silently degrades.

**Effects of degraded mode**:

- The account registry is empty, so cookie-ownership verification is skipped with a
  warning and commands run as the placeholder account `default`
  (`pplx_export/commands/common.py:51`). An explicit `--account` errors out instead.
- `pplx-ask ask` skips the auto-move into the BOT space (`moved_to_bot` stays `false`
  in the result JSON) and telemetry carries an empty user id; asking and archiving
  otherwise work.
- Archives land under the fallback account folder derived from the username.

**Fix**: copy `config.example.toml` to `~/.config/pplx-export/config.toml`, fill in
`[accounts.<name>]` (`display_name` / `email` / `user_id`), `[bot_space]`, and
`default_account` — see [Configuration](configuration.md).

## ENTRY_EXPIRED vs ENTRY_DELETED

**Problem**: exporting or re-syncing a thread reports `ENTRY_EXPIRED` or
`ENTRY_DELETED`, and the thread can never be fetched again.

**Cause**: both arrive as HTTP 400 from `GET /rest/thread/<uuid>` with different error
codes, and both are terminal — the thread no longer exists on the platform:

| Code | Meaning | Tool mapping | Terminal state |
|---|---|---|---|
| `ENTRY_EXPIRED` | The platform purged the thread (~3-month retention) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | The thread was actively deleted by the user / remote side (the downstream effect of `DELETE /rest/thread/delete_thread_by_entry_uuid`) | `EntryDeletedError`, a subclass of `EntryExpiredError` (`pplx_export/core/errors.py:30`) | `deleted` |

**What it means for your archive**:

- Neither state is ever retried — not by incremental sync, not with `--force`. The
  terminal mark lives in `<out>/index/batch_state.json`.
- Your **local archive is never deleted or moved** by the tool — the repository copy is
  the backup. The export command registers the terminal state and exits gracefully
  (`pplx_export/commands/export_cmd.py:51`).
- Because the subclass relationship is deliberate, code paths that only know
  `EntryExpiredError` still treat `ENTRY_DELETED` as terminal; aware paths (batch /
  export / sync-deleted / search-mode-backfill) classify it precisely as `deleted`.
- Practical takeaway: export timely. Past the ~3-month purge, artifact/report source
  links also expire irrecoverably.

Related: [Incremental sync](incremental-sync.md) ·
[Responses and errors](../reference/api/api-responses-errors.md).

## Assets that cannot be downloaded (`toolu_` handles)

**Problem**: some entries in `assets/assets_manifest.json` have versions flagged
`"no_download_channel": true`, and no corresponding file exists under
`assets/files/`.

**Cause**: `toolu_`-prefixed cloud-workspace handles (DOC_FILE / CODE_FILE / UNKNOWN without a
URL form) have no API download channel: `GET /rest/assets/<asset_uuid>/data` returns
404 `ASSET_NOT_FOUND` for them, and `file-repository/download` rejects `file:repo/...`
handles (400). This is a **known archive-completeness boundary**, not a bug in the
export. `pplx-export assets-backfill` marks these versions `no_download_channel` and
skips them (`pplx_export/commands/assets_backfill_cmd.py:356`).

**Fix**:

- Nothing to download today — the flag is the deliberate record of the boundary.
- The content often survives inline: subagent page-extraction text and step payloads
  are preserved in the thread's raw JSON (`raw_entries.json` / `raw_blocks.json`) and
  in the rendered `turns/` — check there first.
- `file-repository/list-files` is tracked as a potential future rescue path; see
  [API discovery roadmap](../reference/api/api-discovery-roadmap.md).

Manifest layout: [Archive layout](archive-layout.md).

## Command seems hung / long silences

**Symptom**: `index` / `batch` / `export` prints nothing for several minutes;
an outer task manager may kill it as "timed out".

**Cause**: almost always a backoff wait, not a hang. On 429 / 5xx / network
errors the transport sleeps between attempts — up to 300 s per wait
(`pplx_export/core/throttle.py:38-50`). At DEBUG level the wait is explicit:

```
19:39:31 GET www.perplexity.ai/rest/thread/<uuid> 网络错误: Remote end closed connection without response
19:39:31 退避 200.9s（连续失败 2 次）
```

**How to tell**: run with `-v` (or `--log-file`) and look for the backoff
lines; as long as the process is alive, no intervention is needed.
Interrupting is safe at any point — state is written atomically and the next
run repairs the gap.

**Anti-pattern**: wrapping the CLI in a task manager with a short hard
timeout (agent background tasks, `timeout(1)`-style cron wrappers) *while*
chaining accounts with `&&` — the first account's backoff cascade burns the
whole timeout and the chained account never runs. One account per
invocation, generous budget: see
[Runtime budget for callers](rate-limiting.md#runtime-budget-for-callers).

## Where are the logs?

**Console**: INFO-level progress by default; `-v` / `--verbose` switches to DEBUG
(request tracing, internal decisions); warnings and errors are always shown.

**File**: pass `--log-file` to capture the full DEBUG stream
(`pplx_export/core/logging.py:45`):

- `--log-file` without a value lands at `<out>/index/logs/<cmd>-<timestamp>.log`
  (`pplx_export/commands/common.py:218`) — e.g. `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH` writes to the given path.

**Other state files useful for diagnosis** (under `<out>/index/`):

| File | Content |
|---|---|
| `.cookies.json` | Cookie cache (12 h freshness; written atomically with 0o600 — it is a login-equivalent credential, keep it private) |
| `batch_state.json` | Per-thread export state, incl. the terminal `expired` / `deleted` marks |
| `answer_variants_log.jsonl` | Answer-rewrite variant registry |
| `library_*.json` | Per-account library index snapshots |

## See also

- [Getting started](getting-started.md) — first-time setup and cookie import
- [Configuration](configuration.md) — accounts, BOT space, degraded mode
- [pplx-ask](pplx-ask.md) — the interactive-query CLI
- [pplx-export](pplx-export.md) — the archiving CLI
- [Rate limiting](rate-limiting.md) — pacing and backoff discipline
