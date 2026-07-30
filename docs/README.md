# docs

Documentation sources for the pplx-tools documentation site, built with
[MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
and [mkdocs-static-i18n](https://github.com/ultrabug/mkdocs-static-i18n) (suffix mode).

Every English page `x.md` has a Chinese twin `x.zh-CN.md` in the same directory.
This README is excluded from the built site (`exclude_docs` in `mkdocs.yml`) and
only serves browsing on GitHub.

## Source layout

The published navigation is organized by audience and task. It is intentionally
decoupled from the source directories below, while each top-level section uses
an `index.md` landing page.

- `index.md` — site home
- `guide/` — task-oriented usage guides
  - `index.md` — user-guide landing page
  - `getting-started.md` — install, configure, first export
  - `configuration.md` — user-level config file, accounts, BOT space
  - `pplx-export.md` — export commands (index / export / batch)
  - `maintenance-commands.md` — backfill, relations, sync-deleted and other maintenance commands
  - `pplx-ask.md` — streaming query command
  - `archive-layout.md` — on-disk archive structure
  - `modes.md` — the five query modes
  - `incremental-sync.md` — incremental export & resumable sync
  - `rate-limiting.md` — rate-limit discipline for operators
  - `troubleshooting.md` — common failures and fixes
- `architecture/` — implementation and reliability design
  - `index.md` — architecture reading map
  - `overview.md` — architecture overview
  - `export-pipeline.md` — export pipeline
  - `subagents-interruptions.md` — sub-agent attribution & interruption semantics
  - `ask-and-accounts.md` — ask sequence & multi-account switching
  - `data-model.md` — data model & directory contract
  - `rate-limiting-errors.md` — rate limiting & error handling
  - `offline-operations.md` — offline operations
- `reference/api/` — observed Perplexity Web API reference
  - `index.md` — API reference landing page and scope
  - `api-authentication.md` — API authentication model
  - `api-graphql.md` — API GraphQL operations
  - `api-rest-endpoints.md` — API REST endpoints
  - `api-responses-errors.md` — API responses & error semantics
  - `api-discovery-roadmap.md` — API discovery methods & roadmap
- `development/` — maintainer and contributor docs
  - `index.md` — maintainer-guide landing page
  - `testing-architecture.md` — testing system architecture
  - `testing.md` — testing practices
  - `fixtures.md` — fixtures & snapshots
  - `i18n.md` — canonical-language and generated-translation contracts
- `perplexity-api-samples/` — `POST /rest/sse/perplexity_ask` request body samples (search / deep-research / council modes)

Historical `/design/.../` URLs are generated as redirect pages by
`mkdocs-redirects`; the source pages themselves live only in their current
directories.

## Building

```bash
uv run mkdocs serve   # local preview
uv run mkdocs build --strict   # static site in site/, warnings fail the build
```

## Auditing

The repository-specific auditor is read-only and offline:

```bash
uv run python scripts/audit_docs.py
uv run python scripts/audit_docs.py --format json
```

It validates bilingual structure, repository-local links, source-line
references, the test and fixture inventories, and the simulated-fixture source
contract. It deliberately does not probe external links, live APIs, user
configuration, or private archives.

The GitHub `quality / validate` job runs the audit together with the dependency
lock check, fixture residue gate, complete pytest suite, and strict build of
every configured locale. Non-English/non-Simplified-Chinese generated pages
are frozen as of 2026-07-30 for cost reasons. The remote translation workflow
is manually disabled; local checks preserve frozen output integrity without
requiring stale generated pages to be refreshed.
