---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/rate-limiting.md"
translation_source_sha256: "0f94f3ddbb3a7ac5ea7eef4a48ecd5479e5a834d8fda263c700df5ada0de3350"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="rate-limiting" data-pplx-source-anchor="true"></a>
# Ограничение скорости

Каждое число в политике регулирования служит одной цели: архивный трафик должен выглядеть как обычный просмотр. Однопоточный экспорт стоит 1–2 запроса — примерно один просмотр страницы — и пакетные запуски распределяют эти запросы по случайным интервалам без параллелизма. Это явное требование по предотвращению рисков (`pplx_export/core/throttle.py:1-2`), а не настраиваемый параметр производительности.

<a id="the-numbers" data-pplx-source-anchor="true"></a>
## Цифры

| где | регулирование | код |
|---|---|---|
| `batch`: между потоками | случайный равномерный 10–20 с (`--delay-min` / `--delay-max`) | `pplx_export/cli.py:126-129`, `pplx_export/core/throttle.py:33-36` |
| `sync-deleted --online`: между кандидатами | случайный равномерный 10–20 с | `pplx_export/cli.py:164-167`, `pplx_export/commands/sync_deleted_cmd.py:368-369` |
| `search-mode-backfill`: онлайн-запасной вариант | случайный равномерный 10–20 с | `pplx_export/cli.py:144-147` |
| пагинация внутри потока / списка пространств | ≥3 с между страницами | `pplx_export/sites/perplexity/rest.py:39,56`, `pplx_export/sites/perplexity/adapter.py:285-309` |
| обратная загрузка схематизированных блоков (computer / deep-research / council / study) | ≥4 с ожидания перед вторым запросом | `pplx_export/sites/perplexity/adapter.py:27-32,88` |
| `spaces --fetch-meta` | 3 с на пространство | `pplx_export/commands/spaces_cmd.py:328` |
| `usage-backfill` | 3 с на поток | `pplx_export/commands/usage_backfill_cmd.py:77` |
| `assets-backfill` онлайн-фазы | 3 с на поток | `pplx_export/commands/assets_backfill_cmd.py:215,456` |
| загрузка ресурсов внутри потока | 0,5 с | `pplx_export/sites/perplexity/assets.py:28,103` |
| `assets-backfill` фаза CDN | 6 параллельных загрузок, без задержки | `pplx_export/commands/assets_backfill_cmd.py:460-475` |
| параллелизм API | никогда — ни одного | — |

<a id="why-these-numbers" data-pplx-source-anchor="true"></a>
## Почему такие цифры

- **Один экспорт = 1–2 запроса ≈ один просмотр страницы.** Поисковый поток стоит одного `GET /rest/thread/<uuid>`; computer / deep-research / council / study добавляют ровно один запрос схематизированных блоков (`pplx_export/sites/perplexity/adapter.py:87-89`). Это примерно то, что делает браузер, когда вы открываете страницу один раз — архив не добавляет значимой нагрузки сверх обычного использования.
- **Случайный интервал 10–20 с, без параллелизма.** Ритм чтения человека, а рандомизация избегает метрономно точного времени. Последовательные запросы удерживают скорость ниже того, что уже производит обычный просмотр.
- **≥3 с перелистывание страниц.** Пагинация внутри одного длинного потока имитирует прокрутку и время чтения.
- **≥4 с перед запросом блоков.** Иначе схематизированный повторный запрос попадал бы в API сразу после обычного запроса; пауза имитирует задержку перед загрузкой полного содержимого тяжелой страницы.
- **0,5 с загрузка ресурсов.** Небольшие статические файлы, гораздо дешевле вызовов API — но все равно регулируются.
- **Фаза CDN — единственное послабление.** Загрузки по подписанным URL попадают в сеть доставки контента, а не в API Perplexity, поэтому 6 параллельных соединений допустимы только там.

<a id="error-handling-and-backoff" data-pplx-source-anchor="true"></a>
## Обработка ошибок и откат

Вся классификация происходит в `CookieTransport._request` (`pplx_export/core/http/cookie_transport.py:63-126`); каждый запрос получает до `max_retries=3` попыток (`cookie_transport.py:48`).

```mermaid
flowchart TD
    R{response} -->|"2xx"| OK["reset backoff counter"]
    R -->|"429"| BO["backoff + retry (≤3 attempts)"]
    R -->|"5xx / network error"| BO
    R -->|"401 / 403"| AF["raise immediately →<br/>abort after 3 consecutive"]
    R -->|"ENTRY_EXPIRED / ENTRY_DELETED"| TERM["terminal mark<br/>never retried"]
```

| ответ | классификация | обработка |
|---|---|---|
| 2xx | успех | сброс счетчика отката (`cookie_transport.py:77`) — счетчики никогда не накапливаются между запросами |
| 429 | ограничение скорости | откат и повтор (`cookie_transport.py:86-92`) |
| 500 / 502 / 503 / 504 | временная ошибка сервера (504 часто является сбоем Cloudflare) | откат и повтор хотя бы один раз перед отказом (`cookie_transport.py:99-107`) |
| сетевая ошибка | временная | откат и повтор (`cookie_transport.py:117-125`) |
| 401 / 403 | ошибка аутентификации | `AuthTransportError` вызывается немедленно — без отката (`cookie_transport.py:82-85`) |
| 400 + `ENTRY_EXPIRED` | очистка платформы | `EntryExpiredError` — терминальная, никогда не повторяется (`cookie_transport.py:96-98`) |
| 400 + `ENTRY_DELETED` | удаление пользователем/удаленно | `EntryDeletedError` — терминальная, никогда не повторяется (`cookie_transport.py:93-95`) |
| 404 / другие коды | обычная ошибка | без повторения на транспортном уровне; **никогда** не переводится в терминальное состояние (`cookie_transport.py:108-116`) |

**Формула отката** (`pplx_export/core/throttle.py:38-50`):
`delay_max × 3^N`, где `N` — количество последовательных сбоев (показатель степени ограничен 8), с разбросом ±20% для предотвращения синхронизации, максимум 300 с. Нет бессмысленного ожидания после последней неудачной попытки, и `throttle.reset()` сбрасывает счетчик при первом успехе (`throttle.py:52`).

Почему существует каждое правило:

- **Откат при 429** — сервер явно попросил замедлиться; уважайте это экспоненциально.
- **Повтор при 5xx** — единичный сбой шлюза не должен приводить к сбою потока.
- **401/403 без отката** — ожидание не восстановит мертвый cookie.
- **`ENTRY_EXPIRED` без повтора** — очистка платформы (окно ~3 месяца) является постоянной; повтор только сжигает запросы и бюджет отката.
- **404 никогда не терминальная** — поток, созданный `pplx-ask`, может временно выдавать 404 сразу после создания (задержка распространения); терминальная отметка похоронила бы живой поток, который лишь ненадолго невидим.

<a id="auth-fail-fast" data-pplx-source-anchor="true"></a>
## Быстрый отказ при аутентификации

Пакетный слой подсчитывает последовательные ошибки аутентификации (`_AUTH_FAIL_FAST = 3`, `pplx_export/commands/batch_cmd.py:43`). Любой ответ, достигший сервера — включая `ENTRY_DELETED` / `ENTRY_EXPIRED` — доказывает, что cookie работает, и сбрасывает счетчик (`batch_cmd.py:170-182`). Три последовательных 401/403, и запуск сохраняет свой файл состояния, затем прерывается (`batch_cmd.py:190-194`): продолжать с мертвым cookie заставило бы сотни потоков каждый раз терпеть неудачу — часы потеряны. `sync-deleted` применяет ту же дисциплину (`pplx_export/commands/sync_deleted_cmd.py:111,333-337`). Исправление — обновить cookie и запустить заново; все уже экспортированное пропускается.

`batch` и транспорт используют один экземпляр `Throttle` (`pplx_export/cli.py:280-282`, `batch_cmd.py:101-105`), поэтому подсчет отката никогда не разделяется между слоями — и общий экземпляр переживает автоматическое переключение учетных записей.

<a id="scheduling-periodic-sync" data-pplx-source-anchor="true"></a>
## Планирование периодической синхронизации

`pplx-export schedule` вычисляет текущий инкрементальный план (количество новых/обновленных) и записывает фрагмент cron в `<out>/index/cron_snippet.txt` (`pplx_export/commands/misc_cmd.py:86-96`, `pplx_export/hooks/scheduler.py:48-77`):

```bash
pplx-export schedule --account alice
```

```cron
17 3 * * * cd '<out-parent>' && '/abs/path/to/pplx-export' batch --account 'alice' --out '<out>'
```

- Периодические запуски являются **только инкрементальными** (ранняя остановка) — без полных повторных выборок (`scheduler.py:4-9`).
- Фрагмент использует абсолютные пути в кавычках, потому что рабочий каталог cron и `PATH` непредсказуемы (`scheduler.py:63-75`).
- Установите его с помощью `crontab -e` и настройте время по вкусу; распределите несколько учетных записей по разным слотам.
- Необязательная подстраховка: добавьте еженедельный или ежемесячный ручной обход с помощью `pplx-export batch --account alice --full` (см. [incremental-sync.md](incremental-sync.md)).

<a id="see-also" data-pplx-source-anchor="true"></a>
## См. также

- [incremental-sync.md](incremental-sync.md) — что именно экспортирует каждый запланированный запуск
- [pplx-export.md](pplx-export.md) — `--delay-min` / `--delay-max` и другие параметры команды
- [troubleshooting.md](troubleshooting.md) — что делать после прерывания из-за быстрого отказа аутентификации
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — полная таксономия ошибок
- [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) — семантика ошибок на стороне платформы (`ENTRY_EXPIRED`, `ENTRY_DELETED`, Cloudflare)
- [../reference/api/api-authentication.md](../reference/api/api-authentication.md) — cookies и переключение между несколькими учетными записями
