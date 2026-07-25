---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/getting-started.md"
translation_source_sha256: "d98ba1f32b1e75bff7b3d51ef17e833417ecaf283996152cfa3342455b6eca7a"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="getting-started" data-pplx-source-anchor="true"></a>
# Начало работы

От свежего клона до первого локального архива: установите две команды, создайте
конфигурацию пользователя, выберите канал cookie и выполните первый экспорт.

<a id="requirements" data-pplx-source-anchor="true"></a>
## Требования

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — используется для установки инструментов и запуска тестов
- **Настольный браузер, в котором выполнен вход в Perplexity** — инструменты повторно используют его сессионные cookie;
  никакой токен никогда не хранится в конфигурации

Расшифровка cookie использует `browser_cookie3`. Автоопределение охватывает Edge, Chrome, Firefox и
Safari; Brave, Chromium, Opera и Vivaldi работают через `--cookies-from`.

<a id="install" data-pplx-source-anchor="true"></a>
## Установка

Клонирование не требуется — установка прямо из URL git:

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

Из локального клона (корень репозитория):

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

Это устанавливает две команды: `pplx-export` (архивирование) и `pplx-ask` (интерактивные
запросы). Проверьте:

```bash
pplx-export --version
pplx-export --help           # overview with examples; each subcommand has its own --help
pplx-ask --help
```

`uvx --from . pplx-export` выполняет одноразовую команду без установки.

<a id="create-the-user-level-config" data-pplx-source-anchor="true"></a>
## Создание конфигурации пользователя

Реестр учётных записей (отображаемое имя / email / user_id) и пространство BOT являются личными
данными и **не фиксируются в репозитории**; они хранятся во внешнем TOML-файле.
Шаблон: `config.example.toml` в корне репозитория.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

1. Создайте каталог конфигурации.
2. Скопируйте шаблон в путь по умолчанию.
3. `chmod 600` — файл содержит личные данные; оставьте доступ только владельцу.
4. Заполните `[accounts.<name>]` — ключом является имя пользователя учётной записи (как оно отображается
   в URL-адресах тем / библиотеке); укажите `display_name`, `email`, `user_id` и выберите
   `default_account`.
5. Заполните `[bot_space]` — куда собираются темы, созданные `pplx-ask`, после
   завершения (реальное пространство можно создать с помощью `pplx-ask space-create`).

**Автоматическая альтернатива:** `pplx-export init` создаёт этот файл за вас — он
перечисляет сессионные cookie для каждой учётной записи в вашем браузере, проверяет
`/api/auth/session` для email / отображаемого имени каждого токена, устанавливает
`default_account` на текущую активную учётную запись, сопоставляет пространство BOT по
названию и атомарно записывает TOML с правами 0600 (существующий файл
перезаписывается только с `--force`).

```bash
pplx-export init                     # discover accounts, write the default config path
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --bot-title TITLE   # match/create a different space title (default BOT)
pplx-export init --config /path/to/config.toml   # write to a custom path
```

Флаги: `--force` перезаписывает существующую конфигурацию; `--create-bot-space [TITLE]`
создаёт пространство через API, если ни одно название не совпадает (операция записи в
учётную запись; явный TITLE используется как для сопоставления, так и для создания); `--bot-title TITLE`
используется как для сопоставления, так и для создания. Обратите внимание, что для
`init` — в отличие от всех остальных команд — `--config` является **путём записи**, а не
путём загрузки. Полные сведения: [pplx-export → init](pplx-export.md#init).

Полная справка по полям находится в [Конфигурация](configuration.md).

**Приоритет загрузки** (от высшего к низшему):

| # | Источник |
|---|----------|
| 1 | `--config PATH` |
| 2 | `PPLX_EXPORT_CONFIG` переменная окружения |
| 3 | `~/.config/pplx-export/config.toml` (по умолчанию) |

!!! note "Когда конфигурация отсутствует"
    Команды без `--account` работают в урезанном режиме — проверка владения email
    пропускается с предупреждением (автономные команды не затрагиваются); явный `--account`
    вызывает ошибку, указывающую на `config.example.toml`. Когда `--account` опущен,
    используется `default_account` из конфигурации.

<a id="choose-a-cookie-channel" data-pplx-source-anchor="true"></a>
## Выбор канала cookie

Учётные данные берутся из сессионных cookie вашего локального браузера, в котором выполнен вход в Perplexity, читаемых
через `browser_cookie3` — включая перечисление токенов для нескольких учётных записей и автоматическое
переключение. Четыре канала:

| Канал | Как | Примечания |
|-------|-----|------------|
| Автоопределение (по умолчанию) | без флага | свежий кеш на 12 ч, затем хранилища браузера в порядке edge→chrome→firefox→safari |
| Именованный браузер | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| Файл cookie | `--cookies /path/to/cookies.txt` | файл cookie Netscape или экспортированный JSON |
| WebBridge | `--transport webbridge` | получение из контекста страницы — резервный канал, используется только при явном запросе |

В Linux установки браузеров snap и flatpak также определяются автоматически — их пути
профилей охвачены встроенным реестром. Полная матрица Linux (связка ключей, окружения
рабочего стола, пакеты дистрибутивов):
[Устранение неполадок → Расшифровка cookie в Linux](troubleshooting.md#linux-cookie-decryption).

```bash
pplx-export export <thread_url>                                 # default: auto-detect browser store
pplx-export export <thread_url> --cookies-from edge             # import from a specific browser
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # use a cookie file
pplx-export export <thread_url> --transport webbridge           # WebBridge page context (explicit fallback)
```

После получения cookie инструмент вызывает `/api/auth/session` и выводит текущий
email учётной записи, чтобы вы могли подтвердить, что используется правильная учётная запись — будьте внимательны, если `--account`
не совпадает с учётной записью cookie. Конструкция транспорта/учётных данных описана в
[Ask и учётные записи](../architecture/ask-and-accounts.md).

<a id="first-run" data-pplx-source-anchor="true"></a>
## Первый запуск

```bash
pplx-export index --account alice     # fetch the library index
pplx-export export <thread_url>       # export a single thread
pplx-export batch --account alice     # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run       # offline re-render, zero network
```

1. **`index`** загружает индекс библиотеки учётной записи — точка входа, на которой строятся `batch` и
   другие команды для всей учётной записи.
2. **`export`** архивирует одну тему от начала до конца: он сохраняет необработанные ответы API
   (`raw_*.json`) вместе с Markdown, чтобы рендеринг можно было воспроизвести офлайн.
3. **`batch`** обрабатывает всю библиотеку. Он останавливается рано, когда всё остальное уже
   заархивировано (инкрементальная ранняя остановка), записывает возобновляемые контрольные точки и принимает
   `--full` для полной обработки. Подробности: [Инкрементальная синхронизация](incremental-sync.md).
4. **`re-render --dry-run`** демонстрирует автономный путь: он заново генерирует `conversation.md`
   + `turns/` из локальных необработанных файлов без сети. Укажите `--dry-run` для записи
   результатов. См. [Автономные операции](../architecture/offline-operations.md).

После того как это заработает, `pplx-ask ask "<prompt>"` выполняет потоковый запрос и автоматически архивирует
полученную тему — см. [pplx-ask](pplx-ask.md).

<a id="where-archives-land" data-pplx-source-anchor="true"></a>
## Куда попадают архивы

Архивы записываются в `./web_archive/` по умолчанию (переопределяется с помощью `--out`): один
каталог на тему.

| Путь | Содержимое |
|------|------------|
| `conversation.md`, `turns/` | отрендеренный разговор |
| `thread.json` | метаданные темы + реестр прерываний |
| `sources.md` / `sources.json` | цитаты |
| `report.md` | отчёт deep-research / council / study |
| `assets/` | загруженные ресурсы (компьютерный режим) |
| `raw_*.json` | сохранённые необработанные ответы API — успешные архивы можно повторно отрендерить офлайн без повторной загрузки |

Полный контракт каталога: [Структура архива](archive-layout.md).

<a id="next-steps" data-pplx-source-anchor="true"></a>
## Следующие шаги

- Что-то пошло не так? → [Устранение неполадок](troubleshooting.md)
- Пошаговая справка по командам → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [Команды обслуживания](maintenance-commands.md)
- Пять режимов разговора → [Режимы](modes.md)
