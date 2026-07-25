---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-rest-endpoints.md"
translation_source_sha256: "f1eb76feaffc48d910b988b54e4bcfcaa8b52a65502495399536392e4da7d146"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-rest-endpoints" data-pplx-source-anchor="true"></a>
# Referencia de la API: Endpoints REST

<a id="rest-endpoints-grouped-by-purpose" data-pplx-source-anchor="true"></a>
## Endpoints REST (agrupados por propósito)

Convención: `?version=2.18&source=default` es la cadena de consulta común (requerida por la mayoría de los endpoints).

<a id="thread-content-main-export-path" data-pplx-source-anchor="true"></a>
### Contenido del hilo (ruta de exportación principal)
| Endpoint | Notas |
|---|---|
| `GET /rest/thread/<uuid>` | **Respuesta simple**: `entries[]` (por turno; `text` contiene todos los textos de paso), `background_entries[]` (**flujos de trabajo completos de subagentes**), `thread_metadata`. Soporta paginación `?cursor=` (`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **Respuesta esquematizada**: `entries[].blocks[]` (`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`), incluyendo indicaciones de subagentes (`workflow_payload.objective_chunks`), URLs firmadas de activos, contenidos de archivos. Casos de uso en `rest.py:SCHEMATIZED_USE_CASES` (workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | Lista de hilos recientes (barra lateral de inicio; incluye el campo `unread`) |
| **`POST /rest/thread/mark_viewed`** | **Confirmación de lectura (descifrado 2026-07-21)**: cuerpo `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`; no leído cambia inmediatamente. El frontend llama a este endpoint cuando se abre un hilo desde la barra lateral. Nota: el evento analítico "hilo visto" **no cambia** el estado de no leído (descartado por pruebas repetidas) |
| `GET /rest/thread/<uuid>/members` | **Miembros de uso compartido a nivel de hilo** (probado): `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | Devuelve `{"will_request_org_join": bool, "org_display_name": str|null}` — relacionado con unión a organización, **no relacionado con la semántica de threadAccess** (descartado por pruebas) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | Presentes en análisis estático; GET directo probado 400 (forma de parámetro por determinar) |

<a id="asset-metadata-discovered-2026-07-20-lifesaver-for-expired-assets" data-pplx-source-anchor="true"></a>
### Metadatos de activos (descubierto 2026-07-20, **salvavidas para activos caducados**)

- **`GET /rest/assets/<asset_uuid>/data`** → metadatos completos del activo (probado 200):
  - `asset_data.<type>.url` y `asset_data.download_info[].url`: **URLs firmadas nuevas de CloudFront** —
    si la URL firmada original ha caducado al momento del archivo, la dirección de descarga se puede volver a obtener con el asset_uuid
    (siempre que la plataforma no haya purgado el activo);
  - también devuelve `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    (cadena de búsqueda inversa activo → hilo);
  - campos como `signed_url: null`, `read_write_token`, `allow_remix`.
- **Límites de aplicabilidad (probados)**: los uuid de activos reales funcionan; **los identificadores de espacio de trabajo en la nube con prefijo `toolu_` (DOC_FILE/CODE_FILE
  sin forma de URL) devuelven 404 ASSET_NOT_FOUND**; `file-repository/download` requiere una URL real y no acepta
  identificadores `file:repo/...` (400 error al analizar). Aún no existe un canal de descarga API para activos de tipo toolu.
- Relacionado: `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access` (presentes en análisis estático, no probados).
- Implementado: la herramienta proporciona `pplx-export assets-backfill` (extracción en línea + actualización en línea a través de este endpoint; consulte la nota de herramientas implementadas en [§4](api-responses-errors.md)).

- **ENTRY_EXPIRED**: los hilos/artefactos de más de ~3 meses son purgados por la plataforma; las solicitudes devuelven un cuerpo de error específico — la herramienta los marca como terminales y no reintenta.
- **Eliminación de hilos (investigación 2026-07-23 WebBridge + chunk, probada)**:
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, cuerpo `{entry_uuid, read_write_token}`,
  éxito `200 {"status":"success"}`; la eliminación repetida es idempotente, sigue siendo 200; eliminar un uuid inexistente → 404 `THREAD_NOT_FOUND`;
  **adquisición de `read_write_token` (verificado en la práctica el mismo día)**: el primer `entries[].read_write_token` no vacío
  en la respuesta `GET /rest/thread/<uuid>` funciona (10/10 eliminaciones exitosas en hilos activos);
  **las operaciones de escritura deben ir al dominio www** (el dominio raíz devuelve 301 para DELETE). No hay mutación GraphQL, no hay endpoint de eliminación por lotes
  (la eliminación por lotes de la interfaz de usuario es un bucle por elemento del frontend). La eliminación es destrucción a nivel de hilo, irrecuperable; el hilo desaparece automáticamente de sus espacios
  (no es necesario `batch_remove_collection_threads` primero).
  Opción suave: `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (cuerpo `{context_uuids:[...]}`; solo análisis estático, no probado).
- **ENTRY_DELETED**: después de eliminar un hilo, `GET /rest/thread/<uuid>` devuelve HTTP 400 `ENTRY_DELETED`
  (mismo 400 que ENTRY_EXPIRED pero un código diferente) — la herramienta lo asigna a `EntryDeletedError`
  (subclase de `EntryExpiredError`); batch_state marca el estado terminal `deleted`.
- Cada entrada de turno lleva `context_uuid` (= el UUID `past_session_contexts` de la plataforma — la clave para la asignación del espacio de nombres de doble ID).

<a id="spaces-collections" data-pplx-source-anchor="true"></a>
### Espacios (colecciones)
| Endpoint | Notas |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **Metadatos del espacio**: `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. Valores de permiso observados: 4=propietario, 2=puede editar. Cuando la cuenta actual no tiene acceso de vista: `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` (HTTP sigue siendo 200) |
| `POST /rest/collections/create_collection` | **Crear espacio** (captura 2026-07-21 WebBridge, probado): cuerpo `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → devuelve la colección completa (uuid/slug/url/user_permission=4). El espacio BOT se creó de esta manera |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **Lista de hilos del espacio (solicitud directa de cookie; puede reemplazar el índice de espacios basado en navegador)**: la respuesta es un array; cada elemento tiene `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview`, etc. **Paginación: `&offset=N` (20 por página)**; `has_next_page` está en cada elemento; `total_threads` lee alto (incluye subhilos de Computer; observado 99 vs 27 de nivel superior) |
| `POST /rest/collections/batch_move_threads` | **Mover hilos a un espacio** (probado con éxito): cuerpo `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}` — **use context_uuid, no entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | Eliminación por lotes de un espacio (cuerpo `{items:[{collection_uuid,...}]}`; no probado) |
| `GET /rest/collections/list_user_collections` | **Lista de espacios de la cuenta actual** (probado, 16 elementos): cada uno tiene `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page`, etc. — más rica que list_recent |
| `GET /rest/collections/list_recent` | Espacios recientes de la cuenta actual (`title/uuid/emoji/is_pinned/link`; probado, 5 elementos) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | Información de solicitud de acceso al espacio (no probado) |
| `GET /rest/collections/<uuid>/join-requests` | Solicitudes de unión (no explorado) |
| `GET /rest/spaces/<uuid>/tasks` | Devuelve `{"tasks":[]}` — observado vacío; se sospecha que son tareas programadas/de Computer del espacio, no una lista de hilos |
| `GET /rest/spaces/<uuid>/recurring_tasks` | Tareas recurrentes (no probado) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | Hilos fijados/programados del espacio (llamados al cargar la página; no explorado) |

- **Ramificación entre cuentas (branch_of; conocimiento verificado por el usuario 2026-07-23)**: un hilo compartido a través de un espacio puede ser
  "continuado" por otra cuenta miembro en un hilo ramificado que es **visible solo para, y continuado por, esa cuenta** — después de que el hilo de la cuenta A se comparte a través de un espacio,
  B puede continuarlo en una rama privada de B. El archivo aún no tiene instancia; las aristas de relaciones no están implementadas por ahora; los campos de señal API del hilo ramificado
  (puntero padre / marcador de rama) se verificarán y registrarán cuando aparezca la primera instancia.

<a id="account-session" data-pplx-source-anchor="true"></a>
### Cuenta / sesión
| Endpoint | Notas |
|---|---|
| `GET /api/auth/session` | Sesión actual `{user:{email,...}}` — utilizado para verificación de cuenta y sondeo de cambio automático |
| `GET /api/auth/linked-accounts` | Ver [§1.2](api-authentication.md) (lista completa solo mientras la principal está activa) |
| `GET /rest/user/info`, `/rest/user/settings` | Perfil de usuario / configuración (no explorado) |

<a id="credit-usage-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Uso de crédito (descubierto 2026-07-20)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → uso de crédito por hilo (probado 200):
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **Nota**: `thread_id` espera el **context_uuid** (psc_uuid); pasar entryUUID produce 403
  `thread_usage_forbidden` ("El hilo no pertenece al usuario actual" — en realidad una forma de ID incorrecta).
- Fuentes de context_uuid: `list_collection_threads` (el índice REST de espacios ya cubre 27/27),
  el campo `context_uuid` de la entrada del hilo (archivado como `psc_uuid` en thread.json).
- Solo se pueden consultar los hilos de la cuenta actual (entre cuentas → 403) — el raspado de múltiples cuentas necesita cambio automático por cuenta.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`: versión de lista; probado vacío en ambas cuentas
  (se sospecha solo facturación de organización; por determinar).
- Otros endpoints de facturación (`/rest/billing/credits/balance`, etc.) en el [apéndice §7](api-discovery-roadmap.md); no explorados.

<a id="official-export-backend-of-the-page-export-button-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Exportación oficial (backend del botón "Exportar" de la página; descubierto 2026-07-20)

- **`POST /rest/thread/export`**, cuerpo: `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<name>"}`
- Respuesta: `{"file_content_64": "<base64>", "filename": "..."}`
- Formatos probados: **`md`** (markdown oficial con un encabezado de logotipo `<img>`), **`pdf`** (binario PDF ~880KB),
  **`docx`** (PK zip ~350KB) — todos HTTP 200. Otros valores de formato no probados.
- **Límite de contenido (verificado)**: devuelve markdown de **hilo completo** (consulta + resumen de respuesta + citas a pie de página `[^1_N]`),
  **sin el cuerpo de RESEARCH_REPORT** — el informe de investigación profunda en sí solo se puede obtener a través de su URL firmada (§3.7);
  es decir, la cadena de URL firmada de report.md actual **es la fuente oficial del informe** (misma fuente que la descarga del panel de artefactos de la página); no es necesario cambiar a este endpoint.
- Valor: el markdown oficial a nivel de hilo puede servir como fuente de validación cruzada a nivel de conversación (citas a pie de página/formato renderizados oficialmente).

<a id="asset-report-download" data-pplx-source-anchor="true"></a>
### Descarga de activos / informes
- **URLs firmadas de CloudFront** en la respuesta esquematizada (`d2z0o16i8xm8ak.cloudfront.net`): descarga directa con urllib,
  no se necesita cookie/auth; archivos multiversión numerados en orden `created_at`.
- Fuente alternativa de informe de investigación: la URL S3 del paso RESEARCH_ANSWER (`ppl-ai-file-upload.s3.amazonaws.com`, **caduca**);
  segunda alternativa: extracción de renderizado de página (KaTeX `<annotation>`).
- **Purga de ~3 meses**: los enlaces de origen de artefactos/informes caducan de forma irrecuperable — las exportaciones deben ser oportunas.

<a id="other-observed-endpoints-page-load-not-explored" data-pplx-source-anchor="true"></a>
### Otros endpoints observados (carga de página; no explorados)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates` (SSE), `/api/version`.

<a id="message-submission-and-telemetry-2026-07-20-webbridge-cdp" data-pplx-source-anchor="true"></a>
### Envío de mensajes y telemetría (2026-07-20 WebBridge + CDP)

<a id="submission-endpoint-post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### Endpoint de envío: `POST /rest/sse/perplexity_ask`
- Muestras completas del cuerpo de la solicitud (ejemplos sintéticos) en `docs/perplexity-api-samples/`:
  - `ask_envelope_deep_research.json` — turno de seguimiento de investigación profunda (2026-07-20; 39 parámetros + query_str):
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + la cadena de continuación `last_backend_uuid`
  - `ask_envelope_search.json` — búsqueda estándar, nueva conversación desde inicio (2026-07-21; 35 parámetros + query_str):
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json` — consejo de modelos, nueva conversación desde inicio (2026-07-21; 36 parámetros + query_str):
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- Campos clave (turno de seguimiento de investigación profunda, probado):
  - `mode: "copilot"` (investigación profunda); `model_preference: "pplx_alpha"`
  - **Cadena de continuación**: `last_backend_uuid` (uuid del backend del turno anterior) + `query_source: "followup"`
  - `frontend_uuid` (nuevo uuid para este turno), `read_write_token`, `target_collection_uuid` (espacio contenedor),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`** (milisegundos desde la primera pulsación hasta el envío — telemetría de comportamiento cargada con el envío)
  - `use_schematized_api: true`, `supported_block_use_cases` (lista de bloques completa, coincidiendo con §3.1 esquematizado),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- La respuesta es un flujo SSE (el frontend lo consume con fetch-event-source `getReader()` — el módulo de la aplicación congela la referencia de fetch al inicio,
  **los hooks de fetch/XHR adjuntos a la página son ineficaces**; y **los cuerpos de respuesta de streaming no son retenidos por el navegador** (`Network.getResponseBody` devuelve
  No data found) — la captura solo es posible a través de CDP `Network.getRequestPostData` (cuerpo de solicitud disponible)).
- El estado final del flujo son exactamente las entradas/bloques de `/rest/thread/<uuid>` (mismos datos, entregados incrementalmente) —
  la herramienta de exportación no necesita leer el flujo; obtiene el estado final directamente.

<a id="telemetry-post-resteventanalytics-batched-high-frequency" data-pplx-source-anchor="true"></a>
#### Telemetría: `POST /rest/event/analytics` (por lotes, alta frecuencia)
Eventos observados (con elementos esenciales de event_data):
| event_name | Campos clave | Notas |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | evento de vista de página — **no cambia el estado de no leído** (descartado por pruebas; la confirmación de lectura real es `POST /rest/thread/mark_viewed`, ver §3.1) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs` (**milisegundos de permanencia de lectura para ese turno**), `userId`, `isPro`, `deviceInfo` (concurrencia/pantalla/profundidad de color) | telemetría de duración de lectura (no cambia el estado de no leído, descartado por pruebas) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | acción de envío |
| `query first llm token` | `startLLMTokenElapsed` (latencia del primer token), `queryStr` completo | telemetría de rendimiento |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, `queryStr` completo | recibo de éxito |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | interacción del selector de modelos del consejo |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | vista del panel derecho |
- Campos comunes de eventos: `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info` (hardwareConcurrency/pantalla/profundidad de color/arquitectura), `isBrowserExtension`, `web_platform`.
- **Nota**: un evento observado llevaba un `userId` perteneciente a la **otra cuenta** (el uid pertenecía a la cuenta A mientras la sesión ya era la cuenta B) —
  el id de perfil del SDK de telemetría tiene retraso de caché; no juzgue la cuenta actual por el userId de telemetría.
- También hay informes de alta frecuencia de datadog RUM (`browser-intake-datadoghq.com/api/v2/rum`) (desplazamiento/ratón/rendimiento; contenido no analizado).

<a id="mode-and-model-selection-2026-07-21-tested-on-a-paid-account" data-pplx-source-anchor="true"></a>
#### Selección de modo y modelo (2026-07-21, probado en una cuenta de pago)
- **`GET /rest/models/config/v2` = tabla de modelos autorizada**: `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`, `agentic_research_compare_models` (tres modelos predeterminados del consejo).
  `pplx-ask models` llama a este endpoint.
  - Correspondencia oficial (probada): **search = `pplx_pro` (nombre en UI "Best"), research = `pplx_alpha`
    (nombre en UI "Deep research")**.
  - Lista de modelos seleccionables en UI del modo search (sin Deep research): Best (pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **El campo `mode` es siempre `"copilot"` — no es un discriminador de modo** (igual para búsqueda / investigación profunda / consejo de modelos).
- La discriminación reside en **`model_preference`**:
  - Búsqueda: `pplx_pro` (o el id de modelo seleccionado por el usuario, ej. `experimental`=Sonar 2, `gpt56_sol`…)
  - Investigación profunda: `pplx_alpha` (**sin selector de modelo en UI**, fijo)
  - **Consejo de modelos**: `pplx_agentic_research` + **`compare_model_preferences: [<2-3 models>]`**
    (predeterminado observado `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`;
    la UI es **selección única por ranura**, reduciendo a 2 modelos en seguimiento).
  - Estudio paso a paso: `pplx_study`; Computer: la familia `pplx_asi*`.
- El selector de modelos del área de redacción ("modelo ⌄") y el selector "N modelos ⌄" del consejo se asignan a los campos anteriores;
  el evento de telemetría `ask input model selector opened` lleva `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels` (los hilos de investigación profunda anteriores tenían `searchMode: "research"`).
- Nueva conversación: `query_source: "home"`, sin `last_backend_uuid`, tiene `frontend_context_uuid`;
  continuación: `query_source: "followup"` + cadena `last_backend_uuid`.

<a id="entrysearch_mode-the-authoritative-record-of-conversation-mode-settled-2026-07-22" data-pplx-source-anchor="true"></a>
#### entry.search_mode: el registro autorizado del modo de conversación (resuelto 2026-07-22)
**Cada entrada** de `/rest/thread/<uuid>` lleva `search_mode`, el registro autorizado de la plataforma del modo de conversación de ese turno
(la señal de detección de modo de mayor prioridad, `normalize.SEARCH_MODE_MAP`):

| search_mode | Significado (UI/modelo) | Modo de archivo |
|---|---|---|
| `SEARCH` | búsqueda normal (default_models.search=pplx_pro "Best" y modelos seleccionables en UI) | search |
| `STUDIO` | sesión de laboratorio (pplx_beta); la UI lo agrupa bajo búsqueda | search |
| `RESEARCH` | Investigación profunda (default_models.research=pplx_alpha; UI fija, sin selector) | deep-research |
| `AGENTIC_RESEARCH` | consejo de modelos (pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | estudio paso a paso (pplx_study) | study |
| `ASI` | Computer (pplx_asi*) | computer |

- Encuesta de valor en todo el archivo: los seis valores tienen instancias en el archivo real; SEARCH y RESEARCH dominan,
  STUDIO a continuación, ASI / STUDY / AGENTIC_RESEARCH raros.
- **pplx_alpha ⟺ RESEARCH prueba cruzada**: 100+ entradas SEARCH de plataforma + hilos pplx_alpha en el archivo son 100%
  `search_mode=RESEARCH`; 100+ hilos puros pplx_pro son todos `search_mode=SEARCH` —
  la estadística antigua "pplx_alpha es un modelo comúnmente utilizado para búsqueda simple" eran en realidad muestras mal clasificadas por el clasificador y no se sostiene.
- Múltiples valores pueden aparecer dentro de un mismo hilo (cambio de modo, ej. una mezcla observada SEARCH+RESEARCH): la detección toma el más alto por especificidad
  computer>council>study>deep-research>search.

<a id="model-council-output-structure-and-expansion-behavior" data-pplx-source-anchor="true"></a>
#### Estructura de salida del consejo de modelos y comportamiento de expansión
- Salida de un solo turno = N bloques específicos de modelo "Council: <model name>" (cada uno con consultas de recuperación/fuentes/respuesta) + una parte de síntesis:
  **Where Models Agree** (matriz de consenso, comparación ✓ de tres modelos por Hallazgo + Evidencia),
  **Where Models Disagree** (tabla de desacuerdo, posición de cada modelo + razones de divergencia),
  **Unique Discoveries** (hallazgos únicos de cada modelo), seguido de recomendaciones de preguntas relacionadas — **todo entregado en el mismo flujo SSE**.
- Comportamiento de expansión (incluyendo expansión **durante la generación**): las filas expandibles llevan un cheurón ">" (filas de paso / filas "Sources" / filas del Consejo);
  al hacer clic se expanden — **renderizado puro del lado del cliente, cero solicitudes de contenido**: de las 1208 solicitudes de esta sesión, 921 fueron activos estáticos de favicon/fuente;
  la expansión en sí solo desencadena cargas de favicon y /api/version. La expansión durante la transmisión no interrumpe la entrega continua.
- Latencia del primer token observada ~204s (tres modelos generando en paralelo, notablemente más larga que un solo modelo); recuento de fuentes observado 236.
- Elementos esenciales de automatización del área de redacción (Lexical): el texto debe inyectarse a través de CDP `Input.insertText` (después de execCommand/fill,
  el estado interno de Lexical se desincroniza y Enter falla); el envío puede usar Enter de CDP o hacer clic en el botón con aria-label="提交" ("Submit")
  (el modo consejo tiene una flecha de envío explícita).

<a id="behavior-when-continuing-a-historical-conversation-tested-2026-07-20" data-pplx-source-anchor="true"></a>
#### Comportamiento al continuar una conversación histórica (probado 2026-07-20)
1. Cargar página del hilo → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. Enviar seguimiento → `rate-limit/status` → `sse/perplexity_ask` (con la cadena `last_backend_uuid`) → análisis de alta frecuencia.
3. Durante la generación → el flujo SSE se renderiza incrementalmente; después de la finalización, otro lote de análisis (incluyendo duración de lectura `thread entry exited`).
4. Los turnos de seguimiento de investigación profunda también producen estructuras de informe (este turno completó 5 pasos).
