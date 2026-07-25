---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/index.md"
translation_source_sha256: "7a016c35bbb11272395a246fd23c0c27be794585c5b1cda9fdc9c6181fe32e48"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="perplexity-cli-toolkit" data-pplx-source-anchor="true"></a>
# Kit de herramientas CLI de Perplexity

<p class="homepage-scope-note" role="note">
  <strong>NO para API de pago por uso</strong>
</p>

Perplexity archivo de conversaciones y kit de consulta interactiva (`pplx-export` / `pplx-ask`).

Se comunica directamente con la API REST/GraphQL de Perplexity usando las cookies de tu sesión iniciada en el navegador, y archiva conversaciones (pasos, citas, informes de investigación profunda, activos del modo computadora y flujos de subagentes) como Markdown + JSON local. Las exportaciones exitosas conservan las respuestas sin procesar de la API junto con los artefactos renderizados, por lo que se puede volver a renderizar sin conexión en cualquier momento.

<a id="introduction" data-pplx-source-anchor="true"></a>
## Introducción

Más allá de archivar conversaciones históricas, este proyecto tiene como objetivo principal brindar a los agentes locales (más cercanos a los datos y a menudo respaldados por más capacidad de cómputo) una medida de las capacidades de Perplexity Computer. Al permitirles acceder a informes producidos por Perplexity Deep Research directamente dentro de su bucle de trabajo, pueden usar información de alta calidad para ajustar parámetros clave en el código con mayor precisión, mientras aprovechan al máximo una suscripción existente a Perplexity Max.

> Al 20 de julio, Perplexity no ofrecía una CLI oficial para entornos tipo Unix. El 23 de julio, Perplexity lanzó públicamente la herramienta `pplx` utilizada en el modo computadora, pero esa herramienta aún utiliza facturación de pago por uso.

No es un reemplazo completo del modo computadora. Dos capacidades siguen fuera de alcance:

- la libertad de la habilidad de investigación profunda para elegir un modelo arbitrario;
- la capacidad de la habilidad Council para ejecutar investigación profunda con varios modelos especificados por el usuario, producir informes y compararlos lado a lado.

El directorio [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context) incluye indicaciones del sistema archivadas y reglas operativas que pueden ayudar a aproximar partes del flujo de trabajo de computadora localmente, incluida la selección del modo de investigación profunda y la selección del modelo de subagente.

<a id="features" data-pplx-source-anchor="true"></a>
## Características

<a id="pplx-export-archive-your-library" data-pplx-source-anchor="true"></a>
### `pplx-export` — archiva tu biblioteca

- Índice de biblioteca e índice de espacios
- Exportación de un solo hilo / por lotes con parada temprana incremental + puntos de control reanudables
- Relleno de activos y relleno de uso de crédito
- Grafo de relaciones de conversación
- Renderizado sin conexión (`re-render`, sin red)
- Fragmento de cron periódico incremental

<a id="pplx-ask-query-perplexity-from-the-shell" data-pplx-source-anchor="true"></a>
### `pplx-ask` — consulta Perplexity desde el shell

- Consultas de transmisión SSE en cuatro modos: búsqueda / investigación profunda / council / estudio
- Movimiento automático a un espacio BOT al finalizar, confirmaciones de lectura
- Archivado automático de cada hilo que crea, diseñado para que otros agentes puedan llamarlo para obtener información en tiempo real

Límites de artefactos por modo (citas / informes / activos / subagentes): consulta [Modos](guide/modes.md); principios de fidelidad de renderizado: consulta [Canalización de exportación](architecture/export-pipeline.md).

!!! nota "Procedencia de la documentación"

    La mayoría de las páginas de este sitio MkDocs se generaron o reconstruyeron a partir del código y las pruebas actuales. Algunas páginas también conservan el contexto de diseño, observaciones y decisiones de discusiones anteriores con agentes. Cuando una declaración de la documentación y la implementación difieran, considera el código y las pruebas actuales como la fuente de verdad.

<a id="where-to-next" data-pplx-source-anchor="true"></a>
## ¿Qué sigue?

- **Usa las herramientas** — sigue la [Guía de usuario](guide/index.md) orientada a tareas.
- **Comprende la implementación** — usa el [Mapa de lectura de arquitectura](architecture/index.md).
- **Trabaja con la interfaz web observada** — consulta la [Referencia de la API web](reference/api/index.md).
- **Cambia el proyecto de forma segura** — sigue la [Guía del mantenedor](development/index.md).
