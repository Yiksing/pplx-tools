---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/pplx-ask.md"
translation_source_sha256: "01eede19356c18b7769f76a4a88c4cf86a543fc0852203e11051a6bacb17dc7e"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="pplx-ask-interactive-queries" data-pplx-source-anchor="true"></a>
# pplx-ask: Интерактивные запросы

`pplx-ask` — вторая точка входа CLI проекта: она задаёт вопросы Perplexity
интерактивно через SSE-поток, затем постобрабатывает полученную нить — перемещает её
в пространство BOT, отправляет опциональное уведомление о прочтении и телеметрию просмотра,
похожую на человеческую, и автоматически архивирует её с помощью того же конвейера экспорта,
что и `pplx-export`. Она разделяет ядро (транспорт / куки / состояние / логирование) с
`pplx-export`, и все формы API проверяются на живой платформе.

Источник: `pplx_export/ask_cli.py` (CLI), `pplx_export/sites/perplexity/ask_api.py` (уровень API).

```bash
pplx-ask models                                  # list the authoritative model table
pplx-ask ask "What is the time resolution of an example parameter?"   # search mode (default)
pplx-ask ask "<long prompt>" --mode council      # model council (default three models)
pplx-ask ask "<prompt>" --mode council --models gpt55_thinking,claude48opusthinking
pplx-ask ask "<prompt>" --mode deep-research     # deep research (fixed pplx_alpha)
pplx-ask ask "<prompt>" --space some-space-slug  # create inside a space, then move into BOT
pplx-ask ask "<prompt>" --mark-read              # send a read receipt after completion
pplx-ask mark-read <thread_url|uuid>             # standalone read receipt
pplx-ask space-create "My Space"                 # create a space
```

<a id="subcommands" data-pplx-source-anchor="true"></a>
## Подкоманды

### `models`

Выводит актуальную авторитетную таблицу моделей из
`GET https://www.perplexity.ai/rest/models/config/v2` (`pplx_export/ask_cli.py:51`):
модели по умолчанию для каждого режима, три модели совета по умолчанию, модели, выбираемые в
режиме поиска, и специальные режимы (`research` / `study` / `agentic_research` / `studio`).
Без опций.

### `ask`

Задаёт вопрос (`pplx_export/ask_cli.py:86`). Потоково передаёт прогресс в консоль через SSE,
запускает конвейер постобработки (см. [Процесс запроса](#the-ask-flow)) и выводит
машиночитаемый JSON-объект в stdout в конце.

| Опция | По умолчанию | Описание |
|---|---|---|
| `prompt` (позиционный) | — | Вопрос. Длинные, содержательные подсказки работают лучше. |
| `--mode` | `search` | `search` = обычный поиск (модель выбирается); `deep-research` = глубокое исследование (фиксированная модель); `council` = совет моделей (2–3 модели параллельно + синтез); `study` = пошаговое изучение |
| `--models` | нет | `council`: разделённые запятыми 2–3 идентификатора моделей (по умолчанию `gpt55_thinking,claude48opusthinking,gemini31pro_high`); `search`: один идентификатор модели; игнорируется для `deep-research` / `study` |
| `--space` | `home` | `home` = создать с домашней страницы, затем переместить в пространство BOT; `<slug>` = создать непосредственно внутри этого пространства, затем переместить в пространство BOT |
| `--mark-read` | выкл | Отправить уведомление о прочтении (`mark_viewed`) после завершения |
| `--no-telemetry` | выкл | Не отправлять телеметрию просмотра, похожую на человеческую (по умолчанию: отправлять — `ask context pane viewed` / `thread viewed` / `thread entry exited` со случайным временем) |
| `--no-export` | выкл | Не архивировать автоматически в `web_archive` |
| `--timeout` | `600` | Тайм-аут SSE-потока в секундах |

Подсказки об ошибках HTTP, выдаваемые `ask` (`pplx_export/ask_cli.py:124`): `401`/`403` = куки
истекли или сработал контроль рисков (обновите куки), `429` = превышение лимита запросов (повторите
позже), `5xx` = ошибка сервера (повторите позже). См. [Устранение неполадок](troubleshooting.md).

### `mark-read`

Отправляет уведомление о прочтении для существующей нити (`pplx_export/ask_cli.py:201`): принимает
URL нити или UUID в чистом виде, разрешает `context_uuid` нити через
`GET /rest/thread/<uuid>`, затем вызывает `POST /rest/thread/mark_viewed` с
`{"context_uuids": [ctx]}` (`pplx_export/sites/perplexity/ask_api.py:190`). Флаг непрочитанного
меняется немедленно. Выводит `{"uuid", "context_uuid", "result"}` в формате JSON.

Примечание: событие аналитики `thread viewed` **не** меняет флаг непрочитанного — настоящим
уведомлением о прочтении является эта конечная точка.

### `space-create`

Создаёт пространство через `POST /rest/collections/create_collection`
(`pplx_export/sites/perplexity/ask_api.py:179`) с проверенными фиксированными полями
(`emoji: "1f4c1"`, `access: 1`). Выводит `{"uuid", "slug", "url"}` в формате JSON.

| Опция | По умолчанию | Описание |
|---|---|---|
| `title` (позиционный) | — | Название пространства |
| `--description` | `""` | Описание пространства |

Чтобы использовать новое пространство как пространство BOT, зарегистрируйте его `uuid`/`slug` в `[bot_space]`
в конфигурации уровня пользователя (см. [Конфигурация](configuration.md)).

<a id="common-options" data-pplx-source-anchor="true"></a>
## Общие опции

Общие с `pplx-export` (идентичные имена и значения по умолчанию, `pplx_export/commands/common.py:232`):

| Опция | По умолчанию | Описание |
|---|---|---|
| `--account` | конфиг `default_account` | Целевая учётная запись; при несовпадении куки/email токены сессии браузера для каждой учётной записи перечисляются и переключаются автоматически |
| `--config PATH` | `~/.config/pplx-export/config.toml` | Конфигурация уровня пользователя (реестр учётных записей / пространство BOT); приоритет: `--config` > переменная окружения `PPLX_EXPORT_CONFIG` > путь по умолчанию |
| `--out` | `./web_archive` | Корневая папка вывода архива |
| `--cookies-from BROWSER` | автоопределение | Импортировать куки из указанного браузера (`edge`/`chrome`/`firefox`/`safari`/`brave`…) |
| `--cookies FILE` | — | Файл куки в формате Netscape или JSON |
| `-v` / `--verbose` | выкл | Вывод DEBUG (трассировка запросов / внутренние решения) |
| `--log-file [PATH]` | выкл | Полный лог DEBUG в файл; без значения попадает в `<out>/index/logs/<cmd>-<timestamp>.log` |

Приоритет источника куки: `--cookies-from` / `--cookies` > свежий кеш
(`<out>/index/.cookies.json`, 12 ч) > автоопределение браузера. См.
[Начало работы](getting-started.md) для первоначальной настройки.

<a id="the-ask-flow" data-pplx-source-anchor="true"></a>
## Процесс запроса

```mermaid
flowchart TD
    A["build_envelope(prompt, mode, models, space)"] --> B["SSE stream: POST /rest/sse/perplexity_ask"]
    B --> C{"final status == COMPLETED?"}
    C -- "no" --> X["abort — no move / no telemetry / no export"]
    C -- "yes" --> D["move thread into BOT space (best-effort)"]
    D --> E["read receipt, if --mark-read (best-effort)"]
    E --> F["view telemetry, unless --no-telemetry (best-effort)"]
    F --> G["auto-archive via the export pipeline (core step)"]
    G --> H["stdout: result JSON"]
```

1. **Сборка конверта** — `build_envelope` (`pplx_export/sites/perplexity/ask_api.py:71`)
   заполняет проверенный шаблон параметров: `mode` всегда `"copilot"` и
   `query_source` — `"home"` (каждый `ask` начинает **новый** разговор; продолжение
   беседы не поддерживается CLI). С `--space <slug>` слаг пространства
   преобразуется в uuid, и конверт содержит `target_collection_uuid` +
   `target_thread_access_level: 1`.
2. **SSE-поток** — `sse_ask` (`pplx_export/sites/perplexity/ask_api.py:153`) отправляет POST на
   `https://www.perplexity.ai/rest/sse/perplexity_ask` и потребляет поток событий,
   логируя создание нити (`https://www.perplexity.ai/search/<uuid>`), переходы
   статусов и прогресс генерации. Поток завершается на `final_sse_message`.
3. **Шлюз завершения** — постобработка запускается только когда финальный статус `COMPLETED`
   (`pplx_export/ask_cli.py:134`). При аномальном завершении потока всё после этого
   пункта пропускается (без перемещения, без телеметрии, без экспорта), чтобы незавершённое состояние
   никогда не попало в архив.
4. **Перемещение в пространство BOT** (по возможности) — `batch_move_threads` с `context_uuid` нити
   в настроенный uuid `[bot_space]`. Пропускается, если пространство BOT не
   настроено, или если нить уже была создана внутри пространства BOT.
5. **Уведомление о прочтении** (по возможности, `--mark-read`) — `POST /rest/thread/mark_viewed`;
   флаг непрочитанного меняется немедленно.
6. **Телеметрия просмотра, похожая на человеческую** (по возможности, включена по умолчанию) —
   `send_view_telemetry` (`pplx_export/sites/perplexity/ask_api.py:234`) имитирует реальное
   время просмотра: `ask context pane viewed` → `thread viewed` → `ask context pane
   viewed` → `thread entry exited` (random `timeOnEntryMs` от 12–45 с, паузы 0.6–2.4 с
   между событиями, устройство выбирается случайно из небольшого пула).
7. **Автоматическое архивирование** (основной шаг, если не `--no-export`) — нить экспортируется
   через тот же конвейер, что и `pplx-export export` (режим принудительно), попадая в
   `<out>/<account>/<mode>/<date>_<title>_<uuid8>/` — см.
   [Структура архива](archive-layout.md) и [Конвейер экспорта](../architecture/export-pipeline.md).
   В отличие от шагов, выполняемых по возможности, сбой архивирования распространяется и приводит к ошибке команды.

**Изоляция сбоев**: шаги 4–6 изолированы как выполняемые по возможности (`pplx_export/ask_cli.py:36`):
сбой логирует предупреждение, устанавливает ключ JSON шага в `false`, записывает детали в
`step_errors` и никогда не блокирует архивирование. Архивирование (шаг 7) является основным шагом, и его
сбои никогда не игнорируются.

<a id="modes-and-model-selection" data-pplx-source-anchor="true"></a>
## Режимы и выбор модели

Авторитетная таблица моделей платформы — `GET /rest/models/config/v2` (то, что
выводит `pplx-ask models`). Различие находится в поле `model_preference` — `mode` конверта
всегда `"copilot"`.

| Режим | Значение `--mode` | `model_preference` | Выбор модели |
|---|---|---|---|
| Поиск | `search` | `pplx_pro` ("Лучшая" в интерфейсе) по умолчанию | Один идентификатор модели через `--models` (см. `pplx-ask models` для списка выбираемых) |
| Глубокое исследование | `deep-research` | `pplx_alpha` | Фиксированная — без выбора |
| Совет моделей | `council` | `pplx_agentic_research` + `compare_model_preferences` | 2–3 идентификатора через запятую через `--models`; по умолчанию `gpt55_thinking,claude48opusthinking,gemini31pro_high` |
| Пошаговое изучение | `study` | `pplx_study` | Фиксированная — без выбора |
| Компьютер | *(не раскрывается)* | семейство `pplx_asi*` | Не поддерживается `pplx-ask` |

Примечания:

- Совет запускает модели параллельно и синтезирует; наблюдаемая задержка первого токена может
  превышать 3 минуты, поэтому увеличьте `--timeout` для запусков совета / глубокого исследования.
- Таксономия режимов на стороне архива (как классифицируются экспортированные нити, включая
  `computer`) описана в [Режимы](modes.md); детали конверта запроса находятся в
  [REST-конечные точки](../reference/api/api-rest-endpoints.md).

<a id="using-pplx-ask-from-other-agents" data-pplx-source-anchor="true"></a>
## Использование pplx-ask из других агентов

`pplx-ask` создан так, чтобы другие агенты могли получать информацию в реальном времени: он задаёт
вопрос, ждёт завершения, архивирует нить и выводит машиночитаемый контракт.

- **stdout содержит ровно один JSON-объект** (последняя строка); все логи идут в stderr, поэтому
  вызывающие программы могут передавать stdout напрямую в JSON-парсер.
- **Код завершения**: `0` при успехе; при сбоях завершается с ненулевым кодом и сообщением об ошибке в
  stderr — сбои на этапе запроса прерываются через `SystemExit` с сообщением `[ask][ERROR]`,
  в то время как сбои архивирования распространяются как есть (см. шаг 7).

Форма результирующего JSON (`pplx_export/ask_cli.py:194`):

| Ключ | Тип | Значение |
|---|---|---|
| `thread_uuid` | строка | Backend uuid созданной нити |
| `thread_url` | строка | `https://www.perplexity.ai/search/<thread_uuid>` |
| `context_uuid` | строка | `context_uuid` нити (используется для перемещения / отметки о прочтении / телеметрии) |
| `moved_to_bot` | булев | `true` = перемещение в пространство BOT выполнено и успешно; `false` = не выполнено или не удалось |
| `mark_read` | булев | То же для уведомления о прочтении |
| `telemetry` | булев | То же для телеметрии просмотра |
| `step_errors` | объект | Детали сбоя по шагам; присутствуют только шаги, завершившиеся сбоем |
| `exported` | строка \| null | `"见上方 [export] 输出"`, когда архивирование выполнялось; `null` с `--no-export` |

Советы по автоматизации:

- Относитесь к булевым значениям шагов строго — сбой никогда не представляется истинным значением;
  проверяйте `step_errors` для деталей.
- `--no-telemetry` пропускает задержку в 12–45 с, имитирующую человеческое поведение, когда важен только ответ.
- Без настроенного пространства BOT (упрощённый режим) `moved_to_bot` остаётся `false`, и
  всё остальное всё равно работает — см. [Устранение неполадок](troubleshooting.md).
- Для настройки учётной записи/куки безголовые агенты должны прочитать
  [Аутентификация API](../reference/api/api-authentication.md); поведение с несколькими учётными записями описано в
  [Запросы и учётные записи](../architecture/ask-and-accounts.md).

<a id="see-also" data-pplx-source-anchor="true"></a>
## См. также

- [Начало работы](getting-started.md) — установка, куки, первый запуск
- [Конфигурация](configuration.md) — учётные записи, пространство BOT, упрощённый режим
- [pplx-export](pplx-export.md) — CLI архивирования
- [Устранение неполадок](troubleshooting.md) — 401/403, не та учётная запись, логи
