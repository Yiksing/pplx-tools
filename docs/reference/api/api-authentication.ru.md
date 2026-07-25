---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-authentication.md"
translation_source_sha256: "dc9067f0d08c997245ee548a335fc762ad0cbe986661ba0ad7f976150131dd72"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="authentication-model" data-pplx-source-anchor="true"></a>
# Модель аутентификации

> Эта страница представляет справочную область API — проверенную на практике запись частного веб-API Perplexity в проекте pplx_export.
> Аудитория: сопровождающие и пользователи этого проекта. Все конечные точки были проверены с помощью захвата сети WebBridge + прямых запросов с аутентификацией по cookie (2026-07).
> **Любые изменения или дополнения к знаниям об API должны быть синхронизированы с этими страницами** (явное требование пользователя).
> Последнее обновление: 2026-07-23
>
> Справочная область разделена на: **1. Модель аутентификации** (эта страница) · [2. GraphQL (постоянные запросы / APQ)](api-graphql.md) · [3. REST-конечные точки (сгруппированы по назначению)](api-rest-endpoints.md) · [4–5. Структура ответов и семантика ошибок](api-responses-errors.md) · [6–8. Пункты TBD, обнаружение конечных точек и дорожная карта](api-discovery-roadmap.md) — для общего описания системы см. [карту чтения архитектуры](../../architecture/index.md).

---

<a id="authentication-model_1" data-pplx-source-anchor="true"></a>
## Модель аутентификации

<a id="cookie-session" data-pplx-source-anchor="true"></a>
### Сессия на основе cookie
- Все запросы к API требуют только cookie сессии браузера (токен CSRF не требуется; как GET, так и POST проверены и работают через прямые запросы).
- Ключевая cookie: `__Secure-next-auth.session-token` (токен сессии **текущей активной учётной записи**).
- Cloudflare находится перед сервером: `cf_clearance`/`__cf_bm` привязаны к TLS-отпечатку браузера — **простые запросы curl получают 403**;
  инструмент работает с Python urllib + cookie, импортированными из браузера (UA замаскирован под настольный Chrome).

<a id="multi-account-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Мультиаккаунт (обнаружено 2026-07-20)
- Когда в один браузер выполнен вход с несколькими учётными записями, каждая учётная запись имеет свою собственную cookie `__Secure-pplx.session.<user_id>`
  (домен www.perplexity.ai; значение обновляется с каждым ответом).
- Значение `__Secure-next-auth.session-token` = значение cookie активной учётной записи.
- **Переключение учётных записей в веб-интерфейсе** = переход на `https://www.perplexity.ai/?pplx_account=<user_id>`; сервер перезаписывает активный токен.
- **Автоматическое переключение на стороне инструмента** (реализовано в pplx_export): перечисление cookie `__Secure-pplx.session.*` браузера,
  замена `__Secure-next-auth.session-token` на каждую по очереди и проверка `/api/auth/session` до совпадения целевого email.
- `GET /api/auth/linked-accounts` возвращает `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`,
  но **возвращает полный список учётных записей только когда активна основная учётная запись** (только текущую учётную запись, когда активна не основная) — поэтому инструмент на него не полагается.
- Примеры зарегистрированных учётных записей (реальная таблица учётных записей находится в `config.toml` на уровне пользователя; здесь показаны заполнители):
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa` (Max);
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb` (Pro, основная).
