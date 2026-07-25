---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/index.md"
translation_source_sha256: "a64006f8b94ad04a3bc498468e674f3b8a22f27242c9bb7b8c5a9252019cc751"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="architecture-reading-map" data-pplx-source-anchor="true"></a>
# Mapa de lectura de arquitectura

Referencia a nivel de mecanismo para las herramientas pplx (`pplx-export` / `pplx-ask`):
dependencias, tuberías, máquinas de estado, contratos de datos y límites
de confiabilidad. Para uso orientado a tareas, comience con la [Guía de usuario](../guide/index.md).

!!! note "Alcance y fuente de verdad"

    Estas páginas explican la arquitectura de `pplx_export/` para agentes e
    ingenieros que mantienen el proyecto. Las referencias de línea usan `file.py:NN`,
    relativas a `pplx_export/`. Las descripciones se verificaron contra el
    repositorio el 2026-07-23 (`__version__ = "0.1.0"`,
    `pplx_export/__init__.py:31`); el código y las pruebas actuales siguen siendo autoritativos.

<a id="start-with-the-system-map" data-pplx-source-anchor="true"></a>
## Comience con el mapa del sistema

- [Visión general de la arquitectura](overview.md) — capas, responsabilidades de los módulos y
  el gráfico de dependencias a nivel de importación.

<a id="follow-a-runtime-flow" data-pplx-source-anchor="true"></a>
## Siga un flujo de ejecución

- [Tubería de exportación](export-pipeline.md) — obtención, retención de respuestas sin procesar,
  detección de modo y renderizado Markdown.
- [Subagentes e interrupciones](subagents-interruptions.md) — atribución de
  carga útil y semántica de interrupción/reanudación.
- [pplx-ask y cuentas](ask-and-accounts.md) — consultas en streaming y
  cambio de cookies entre cuentas múltiples.

<a id="understand-data-and-reliability" data-pplx-source-anchor="true"></a>
## Comprenda los datos y la confiabilidad

- [Modelo de datos y contrato de directorio](data-model.md) — modelos, límites
  de escritura y el contrato de archivo en disco.
- [Límite de velocidad y manejo de errores](rate-limiting-errors.md) — limitación,
  retroceso, estados terminales y enrutamiento de errores.
- [Operaciones sin conexión](offline-operations.md) — re-renderizado sin red,
  reconstrucción de relaciones y tuberías de mantenimiento local.

<a id="related-references" data-pplx-source-anchor="true"></a>
## Referencias relacionadas

- [Referencia de API web](../reference/api/index.md) — contratos REST/GraphQL observados,
  semántica de respuestas y notas de descubrimiento.
- [Guía del mantenedor](../development/index.md) — arquitectura de pruebas, flujo de trabajo
  del colaborador y contratos de fixtures simulados.
