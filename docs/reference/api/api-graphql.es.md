---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-graphql.md"
translation_source_sha256: "3963e26d58d8dc1ad0835fe715357592295f31dd7c3b7c3f1ca67854fa3c98a0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-graphql" data-pplx-source-anchor="true"></a>
# Referencia de la API: GraphQL

<a id="graphql-persisted-queries-apq" data-pplx-source-anchor="true"></a>
## GraphQL (consultas persistentes / APQ)

- **Endpoint**: `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **Forma**: consulta persistente — el cuerpo lleva operationName + variables + un hash sha256 (no se necesita texto de consulta).
- Implementación: `pplx_export/sites/perplexity/graphql.py`.

<a id="librarythreadsrelayquery-list-first-page" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery (listar primera página)
- sha256: `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- Variables: `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- Ruta de respuesta: `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- Campos de nodo (usados por el adaptador): `name(title)`, `entryId(entryUUID)`, `slug(href)`, `mode`, `displayModel.modelID`,
  `updatedAt(lastUpdated)`, `status`, `space{spaceUuid,title,slug}`
- **Contrato del lado del archivo (2026-07-22 V5-01)**: el `lastUpdated` de `web_archive/**/thread.json` siempre es igual a este campo
  (escrito en disco con precisión ISO completa, textualmente); la comparación de idempotencia de exportación por lotes/individual (`is_unchanged`) se basa en él,
  ya no en el formato de presentación de la capa de renderizado (`YYYY-MM-DD HH:MM UTC`).
- **Enriquecimiento del lado del archivo (2026-07-23)**: la clave `search_mode` de las filas de índice (`index/library_*.json`) es un
  campo de enriquecimiento del lado del archivo — el nodo de esta consulta no contiene search_mode; se rellena mediante `pplx-export search-mode-backfill`
  a partir de datos a nivel de hilo (`entries[].search_mode` de `GET /rest/thread/<uuid>`) (primero raw local,
  fallback en línea); la actualización `index` fusiona y lo conserva por entryUUID. El filtrado `batch --mode` prefiere la asignación autoritativa de este campo.

<a id="libraryrecentthreadspaginationquery-pagination" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery (paginación)
- sha256: `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- Variables: variables de primera página + `{cursor, count}` (**los nombres de variable son cursor/count, no after/first**)
- Misma estructura de respuesta que arriba. Cuando `hasNextPage` es verdadero pero `endCursor` está vacío, detenerse (de lo contrario, la misma página se repite).

<a id="computer-dashboard-operation-group-extracted-from-route-chunk-2026-07-20-not-registered-on-the-server" data-pplx-source-anchor="true"></a>
### Grupo de operaciones del panel de Computer (extraído del chunk de ruta 2026-07-20, **no registrado en el servidor**)

El chunk `ComputerDashboardPage-*.js` incrusta textos completos de consultas Relay + ids persistentes (método de extracción en [§7](api-discovery-roadmap.md)).
Elementos estructurales esenciales: `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— es decir, una lista de hilos filtrada por threadGroup + mode; el nodo contiene `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`.

| operación | id persistente (primeros 16 caracteres) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (suscripción WebSocket) |

**Probado**: llamar a `/rest/perplexity_ask/graphql` con estos ids devuelve `PERSISTED_QUERY_NOT_FOUND`
(no registrado en la implementación actual — desfase de versión o contexto de panel requerido; los textos completos de consulta y los ids se mantienen en las notas de exploración `/tmp`;
si es necesario, enviar el texto de consulta directamente o reextraer del bundle en vivo).

<a id="notes" data-pplx-source-anchor="true"></a>
### Notas
- No se observaron llamadas graphql en la página de espacio web ni en la página de inicio (todas pasan por /rest); graphql está confirmado para la lista /library y el panel de Computer.
- Los hashes sha256 pueden cambiar con las versiones del frontend; el modo de fallo es `PERSISTED_QUERY_NOT_FOUND` — luego reextraer de la
  captura de red del navegador (herramienta WebBridge `network` filtrando `perplexity_ask/graphql`), o reextraer del bundle en vivo ([§7](api-discovery-roadmap.md)).

<a id="extracted-dashboard-connection-keys-relay-cache-keys-for-debugging" data-pplx-source-anchor="true"></a>
### Claves de conexión del panel extraídas (claves de caché de Relay, para depuración)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
