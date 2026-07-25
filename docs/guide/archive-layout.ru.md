---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/archive-layout.md"
translation_source_sha256: "6302a47c60b6c8703d36f420cee6c18017110fcbb6127926eedb5c77e3e1f8e2"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="archive-layout" data-pplx-source-anchor="true"></a>
# Структура архива

Все загрузки `pplx-export` попадают в единое дерево вывода — по умолчанию `./web_archive/`
(переопределяется с помощью `--out`). Эта страница — путеводитель по этому дереву: что представляет собой каждый каталог и файл,
какие ключи несёт `thread.json`, и как инструмент сохраняет один каталог на поток, когда
беседа продолжается в течение нескольких дней. Всё это создаётся инструментом; механизм подробно описан в
[Модель данных и контракт каталога](../architecture/data-model.md) и
[Конвейер экспорта](../architecture/export-pipeline.md).

<a id="the-output-tree" data-pplx-source-anchor="true"></a>
## Дерево вывода

```
web_archive/
├── alice/                                # one folder per account (author display name)
│   ├── search/                           # mode: search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # one directory per thread
│   │       ├── thread.json               # metadata + optional registries
│   │       ├── conversation.md           # compact read: per-turn Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # full read: complete work-process detail
│   │       │   └── ...
│   │       ├── sources.json              # thread-wide citations (deduped by url)
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research report (only when one exists)
│   │       ├── raw_entries.json          # plain API response, verbatim (always present)
│   │       ├── raw_blocks.json           # schematized API response (absent for search)
│   │       └── assets/
│   │           ├── assets_manifest.json  # versioned manifest
│   │           └── files/                # downloaded asset bodies
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # state files and indexes (see below)
├── relations/                            # edges.jsonl + graph.md (rebuilt by `pplx-export relations`)
├── crosscheck/                           # cross-validation reports (manual/review artifacts)
└── bob/ ...
```

<a id="the-thread-directory" data-pplx-source-anchor="true"></a>
## Каталог потока

Каждый поток получает ровно один каталог, вычисляемый с помощью `thread_dir_for` (`fs_writer.py:58-72`):

```
<account display name>/<mode>/<YYYY-MM-DD>_<title-slug>_<uuid8>/
```

| Компонент | Источник | Примечания |
|---|---|---|
| `<account display name>` | автор потока, через `author_folder` → `_safe_folder` (`fs_writer.py:40-51`) | разделители путей и символы, недопустимые в Windows (`:*?"<>\|`), заменяются на `_`; `.`/`..` отклоняются (защита от обхода пути для общих пространств); всё остальное, включая пробелы, сохраняется |
| `<mode>` | `detect_mode` | один из пяти режимов; см. [Режимы беседы](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` `lastUpdated` префикс даты | дата последнего обновления платформы, **не** дата экспорта — она изменяется при обновлении продолженного потока (см. миграцию ниже) |
| `<title-slug>` | `slugify(title)` (`normalize.py:261-263`) | макс. 40 символов, не-словесные символы → `-`, пусто → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | первые 8 символов UUID потока — идентификационный якорь каталога |

<a id="files-in-a-thread-directory" data-pplx-source-anchor="true"></a>
## Файлы в каталоге потока

<a id="threadjson-metadata-and-registries" data-pplx-source-anchor="true"></a>
### thread.json — метаданные и реестры

Записывается с помощью `write_thread` (`fs_writer.py:224-253`). Всегда присутствующие ключи:

| Ключ | Содержимое |
|---|---|
| `web_uuid` | веб- entryUUID — UUID в URL потока; идентификатор потока |
| `psc_uuid` | платформенный `context_uuid` (может быть null; из первого непустого оборота) — двойной идентификатор, используемый индексами пространств |
| `url` | канонический URL потока |
| `title` | заголовок потока |
| `mode` | обнаруженный режим (`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | отображаемое имя автора аккаунта |
| `export_via` | имя пользователя аккаунта, выполнившего экспорт — важно для потоков из общих пространств, экспортированных через другой аккаунт |
| `space` | `{"uuid", "title", "slug"}` или `null` |
| `lastUpdated` | временная метка последнего обновления платформы (контракт машинного сравнения для инкрементальной синхронизации) |
| `threadAccess` | флаг доступа платформы |
| `n_turns` | количество оборотов |
| `n_sources` | общее количество цитирований в потоке |
| `metadata` | `thread_metadata` из ответа API, дословно |
| `report_info` | `{"title", "file_name", "url"}` или `null` |
| `exported_at` | время экспорта (UTC ISO 8601) |

Необязательные ключи — отсутствуют, когда нечего записывать:

| Ключ | Добавляется когда | Содержимое |
|---|---|---|
| `interruptions` | любой незавершённый рабочий процесс (`fs_writer.py:242-244`) | список `{location, kind, headline, status}`; см. [Режимы беседы — Прерывания](modes.md#interruptions-non-completed-workflows) |
| `answer_variants` | обнаружен вариант перезаписи ответа (`fs_writer.py:247-252`) | суженные `side_by_side_metadata` поля локации; см. [Режимы беседы — Варианты перезаписи ответа](modes.md#answer-rewrite-variants-answer_variants) |
| `remote_deleted` | `pplx-export sync-deleted --online` подтверждает удаление на сервере | временная метка надгробия, записывается на месте, идемпотентно (существующее значение никогда не перезаписывается; `sync_deleted_cmd.py:215-244`) — сам локальный архив сохраняется |

<a id="conversationmd-the-compact-read" data-pplx-source-anchor="true"></a>
### conversation.md — компактное чтение

`render_conversation` (`render.py:641`): заголовок (режим / автор / обороты / количество цитирований),
затем для каждого оборота пара `### Query` + `### Answer` с полными ответами, и — при наличии —
приложение фоновых задач уровня потока в конце. Это файл для первого открытия; процессы работы с оборотами
находятся в `turns/`.

<a id="turnsturn_nnnnmd-the-full-read" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md — полное чтение

`render_turn` (`render.py:596`): один файл на оборот (`turn_0001.md` …), каждый с полным
рабочим процессом — шаги, вызовы инструментов, запуски под-агентов, таблицы, цитирования на оборот. Когда количество оборотов
потока уменьшается, устаревшие файлы с большими номерами `turn_*.md` удаляются, но нетронутые файлы сохраняют
своё mtime (`fs_writer.py:287-301`).

### sources.json / sources.md

Цитирования по всему потоку, дедуплицированные по URL (`fs_writer.py:270-278`). `sources.json` — это
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`; `sources.md` — тот же
список в виде нумерованного списка ссылок Markdown.

### report.md

Продукт отчёта глубокого исследования, записывается только если поток его содержит
(`fs_writer.py:308-316`): заголовок отчёта, исходное имя файла продукта, затем полный Markdown
отчёта.

<a id="raw_entriesjson-raw_blocksjson-raw-fidelity" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json — сырая точность

Ответы API, сохранённые дословно **до** любого разбора (`fs_writer.py:257-266`):

- `raw_entries.json` — простой ответ: `{"thread_metadata", "entries", "background_entries"}`.
  Всегда присутствует.
- `raw_blocks.json` — схематизированный ответ, той же формы. Отсутствует для потоков `search`
  (нет выборки блоков); выбирается для остальных четырёх режимов, а также как запасной вариант, когда отсутствуют
  все сигналы определения режима.

Эти два файла являются якорем точности архива: разбор, рендеринг и реестры могут быть
перестроены из них офлайн, без сети. См.
[Офлайн-операции](../architecture/offline-operations.md).

<a id="assets-products-and-their-manifest" data-pplx-source-anchor="true"></a>
### assets/ — продукты и их манифест

Загружаемые продукты (файлы компьютерного режима и любые другие ресурсы, перечисленные API) извлекаются
из подписанных URL CloudFront в `assets/files/`; расширение определяется во время загрузки
по пути URL, магическим байтам содержимого или типу ресурса. `assets/assets_manifest.json`
(`fs_writer.py:320-330`) записывает каждую версию:

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` всегда **общее количество версий** (Σ `len(versions)`), а не количество групп
файлов — используйте `len(files)` для этого.

<a id="the-index-layer" data-pplx-source-anchor="true"></a>
## Слой index/

`web_archive/index/` содержит состояние и индексы, управляемые инструментом — не редактируйте вручную:

| Файл | Записывается | Семантика |
|---|---|---|
| `library_<account>.json` | `pplx-export index` (`index_cmd.py:17-43`) | полный индекс потоков аккаунта (GraphQL); входные данные для пакетных / планировщика / индексов пространств |
| `batch_state.json` | `BatchState` (`state.py`) | возобновляемая контрольная точка: uuid → статус (ok/error/expired/deleted) + lastUpdated; атомарные записи; повреждённые файлы автоматически резервируются как `.corrupt-<ts>` |
| `.cookies.json` | кэш cookie (`common.py:111`, `common.py:150`) | кэш cookie со свежестью 12 часов с источником и email аккаунта; записывается `0o600` затем атомарно заменяется (учётные данные сессии, доступно только владельцу) |
| `space_<slug>.json` | `pplx-export space-index` (`spaces_cmd.py:106-167`) | список потоков по пространству, включая отображение двойного ID `context_uuid` |
| `space_meta.json` | `pplx-export spaces --fetch-meta` (`spaces_cmd.py:299-330`) | кэш владельца/участника пространства, повторно используемый при перестройках |
| `credit_usage_<account>.json` | `pplx-export usage-backfill` (`usage_backfill_cmd.py:17`) | использование кредитов по потокам (идемпотентно, возобновляемо, сбрасывается каждые 25 записей) |
| `cron_snippet.txt` | `pplx-export schedule` (`scheduler.py:48-78`) | фрагмент вызова cron (абсолютные пути) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (`variant_log.py:76`) | центральный реестр вариантов перезаписи ответа, дедуплицированный по (thread, entry), идемпотентен |
| `logs/` | `--log-file` (`common.py:218-229`) | полные журналы DEBUG |

<a id="the-spaces-layer" data-pplx-source-anchor="true"></a>
## Слой spaces/

`pplx-export spaces` агрегирует `index/library_*.json` в индекс пространств (`spaces_cmd.py:259-389`):
один `<slug>.md` на пространство (участвующие аккаунты, заголовок владелец/участник, таблица потоков,
обратные ссылки на местоположение экспорта) плюс реестр `spaces.json`.

!!! note "Расположение вывода"
    `spaces/` записывается относительно текущего рабочего каталога (`spaces_cmd.py:332`) — он
    **не** следует за `--out`. Не редактируйте вручную: следующая перестройка перезапишет.

<a id="cross-day-continuation-directory-migration-by-uuid-identity" data-pplx-source-anchor="true"></a>
## Продолжение через несколько дней: миграция каталога по UUID-идентичности

Имя каталога содержит дату `lastUpdated`, поэтому при продолжении потока в другой день
наивное вычисление даёт *новый* каталог. Запись предотвращает дубликаты по UUID-идентичности
(`thread_dir_for`, `fs_writer.py:58-72`):

1. **Поиск**: `find_thread_dirs` (`fs_writer.py:74-105`) ищет во всём архиве
   каталоги, оканчивающиеся на `_<uuid8>` — между аккаунтами и режимами. Кандидат принимается только
   если его `thread.json` существует, разбирается, и его `web_uuid` точно совпадает; отсутствующие, повреждённые или
   несовпадающие каталоги никогда не трогаются (лучше пропустить миграцию, чем неправильно объединить).
2. **Слияние**: `_merge_into` (`fs_writer.py:107-178`) объединяет старый каталог в новый —
   объединение файлов (ничего уникального из старого каталога не теряется); одинаковое имя + одинаковое содержимое → пропуск;
   конфликты одинаковых имён **всегда сохраняют целевую сторону** (семантически более новую), каждый
   конфликт регистрируется. Каждый скопированный файл проверяется по sha256 перед удалением старого каталога; любой
   сбой оставляет старый каталог нетронутым, и повторные попытки идемпотентны.
3. **Очистка исторических дубликатов**: `consolidate_uuid` (`fs_writer.py:180-209`) объединяет
   дублирующиеся каталоги дат одного UUID в масштабе архива, сохраняя каталог с максимальным
   `lastUpdated` — подстраховка для дубликатов, оставленных старыми версиями.

Та же строгость UUID защищает обратные ссылки индекса пространств: каталоги-кандидаты с
отсутствующим/повреждённым/несовпадающим `thread.json` никогда не связываются.

<a id="hand-editable-vs-tool-managed" data-pplx-source-anchor="true"></a>
## Редактируемые вручную и управляемые инструментом

- **Управляемые инструментом (не редактировать вручную)**: всё внутри каталогов потоков, а также `index/`,
  `spaces/` и `relations/`. Если содержимое неверно, исправьте инструмент и перегенерируйте — исправления
  рендеринга проходят через `pplx-export re-render`, исправления данных через соответствующую команду обратного заполнения
  (см. [Команды обслуживания](maintenance-commands.md)) — так каждый артефакт остаётся воспроизводимым из
  сырых данных.
- **Редактируемые вручную**: документация и отчёты проверки `web_archive/crosscheck/`.
  Одно исключение на уровне пользователя: вручную сохранённый альтернативный ответ может быть записан как
  `rewritten_answer_variant.md` внутри каталога потока — см.
  [Режимы беседы — Варианты перезаписи ответа](modes.md#answer-rewrite-variants-answer_variants).

<a id="see-also" data-pplx-source-anchor="true"></a>
## См. также

- [Режимы беседы](modes.md) — пять режимов и что каждый из них создаёт
- [Инкрементальная синхронизация](incremental-sync.md) — как `lastUpdated` управляет повторными экспортами
- [Команды обслуживания](maintenance-commands.md) — перерендеринг, обратные заполнения, синхронизация удалённых
- [Модель данных и контракт каталога](../architecture/data-model.md) — базовые классы данных
- [Конвейер экспорта](../architecture/export-pipeline.md) — как эти файлы записываются
- [Офлайн-операции](../architecture/offline-operations.md) — перестройка всего из `raw_*.json`
