# Getting started

From a fresh checkout to a first local archive: install the two commands, create the
user-level config, choose a cookie channel, and walk through a first export.

## Requirements

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — used to install the tools and run the test suite
- **A desktop browser logged into Perplexity** — the tools reuse its session cookies;
  no token is ever stored in the config

Cookie decryption uses `browser_cookie3`. Auto-detect covers Edge, Chrome, Firefox and
Safari; Brave, Chromium, Opera and Vivaldi work via `--cookies-from`.

## Install

No clone needed — install straight from the git URL:

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

From a local clone (repo root):

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

This installs two commands: `pplx-export` (archiving) and `pplx-ask` (interactive
queries). Verify:

```bash
pplx-export --version
pplx-export --help           # overview with examples; each subcommand has its own --help
pplx-ask --help
```

`uvx --from . pplx-export` runs a one-off command without installing.

## Create the user-level config

The account registry (display name / email / user_id) and the BOT space are personal
data and are **not committed to the repo**; they live in an external TOML file.
Template: `config.example.toml` at the repo root.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

1. Create the config directory.
2. Copy the template to the default path.
3. `chmod 600` — the file holds personal data; keep it owner-only.
4. Fill in `[accounts.<name>]` — the key is the account username (as it appears in
   thread URLs / the library); set `display_name`, `email`, `user_id`, and pick a
   `default_account`.
5. Fill in `[bot_space]` — where threads created by `pplx-ask` are collected after
   completion (a real space can be created with `pplx-ask space-create`).

**Automatic alternative:** `pplx-export init` derives this file for you — it
enumerates the per-account session cookies in your browser, probes
`/api/auth/session` for each token's email / display name, sets
`default_account` to the currently active account, matches the BOT space by
title, and writes the TOML atomically with 0600 permissions (an existing file
is only overwritten with `--force`).

```bash
pplx-export init                     # discover accounts, write the default config path
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --bot-title TITLE   # match/create a different space title (default BOT)
pplx-export init --config /path/to/config.toml   # write to a custom path
```

Flags: `--force` overwrites an existing config; `--create-bot-space [TITLE]`
creates the space via the API when no title matches (a write operation on the
account; an explicit TITLE drives both matching and creation); `--bot-title TITLE`
is used for both matching and creation. Note that for
`init` — unlike every other command — `--config` is the **write** path, not
the load path. Full details: [pplx-export → init](pplx-export.md#init).

The full field reference lives in [Configuration](configuration.md).

**Load priority** (highest first):

| # | Source |
|---|--------|
| 1 | `--config PATH` |
| 2 | `PPLX_EXPORT_CONFIG` environment variable |
| 3 | `~/.config/pplx-export/config.toml` (default) |

!!! note "When the config is missing"
    Commands without `--account` run in a degraded mode — the email ownership check is
    skipped with a warning (offline commands are unaffected); an explicit `--account`
    raises an error pointing at `config.example.toml`. When `--account` is omitted,
    `default_account` from the config is used.

## Choose a cookie channel

Credentials come from your local browser's logged-in Perplexity session cookies, read
via `browser_cookie3` — including multi-account token enumeration and automatic
switching. Four channels:

| Channel | How | Notes |
|---------|-----|-------|
| Auto-detect (default) | no flag | fresh 12 h cache first, then browser stores in the order edge→chrome→firefox→safari |
| Named browser | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| Cookie file | `--cookies /path/to/cookies.txt` | Netscape cookie file or exported JSON |
| WebBridge | `--transport webbridge` | page-context fetch — the fallback channel, only used when explicitly requested |

On Linux, snap and flatpak browser installs are auto-detected too — their profile
paths are covered by the built-in registry. The full Linux matrix (keyring, desktop
environments, distro packages):
[Troubleshooting → Linux cookie decryption](troubleshooting.md#linux-cookie-decryption).

```bash
pplx-export export <thread_url>                                 # default: auto-detect browser store
pplx-export export <thread_url> --cookies-from edge             # import from a specific browser
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # use a cookie file
pplx-export export <thread_url> --transport webbridge           # WebBridge page context (explicit fallback)
```

After cookies are obtained, the tool calls `/api/auth/session` and prints the current
account email so you can confirm the right account is in use — watch out if `--account`
disagrees with the cookie account. The transport/credential design is covered in
[Ask & accounts](../architecture/ask-and-accounts.md).

## First run

```bash
pplx-export index --account alice     # fetch the library index
pplx-export export <thread_url>       # export a single thread
pplx-export batch --account alice     # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run       # offline re-render, zero network
```

1. **`index`** fetches the account's library index — the entry point that `batch` and
   the other account-wide commands build on.
2. **`export`** archives one thread end to end: it retains the raw API responses
   (`raw_*.json`) alongside Markdown so the render can be replayed offline.
3. **`batch`** sweeps the whole library. It stops early once everything remaining is
   already archived (incremental early-stop), writes resumable checkpoints, and accepts
   `--full` for a full sweep. Details: [Incremental sync](incremental-sync.md).
4. **`re-render --dry-run`** proves the offline path: it regenerates `conversation.md`
   + `turns/` from local raw files with zero network. Drop `--dry-run` to write the
   results. See [Offline operations](../architecture/offline-operations.md).

Once that works, `pplx-ask ask "<prompt>"` runs a streaming query and archives the
resulting thread automatically — see [pplx-ask](pplx-ask.md).

## Where archives land

Archives are written to `./web_archive/` by default (override with `--out`): one
directory per thread.

| Path | Content |
|------|---------|
| `conversation.md`, `turns/` | rendered conversation |
| `thread.json` | thread metadata + interruptions registry |
| `sources.md` / `sources.json` | citations |
| `report.md` | deep-research / council / study report |
| `assets/` | downloaded assets (computer mode) |
| `raw_*.json` | retained raw API responses — successful archives can be re-rendered offline without re-fetching |

The full directory contract: [Archive layout](archive-layout.md).

## Next steps

- Something went wrong? → [Troubleshooting](troubleshooting.md)
- Command-by-command reference → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [Maintenance commands](maintenance-commands.md)
- The five conversation modes → [Modes](modes.md)
