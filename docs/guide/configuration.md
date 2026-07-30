# Configuration

pplx-export keeps your identity data — the account registry (display names, login emails, user IDs) and the BOT space — in a user-level TOML file that lives outside the repository. This page covers where that file lives, every field it accepts, what happens when it is missing, and how the registry drives multi-account cookie handling.

## Why the config lives outside the repo

The account registry and the BOT space are personal data and are **never committed** to the repository (`pplx_export/config.py:7-12`). The repo ships only a placeholder template, `config.example.toml`; your real values go into a private copy. Everything else the tool needs — the site domain, API URLs, the default archive root — is a code constant (`pplx_export/config.py:50-58`), not user configuration.

The TOML carries identity data only. Cookie sourcing and transport selection are per-invocation CLI flags, not config fields — see [CLI flags, not config fields](#cli-flags-not-config-fields) below.

## Location and load priority

`configure()` (`pplx_export/config.py:113`) resolves the config path with this precedence (`pplx_export/config.py:95-110`):

| Priority | Source | Counts as explicit |
|---|---|---|
| 1 | `--config PATH` CLI flag | yes |
| 2 | `PPLX_EXPORT_CONFIG` environment variable | yes |
| 3 | `~/.config/pplx-export/config.toml` (default path) | no |

"Explicit" matters for error behavior when the file is missing — see [degraded mode](#missing-config-degraded-mode). Both CLI entries reload the config in strict mode after argument parsing (`pplx_export/cli.py:222`, `pplx_export/ask_cli.py:277`); the import-time load (`pplx_export/config.py:174-179`) is fault-tolerant, so importing the package never fails on a missing file.

## Creating your config

!!! tip "Automatic alternative"
    `pplx-export init` can generate this file automatically — it discovers the signed-in accounts from your browser cookies and writes the TOML with 0600 permissions. See [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

Then edit the copy. The template uses pure placeholders — copy the structure, replace every value:

```toml
# Default account used when --account is not given (a key of [accounts.<name>] below)
default_account = "alice"

# Account registry: key = account username (the username in thread URLs / library)
[accounts.alice]
# Full display name: used for archive directory naming (web_archive/<display name>/…)
display_name = "Alice Example"
# Login email: verifies cookie ownership
email = "alice@example.com"
# Account uid (required for thread-viewed telemetry)
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT space: where threads created by pplx-ask are collected after completion
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

Placeholder style: `alice`/`bob` are made-up account usernames, emails use `example.com`, and UUIDs use the all-zeros `00000000-0000-4000-8000-…` form. In your real file the table key **must be the actual account username** as it appears in thread URLs and your library.

!!! warning "Keep it private"
    The real config contains personal data (emails, user IDs). Recommended permission is `0o600`; never commit it to any git repository (`config.example.toml:4-6`).

## Field reference

### Top level

| Field | Type | Meaning |
|---|---|---|
| `default_account` | string | Key of one `[accounts.<name>]` table, used when `--account` is not given (`pplx_export/commands/common.py:84-85`). Empty/missing = degraded mode. |
| `archive_root` | string | Optional. Archive output root used as the `--out` fallback, so daily commands can omit `--out`. Precedence: `--out` > `archive_root` > `./web_archive` (`pplx_export/config.py`, loaded into `ARCHIVE_ROOT`; resolved in `cli.py` / `ask_cli.py`). `~` is expanded. |
| `[models]` (table) | table | **Auto-managed, not hand-authored.** Metadata-only table updated by `pplx-ask models --refresh` and seeded by `pplx-export init`: `last_refreshed` (UTC), `source_version`, `auto_refresh` (bool). The full model catalog (113 raw models, frontend `search_config` / `computer_config`, mode defaults) lives in `models_cache.json` alongside the config file, written atomically on every refresh. Requests read from it (with `pplx_export/sites/perplexity/platform.py` as fallback); a 7-day TTL prints a refresh reminder, or auto-refreshes when `auto_refresh = true`. The round-trip write preserves your other tables and comments and stays `0600`. |
| `last_export` | string | Optional. ISO 8601 UTC timestamp of the last successful export (`pplx-export export` or `pplx-export batch`). Updated automatically by the CLI (`pplx_export/commands/common.py:update_last_export`); best-effort, never blocks export. |

### `[accounts.<name>]`

One table per account; `<name>` is the account username. The registry loads into three dicts keyed by username: `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Field | Type | Required | Meaning |
|---|---|---|---|
| `display_name` | string | no | Full display name, used for archive directory naming (`web_archive/<display name>/…`); falls back to the username when omitted. See [Archive layout](archive-layout.md). |
| `email` | string | recommended | Login email. The transport verifies cookie ownership against it, preventing "an export for account B carrying account A's session" (`pplx_export/config.py:69-72`). On mismatch the tool enumerates per-account session tokens in the browser and switches automatically — see [Multi-account cookie model](#multi-account-cookie-model). |
| `user_id` | string | for `pplx-ask` telemetry | Account uid, required by thread-viewed telemetry (`pplx_export/config.py:73-75`). Read it from `GET /api/auth/linked-accounts`, which returns every signed-in account's `user_id` / `email` / `display_name` — see [API authentication](../reference/api/api-authentication.md). |

### `[bot_space]`

The BOT space is the collection point for threads created by `pplx-ask` after they complete (`pplx_export/config.py:76-79`). Create the space itself with `pplx-ask space-create` (see [pplx-ask](pplx-ask.md)), then register it here.

| Field | Type | Meaning |
|---|---|---|
| `uuid` | string | Space UUID. `pplx-ask` moves finished threads here (`pplx_export/ask_cli.py:155-157`); when empty, the move step is skipped. |
| `slug` | string | The space's URL slug. Loaded into `BOT_SPACE_SLUG` (`pplx_export/config.py:79`); the runtime CLI does not read it — the fixture-maintenance tool consumes it, building an identity-replacement pair from it (`tests/scrub_fixtures.py:446-447`). |

### CLI flags, not config fields

The TOML has no transport or cookie settings. Those are chosen per invocation:

| Concern | Where it is set |
|---|---|
| Config file path | `--config PATH`, or `PPLX_EXPORT_CONFIG` |
| Cookie source | `--cookies-from BROWSER` / `--cookies FILE` |
| Transport | `--transport cookie\|webbridge` (`pplx-export` only; default `cookie`) |
| Skip the startup account check | `--skip-auth-check` (both entries) — see [Multi-account cookie model](#multi-account-cookie-model) |

See [pplx-export](pplx-export.md) for the full flag reference.

## Missing config: degraded mode

When nothing is loaded, the module-level registries stay empty and `LOADED_CONFIG_PATH` is `None` (`pplx_export/config.py:83-85`). Behavior by scenario (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`):

| Scenario | Behavior |
|---|---|
| No config at the default path, `--account` not given | Degraded mode: a warning is logged and commands run with a placeholder account (`username='default'`); the email ownership check is skipped. Day-to-day offline commands are unaffected (`pplx_export/commands/common.py:86-90`). |
| No config, explicit `--account` | `SystemExit` naming the lookup order and pointing at `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| Config loaded, `--account` not registered | `SystemExit` naming the loaded file, asking you to add `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| Explicit path (`--config` / env var) does not exist | `ConfigError` in strict mode (`pplx_export/config.py:140-146`). |
| File exists but fails to parse | Always `ConfigError` — a corrupt config must not silently degrade (`pplx_export/config.py:147-150`). |
| `--account` omitted, config loaded | `default_account` is used (`pplx_export/commands/common.py:84-85`). |

What "offline commands" cover and how degraded runs interact with the archive is detailed in [Offline operations](../architecture/offline-operations.md).

## Multi-account cookie model

With several accounts signed into the same browser, the store holds one session cookie **per account**, and the config's `email` field tells the tool which one it needs:

- Each signed-in account has a `__Secure-pplx.session.<uid>` cookie (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`); the `<uid>` suffix is the account's `user_id`.
- The **active** account is whichever token currently sits in `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). Switching accounts = writing the target account's per-account cookie value into that cookie — no browser UI needed (`pplx_export/core/cookies/loaders.py:180-187`).
- At startup the transport probes `GET https://www.perplexity.ai/api/auth/session` and compares the returned email against `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- On mismatch, `_try_switch_account` (`pplx_export/commands/common.py:190-215`) enumerates every account token in the browser via `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`, preferring entries on the `www.` subdomain), tries each one in `__Secure-next-auth.session-token`, and rebuilds the transport on the first match.
- If no token matches, the command exits naming both emails and asking you to log the target account in the browser first (`pplx_export/commands/common.py:142-145`) — see [Troubleshooting](troubleshooting.md).
- An account with no registered `email` proceeds unchecked, with a warning asking you to confirm the browser login yourself (`pplx_export/commands/common.py:146-149`).

For the full switching flow and the session-endpoint semantics, see [Ask and accounts](../architecture/ask-and-accounts.md) and [API authentication](../reference/api/api-authentication.md).

**Skipping the check (`--skip-auth-check`).** The startup session probe above
trades a few seconds — sometimes minutes on a poor network — for the "account B
used as account A" ownership guard. When you know the browser is signed into the
right account, `--skip-auth-check` (shared by `pplx-export` and `pplx-ask`) skips
that probe entirely and goes straight to work (`pplx_export/commands/common.py`,
`make_transport`):

- No `GET /api/auth/session` at startup, so a flaky network no longer produces
  a long silent wait (now heartbeated) before the first real request.
- The tool trusts whichever account is currently logged in; the upfront
  email-ownership check and the automatic multi-account switching above are not
  run.
- **Deferred safety net**: in `batch`, once generic export errors accumulate
  (three failures), a one-time account check runs and warns you what it found —
  the cookie is expired, the account mismatches the target, or the account is
  fine (so the errors are network / rate-limit, not auth)
  (`pplx_export/commands/common.py`, `report_account_status`;
  `pplx_export/commands/batch_cmd.py`).
- **Trade-off**: the deferred check catches an expired cookie, but it cannot
  catch a *wrong-but-valid* account that exports without error — with
  `--skip-auth-check` you take responsibility that the logged-in account is the
  intended one.

Use it for fast, unattended runs on a known-good login; omit it when you rely
on the upfront ownership guard or automatic account switching.

## Cookie cache

After successful validation the resolved cookies are cached so later runs skip the browser:

| Property | Value |
|---|---|
| Path | `<archive root>/index/.cookies.json` — follows `--out` (`pplx_export/commands/common.py:111`) |
| Freshness | 12 hours (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`); a stale or corrupt cache is treated as absent |
| Contents | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Write | Atomic: temp file created with mode `0o600`, then `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Covered by `.gitignore` (`**/index/.cookies.json`) |

Cookie resolution order (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`): explicit `--cookies-from` → explicit `--cookies` file → fresh cache → auto-detect browsers (edge → chrome → firefox → safari). The cache is refreshed after every successful account validation (`pplx_export/commands/common.py:150`).

## Protecting your files

- `chmod 600` your `config.toml` — it contains personal data (emails, user IDs).
- The cookie cache is already written with mode `0o600` by the tool; session cookies are login-equivalent credentials.
- If you hand-craft a cookie file for `--cookies`, apply `chmod 600` to it as well.

## When authentication fails

Expired cookies, an account the auto-switch cannot find, browser keychain permission errors, and other auth failures are covered in [Troubleshooting](troubleshooting.md).
