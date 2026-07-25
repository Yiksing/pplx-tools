# Endpoint Discovery and Improvement Roadmap

*Part of the Perplexity web API reference — full map at the [API index](index.md).*

## Known unexplored / TBD items

- `list_collection_threads` sort field and exact `total_threads` semantics
  (2026-07 live-account snapshot: reported 99 vs 27 top-level items).
- Full spectrum of `threadAccess`/`access`/`user_permission` values (2026-07
  observed sample: threadAccess 5 normal, 1 with 🔒; collection access 1;
  permission 4 owner / 2 can edit; assets data also carries thread_access).
- Correct parameter shapes for `list_ask_threads`, `list_scheduled_computer_tasks` (direct GET 400).
- Response structures of `collections/*/request-access-info`, `spaces/<uuid>/recurring_tasks`, `assets/<id>/members`.
- Why the dashboard GraphQL operations are unregistered (PERSISTED_QUERY_NOT_FOUND): version skew or context gating;
  when needed, re-extract with live hashes from network capture.
- Division of labor among `frontend_uuid` vs `uuid` vs `context_uuid` in computer threads.
- API signal fields of cross-account space-shared branch threads (branch_of)
  (parent pointer / branch marker) — mechanism confirmed (end of
  [§3.3](api-rest-endpoints.md)); no archived instance as of 2026-07-23;
  verify and record when the first appears.

## Endpoint discovery method: frontend bundle static analysis (zero API cost; established 2026-07-20)

Discovered **147 `/rest/` endpoints** in one pass; the method is reusable (re-run after frontend revamps):

1. The page-load entry `_spa/assets/index.html-*.js` references `bootstrap-*.js` (the runtime contains all chunk mappings);
2. Extract 682 chunk filenames (`<name>-<hash8>.js` pattern) from bootstrap; filter API-related by name
   (client/api/thread/collection/space/computer…);
3. Download directly from the public CDN `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js`
   (no cookie needed); hub modules: `platform-core-*` (API client), `spa-shell-*`, `spa-metadata-*`;
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` yields the endpoint list (147);
5. Chunks also leak call shapes (e.g. export's `format:'md'` and `file_content_64`).
6. Sourcemaps also exist: `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (not explored).

### Appendix: 147 endpoints grouped by category (archive-relevance marked)

- **thread**: `/rest/thread/{entry_uuid_or_slug}`, `/rest/thread/export`★, `/rest/thread/{uuid}/members`,
  `/rest/thread/list_recent`, `/rest/thread/list_ask_threads`, `/rest/thread/list_pinned_ask_threads`,
  `/rest/thread/list_scheduled_computer_tasks`, `/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★: see the [§3.3](api-rest-endpoints.md) full table (incl. batch_move/batch_remove, list_user_collections, request-access-info,
  recurring_tasks, pins/threads, scheduled_threads)
- **assets**★: `/rest/assets/{asset_id}/data`, `/rest/assets/{asset_id}/members`,
  `/rest/assets/{asset_id}/published-access`, `/rest/assets/sites/{site_id}/publish-info`
- **analytics**: `/rest/analytics/computer/usage`, `/rest/analytics/computer/usage/members`
  (both 403 NOT_ORG_MEMBER — org accounts only)
- **models/skills**: `/rest/models/config(/v2)`, `/rest/skills`, `/rest/skills/selectable`,
  `/rest/skills/grants`, `/rest/skills/submissions(/source)`
- **files/uploads**: `/rest/file-repository/*` (list/download/get-file-upload-urls/delete-files…),
  `/rest/files/list(/list-infinite/list-errors)`, `/rest/uploads/(batch_)create_upload_url(s)`,
  `/rest/connectors/attachments/upload`
- **tasks/computer**: `/rest/tasks/`, `/rest/tasks/{task_id}`, `/rest/tasks/shortcuts/mentions`,
  `/rest/tasks/shortcuts/paste/{copy_token}`, `/rest/computer/asset`, `/rest/computer/menu`,
  `/rest/computer/onboarding_cards`
- **user/auth**: `/rest/user/settings`, `/rest/user/get_user_ai_profile`, `/rest/user/promotions`,
  `/rest/user/site-instructions`, `/rest/auth/get_special_profile`, `/rest/visitor/*`
- **billing/stripe**: `/rest/billing/*` (credits/paypal/subscription…), `/rest/stripe/*`
- **enterprise/org**: `/rest/enterprise/*`, `/rest/organizations/{id}/credit-limits*`,
  `/rest/pplx-api/v2/enterprise-api-org`
- **sse**: `/rest/sse/attachment_processing/subscribe`, `/rest/sse/index_files`,
  `/rest/sse/perplexity_terminate`, `/rest/sse/related-queries/{entry_uuid}`
- **verticals** (irrelevant to archiving): `/rest/finance/*`, `/rest/sports/*`, `/rest/travel/hotels/{slug}`,
  `/rest/health-assistant/*`, `/rest/article/{uuid_or_slug}`
- **misc**: `/rest/pins`, `/rest/rate-limit/(all|status)`, `/rest/notifications/web-push/*`,
  `/rest/attribution/*`, `/rest/homepage-widgets/upsell`, `/rest/ntp/upsell/`, `/rest/sidebar/upsell/`,
  `/rest/incentives/comet-activation`, `/rest/connector-service/usage`

(★ = directly relevant to archiving)

## Endpoint → tool capability status and roadmap

Implementation status below was synchronized with the current code and test
suite on **2026-07-24**. API evidence keeps the date and scope of the original
live observation or static analysis; this documentation sync did not re-probe
private endpoints. Account/archive counts are snapshots, not platform-wide
guarantees.

Status meanings:

- **Implemented** — a current CLI or production path uses the endpoint for the
  stated capability.
- **Partial** — the endpoint is in use, but the downstream capability in the
  roadmap remains incomplete.
- **Tested, not integrated** — the live API behavior was observed, but no tool
  path consumes it.
- **Planned** — evidence exists, but implementation has not started.
- **Blocked** — a known upstream or protocol blocker prevents implementation.
- **Closed** — evidence disproved the proposed use or placed it out of scope.

### Capability status matrix

| Endpoint / operation | Verification basis | Current integration | Status | Remaining gap |
|---|---|---|---|---|
| `collections/get_collection` | live observation + current code | `spaces --fetch-meta` builds the space owner/member index | **Implemented** | — |
| `collections/list_collection_threads` | live observation + current code | `space-index` uses REST by default with context_uuid dual-ID mapping; WebBridge is fallback | **Implemented** | Sort order and exact `total_threads` semantics remain TBD |
| `assets/<uuid>/data` | live-tested 2026-07-20 + current code | `assets-backfill --online` refreshes signed URLs for real asset UUIDs | **Implemented** | `toolu_` cloud-workspace handles are outside this endpoint's coverage |
| `LibraryThreadsRelayQuery` and pagination query | captured APQ + current code | `index`/`batch` provide full indexing and incremental early-stop | **Implemented** | Dashboard mode-filter queries remain blocked separately |
| `collections/list_user_collections` | live-observed 2026-07 + current code | `init` uses an exact-title match to discover the BOT space | **Partial** | Build an authoritative account-space registry for new-space discovery and `spaces` rebuild |
| `credits/thread-usage` | live-tested 2026-07-20 + current code | `usage-backfill` writes `index/credit_usage_<account>.json` | **Partial** | Decide whether to enrich `thread.json` and/or library index rows without duplicating authority |
| `models/config/v2` | live-tested 2026-07-21 + current code | `pplx-ask models` lists models/defaults; normalization constants are cross-checked against it | **Partial** | Persist stable model display metadata in archive/index records if useful |
| `POST /rest/thread/export` | md/pdf/docx live-tested 2026-07-20 | no CLI integration | **Tested, not integrated** | Multi-format archiving and official-Markdown reconciliation |
| `rate-limit/status` | page-load observation; response semantics unexplored | none | **Planned** | Validate semantics before using it for adaptive throttling |
| `file-repository/list-files` | frontend static analysis only | none | **Planned** | Validate whether it can enumerate/rescue `toolu_` handles; a 2026-07 archive snapshot recorded 270 handles without a download channel |
| `pins`, `tasks/{id}` | frontend static analysis / page-load observations | none | **Planned** | Pin state and computer-task duration enrichment |
| `thread/<uuid>/members` | live-tested 2026-07 | none | **Planned** | Thread-level sharing edges for the relations graph |
| Dashboard GraphQL `threadGroup` + mode filters | direct calls returned `PERSISTED_QUERY_NOT_FOUND` | none | **Blocked** | Recover live persisted-query hashes or establish the required context |
| `related_queries` / `sse/related-queries` | archive-wide forensics settled 2026-07-23 | deliberately produces no relation edges | **Closed** | Reopen only if new evidence establishes resolvable thread identity |

### Active roadmap

#### P0 — Official export integration

- **Multi-format archiving**: optionally retain PDF/DOCX products returned by
  `POST /rest/thread/export`.
- **Renderer reconciliation**: compare official whole-thread Markdown with
  `conversation.md` as an independent regression signal.

#### P1 — Space discovery

- Promote `list_user_collections` from BOT-title lookup to an authoritative,
  account-scoped space registry used for new-space discovery and `spaces`
  rebuilding.

#### P2 — Metadata, risk control, and asset rescue

- Decide and document the authority boundary for credit usage: keep the
  dedicated `credit_usage_<account>.json`, or also enrich `thread.json` /
  library rows.
- Add model display metadata, pin state, computer-task duration, and thread
  sharing relations only where the endpoint semantics are stable.
- Validate `rate-limit/status` before designing adaptive throttling.
- Test `file-repository/list-files` as a possible `toolu_` rescue path before
  adding any archive mutation.

#### P3 — Blocked discovery

- Re-capture the dashboard GraphQL persisted-query hashes only if per-mode
  incremental indexing becomes valuable enough to justify the maintenance
  cost.

### Closed decisions / not adopted

- **Official export as report source**: disproved. The endpoint returns
  whole-thread Markdown without the report body; the signed-URL chain remains
  the official source for `report.md` ([§3.6](api-rest-endpoints.md)).
- **Relations from `related_queries`**: disproved 2026-07-23. Item UUIDs are not
  thread UUIDs and recommendation texts did not resolve to archived queries;
  no relation edges are built ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)`: observed as organization-only
  (`403 NOT_ORG_MEMBER`) for the tested accounts.
- `thread/request-access-info`: tested as organization-join related, not a
  `threadAccess` signal.
- Billing/Stripe/enterprise and finance/sports verticals remain outside the
  archive tool's scope.

---

*This document complements [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md) (tool architecture) and [overview.md](../../architecture/overview.md) (system design).*
