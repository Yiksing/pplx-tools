---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "39f85a86f94a3b326e9d3b9a74e9452a379a4745667b57c124c9512bfd1d9755"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="configuration" data-pplx-source-anchor="true"></a>
# Конфигурация

pplx-export хранит ваши идентификационные данные — реестр учетных записей (отображаемые имена, адреса электронной почты для входа, идентификаторы пользователей) и пространство BOT — в пользовательском TOML-файле, который находится вне репозитория. На этой странице описано, где находится этот файл, все поля, которые он принимает, что происходит, когда он отсутствует, и как реестр управляет обработкой файлов cookie для нескольких учетных записей.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## Почему конфигурация находится вне репозитория

Реестр учетных записей и пространство BOT являются личными данными и **никогда не фиксируются** в репозитории (`pplx_export/config.py:7-12`). Репозиторий поставляется только с шаблоном-заполнителем, `config.example.toml`; ваши реальные значения помещаются в личную копию. Все остальное, что нужно инструменту — домен сайта, URL-адреса API, корневой каталог архива по умолчанию — является константой кода (`pplx_export/config.py:50-58`), а не пользовательской конфигурацией.

TOML содержит только идентификационные данные. Выбор источника файлов cookie и транспорта осуществляется с помощью флагов командной строки при каждом вызове, а не полей конфигурации — см. раздел [Флаги CLI, а не поля конфигурации](#cli-flags-not-config-fields) ниже.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## Расположение и приоритет загрузки

`configure()` (`pplx_export/config.py:113`) определяет путь к конфигурации со следующим приоритетом (`pplx_export/config.py:95-110`):

| Приоритет | Источник | Считается явным |
|---|---|---|
| 1 | Флаг CLI `--config PATH` | да |
| 2 | Переменная окружения `PPLX_EXPORT_CONFIG` | да |
| 3 | `~/.config/pplx-export/config.toml` (путь по умолчанию) | нет |

«Явный» важен для поведения при ошибке, когда файл отсутствует — см. [режим пониженной функциональности](#missing-config-degraded-mode). Оба варианта CLI перезагружают конфигурацию в строгом режиме после разбора аргументов (`pplx_export/cli.py:223`, `pplx_export/ask_cli.py:278`); загрузка во время импорта (`pplx_export/config.py:174-179`) отказоустойчива, поэтому импорт пакета никогда не завершается ошибкой из-за отсутствующего файла.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## Создание вашей конфигурации

!!! tip "Автоматическая альтернатива"
    `pplx-export init` может создать этот файл автоматически — он обнаруживает учетные записи, выполнившие вход, из файлов cookie вашего браузера и записывает TOML с правами 0600. См. [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

Затем отредактируйте копию. Шаблон использует чистые заполнители — скопируйте структуру, замените каждое значение:

```toml
# Default account used when --account is not given (a key of [accounts.<name>] below)
default_account = "alice"

# Account registry: key = account username (the username in thread URLs / library)
[accounts.alice]
# Full display name: used for archive directory naming (web_archive/<display name>/…)
display_name = "Alice Example"
# Login email: verifies cookie ownership
email = "alice@example.com"
# Account uid (required for thread-viewed telemetry)
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT space: where threads created by pplx-ask are collected after completion
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

Стиль заполнителей: `alice`/`bob` — вымышленные имена пользователей учетных записей, адреса электронной почты используют `example.com`, а UUID — форму со всеми нулями `00000000-0000-4000-8000-…`. В вашем реальном файле ключ таблицы **должен быть фактическим именем пользователя учетной записи**, как оно отображается в URL-адресах обсуждений и вашей библиотеке.

!!! warning "Храните в секрете"
    Реальная конфигурация содержит личные данные (адреса электронной почты, идентификаторы пользователей). Рекомендуемые права доступа — `0o600`; никогда не фиксируйте ее в каком-либо git-репозитории (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## Справочник полей

<a id="top-level" data-pplx-source-anchor="true"></a>
### Верхний уровень

| Поле | Тип | Значение |
|---|---|---|
| `default_account` | строка | Ключ одной таблицы `[accounts.<name>]`, используемый, когда `--account` не указан (`pplx_export/commands/common.py:84-85`). Пусто/отсутствует = режим пониженной функциональности. |

### `[accounts.<name>]`

Одна таблица на учетную запись; `<name>` — имя пользователя учетной записи. Реестр загружается в три словаря с ключом по имени пользователя: `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Поле | Тип | Обязательно | Значение |
|---|---|---|---|
| `display_name` | строка | нет | Полное отображаемое имя, используется для именования каталогов архива (`web_archive/<display name>/…`); при отсутствии используется имя пользователя. См. [Структура архива](archive-layout.md). |
| `email` | строка | рекомендуется | Адрес электронной почты для входа. Транспорт проверяет принадлежность файлов cookie по нему, предотвращая «экспорт для учетной записи B с сессией учетной записи A» (`pplx_export/config.py:69-72`). При несовпадении инструмент перечисляет токены сессии для каждой учетной записи в браузере и переключается автоматически — см. [Модель файлов cookie для нескольких учетных записей](#multi-account-cookie-model). |
| `user_id` | строка | для телеметрии `pplx-ask` | Идентификатор учетной записи (uid), необходимый для телеметрии просмотра обсуждений (`pplx_export/config.py:73-75`). Прочитайте его из `GET /api/auth/linked-accounts`, который возвращает `user_id` / `email` / `display_name` для каждой выполнившей вход учетной записи — см. [Аутентификация API](../reference/api/api-authentication.md). |

### `[bot_space]`

Пространство BOT — это точка сбора обсуждений, созданных `pplx-ask` после их завершения (`pplx_export/config.py:76-79`). Создайте само пространство с помощью `pplx-ask space-create` (см. [pplx-ask](pplx-ask.md)), затем зарегистрируйте его здесь.

| Поле | Тип | Значение |
|---|---|---|
| `uuid` | строка | UUID пространства. `pplx-ask` перемещает завершенные обсуждения сюда (`pplx_export/ask_cli.py:156-158`); если пусто, шаг перемещения пропускается. |
| `slug` | строка | URL-слаг пространства. Загружается в `BOT_SPACE_SLUG` (`pplx_export/config.py:79`); CLI времени выполнения не читает его — его использует инструмент обслуживания фикстур, создавая из него пару для замены идентификатора (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### Флаги CLI, а не поля конфигурации

TOML не содержит настроек транспорта или файлов cookie. Они выбираются при каждом вызове:

| Аспект | Где устанавливается |
|---|---|
| Путь к файлу конфигурации | `--config PATH` или `PPLX_EXPORT_CONFIG` |
| Источник файлов cookie | `--cookies-from BROWSER` / `--cookies FILE` |
| Транспорт | `--transport cookie\|webbridge` (только `pplx-export`; по умолчанию `cookie`) |

Полный справочник флагов см. в [pplx-export](pplx-export.md).

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## Отсутствие конфигурации: режим пониженной функциональности

Если ничего не загружено, реестры на уровне модуля остаются пустыми, а `LOADED_CONFIG_PATH` равен `None` (`pplx_export/config.py:83-85`). Поведение по сценариям (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`):

| Сценарий | Поведение |
|---|---|
| Нет конфигурации по пути по умолчанию, `--account` не указан | Режим пониженной функциональности: регистрируется предупреждение, и команды выполняются с учетной записью-заполнителем (`username='default'`); проверка принадлежности электронной почты пропускается. Повседневные автономные команды не затрагиваются (`pplx_export/commands/common.py:86-90`). |
| Нет конфигурации, явный `--account` | `SystemExit` с указанием порядка поиска и ссылкой на `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| Конфигурация загружена, `--account` не зарегистрирован | `SystemExit` с указанием загруженного файла и просьбой добавить `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| Явный путь (`--config` / переменная окружения) не существует | `ConfigError` в строгом режиме (`pplx_export/config.py:140-146`). |
| Файл существует, но не удается разобрать | Всегда `ConfigError` — поврежденная конфигурация не должна незаметно деградировать (`pplx_export/config.py:147-150`). |
| `--account` опущен, конфигурация загружена | Используется `default_account` (`pplx_export/commands/common.py:84-85`). |

Что охватывают «автономные команды» и как работа в режиме пониженной функциональности взаимодействует с архивом, подробно описано в разделе [Автономные операции](../architecture/offline-operations.md).

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## Модель файлов cookie для нескольких учетных записей

Если в одном браузере выполнен вход в несколько учетных записей, хранилище содержит один сессионный файл cookie **на учетную запись**, а поле `email` конфигурации сообщает инструменту, какой из них нужен:

- Каждая выполнившая вход учетная запись имеет файл cookie `__Secure-pplx.session.<uid>` (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`); суффикс `<uid>` — это `user_id` учетной записи.
- **Активная** учетная запись — это та, чей токен в данный момент находится в `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). Переключение учетных записей = запись значения файла cookie целевой учетной записи в этот файл cookie — без необходимости в пользовательском интерфейсе браузера (`pplx_export/core/cookies/loaders.py:180-187`).
- При запуске транспорт проверяет `GET https://www.perplexity.ai/api/auth/session` и сравнивает возвращенный адрес электронной почты с `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- При несовпадении `_try_switch_account` (`pplx_export/commands/common.py:190-215`) перечисляет все токены учетных записей в браузере через `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`, отдавая предпочтение записям на поддомене `www.`), пробует каждый из них в `__Secure-next-auth.session-token` и перестраивает транспорт при первом совпадении.
- Если ни один токен не совпадает, команда завершается с указанием обоих адресов электронной почты и просьбой сначала выполнить вход в целевую учетную запись в браузере (`pplx_export/commands/common.py:142-145`) — см. [Устранение неполадок](troubleshooting.md).
- Учетная запись без зарегистрированного `email` продолжает работу без проверки, с предупреждением с просьбой самостоятельно подтвердить вход в браузер (`pplx_export/commands/common.py:146-149`).

Полный процесс переключения и семантику конечных точек сессии см. в разделах [Ask и учетные записи](../architecture/ask-and-accounts.md) и [Аутентификация API](../reference/api/api-authentication.md).

<a id="cookie-cache" data-pplx-source-anchor="true"></a>
## Кэш файлов cookie

После успешной проверки разрешенные файлы cookie кэшируются, чтобы последующие запуски пропускали браузер:

| Свойство | Значение |
|---|---|
| Путь | `<archive root>/index/.cookies.json` — следует за `--out` (`pplx_export/commands/common.py:111`) |
| Актуальность | 12 часов (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`); устаревший или поврежденный кэш считается отсутствующим |
| Содержимое | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Запись | Атомарно: временный файл создается с режимом `0o600`, затем `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Обрабатывается `.gitignore` (`**/index/.cookies.json`) |

Порядок разрешения файлов cookie (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`): явный `--cookies-from` → явный файл `--cookies` → свежий кэш → автоматическое обнаружение браузеров (edge → chrome → firefox → safari). Кэш обновляется после каждой успешной проверки учетной записи (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## Защита ваших файлов

- `chmod 600` ваш `config.toml` — он содержит личные данные (адреса электронной почты, идентификаторы пользователей).
- Кэш файлов cookie уже записывается с режимом `0o600` инструментом; сессионные файлы cookie эквивалентны учетным данным для входа.
- Если вы вручную создаете файл cookie для `--cookies`, также примените к нему `chmod 600`.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## Когда аутентификация не удается

Просроченные файлы cookie, учетная запись, которую не может найти автоматическое переключение, ошибки разрешений связки ключей браузера и другие сбои аутентификации описаны в разделе [Устранение неполадок](troubleshooting.md).
