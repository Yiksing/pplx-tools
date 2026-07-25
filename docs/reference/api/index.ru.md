---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/index.md"
translation_source_sha256: "ca4f72f6b2dd481ccfbaebc2b4a1c807271077753873ce318b60d94c60f54228"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-reference" data-pplx-source-anchor="true"></a>
# Справочник по веб-API

Наблюдаемое поведение Perplexity REST и GraphQL, используемое `pplx-export` и
`pplx-ask`.

!!! warning "Наблюдаемый интерфейс, а не гарантия стабильности"

    Эти страницы описывают поведение, которое проект наблюдал в веб-приложении,
    архивных ответах, фронтенд-сборках и текущей реализации. Они не являются
    официальным контрактом API Perplexity. Датированные наблюдения
    следует перепроверять перед изменением сетевого кода.

<a id="reading-order" data-pplx-source-anchor="true"></a>
## Порядок чтения

1. [Модель аутентификации](api-authentication.md) — сессионные куки, токены,
   связанные аккаунты и идентичность.
2. [GraphQL](api-graphql.md) — сохранённые запросы, идентификаторы APQ и
   используемые операции.
3. [REST-эндпоинты](api-rest-endpoints.md) — наблюдаемые эндпоинты, сгруппированные по
   назначению.
4. [Ответы и семантика ошибок](api-responses-errors.md) — структуры ответов,
   правила парсинга, конечные состояния и поведение контроля рисков.
5. [Методы обнаружения и дорожная карта](api-discovery-roadmap.md) — как находятся
   эндпоинты и какие неопределённости остаются.

<a id="related-implementation-documents" data-pplx-source-anchor="true"></a>
## Связанные документы реализации

- [pplx-ask и аккаунты](../../architecture/ask-and-accounts.md)
- [Лимитирование запросов и обработка ошибок](../../architecture/rate-limiting-errors.md)
- [Устранение неполадок](../../guide/troubleshooting.md)
