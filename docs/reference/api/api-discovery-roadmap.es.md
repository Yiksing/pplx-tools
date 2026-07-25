---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-discovery-roadmap.md"
translation_source_sha256: "60c675dcc583c059cd489ea085f9c2923f9447f7bbafb0a7ac991fee9f8add08"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="endpoint-discovery-and-improvement-roadmap" data-pplx-source-anchor="true"></a>
# Descubrimiento de Endpoints y Hoja de Ruta de Mejoras

*Parte de la referencia de la API web de Perplexity — mapa completo en el [índice de API](index.md).*

<a id="known-unexplored-tbd-items" data-pplx-source-anchor="true"></a>
## Elementos conocidos no explorados / por determinar

- Campo de ordenación de `list_collection_threads` y semántica exacta de `total_threads`
  (instantánea de cuenta activa de julio de 2026: reportó 99 frente a 27 elementos de nivel superior).
- Espectro completo de valores de `threadAccess`/`access`/`user_permission` (muestra observada en julio de 2026:
  threadAccess 5 normal, 1 con 🔒; collection access 1;
  permission 4 owner / 2 can edit; los datos de assets también incluyen thread_access).
- Formas correctas de los parámetros para `list_ask_threads`, `list_scheduled_computer_tasks` (GET directo devuelve 400).
- Estructuras de respuesta de `collections/*/request-access-info`, `spaces/<uuid>/recurring_tasks`, `assets/<id>/members`.
- Por qué las operaciones GraphQL del panel de control no están registradas (PERSISTED_QUERY_NOT_FOUND): desfase de versión o restricción de contexto;
  cuando sea necesario, reextraer con hashes en vivo de la captura de red.
- División de trabajo entre `frontend_uuid` vs `uuid` vs `context_uuid` en hilos de Computer.
- Campos de señal de API de hilos de rama compartidos entre cuentas (branch_of)
  (puntero padre / marcador de rama) — mecanismo confirmado (final de
  [§3.3](api-rest-endpoints.md)); ninguna instancia archivada al 23 de julio de 2026;
  verificar y registrar cuando aparezca la primera.

<a id="endpoint-discovery-method-frontend-bundle-static-analysis-zero-api-cost-established-2026-07-20" data-pplx-source-anchor="true"></a>
## Método de descubrimiento de endpoints: análisis estático del bundle del frontend (coste de API cero; establecido el 20 de julio de 2026)

Se descubrieron **147 endpoints de `/rest/`** en una pasada; el método es reutilizable (reejecutar después de rediseños del frontend):

1. La entrada de carga de página `_spa/assets/index.html-*.js` referencia a `bootstrap-*.js` (el runtime contiene todos los mapeos de chunks);
2. Extraer 682 nombres de archivos de chunk (patrón `<name>-<hash8>.js`) del bootstrap; filtrar los relacionados con API por nombre
   (client/api/thread/collection/space/computer…);
3. Descargar directamente desde la CDN pública `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js`
   (no se necesita cookie); módulos hub: `platform-core-*` (cliente API), `spa-shell-*`, `spa-metadata-*`;
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` produce la lista de endpoints (147);
5. Los chunks también filtran formas de llamada (por ejemplo, `format:'md'` y `file_content_64` de export).
6. También existen sourcemaps: `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (no explorados).

<a id="appendix-147-endpoints-grouped-by-category-archive-relevance-marked" data-pplx-source-anchor="true"></a>
### Apéndice: 147 endpoints agrupados por categoría (relevancia para archivo marcada)

- **thread**: `/rest/thread/{entry_uuid_or_slug}`, `/rest/thread/export`★, `/rest/thread/{uuid}/members`,
  `/rest/thread/list_recent`, `/rest/thread/list_ask_threads`, `/rest/thread/list_pinned_ask_threads`,
  `/rest/thread/list_scheduled_computer_tasks`, `/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★: ver la tabla completa de [§3.3](api-rest-endpoints.md) (incluye batch_move/batch_remove, list_user_collections, request-access-info,
  recurring_tasks, pins/threads, scheduled_threads)
- **assets**★: `/rest/assets/{asset_id}/data`, `/rest/assets/{asset_id}/members`,
  `/rest/assets/{asset_id}/published-access`, `/rest/assets/sites/{site_id}/publish-info`
- **analytics**: `/rest/analytics/computer/usage`, `/rest/analytics/computer/usage/members`
  (ambos 403 NOT_ORG_MEMBER — solo cuentas de organización)
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
- **verticals** (irrelevantes para archivo): `/rest/finance/*`, `/rest/sports/*`, `/rest/travel/hotels/{slug}`,
  `/rest/health-assistant/*`, `/rest/article/{uuid_or_slug}`
- **misc**: `/rest/pins`, `/rest/rate-limit/(all|status)`, `/rest/notifications/web-push/*`,
  `/rest/attribution/*`, `/rest/homepage-widgets/upsell`, `/rest/ntp/upsell/`, `/rest/sidebar/upsell/`,
  `/rest/incentives/comet-activation`, `/rest/connector-service/usage`

(★ = directamente relevante para archivo)

<a id="endpoint-tool-capability-status-and-roadmap" data-pplx-source-anchor="true"></a>
## Estado de capacidad de endpoint a herramienta y hoja de ruta

El estado de implementación a continuación se sincronizó con el código actual y el conjunto de pruebas
el **24 de julio de 2026**. La evidencia de la API mantiene la fecha y el alcance de la observación
en vivo original o el análisis estático; esta sincronización de documentación no volvió a sondear
endpoints privados. Los recuentos de cuentas/archivos son instantáneas, no garantías a nivel de plataforma.

Significados de estado:

- **Implementado** — una CLI actual o ruta de producción utiliza el endpoint para la
  capacidad indicada.
- **Parcial** — el endpoint está en uso, pero la capacidad descendente en la
  hoja de ruta sigue incompleta.
- **Probado, no integrado** — se observó el comportamiento de la API en vivo, pero ninguna
  ruta de herramienta lo consume.
- **Planificado** — existe evidencia, pero la implementación no ha comenzado.
- **Bloqueado** — un bloqueador upstream o de protocolo conocido impide la implementación.
- **Cerrado** — la evidencia refutó el uso propuesto o lo colocó fuera del alcance.

<a id="capability-status-matrix" data-pplx-source-anchor="true"></a>
### Matriz de estado de capacidad

| Endpoint / operación | Base de verificación | Integración actual | Estado | Brecha restante |
|---|---|---|---|---|
| `collections/get_collection` | observación en vivo + código actual | `spaces --fetch-meta` construye el índice de propietario/miembro del espacio | **Implementado** | — |
| `collections/list_collection_threads` | observación en vivo + código actual | `space-index` usa REST por defecto con mapeo de ID dual context_uuid; WebBridge es alternativa | **Implementado** | El orden de clasificación y la semántica exacta de `total_threads` siguen sin determinar |
| `assets/<uuid>/data` | probado en vivo el 20 de julio de 2026 + código actual | `assets-backfill --online` actualiza las URL firmadas para UUIDs de assets reales | **Implementado** | Los handles de espacio de trabajo en la nube de `toolu_` están fuera de la cobertura de este endpoint |
| `LibraryThreadsRelayQuery` y consulta de paginación | APQ capturado + código actual | `index`/`batch` proporcionan indexación completa y parada temprana incremental | **Implementado** | Las consultas de filtro de modo del panel de control siguen bloqueadas por separado |
| `collections/list_user_collections` | observado en vivo en julio de 2026 + código actual | `init` usa una coincidencia de título exacta para descubrir el espacio BOT | **Parcial** | Construir un registro de espacios autoritativo de la cuenta para el descubrimiento de nuevos espacios y la reconstrucción de `spaces` |
| `credits/thread-usage` | probado en vivo el 20 de julio de 2026 + código actual | `usage-backfill` escribe `index/credit_usage_<account>.json` | **Parcial** | Decidir si enriquecer `thread.json` y/o las filas del índice de la biblioteca sin duplicar la autoridad |
| `models/config/v2` | probado en vivo el 21 de julio de 2026 + código actual | `pplx-ask models` lista modelos/valores predeterminados; las constantes de normalización se verifican contra él | **Parcial** | Persistir metadatos de visualización de modelos estables en registros de archivo/índice si es útil |
| `POST /rest/thread/export` | md/pdf/docx probado en vivo el 20 de julio de 2026 | sin integración en CLI | **Probado, no integrado** | Archivado multiformato y reconciliación de Markdown oficial |
| `rate-limit/status` | observación de carga de página; semántica de respuesta no explorada | ninguno | **Planificado** | Validar semántica antes de usarlo para limitación adaptativa |
| `file-repository/list-files` | solo análisis estático del frontend | ninguno | **Planificado** | Validar si puede enumerar/rescatar handles de `toolu_`; una instantánea de archivo de julio de 2026 registró 270 handles sin un canal de descarga |
| `pins`, `tasks/{id}` | análisis estático del frontend / observaciones de carga de página | ninguno | **Planificado** | Enriquecimiento de estado y duración de tareas de Computer |
| `thread/<uuid>/members` | probado en vivo en julio de 2026 | ninguno | **Planificado** | Aristas de uso compartido a nivel de hilo para el grafo de relaciones |
| GraphQL del panel de control `threadGroup` + filtros de modo | llamadas directas devolvieron `PERSISTED_QUERY_NOT_FOUND` | ninguno | **Bloqueado** | Recuperar hashes de consulta persistida en vivo o establecer el contexto requerido |
| `related_queries` / `sse/related-queries` | análisis forense de todo el archivo resuelto el 23 de julio de 2026 | deliberadamente no produce aristas de relación | **Cerrado** | Reabrir solo si nueva evidencia establece una identidad de hilo resoluble |

<a id="active-roadmap" data-pplx-source-anchor="true"></a>
### Hoja de ruta activa

<a id="p0-official-export-integration" data-pplx-source-anchor="true"></a>
#### P0 — Integración de exportación oficial

- **Archivado multiformato**: conservar opcionalmente los productos PDF/DOCX devueltos por
  `POST /rest/thread/export`.
- **Reconciliación de renderizador**: comparar el Markdown oficial de todo el hilo con
  `conversation.md` como señal de regresión independiente.

<a id="p1-space-discovery" data-pplx-source-anchor="true"></a>
#### P1 — Descubrimiento de espacios

- Promover `list_user_collections` de búsqueda por título BOT a un registro de espacios autoritativo
  y con ámbito de cuenta utilizado para el descubrimiento de nuevos espacios y la reconstrucción de `spaces`.

<a id="p2-metadata-risk-control-and-asset-rescue" data-pplx-source-anchor="true"></a>
#### P2 — Metadatos, control de riesgos y rescate de assets

- Decidir y documentar el límite de autoridad para el uso de crédito: mantener el
  `credit_usage_<account>.json` dedicado, o también enriquecer `thread.json` /
  filas de la biblioteca.
- Agregar metadatos de visualización de modelos, estado de pin, duración de tareas de Computer y relaciones
  de uso compartido de hilos solo donde la semántica del endpoint sea estable.
- Validar `rate-limit/status` antes de diseñar la limitación adaptativa.
- Probar `file-repository/list-files` como posible ruta de rescate de `toolu_` antes de
  agregar cualquier mutación de archivo.

<a id="p3-blocked-discovery" data-pplx-source-anchor="true"></a>
#### P3 — Descubrimiento bloqueado

- Recapturar los hashes de consulta persistida de GraphQL del panel de control solo si la indexación
  incremental por modo se vuelve lo suficientemente valiosa como para justificar el costo
  de mantenimiento.

<a id="closed-decisions-not-adopted" data-pplx-source-anchor="true"></a>
### Decisiones cerradas / no adoptadas

- **Exportación oficial como fuente de informes**: refutado. El endpoint devuelve
  Markdown de todo el hilo sin el cuerpo del informe; la cadena de URL firmada sigue
  siendo la fuente oficial para `report.md` ([§3.6](api-rest-endpoints.md)).
- **Relaciones de `related_queries`**: refutado el 23 de julio de 2026. Los UUIDs de elementos no son
  UUIDs de hilos y los textos de recomendación no se resolvieron en consultas archivadas;
  no se construyen aristas de relación ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)`: observado como solo para organizaciones
  (`403 NOT_ORG_MEMBER`) para las cuentas probadas.
- `thread/request-access-info`: probado como relacionado con la unión a organizaciones, no una
  señal de `threadAccess`.
- Los verticales de facturación/Stripe/empresa y finanzas/deportes permanecen fuera del
  alcance de la herramienta de archivo.

---

*Este documento complementa [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md) (arquitectura de la herramienta) y [overview.md](../../architecture/overview.md) (diseño del sistema).*
