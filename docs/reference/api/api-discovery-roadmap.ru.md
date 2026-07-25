---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-discovery-roadmap.md"
translation_source_sha256: "60c675dcc583c059cd489ea085f9c2923f9447f7bbafb0a7ac991fee9f8add08"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="endpoint-discovery-and-improvement-roadmap" data-pplx-source-anchor="true"></a>
# Обнаружение конечных точек и дорожная карта улучшений

*Часть справочника веб-API Perplexity — полная карта в [индексе API](index.md).*

<a id="known-unexplored-tbd-items" data-pplx-source-anchor="true"></a>
## Известные неисследованные / TBD элементы

- Поле сортировки `list_collection_threads` и точная семантика `total_threads`
  (снимок живого аккаунта 2026-07: сообщалось 99 против 27 элементов верхнего уровня).
- Полный спектр значений `threadAccess`/`access`/`user_permission` (2026-07
  наблюдаемая выборка: threadAccess 5 normal, 1 с 🔒; collection access 1;
  permission 4 owner / 2 can edit; assets data также содержит thread_access).
- Корректные формы параметров для `list_ask_threads`, `list_scheduled_computer_tasks` (прямой GET 400).
- Структуры ответов `collections/*/request-access-info`, `spaces/<uuid>/recurring_tasks`, `assets/<id>/members`.
- Почему операции GraphQL панели управления незарегистрированы (PERSISTED_QUERY_NOT_FOUND): расхождение версий или контекстное ограничение;
  при необходимости повторно извлеките с живыми хешами из сетевого захвата.
- Разделение труда между `frontend_uuid` и `uuid` и `context_uuid` в компьютерных тредах.
- Поля сигналов API для межаккаунтных веток, общих для пространства (branch_of)
  (родительский указатель / маркер ветки) — механизм подтвержден (конец
  [§3.3](api-rest-endpoints.md)); нет архивного экземпляра по состоянию на 2026-07-23;
  проверьте и запишите, когда появится первый.

<a id="endpoint-discovery-method-frontend-bundle-static-analysis-zero-api-cost-established-2026-07-20" data-pplx-source-anchor="true"></a>
## Метод обнаружения конечных точек: статический анализ бандла фронтенда (нулевая стоимость API; установлен 2026-07-20)

Обнаружено **147 конечных точек `/rest/`** за один проход; метод повторно используем (повторный запуск после обновлений фронтенда):

1. Точка входа загрузки страницы `_spa/assets/index.html-*.js` ссылается на `bootstrap-*.js` (среда выполнения содержит все отображения чанков);
2. Извлеките 682 имени файлов чанков (шаблон `<name>-<hash8>.js`) из бутстрапа; отфильтруйте связанные с API по имени
   (client/api/thread/collection/space/computer…);
3. Загрузите напрямую с публичного CDN `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js`
   (cookie не требуется); модули хаба: `platform-core-*` (клиент API), `spa-shell-*`, `spa-metadata-*`;
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` выдает список конечных точек (147);
5. Чанки также раскрывают формы вызовов (например, `format:'md'` и `file_content_64` экспорта).
6. Sourcemaps также существуют: `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (не исследованы).

<a id="appendix-147-endpoints-grouped-by-category-archive-relevance-marked" data-pplx-source-anchor="true"></a>
### Приложение: 147 конечных точек, сгруппированных по категориям (отмечена релевантность для архивирования)

- **thread**: `/rest/thread/{entry_uuid_or_slug}`, `/rest/thread/export`★, `/rest/thread/{uuid}/members`,
  `/rest/thread/list_recent`, `/rest/thread/list_ask_threads`, `/rest/thread/list_pinned_ask_threads`,
  `/rest/thread/list_scheduled_computer_tasks`, `/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★: см. полную таблицу [§3.3](api-rest-endpoints.md) (включая batch_move/batch_remove, list_user_collections, request-access-info,
  recurring_tasks, pins/threads, scheduled_threads)
- **assets**★: `/rest/assets/{asset_id}/data`, `/rest/assets/{asset_id}/members`,
  `/rest/assets/{asset_id}/published-access`, `/rest/assets/sites/{site_id}/publish-info`
- **analytics**: `/rest/analytics/computer/usage`, `/rest/analytics/computer/usage/members`
  (оба 403 NOT_ORG_MEMBER — только для организационных аккаунтов)
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
- **verticals** (нерелевантны для архивирования): `/rest/finance/*`, `/rest/sports/*`, `/rest/travel/hotels/{slug}`,
  `/rest/health-assistant/*`, `/rest/article/{uuid_or_slug}`
- **misc**: `/rest/pins`, `/rest/rate-limit/(all|status)`, `/rest/notifications/web-push/*`,
  `/rest/attribution/*`, `/rest/homepage-widgets/upsell`, `/rest/ntp/upsell/`, `/rest/sidebar/upsell/`,
  `/rest/incentives/comet-activation`, `/rest/connector-service/usage`

(★ = напрямую релевантно для архивирования)

<a id="endpoint-tool-capability-status-and-roadmap" data-pplx-source-anchor="true"></a>
## Статус конечной точки → возможности инструмента и дорожная карта

Статус реализации ниже синхронизирован с текущим кодом и набором тестов
на **2026-07-24**. Данные API сохраняют дату и объем исходного
живого наблюдения или статического анализа; эта синхронизация документации не перепроверяла
частные конечные точки. Счетчики аккаунтов/архивов являются снимками, а не общеплатформенными
гарантиями.

Значения статуса:

- **Implemented** — текущий CLI или производственный путь использует конечную точку для
  указанной возможности.
- **Partial** — конечная точка используется, но последующая возможность в
  дорожной карте остается неполной.
- **Tested, not integrated** — поведение живого API наблюдалось, но ни один путь инструмента
  его не потребляет.
- **Planned** — доказательства существуют, но реализация не начата.
- **Blocked** — известный вышестоящий или протокольный блокировщик препятствует реализации.
- **Closed** — доказательства опровергли предлагаемое использование или вывели его за рамки.

<a id="capability-status-matrix" data-pplx-source-anchor="true"></a>
### Матрица статуса возможностей

| Конечная точка / операция | Основание проверки | Текущая интеграция | Статус | Оставшийся пробел |
|---|---|---|---|---|
| `collections/get_collection` | живое наблюдение + текущий код | `spaces --fetch-meta` строит индекс владельцев/участников пространства | **Implemented** | — |
| `collections/list_collection_threads` | живое наблюдение + текущий код | `space-index` использует REST по умолчанию с контекстным UUID dual-ID отображением; WebBridge является запасным | **Implemented** | Порядок сортировки и точная семантика `total_threads` остаются TBD |
| `assets/<uuid>/data` | протестировано вживую 2026-07-20 + текущий код | `assets-backfill --online` обновляет подписанные URL для реальных UUID активов | **Implemented** | Обработчики облачного рабочего пространства `toolu_` находятся вне покрытия этой конечной точки |
| `LibraryThreadsRelayQuery` и запрос пагинации | захваченный APQ + текущий код | `index`/`batch` обеспечивают полное индексирование и инкрементальную раннюю остановку | **Implemented** | Запросы фильтра режимов панели управления остаются заблокированными отдельно |
| `collections/list_user_collections` | наблюдалось вживую 2026-07 + текущий код | `init` использует точное совпадение названия для обнаружения пространства BOT | **Partial** | Создайте авторитетный реестр пространств аккаунта для обнаружения новых пространств и перестроения `spaces` |
| `credits/thread-usage` | протестировано вживую 2026-07-20 + текущий код | `usage-backfill` записывает `index/credit_usage_<account>.json` | **Partial** | Решите, обогащать ли `thread.json` и/или строки библиотечного индекса без дублирования авторитетности |
| `models/config/v2` | протестировано вживую 2026-07-21 + текущий код | `pplx-ask models` перечисляет модели/значения по умолчанию; константы нормализации перекрестно проверяются по нему | **Partial** | Сохраняйте стабильные метаданные отображения модели в записях архива/индекса, если это полезно |
| `POST /rest/thread/export` | md/pdf/docx протестировано вживую 2026-07-20 | нет интеграции в CLI | **Tested, not integrated** | Многоформатное архивирование и сверка официального Markdown |
| `rate-limit/status` | наблюдение загрузки страницы; семантика ответа не исследована | нет | **Planned** | Проверьте семантику перед использованием для адаптивного ограничения |
| `file-repository/list-files` | только статический анализ фронтенда | нет | **Planned** | Проверьте, может ли он перечислять/спасать обработчики `toolu_`; снимок архива 2026-07 зафиксировал 270 обработчиков без канала загрузки |
| `pins`, `tasks/{id}` | статический анализ фронтенда / наблюдения загрузки страницы | нет | **Planned** | Обогащение состояния закрепления и длительности компьютерных задач |
| `thread/<uuid>/members` | протестировано вживую 2026-07 | нет | **Planned** | Ребра общего доступа на уровне треда для графа отношений |
| Dashboard GraphQL `threadGroup` + фильтры режимов | прямые вызовы вернули `PERSISTED_QUERY_NOT_FOUND` | нет | **Blocked** | Восстановите живые хеши сохраненных запросов или установите необходимый контекст |
| `related_queries` / `sse/related-queries` | криминалистика по всему архиву завершена 2026-07-23 | намеренно не создает ребер отношений | **Closed** | Откройте заново только если новые доказательства установят разрешимую идентичность треда |

<a id="active-roadmap" data-pplx-source-anchor="true"></a>
### Активная дорожная карта

<a id="p0-official-export-integration" data-pplx-source-anchor="true"></a>
#### P0 — Интеграция официального экспорта

- **Многоформатное архивирование**: опционально сохраняйте продукты PDF/DOCX, возвращаемые
  `POST /rest/thread/export`.
- **Сверка рендерера**: сравните официальный Markdown всего треда с
  `conversation.md` как независимый сигнал регрессии.

<a id="p1-space-discovery" data-pplx-source-anchor="true"></a>
#### P1 — Обнаружение пространств

- Продвиньте `list_user_collections` от поиска по названию BOT до авторитетного,
  реестра пространств в рамках аккаунта, используемого для обнаружения новых пространств и перестроения `spaces`.

<a id="p2-metadata-risk-control-and-asset-rescue" data-pplx-source-anchor="true"></a>
#### P2 — Метаданные, контроль рисков и спасение активов

- Определите и задокументируйте границу авторитетности для использования кредитов: сохраните
  выделенный `credit_usage_<account>.json`, или также обогащайте `thread.json` /
  строки библиотеки.
- Добавляйте метаданные отображения модели, состояние закрепления, длительность компьютерных задач и ребра
  общего доступа треда только там, где семантика конечной точки стабильна.
- Проверьте `rate-limit/status` перед проектированием адаптивного ограничения.
- Протестируйте `file-repository/list-files` как возможный путь спасения `toolu_` перед
  добавлением любых мутаций архива.

<a id="p3-blocked-discovery" data-pplx-source-anchor="true"></a>
#### P3 — Заблокированное обнаружение

- Повторно захватите хеши сохраненных запросов GraphQL панели управления только если
  порежимное инкрементальное индексирование станет достаточно ценным, чтобы оправдать затраты
  на обслуживание.

<a id="closed-decisions-not-adopted" data-pplx-source-anchor="true"></a>
### Закрытые решения / не приняты

- **Официальный экспорт как источник отчета**: опровергнуто. Конечная точка возвращает
  Markdown всего треда без тела отчета; цепочка подписанных URL остается
  официальным источником для `report.md` ([§3.6](api-rest-endpoints.md)).
- **Отношения из `related_queries`**: опровергнуто 2026-07-23. UUID элементов не являются
  UUID тредов, и тексты рекомендаций не разрешались в архивные запросы;
  ребра отношений не строятся ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)`: наблюдалось как только для организаций
  (`403 NOT_ORG_MEMBER`) для протестированных аккаунтов.
- `thread/request-access-info`: протестировано как связанное с присоединением к организации, а не
  сигнал `threadAccess`.
- Вертикали Billing/Stripe/enterprise и finance/sports остаются вне
  рамок инструмента архивирования.

---

*Этот документ дополняет [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md) (архитектура инструмента) и [overview.md](../../architecture/overview.md) (системный дизайн).*
