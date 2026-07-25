---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/index.md"
translation_source_sha256: "4687af317a6aa8c7f17c6b758463042f3f6fa6f00ba78bc0ec76464bc1bec69b"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="user-guide" data-pplx-source-anchor="true"></a>
# Руководство пользователя

Задачно-ориентированная документация по установке, настройке и эксплуатации
`pplx-export` и `pplx-ask`.

<a id="start-here" data-pplx-source-anchor="true"></a>
## Начало работы

- [Начало работы](getting-started.md) — установка команд, инициализация
  конфигурации и запуск первого экспорта.
- [Конфигурация](configuration.md) — учетные записи, источники cookie, корневые
  каталоги вывода и настройки пространства BOT.

<a id="command-reference" data-pplx-source-anchor="true"></a>
## Справочник команд

- [pplx-export](pplx-export.md) — команды индексации, экспорта и пакетного архивирования.
- [pplx-ask](pplx-ask.md) — потоковый поиск, глубокое исследование, совет и учебные
  запросы.
- [Команды обслуживания](maintenance-commands.md) — повторный рендеринг, обратное заполнение,
  операции с отношениями и синхронизацией.

<a id="archives-and-synchronization" data-pplx-source-anchor="true"></a>
## Архивы и синхронизация

- [Структура архива](archive-layout.md) — файлы, индексы, состояние и сохраненные необработанные
  ответы.
- [Режимы беседы](modes.md) — границы артефактов для каждого поддерживаемого режима.
- [Инкрементальная синхронизация](incremental-sync.md) — досрочная остановка, контрольные точки и поведение
  возобновления.

<a id="operations" data-pplx-source-anchor="true"></a>
## Эксплуатация

- [Ограничение частоты запросов](rate-limiting.md) — безопасный темп запросов и планирование.
- [Устранение неполадок](troubleshooting.md) — частые сбои и пути восстановления.

Подробности реализации см. в
[карте чтения архитектуры](../architecture/index.md).
