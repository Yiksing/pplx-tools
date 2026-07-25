---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-rest-endpoints.md"
translation_source_sha256: "f1eb76feaffc48d910b988b54e4bcfcaa8b52a65502495399536392e4da7d146"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-rest-endpoints" data-pplx-source-anchor="true"></a>
# Справочник API: REST-конечные точки

<a id="rest-endpoints-grouped-by-purpose" data-pplx-source-anchor="true"></a>
## REST-конечные точки (сгруппированы по назначению)

Соглашение: `?version=2.18&source=default` — общая строка запроса (требуется большинством конечных точек).

<a id="thread-content-main-export-path" data-pplx-source-anchor="true"></a>
### Содержимое обсуждения (основной путь экспорта)
| Конечная точка | Примечания |
|---|---|
| `GET /rest/thread/<uuid>` | **Обычный ответ**: `entries[]` (на виток; `text` содержит все тексты шагов), `background_entries[]` (**полные рабочие процессы субагентов**), `thread_metadata`. Поддерживает пагинацию `?cursor=` (`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **Схематизированный ответ**: `entries[].blocks[]` (`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`), включая подсказки субагентов (`workflow_payload.objective_chunks`), подписанные URL ресурсов, содержимое файлов. Варианты использования в `rest.py:SCHEMATIZED_USE_CASES` (workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | Список последних обсуждений (боковая панель главной; включает поле `unread`) |
| **`POST /rest/thread/mark_viewed`** | **Подтверждение прочтения (взломано 2026-07-21)**: тело `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`; непрочитанное переключается немедленно. Интерфейс вызывает эту конечную точку при открытии обсуждения из боковой панели. Примечание: событие аналитики "просмотр обсуждения" **не переключает** непрочитанное (исключено повторными тестами) |
| `GET /rest/thread/<uuid>/members` | **Участники общего доступа на уровне обсуждения** (проверено): `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | Возвращает `{"will_request_org_join": bool, "org_display_name": str|null}` — связано с присоединением к организации, **не связано с семантикой threadAccess** (исключено тестированием) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | Присутствуют в статическом анализе; прямой GET протестирован с 400 (форма параметров TBD) |

<a id="asset-metadata-discovered-2026-07-20-lifesaver-for-expired-assets" data-pplx-source-anchor="true"></a>
### Метаданные ресурсов (обнаружено 2026-07-20, **спасение для просроченных ресурсов**)

- **`GET /rest/assets/<asset_uuid>/data`** → полные метаданные ресурса (протестировано 200):
  - `asset_data.<type>.url` и `asset_data.download_info[].url`: **новые подписанные URL CloudFront** —
    если исходный подписанный URL истек к моменту архивации, адрес загрузки можно повторно получить с помощью asset_uuid
    (при условии, что платформа не удалила ресурс);
  - также возвращает `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    (цепочка обратного поиска ресурс → обсуждение);
  - поля, такие как `signed_url: null`, `read_write_token`, `allow_remix`.
- **Границы применимости (проверено)**: реальные uuid ресурсов работают; **дескрипторы облачного рабочего пространства с префиксом `toolu_` (DOC_FILE/CODE_FILE
  без формы URL) возвращают 404 ASSET_NOT_FOUND**; `file-repository/download` требует реальный URL и не принимает
  дескрипторы `file:repo/...` (400 failed to parse). Канал загрузки через API для ресурсов типа toolu пока отсутствует.
- Связанные: `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access` (присутствуют в статическом анализе, не тестировались).
- Реализовано: инструмент предоставляет `pplx-export assets-backfill` (встроенное извлечение + онлайн-обновление через эту конечную точку; см. примечание о реализованных инструментах в [§4](api-responses-errors.md)).

- **ENTRY_EXPIRED**: обсуждения/артефакты старше ~3 месяцев удаляются платформой; запросы возвращают определенное тело ошибки — инструмент помечает их как терминальные и не повторяет попытки.
- **Удаление обсуждения (2026-07-23 WebBridge + исследование фрагментов, проверено)**:
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, тело `{entry_uuid, read_write_token}`,
  успех `200 {"status":"success"}`; повторное удаление идемпотентно, все еще 200; удаление несуществующего uuid → 404 `THREAD_NOT_FOUND`;
  **получение `read_write_token` (подтверждено на практике в тот же день)**: первый непустой `entries[].read_write_token`
  в ответе `GET /rest/thread/<uuid>` работает (10/10 удалений выполнены на живых обсуждениях);
  **операции записи должны идти на домен www** (корневой домен возвращает 301 для DELETE). Нет GraphQL-мутации, нет конечной точки для пакетного удаления
  (пакетное удаление в UI — это цикл по элементам на стороне интерфейса). Удаление — это уничтожение на уровне обсуждения, безвозвратное; обсуждение автоматически исчезает из своих пространств
  (нет необходимости сначала `batch_remove_collection_threads`).
  Мягкий вариант: `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (тело `{context_uuids:[...]}`; только статический анализ, не тестировалось).
- **ENTRY_DELETED**: после удаления обсуждения `GET /rest/thread/<uuid>` возвращает HTTP 400 `ENTRY_DELETED`
  (тот же 400, что и ENTRY_EXPIRED, но другой код) — инструмент сопоставляет его с `EntryDeletedError`
  (подкласс `EntryExpiredError`); batch_state отмечает терминальное состояние `deleted`.
- Каждая запись витка содержит `context_uuid` (= UUID `past_session_contexts` платформы — ключ к сопоставлению пространства имен двойных идентификаторов).

<a id="spaces-collections" data-pplx-source-anchor="true"></a>
### Пространства (коллекции)
| Конечная точка | Примечания |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **Метаданные пространства**: `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. Наблюдаемые значения разрешений: 4=владелец, 2=может редактировать. Когда текущая учетная запись не имеет доступа к просмотру: `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` (HTTP все еще 200) |
| `POST /rest/collections/create_collection` | **Создать пространство** (2026-07-21 захват WebBridge, проверено): тело `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → возвращает полную коллекцию (uuid/slug/url/user_permission=4). Пространство BOT было создано таким образом |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **Список обсуждений пространства (прямой запрос с cookie; может заменить индекс пространства на основе браузера)**: ответ — массив; каждый элемент имеет `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview` и т.д. **Пагинация: `&offset=N` (20 на страницу)**; `has_next_page` есть в каждом элементе; `total_threads` читает высоко (включает под-обсуждения Computer; наблюдалось 99 против 27 верхнего уровня) |
| `POST /rest/collections/batch_move_threads` | **Переместить обсуждения в пространство** (проверено успешно): тело `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}` — **используйте context_uuid, а не entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | Пакетное удаление из пространства (тело `{items:[{collection_uuid,...}]}`; не тестировалось) |
| `GET /rest/collections/list_user_collections` | **Список пространств текущей учетной записи** (проверено, 16 элементов): каждый имеет `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page` и т.д. — богаче, чем list_recent |
| `GET /rest/collections/list_recent` | Недавние пространства текущей учетной записи (`title/uuid/emoji/is_pinned/link`; проверено, 5 элементов) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | Информация о запросе доступа к пространству (не тестировалось) |
| `GET /rest/collections/<uuid>/join-requests` | Запросы на присоединение (не исследовано) |
| `GET /rest/spaces/<uuid>/tasks` | Возвращает `{"tasks":[]}` — наблюдалось пустым; предполагается, что это запланированные/компьютерные задачи пространства, а не список обсуждений |
| `GET /rest/spaces/<uuid>/recurring_tasks` | Повторяющиеся задачи (не тестировалось) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | Закрепленные/запланированные обсуждения пространства (вызываются при загрузке страницы; не исследовано) |

- **Межучетное ветвление (branch_of; знания, подтвержденные пользователем 2026-07-23)**: обсуждение, опубликованное через пространство, может быть
  "продолжено" другой учетной записью участника в ветвь, которая **видна только этой учетной записи и продолжается ею** — после того, как обсуждение учетной записи A опубликовано через пространство,
  B может продолжить его в частную ветвь B. В архиве пока нет экземпляров; ребра отношений не реализованы на данный момент; сигнальные поля API ветви
  (родительский указатель / маркер ветви) будут проверены и записаны при появлении первого экземпляра.

<a id="account-session" data-pplx-source-anchor="true"></a>
### Учетная запись / сессия
| Конечная точка | Примечания |
|---|---|
| `GET /api/auth/session` | Текущая сессия `{user:{email,...}}` — используется для проверки учетной записи и зондирования автоматического переключения |
| `GET /api/auth/linked-accounts` | См. [§1.2](api-authentication.md) (полный список только при активной основной учетной записи) |
| `GET /rest/user/info`, `/rest/user/settings` | Профиль пользователя / настройки (не исследовано) |

<a id="credit-usage-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Использование кредитов (обнаружено 2026-07-20)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → использование кредитов на обсуждение (проверено 200):
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **Примечание**: `thread_id` ожидает **context_uuid** (psc_uuid); передача entryUUID дает 403
  `thread_usage_forbidden` ("Обсуждение не принадлежит текущему пользователю" — на самом деле неправильная форма идентификатора).
- Источники context_uuid: `list_collection_threads` (REST-индекс пространства уже охватывает 27/27),
  поле `context_uuid` записи обсуждения (архивируется как `psc_uuid` в thread.json).
- Можно запрашивать только обсуждения текущей учетной записи (межучетная → 403) — сбор с нескольких учетных записей требует автоматического переключения на каждую.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`: версия списка; проверено пусто на обеих учетных записях
  (предположительно только для биллинга организации; TBD).
- Другие конечные точки биллинга (`/rest/billing/credits/balance` и т.д.) в [приложении §7](api-discovery-roadmap.md); не исследованы.

<a id="official-export-backend-of-the-page-export-button-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Официальный экспорт (бэкенд кнопки "Экспорт" на странице; обнаружено 2026-07-20)

- **`POST /rest/thread/export`**, тело: `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<name>"}`
- Ответ: `{"file_content_64": "<base64>", "filename": "..."}`
- Проверенные форматы: **`md`** (официальный Markdown с заголовком с логотипом `<img>`), **`pdf`** (двоичный PDF ~880 КБ),
  **`docx`** (PK zip ~350 КБ) — все HTTP 200. Другие значения формата не тестировались.
- **Границы содержимого (подтверждено)**: возвращает Markdown **всего обсуждения** (запрос + сводка ответа + сноски с цитированием `[^1_N]`),
  **без тела RESEARCH_REPORT** — сам отчет глубокого исследования можно получить только через его подписанный URL (§3.7);
  т.е. текущая цепочка подписанных URL report.md **является официальным источником отчета** (тот же источник, что и загрузка панели артефактов на странице); нет необходимости переключаться на эту конечную точку.
- Ценность: официальный Markdown на уровне обсуждения может служить источником перекрестной проверки на уровне беседы (официально отформатированные сноски с цитированием/формат).

<a id="asset-report-download" data-pplx-source-anchor="true"></a>
### Загрузка ресурсов / отчетов
- **Подписанные URL CloudFront** в схематизированном ответе (`d2z0o16i8xm8ak.cloudfront.net`): прямая загрузка urllib,
  не требуется cookie/аутентификация; файлы с несколькими версиями нумеруются в порядке `created_at`.
- Резервный источник отчета об исследовании: URL S3 шага RESEARCH_ANSWER (`ppl-ai-file-upload.s3.amazonaws.com`, **истекает**);
  второй резерв: извлечение при рендеринге страницы (KaTeX `<annotation>`).
- **Очистка ~3 месяца**: ссылки на источники артефактов/отчетов истекают безвозвратно — экспорт должен быть своевременным.

<a id="other-observed-endpoints-page-load-not-explored" data-pplx-source-anchor="true"></a>
### Другие наблюдаемые конечные точки (загрузка страницы; не исследованы)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates` (SSE), `/api/version`.

<a id="message-submission-and-telemetry-2026-07-20-webbridge-cdp" data-pplx-source-anchor="true"></a>
### Отправка сообщений и телеметрия (2026-07-20 WebBridge + CDP)

<a id="submission-endpoint-post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### Конечная точка отправки: `POST /rest/sse/perplexity_ask`
- Полные образцы тела запроса (синтетические примеры) в `docs/perplexity-api-samples/`:
  - `ask_envelope_deep_research.json` — последующий виток глубокого исследования (2026-07-20; 39 параметров + query_str):
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + цепочка продолжения `last_backend_uuid`
  - `ask_envelope_search.json` — стандартный поиск, новый разговор с главной (2026-07-21; 35 параметров + query_str):
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json` — совет моделей, новый разговор с главной (2026-07-21; 36 параметров + query_str):
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- Ключевые поля (последующий виток глубокого исследования, проверено):
  - `mode: "copilot"` (глубокое исследование); `model_preference: "pplx_alpha"`
  - **Цепочка продолжения**: `last_backend_uuid` (uuid предыдущего витка бэкенда) + `query_source: "followup"`
  - `frontend_uuid` (новый uuid для этого витка), `read_write_token`, `target_collection_uuid` (содержащее пространство),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`** (миллисекунды от первого нажатия клавиши до отправки — поведенческая телеметрия, загружаемая с отправкой)
  - `use_schematized_api: true`, `supported_block_use_cases` (полный список блоков, соответствует §3.1 схематизированному),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- Ответ — это SSE-поток (интерфейс потребляет его с помощью fetch-event-source `getReader()` — модуль приложения замораживает ссылку fetch при инициализации,
  **перехватчики fetch/XHR, прикрепленные к странице, неэффективны**; и **тела потоковых ответов не сохраняются браузером** (`Network.getResponseBody` возвращает
  No data found) — захват возможен только через CDP `Network.getRequestPostData` (тело запроса доступно)).
- Конечное состояние потока — это в точности записи/блоки `/rest/thread/<uuid>` (те же данные, доставляемые инкрементально) —
  инструменту экспорта не нужно читать поток; он извлекает конечное состояние напрямую.

<a id="telemetry-post-resteventanalytics-batched-high-frequency" data-pplx-source-anchor="true"></a>
#### Телеметрия: `POST /rest/event/analytics` (пакетная, высокая частота)
Наблюдаемые события (с essentials event_data):
| event_name | Ключевые поля | Примечания |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | событие просмотра страницы — **не переключает непрочитанное** (исключено тестированием; реальное подтверждение прочтения — `POST /rest/thread/mark_viewed`, см. §3.1) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs` (**время чтения в миллисекундах для этого витка**), `userId`, `isPro`, `deviceInfo` (одновременность/экран/глубина цвета) | телеметрия продолжительности чтения (не переключает непрочитанное, исключено тестированием) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | действие отправки |
| `query first llm token` | `startLLMTokenElapsed` (задержка первого токена), полный `queryStr` | телеметрия производительности |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, полный `queryStr` | подтверждение успеха |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | взаимодействие с селектором моделей совета |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | просмотр правой панели |
- Общие поля событий: `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info` (hardwareConcurrency/экран/глубина цвета/архитектура), `isBrowserExtension`, `web_platform`.
- **Примечание**: одно наблюдаемое событие содержало `userId`, принадлежащий **другой учетной записи** (uid принадлежал учетной записи A, в то время как сессия уже была учетной записью B) —
  идентификатор профиля SDK телеметрии имеет задержку кэша; не судите о текущей учетной записи по userId телеметрии.
- Также есть datadog RUM (`browser-intake-datadoghq.com/api/v2/rum`) с высокочастотной отчетностью (прокрутка/мышь/производительность; содержимое не анализируется).

<a id="mode-and-model-selection-2026-07-21-tested-on-a-paid-account" data-pplx-source-anchor="true"></a>
#### Выбор режима и модели (2026-07-21, проверено на платной учетной записи)
- **`GET /rest/models/config/v2` = авторитетная таблица моделей**: `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`, `agentic_research_compare_models` (по умолчанию три модели совета).
  `pplx-ask models` вызывает эту конечную точку.
  - Официальное соответствие (проверено): **search = `pplx_pro` (имя в UI "Best"), research = `pplx_alpha`
    (имя в UI "Deep research")**.
  - Список моделей, выбираемых в UI для режима поиска (без Deep research): Best (pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **Поле `mode` всегда равно `"copilot"` — не является дискриминатором режима** (одинаково для поиска / глубокого исследования / совета моделей).
- Дискриминация находится в **`model_preference`**:
  - Поиск: `pplx_pro` (или выбранный пользователем идентификатор модели, например `experimental`=Sonar 2, `gpt56_sol`…)
  - Глубокое исследование: `pplx_alpha` (**нет селектора модели в UI**, фиксировано)
  - **Совет моделей**: `pplx_agentic_research` + **`compare_model_preferences: [<2-3 models>]`**
    (наблюдаемое по умолчанию `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`;
    UI — **одиночный выбор на слот**, уменьшается до 2 моделей при продолжении).
  - Пошаговое изучение: `pplx_study`; Computer: семейство `pplx_asi*`.
- Селектор модели в области компоновки ("model ⌄") и селектор "N models ⌄" совета сопоставляются с полями выше;
  событие телеметрии `ask input model selector opened` содержит `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels` (более ранние обсуждения глубокого исследования имели `searchMode: "research"`).
- Новый разговор: `query_source: "home"`, нет `last_backend_uuid`, есть `frontend_context_uuid`;
  продолжение: цепочка `query_source: "followup"` + `last_backend_uuid`.

<a id="entrysearch_mode-the-authoritative-record-of-conversation-mode-settled-2026-07-22" data-pplx-source-anchor="true"></a>
#### entry.search_mode: авторитетная запись режима разговора (установлено 2026-07-22)
**Каждая запись** `/rest/thread/<uuid>` содержит `search_mode`, авторитетную запись платформы о режиме разговора для этого витка
(сигнал обнаружения режима наивысшего приоритета, `normalize.SEARCH_MODE_MAP`):

| search_mode | Значение (UI/модель) | Режим архива |
|---|---|---|
| `SEARCH` | обычный поиск (default_models.search=pplx_pro "Best" и модели, выбираемые в UI) | search |
| `STUDIO` | сессия labs (pplx_beta); UI группирует его под поиском | search |
| `RESEARCH` | Глубокое исследование (default_models.research=pplx_alpha; UI фиксировано, нет селектора) | deep-research |
| `AGENTIC_RESEARCH` | совет моделей (pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | пошаговое изучение (pplx_study) | study |
| `ASI` | Computer (pplx_asi*) | computer |

- Обзор значений по всему архиву: все шесть значений имеют экземпляры в реальном архиве; SEARCH и RESEARCH доминируют,
  STUDIO следующий, ASI / STUDY / AGENTIC_RESEARCH редки.
- **pplx_alpha ⟺ RESEARCH перекрестное доказательство**: 100+ обсуждений платформы SEARCH-entry + pplx_alpha в архиве на 100%
  `search_mode=RESEARCH`; 100+ чистых pplx_pro обсуждений все `search_mode=SEARCH` —
  старая статистика "pplx_alpha — часто используемая модель для обычного поиска" на самом деле была образцами ошибочной классификации и не подтверждается.
- Несколько значений могут появляться в одном обсуждении (переключение режимов, например, наблюдаемая смесь SEARCH+RESEARCH): обнаружение берет наивысшее по специфичности
  computer>council>study>deep-research>search.

<a id="model-council-output-structure-and-expansion-behavior" data-pplx-source-anchor="true"></a>
#### Структура вывода совета моделей и поведение разворачивания
- Вывод одного витка = N блоков, специфичных для модели "Council: <model name>" (каждый с поисковыми запросами/источниками/ответом) + часть синтеза:
  **Where Models Agree** (матрица консенсуса, сравнение трех моделей по каждому выводу + Evidence),
  **Where Models Disagree** (таблица разногласий, позиция каждой модели + причины расхождений),
  **Unique Discoveries** (уникальные находки каждой модели), за которыми следуют рекомендации по связанным вопросам — **все доставляется в том же SSE-потоке**.
- Поведение разворачивания (включая разворачивание **во время генерации**): разворачиваемые строки имеют шеврон ">" (строки шагов / строки "Sources" / строки Council);
  щелчок разворачивает их — **чисто клиентский рендеринг, нулевые запросы содержимого**: из 1208 запросов этой сессии 921 были статическими ресурсами favicon/шрифтов;
  само разворачивание вызывает только загрузки favicon и /api/version. Разворачивание во время потоковой передачи не нарушает продолжение доставки.
- Наблюдаемая задержка первого токена ~204 с (три модели генерируют параллельно, заметно дольше, чем одна модель); наблюдаемое количество источников 236.
- Основы автоматизации области композиции (Lexical): текст должен вводиться через CDP `Input.insertText` (после execCommand/fill
  внутреннее состояние Lexical рассинхронизируется, и Enter не срабатывает); отправка может использовать CDP Enter или нажатие кнопки с aria-label="提交" ("Submit")
  (режим совета имеет явную стрелку отправки).

<a id="behavior-when-continuing-a-historical-conversation-tested-2026-07-20" data-pplx-source-anchor="true"></a>
#### Поведение при продолжении исторического разговора (проверено 2026-07-20)
1. Загрузка страницы обсуждения → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. Отправка продолжения → `rate-limit/status` → `sse/perplexity_ask` (с цепочкой `last_backend_uuid`) → высокочастотная аналитика.
3. Во время генерации → SSE-поток рендерится инкрементально; после завершения — еще одна порция аналитики (включая продолжительность чтения `thread entry exited`).
4. Последующие витки глубокого исследования также создают структуры отчетов (этот виток завершил 5 шагов).
