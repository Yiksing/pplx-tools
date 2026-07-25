---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-graphql.md"
translation_source_sha256: "3963e26d58d8dc1ad0835fe715357592295f31dd7c3b7c3f1ca67854fa3c98a0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-graphql" data-pplx-source-anchor="true"></a>
# Riferimento API: GraphQL

<a id="graphql-persisted-queries-apq" data-pplx-source-anchor="true"></a>
## GraphQL (query persistenti / APQ)

- **Endpoint**: `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **Forma**: query persistente — il corpo contiene operationName + variabili + un hash sha256 (nessun testo di query necessario).
- Implementazione: `pplx_export/sites/perplexity/graphql.py`.

<a id="librarythreadsrelayquery-list-first-page" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery (elenco prima pagina)
- sha256: `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- Variabili: `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- Percorso risposta: `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- Campi nodo (usati dall'adattatore): `name(title)`, `entryId(entryUUID)`, `slug(href)`, `mode`, `displayModel.modelID`,
  `updatedAt(lastUpdated)`, `status`, `space{spaceUuid,title,slug}`
- **Contratto lato archivio (2026-07-22 V5-01)**: il `lastUpdated` di `web_archive/**/thread.json` è sempre uguale a questo campo
  (scritto su disco con precisione ISO completa, testuale); il confronto di idempotenza per esportazione batch/singola (`is_unchanged`) si basa su di esso,
  non più sul formato di presentazione del livello di rendering (`YYYY-MM-DD HH:MM UTC`).
- **Arricchimento lato archivio (2026-07-23)**: la chiave `search_mode` delle righe dell'indice (`index/library_*.json`) è un
  campo di arricchimento lato archivio — il nodo di questa query non contiene search_mode; viene riempito da `pplx-export search-mode-backfill`
  a partire dai dati a livello di thread (`entries[].search_mode` di `GET /rest/thread/<uuid>`) (prima raw locale,
  fallback online); l'aggiornamento `index` unisce e preserva per entryUUID. Il filtraggio `batch --mode` preferisce la mappatura autorevole di questo campo.

<a id="libraryrecentthreadspaginationquery-pagination" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery (paginazione)
- sha256: `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- Variabili: variabili della prima pagina + `{cursor, count}` (**i nomi delle variabili sono cursor/count, non after/first**)
- Stessa struttura di risposta di cui sopra. Quando `hasNextPage` è true ma `endCursor` è vuoto, fermati (altrimenti la stessa pagina si ripete).

<a id="computer-dashboard-operation-group-extracted-from-route-chunk-2026-07-20-not-registered-on-the-server" data-pplx-source-anchor="true"></a>
### Gruppo di operazioni della dashboard Computer (estratto dal chunk di route 2026-07-20, **non registrato sul server**)

Il chunk `ComputerDashboardPage-*.js` incorpora testi completi delle query Relay + id persistenti (metodo di estrazione in [§7](api-discovery-roadmap.md)).
Elementi strutturali essenziali: `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— cioè un elenco di thread filtrato per threadGroup + mode; il nodo contiene `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`.

| operazione | id persistente (primi 16 caratteri) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (sottoscrizione WebSocket) |

**Testato**: chiamare `/rest/perplexity_ask/graphql` con questi id restituisce `PERSISTED_QUERY_NOT_FOUND`
(non registrato nel deployment corrente — disallineamento di versione o contesto dashboard richiesto; i testi completi delle query e gli id sono conservati nelle note di esplorazione `/tmp`;
se necessario, inviare il testo della query direttamente o re-estrarre dal bundle live).

<a id="notes" data-pplx-source-anchor="true"></a>
### Note
- Nessuna chiamata graphql osservata sulla pagina web space o sulla home page (tutte passano attraverso /rest); graphql è confermato per l'elenco /library e la dashboard Computer.
- Gli hash sha256 possono cambiare con le versioni del frontend; la modalità di errore è `PERSISTED_QUERY_NOT_FOUND` — quindi re-estrarre dalla
  cattura di rete del browser (strumento WebBridge `network` filtrando `perplexity_ask/graphql`), o re-estrarre dal bundle live ([§7](api-discovery-roadmap.md)).

<a id="extracted-dashboard-connection-keys-relay-cache-keys-for-debugging" data-pplx-source-anchor="true"></a>
### Chiavi di connessione della dashboard estratte (chiavi cache Relay, per debug)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
