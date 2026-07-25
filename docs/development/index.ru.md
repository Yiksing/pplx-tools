---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/index.md"
translation_source_sha256: "fc5f2fa607251be85bdc126f3701791c17d7330461b2ab49402ea485fcc961b7"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintainer-guide" data-pplx-source-anchor="true"></a>
# Руководство для мейнтейнеров

Контракты и рабочие процессы для изменения инструментов pplx без снижения точности архива или изоляции тестов.

<a id="choose-the-right-document" data-pplx-source-anchor="true"></a>
## Выберите правильный документ

- [Архитектура тестирования](testing-architecture.md) — уровни тестирования, границы доверия и гарантии, предоставляемые офлайн-снимками.
- [Практики тестирования](testing.md) — текущий инвентарь тестов и рабочий процесс для участников.
- [Фикстуры и снимки](fixtures.md) — происхождение симулированных данных, соглашения о каталогах, генерация эталонов и проверка остатков.

<a id="local-quality-loop" data-pplx-source-anchor="true"></a>
## Локальный цикл качества

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Входные данные фикстур являются детерминированными симулированными данными. Они не копируются из реальных аккаунтов, реальных ответов API, `web_archive/` или частных архивов.
