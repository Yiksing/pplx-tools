---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-graphql.md"
translation_source_sha256: "3963e26d58d8dc1ad0835fe715357592295f31dd7c3b7c3f1ca67854fa3c98a0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-graphql" data-pplx-source-anchor="true"></a>
# Справочник API: GraphQL

<a id="graphql-persisted-queries-apq" data-pplx-source-anchor="true"></a>
## GraphQL (персистентные запросы / APQ)

- **Endpoint**: `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **Форма**: персистентный запрос — тело содержит operationName + variables + хеш sha256 (текст запроса не требуется).
- Реализация: `pplx_export/sites/perplexity/graphql.py`.

<a id="librarythreadsrelayquery-list-first-page" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery (список первой страницы)
- sha256: `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- Переменные: `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- Путь ответа: `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- Поля узла (используемые адаптером): `name(title)`, `entryId(entryUUID)`, `slug(href)`, `mode`, `displayModel.modelID`,
  `updatedAt(lastUpdated)`, `status`, `space{spaceUuid,title,slug}`
- **Контракт архивной стороны (2026-07-22 V5-01)**: `lastUpdated` из `web_archive/**/thread.json` всегда равен этому полю
  (записывается на диск с полной точностью ISO, дословно); сравнение идемпотентности пакетного/одиночного экспорта (`is_unchanged`) основано на нём,
  а не на формате представления слоя рендеринга (`YYYY-MM-DD HH:MM UTC`).
- **Обогащение архивной стороны (2026-07-23)**: ключ `search_mode` строк индекса (`index/library_*.json`) является
  полем обогащения архивной стороны — узел этого запроса не содержит search_mode; оно заполняется `pplx-export search-mode-backfill`
  из данных уровня потока (`entries[].search_mode` из `GET /rest/thread/<uuid>`) (сначала локальные необработанные данные,
  затем онлайн-запасной вариант); обновление `index` объединяет и сохраняет его по entryUUID. Фильтрация `batch --mode` предпочитает авторитетное отображение этого поля.

<a id="libraryrecentthreadspaginationquery-pagination" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery (пагинация)
- sha256: `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- Переменные: переменные первой страницы + `{cursor, count}` (**имена переменных — cursor/count, а не after/first**)
- Та же структура ответа, что и выше. Когда `hasNextPage` равно true, но `endCursor` пусто, остановиться (иначе та же страница повторяется).

<a id="computer-dashboard-operation-group-extracted-from-route-chunk-2026-07-20-not-registered-on-the-server" data-pplx-source-anchor="true"></a>
### Группа операций панели управления Computer (извлечена из чанка маршрута 2026-07-20, **не зарегистрирована на сервере**)

Чанк `ComputerDashboardPage-*.js` содержит полные тексты Relay-запросов + персистентные идентификаторы (метод извлечения в [§7](api-discovery-roadmap.md)).
Структурные основы: `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— т.е. список потоков, отфильтрованный по threadGroup + mode; узел содержит `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`.

| Операция | Персистентный идентификатор (первые 16 символов) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (подписка WebSocket) |

**Проверено**: вызов `/rest/perplexity_ask/graphql` с этими идентификаторами возвращает `PERSISTED_QUERY_NOT_FOUND`
(не зарегистрировано в текущем развёртывании — расхождение версий или требуется контекст панели управления; полные тексты запросов и идентификаторы хранятся в заметках исследования `/tmp`;
при необходимости отправьте текст запроса напрямую или извлеките заново из живого бандла).

<a id="notes" data-pplx-source-anchor="true"></a>
### Примечания
- На странице веб-пространства или домашней странице вызовов graphql не наблюдалось (все идут через /rest); graphql подтверждён для списка /library и панели управления Computer.
- Хеши sha256 могут меняться с версиями фронтенда; режим отказа — `PERSISTED_QUERY_NOT_FOUND` — затем извлеките заново из
  сетевого захвата браузера (инструмент WebBridge `network` с фильтром `perplexity_ask/graphql`) или из живого бандла ([§7](api-discovery-roadmap.md)).

<a id="extracted-dashboard-connection-keys-relay-cache-keys-for-debugging" data-pplx-source-anchor="true"></a>
### Извлечённые ключи соединений панели управления (ключи кэша Relay, для отладки)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
