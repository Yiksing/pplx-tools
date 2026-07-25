---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-authentication.md"
translation_source_sha256: "dc9067f0d08c997245ee548a335fc762ad0cbe986661ba0ad7f976150131dd72"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="authentication-model" data-pplx-source-anchor="true"></a>
# Modelo de autenticación

> Esta página presenta el área de referencia de la API: el registro verificado en campo del proyecto pplx_export de la API web privada de Perplexity.
> Audiencia: mantenedores y usuarios de este proyecto. Todos los endpoints fueron verificados mediante captura de red WebBridge + solicitudes directas autenticadas con cookies (julio de 2026).
> **Cualquier cambio o adición al conocimiento de la API debe sincronizarse en estas páginas** (requisito explícito del usuario).
> Última actualización: 2026-07-23
>
> El área de referencia se divide en: **1. Modelo de autenticación** (esta página) · [2. GraphQL (consultas persistentes / APQ)](api-graphql.md) · [3. Endpoints REST (agrupados por propósito)](api-rest-endpoints.md) · [4–5. Estructura de respuesta y semántica de errores](api-responses-errors.md) · [6–8. Elementos pendientes, descubrimiento de endpoints y hoja de ruta](api-discovery-roadmap.md) — para el diseño del sistema circundante, consulte el [mapa de lectura de arquitectura](../../architecture/index.md).

---

<a id="authentication-model_1" data-pplx-source-anchor="true"></a>
## Modelo de autenticación

<a id="cookie-session" data-pplx-source-anchor="true"></a>
### Sesión de cookie
- Todas las solicitudes a la API solo necesitan la cookie de sesión del navegador (no se requiere token CSRF; tanto GET como POST verificados funcionando mediante solicitudes directas).
- Cookie clave: `__Secure-next-auth.session-token` (token de sesión de la **cuenta actualmente activa**).
- Cloudflare está al frente: `cf_clearance`/`__cf_bm` están vinculados a la huella digital TLS del navegador — **las solicitudes curl simples obtienen 403**;
  la herramienta pasa con Python urllib + cookies importadas del navegador (UA disfrazado como Chrome de escritorio).

<a id="multi-account-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Multi-cuenta (descubierto el 2026-07-20)
- Cuando varias cuentas están conectadas en el mismo navegador, cada cuenta tiene su propia cookie `__Secure-pplx.session.<user_id>`
  (dominio www.perplexity.ai; el valor avanza con las respuestas).
- El valor de `__Secure-next-auth.session-token` = el valor de la cookie por cuenta de la cuenta activa.
- **Cambiar de cuenta en la web** = navegar a `https://www.perplexity.ai/?pplx_account=<user_id>`; el servidor reescribe el token activo.
- **Cambio automático del lado de la herramienta** (implementado en pplx_export): enumerar las cookies `__Secure-pplx.session.*` del navegador,
  reemplazar `__Secure-next-auth.session-token` con cada una a su vez, y sondear `/api/auth/session` hasta que el correo electrónico objetivo coincida.
- `GET /api/auth/linked-accounts` devuelve `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`,
  pero **devuelve la lista completa de cuentas solo mientras la cuenta principal está activa** (solo la cuenta actual cuando una no principal está activa) — por lo tanto, la herramienta no depende de ella.
- Ejemplos de cuentas registradas (la tabla de cuentas real reside en `config.toml` a nivel de usuario; aquí se muestran marcadores de posición):
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa` (Max);
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb` (Pro, principal).
