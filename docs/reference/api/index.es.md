---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/index.md"
translation_source_sha256: "ca4f72f6b2dd481ccfbaebc2b4a1c807271077753873ce318b60d94c60f54228"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-reference" data-pplx-source-anchor="true"></a>
# Referencia de la API web

Comportamiento observado de REST y GraphQL Perplexity utilizado por `pplx-export` y
`pplx-ask`.

!!! warning "Interfaz observada, no una garantía de estabilidad"

    Estas páginas describen el comportamiento que el proyecto observó de la aplicación
    web, respuestas archivadas, paquetes frontend y la implementación actual. No
    constituyen un contrato oficial de la API de Perplexity. Las observaciones
    con fecha deben ser revalidadas antes de modificar el código que interactúa con la red.

<a id="reading-order" data-pplx-source-anchor="true"></a>
## Orden de lectura

1. [Modelo de autenticación](api-authentication.md) — cookies de sesión, tokens,
   cuentas vinculadas e identidad.
2. [GraphQL](api-graphql.md) — consultas persistentes, identificadores APQ y
   operaciones en uso.
3. [Puntos finales REST](api-rest-endpoints.md) — puntos finales observados agrupados por
   propósito.
4. [Respuestas y semántica de errores](api-responses-errors.md) — formas de respuesta,
   reglas de análisis, estados terminales y comportamiento de control de riesgos.
5. [Métodos de descubrimiento y hoja de ruta](api-discovery-roadmap.md) — cómo se
   encuentran los puntos finales y qué incertidumbres persisten.

<a id="related-implementation-documents" data-pplx-source-anchor="true"></a>
## Documentos de implementación relacionados

- [pplx-ask y cuentas](../../architecture/ask-and-accounts.md)
- [Límite de velocidad y manejo de errores](../../architecture/rate-limiting-errors.md)
- [Solución de problemas](../../guide/troubleshooting.md)
