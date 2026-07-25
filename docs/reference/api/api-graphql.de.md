---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-graphql.md"
translation_source_sha256: "3963e26d58d8dc1ad0835fe715357592295f31dd7c3b7c3f1ca67854fa3c98a0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-graphql" data-pplx-source-anchor="true"></a>
# API-Referenz: GraphQL

<a id="graphql-persisted-queries-apq" data-pplx-source-anchor="true"></a>
## GraphQL (persistierte Abfragen / APQ)

- **Endpunkt**: `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **Form**: persistierte Abfrage – der Body enthält operationName + Variablen + einen SHA-256-Hash (kein Abfragetext erforderlich).
- Implementierung: `pplx_export/sites/perplexity/graphql.py`.

<a id="librarythreadsrelayquery-list-first-page" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery (erste Seite auflisten)
- SHA-256: `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- Variablen: `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- Antwortpfad: `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- Knotenfelder (vom Adapter verwendet): `name(title)`, `entryId(entryUUID)`, `slug(href)`, `mode`, `displayModel.modelID`,
  `updatedAt(lastUpdated)`, `status`, `space{spaceUuid,title,slug}`
- **Archivseitiger Vertrag (2026-07-22 V5-01)**: der `lastUpdated` von `web_archive/**/thread.json` ist immer gleich diesem Feld
  (auf Disk mit voller ISO-Genauigkeit, wörtlich geschrieben); der Idempotenzvergleich (`is_unchanged`) für Batch-/Einzelexport basiert darauf,
  nicht mehr auf dem Präsentationsformat der Rendering-Ebene (`YYYY-MM-DD HH:MM UTC`).
- **Archivseitige Anreicherung (2026-07-23)**: der `search_mode`-Schlüssel von Indexzeilen (`index/library_*.json`) ist ein
  archivseitiges Anreicherungsfeld – dieser Abfrageknoten enthält kein search_mode; es wird von `pplx-export search-mode-backfill`
  aus Thread-Level-Daten (`entries[].search_mode` von `GET /rest/thread/<uuid>`) nachgefüllt (lokal roh zuerst,
  Online-Fallback); `index`-Aktualisierung führt zusammen und bewahrt es nach entryUUID. `batch --mode`-Filterung bevorzugt die autoritative Zuordnung dieses Felds.

<a id="libraryrecentthreadspaginationquery-pagination" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery (Paginierung)
- SHA-256: `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- Variablen: Variablen der ersten Seite + `{cursor, count}` (**die Variablennamen sind cursor/count, nicht after/first**)
- Gleiche Antwortstruktur wie oben. Wenn `hasNextPage` wahr ist, aber `endCursor` leer ist, anhalten (andernfalls wiederholt sich dieselbe Seite).

<a id="computer-dashboard-operation-group-extracted-from-route-chunk-2026-07-20-not-registered-on-the-server" data-pplx-source-anchor="true"></a>
### Computer-Dashboard-Operationsgruppe (extrahiert aus Routen-Chunk 2026-07-20, **nicht auf dem Server registriert**)

Der `ComputerDashboardPage-*.js`-Chunk enthält vollständige Relay-Abfragetexte + persistierte IDs (Extraktionsmethode in [§7](api-discovery-roadmap.md)).
Strukturelle Grundlagen: `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— d.h. eine Thread-Liste gefiltert nach threadGroup + Modus; Knoten enthält `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`.

| Operation | Persistierte ID (erste 16 Zeichen) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (WebSocket-Abonnement) |

**Getestet**: Aufruf von `/rest/perplexity_ask/graphql` mit diesen IDs gibt `PERSISTED_QUERY_NOT_FOUND` zurück
(nicht in der aktuellen Bereitstellung registriert – Versionsabweichung oder Dashboard-Kontext erforderlich; die vollständigen Abfragetexte und IDs werden in `/tmp`-Erkundungsnotizen aufbewahrt;
falls erforderlich, den Abfragetext direkt senden oder aus dem Live-Bundle erneut extrahieren).

<a id="notes" data-pplx-source-anchor="true"></a>
### Hinweise
- Keine GraphQL-Aufrufe auf der Web-Space-Seite oder Startseite beobachtet (alle gehen über /rest); GraphQL ist für die /library-Liste und das Computer-Dashboard bestätigt.
- Die SHA-256-Hashes können sich mit Frontend-Versionen ändern; der Fehlermodus ist `PERSISTED_QUERY_NOT_FOUND` – dann erneut aus dem Browser-Netzwerk-Mitschnitt extrahieren
  (WebBridge `network`-Tool-Filterung `perplexity_ask/graphql`) oder aus dem Live-Bundle erneut extrahieren ([§7](api-discovery-roadmap.md)).

<a id="extracted-dashboard-connection-keys-relay-cache-keys-for-debugging" data-pplx-source-anchor="true"></a>
### Extrahierte Dashboard-Verbindungsschlüssel (Relay-Cache-Schlüssel, zum Debuggen)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
