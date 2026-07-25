---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/index.md"
translation_source_sha256: "a64006f8b94ad04a3bc498468e674f3b8a22f27242c9bb7b8c5a9252019cc751"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="architecture-reading-map" data-pplx-source-anchor="true"></a>
# Карта чтения архитектуры

Справочник на уровне механизмов для инструментов pplx (`pplx-export` / `pplx-ask`):
зависимости, конвейеры, конечные автоматы, контракты данных и границы
надежности. Для использования, ориентированного на задачи, начните с [Руководства пользователя](../guide/index.md).

!!! note "Область применения и источник истины"

    Эти страницы объясняют архитектуру `pplx_export/` для агентов и
    инженеров, поддерживающих проект. Ссылки на строки используют `file.py:NN`,
    относительно `pplx_export/`. Описания были проверены по репозиторию
    на 2026-07-23 (`__version__ = "0.1.0"`,
    `pplx_export/__init__.py:31`); текущий код и тесты остаются авторитетными.

<a id="start-with-the-system-map" data-pplx-source-anchor="true"></a>
## Начните с карты системы

- [Обзор архитектуры](overview.md) — уровни, обязанности модулей и
  граф зависимостей на уровне импорта.

<a id="follow-a-runtime-flow" data-pplx-source-anchor="true"></a>
## Проследите поток выполнения

- [Конвейер экспорта](export-pipeline.md) — получение, сохранение необработанных ответов,
  определение режима и рендеринг Markdown.
- [Под-агенты и прерывания](subagents-interruptions.md) — атрибуция
  полезной нагрузки и семантика прерывания/возобновления.
- [pplx-ask и учетные записи](ask-and-accounts.md) — потоковые запросы и
  переключение куки для нескольких учетных записей.

<a id="understand-data-and-reliability" data-pplx-source-anchor="true"></a>
## Понимание данных и надежности

- [Модель данных и контракт каталога](data-model.md) — модели, границы
  записи и контракт архива на диске.
- [Ограничение скорости и обработка ошибок](rate-limiting-errors.md) — троттлинг,
  откат, терминальные состояния и маршрутизация ошибок.
- [Автономные операции](offline-operations.md) — повторный рендеринг без сети,
  перестроение связей и локальные конвейеры обслуживания.

<a id="related-references" data-pplx-source-anchor="true"></a>
## Связанные ссылки

- [Справочник веб-API](../reference/api/index.md) — наблюдаемые контракты REST/GraphQL,
  семантика ответов и заметки об обнаружении.
- [Руководство сопровождающего](../development/index.md) — архитектура тестов, рабочий процесс
  участника и контракты симулированных фикстур.
