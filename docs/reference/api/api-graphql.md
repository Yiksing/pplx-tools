# API Reference: GraphQL

## GraphQL (persisted queries / APQ)

- **Endpoint**: `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **Form**: persisted query — the body carries operationName + variables + a sha256 hash (no query text needed).
- Implementation: `pplx_export/sites/perplexity/graphql.py`.

### LibraryThreadsRelayQuery (list first page)
- sha256: `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- Variables: `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- Response path: `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- node fields (used by the adapter): `name(title)`, `entryId(entryUUID)`, `slug(href)`, `mode`, `displayModel.modelID`,
  `updatedAt(lastUpdated)`, `status`, `space{spaceUuid,title,slug}`
- **Archive-side contract (2026-07-22 V5-01)**: the `lastUpdated` of `web_archive/**/thread.json` is always equal to this field
  (written to disk at full ISO precision, verbatim); batch/single-export idempotence comparison (`is_unchanged`) is based on it,
  no longer on the presentation format of the render layer (`YYYY-MM-DD HH:MM UTC`).
- **Archive-side enrichment (2026-07-23)**: the `search_mode` key of index rows (`index/library_*.json`) is an
  archive-side enrichment field — this query's node does not contain search_mode; it is backfilled by `pplx-export search-mode-backfill`
  from thread-level data (`entries[].search_mode` of `GET /rest/thread/<uuid>`) (local raw first,
  online fallback); `index` refresh merges and preserves it by entryUUID. `batch --mode` filtering prefers the authoritative mapping of this field.

### LibraryRecentThreadsPaginationQuery (pagination)
- sha256: `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- Variables: first-page variables + `{cursor, count}` (**the variable names are cursor/count, not after/first**)
- Same response structure as above. When `hasNextPage` is true but `endCursor` is empty, stop (otherwise the same page repeats).

### Computer dashboard operation group (extracted from route chunk 2026-07-20, **not registered on the server**)

The `ComputerDashboardPage-*.js` chunk embeds full Relay query texts + persisted ids (extraction method in [§7](api-discovery-roadmap.md)).
Structural essentials: `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— i.e. a thread list filtered by threadGroup + mode; node contains `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`.

| operation | persisted id (first 16 chars) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (WebSocket subscription) |

**Tested**: calling `/rest/perplexity_ask/graphql` with these ids returns `PERSISTED_QUERY_NOT_FOUND`
(not registered in the current deployment — version skew or dashboard context required; the full query texts and ids are kept in `/tmp` exploration notes;
if needed, send the query text directly or re-extract from the live bundle).

### Notes
- No graphql calls observed on the web space page or home page (all go through /rest); graphql is confirmed for the /library list and the computer dashboard.
- The sha256 hashes may change with frontend versions; the failure mode is `PERSISTED_QUERY_NOT_FOUND` — then re-extract from browser
  network capture (WebBridge `network` tool filtering `perplexity_ask/graphql`), or re-extract from the live bundle ([§7](api-discovery-roadmap.md)).

### Extracted dashboard connection keys (Relay cache keys, for debugging)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
