---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/incremental-sync.md"
translation_source_sha256: "35868edfb3e8e914afd9afa1b00370bffb9f8a50ca374691229f41d51ffa9b64"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="incremental-sync" data-pplx-source-anchor="true"></a>
# Инкрементальная синхронизация

`pplx-export batch` создан для частого запуска: каждый запуск экспортирует только то, что новое или
изменённое, устраняет пробелы, оставленные прерванными запусками, и никогда не пересматривает темы, которые
платформа уже завершила. Единственным источником истины для «что было экспортировано» является
`index/batch_state.json` (`BatchState`,
`pplx_export/core/state.py:63`), обновляемый после каждой темы — нет
отдельной теневой копии.

<a id="prerequisites-and-basic-usage" data-pplx-source-anchor="true"></a>
## Предварительные требования и базовое использование

```bash
pplx-export index --account alice   # refresh index/library_alice.json first
pplx-export batch --account alice   # incremental export (early stop, resumable)
```

`batch` отказывается работать без индекса
(`pplx_export/commands/batch_cmd.py:79-81`). `--limit N` и `--mode <mode>`
фильтруют строки индекса перед планированием; строки без `entryUUID` пропускаются
с предупреждением вместо аварийного завершения запуска (`batch_cmd.py:95-100`).

<a id="how-the-incremental-plan-works" data-pplx-source-anchor="true"></a>
## Как работает инкрементальный план

1. **Сортировка.** Строки индекса сортируются по `lastUpdated`, сначала новые
   (`batch_cmd.py:89`). Совершенно новые беседы и возобновлённые старые (чьи
   `lastUpdated` только что переместили их вверх) находятся наверху — этот порядок
   делает безопасной раннюю остановку.
2. **Классификация.** `plan_incremental`
   (`pplx_export/hooks/incremental.py:36-87`) — чистая функция, общая для
   `batch` и `schedule` — назначает каждой строке ровно одно действие:

   | действие | условие | что делает пакет |
   |---|---|---|
   | `new` | uuid никогда не встречался в `batch_state` | экспорт |
   | `updated` | `lastUpdated` отличается от записанного значения, или `--force` | повторный экспорт |
   | `done` | статус `ok` и `lastUpdated` не изменились | пропуск |
   | `expired` | платформа вернула `ENTRY_EXPIRED` при предыдущей попытке | пропуск — терминальный, никогда не повторяется |
   | `deleted` | `sync-deleted` подтвердил удаление на стороне | пропуск — терминальный, никогда не повторяется |

3. **Ранняя остановка.** По умолчанию (ни `--full`, ни `--force`) самая длинная
   завершающая последовательность терминальных записей (`done` / `expired` / `deleted`) обрезается
   целиком и учитывается как `n_stopped` (`incremental.py:83-87`). Поскольку
   список отсортирован от новых к старым, всё ниже неизменённой записи обязательно
   старше и тоже не изменилось — дальнейшее сканирование только тратило бы время.

   ```mermaid
   flowchart TD
       IDX["library index rows<br/>sorted by lastUpdated, newest first"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → export"]
       PLAN --> UPD["updated → re-export"]
       PLAN --> DONE["done → skip"]
       PLAN --> TERM["expired / deleted → skip (terminal)"]
       DONE --> STOP["early stop:<br/>trailing terminal run trimmed"]
       TERM --> STOP
   ```

4. **Выполнение.** Каждая экспортированная тема немедленно отмечается (`mark_ok` /
   `mark_error` / `mark_expired` / `mark_deleted`), и файл состояния сохраняется
   после каждого элемента (`batch_cmd.py:154-201`); `KeyboardInterrupt` также сохраняется
   перед распространением (`batch_cmd.py:158-161`). Записи атомарны — временный файл
   плюс `os.replace` (`state.py:145-152`) — поэтому прерванный запуск никогда не оставляет
   усечённый JSON.

<a id="gap-healing-after-interrupted-runs" data-pplx-source-anchor="true"></a>
## Устранение пробелов после прерванных запусков

Ранняя остановка никогда не скрывает пробел. Темы, которые завершились ошибкой (статус `error`) или не были
достигнуты, находятся **выше** терминального суффикса, поэтому следующий запуск перепланирует их
как `updated` / `new` и экспортирует их до достижения точки ранней остановки
(`incremental.py:12-14`, `batch_cmd.py:206-208`). В сочетании с сохранением состояния
для каждого элемента пакетный запуск может быть прерван в любой точке и просто перезапущен.

Если сам `batch_state.json` повреждён, он не затирается молча: оригинал
переименовывается в `batch_state.json.corrupt-<timestamp>`, чтобы записанные
терминальные состояния не были потеряны и не повторялись без необходимости (`state.py:68-81`).

<a id="-full-and-force" data-pplx-source-anchor="true"></a>
## `--full` и `--force`

| флаг | эффект | терминальные состояния | когда использовать |
|---|---|---|---|
| *(по умолчанию)* | ранняя остановка над завершающей терминальной последовательностью | пропущены | каждый обычный / плановый запуск |
| `--full` | полное сканирование, без ранней остановки; неизменённые темы всё равно пропускаются как `done` | пропущены | периодическая подстраховка или при подозрении на пробелы в архиве |
| `--force` | повторный экспорт всего, даже неизменённых тем | всё ещё исключены — никогда не повторяются | после исправлений конвейера, требующих повторной загрузки сырых данных |

Терминальные состояния исключены из `--force` по замыслу: повторная попытка для истёкшей или
удалённой на стороне темы только тратит запросы и бюджет отсрочек
(`batch_cmd.py:120-127`).

См. также [`status`](maintenance-commands.md#status): отчёт без сетевых запросов о
состоянии учёта и плане изменений, вычисленный с той же семантикой `plan_incremental`
(`new`/`updated`/количество ранних остановок).

Сравнение `lastUpdated` нормализует завершающие нули в
дробной части секунд (`.18033Z` равно `.180330Z`; `state.py:23-55`),
потому что платформа иногда их опускает — точное строковое сравнение могло бы
ошибочно определить «изменено» и вызвать дублирующий экспорт.

<a id="terminal-states-expired-and-deleted" data-pplx-source-anchor="true"></a>
## Терминальные состояния: `expired` и `deleted`

| | `expired` | `deleted` |
|---|---|---|
| значение | платформа удалила тему (~3-месячное окно хранения); попытка экспорта вернула `ENTRY_EXPIRED` | удаление пользователем/удалённо, подтверждено `sync-deleted` |
| записывается | самим `batch` (`mark_expired`, `state.py:131-134`) | `pplx-export sync-deleted --online` (`mark_deleted`, `state.py:136-143`) |
| повторяется? | никогда — даже с `--force` | никогда — даже с `--force` |
| доказательство | ответ `ENTRY_EXPIRED` | поле `note`: отсутствие в индексе + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted-confirming-remote-deletions" data-pplx-source-anchor="true"></a>
### sync-deleted: подтверждение удалений на стороне

```bash
pplx-export sync-deleted --account alice            # offline dry-run: list candidates only
pplx-export sync-deleted --account alice --online   # confirm each candidate online
```

1. **Кандидаты (офлайн, без сети).** Любая тема со статусом `ok` в
   `batch_state`, отсутствующая в объединении `entryUUID` **всех**
   индексов учётных записей `index/library_*.json`, является подозреваемым кандидатом на удаление
   на стороне (`pplx_export/commands/sync_deleted_cmd.py:148-212`). Объединение
   по всем учётным записям необходимо: тема, принадлежащая `bob`, но экспортированная `alice`
   через общее пространство, никогда не появляется в собственном индексе `alice` —
   сравнение по одной учётной записи дало бы ложноположительный результат для всего этого набора. Когда
   нет ни одного пригодного индекса, каждый кандидат безопасно пропускается с записью причины.
2. **Пробный запуск по умолчанию.** Без `--online` команда только перечисляет
   кандидатов — без сети, без изменений файлов.
3. **Подтверждение `--online`.** Каждый кандидат проверяется с помощью
   `GET /rest/thread/<uuid>`, используя учётную запись `export_via` кандидата из
   `thread.json` (cookie переключается автоматически):

   | результат | исход |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | подтверждено: `batch_state` помечает как терминальное `deleted` (`note` записывает причину), и каждый `thread.json` этой темы получает метку времени `remote_deleted` на своё место |
   | тема всё ещё существует | ложноположительный результат: сообщается как есть (индекс может быть не полностью обновлён — перезапустите `index` и проверьте снова), ничего не изменено |
   | 5xx / сетевая ошибка | состояние не меняется; кандидат оставляется для следующего раунда |
   | 3 последовательных 401/403 | быстрый аварийный останов — истёкший cookie не может восстановиться сам, и продолжение могло бы неправильно пометить активные темы (`sync_deleted_cmd.py:333-337`) |

   Подтверждённые метки сохраняются для каждого элемента, поэтому прерванный запуск `--online`
   ничего не теряет, и повторные запуски идемпотентны (`sync_deleted_cmd.py:254-256`).

<a id="the-tombstone-principle" data-pplx-source-anchor="true"></a>
## Принцип надгробия

!!! warning "Локальные архивы никогда не удаляются"
    Этот архив является резервной копией экспортированных бесед.
    `sync-deleted` только *идентифицирует и помечает* (надгробие): он **никогда не удаляет
    и не перемещает ни один файл архива**. Подтверждение меняет ровно две вещи —
    статус `batch_state` и один ключ-маркер в `thread.json`:

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    Метка идемпотентна: существующий ключ `remote_deleted` не
    перезаписывается и не заменяется (`sync_deleted_cmd.py:215-244`).

<a id="idempotence-and-offline-re-render" data-pplx-source-anchor="true"></a>
## Идемпотентность и офлайн-перерендеринг

- Повторный запуск `batch` с неизменённым индексом ничего не экспортирует: каждая
  строка классифицируется как `done`, и запуск останавливается в точке ранней остановки. Записи состояния
  атомарны, метки по каждой теме, и повторно подтверждённые удаления никогда не дублируют
  метку `remote_deleted`.
- Архив хранит сырые полезные данные API (`raw_entries.json` /
  `raw_blocks.json`), поэтому отрендеренные файлы могут быть регенерированы в любое время
  без доступа к сети:

  ```bash
  pplx-export re-render                 # rebuild conversation.md + turns/ everywhere
  pplx-export re-render --dry-run       # only list the thread directories
  pplx-export re-render --thread-json   # also sync interruptions / answer_variants keys
  ```

  `re-render` повторно разбирает сырой JSON с текущим рендерером
  (`pplx_export/commands/rerender_cmd.py:105-190`): `conversation.md` и
  `turns/turn_*.md` перезаписываются, устаревшие файлы поворотов с номерами выше текущего
  количества поворотов удаляются, а источники, ресурсы, `report.md` и `thread.json`
  остаются нетронутыми. Так исправления рендерера распространяются на весь
  архив без единого запроса.

<a id="see-also" data-pplx-source-anchor="true"></a>
## См. также

- [pplx-export.md](pplx-export.md) — полная справка по команде `batch` (`--mode`, `--limit`, задержки)
- [maintenance-commands.md](maintenance-commands.md) — `sync-deleted`, `re-render` и команды обратного заполнения
- [archive-layout.md](archive-layout.md) — где находятся `batch_state.json` и `thread.json`
- [rate-limiting.md](rate-limiting.md) — темп между темами, отсрочка, быстрый аварийный останов при ошибке аутентификации
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) — полный конвейер экспорта
- [../architecture/offline-operations.md](../architecture/offline-operations.md) — конвейер офлайн-перестроения в деталях
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — таксономия ошибок и обработка терминальных состояний
