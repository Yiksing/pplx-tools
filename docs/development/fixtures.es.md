---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/fixtures.md"
translation_source_sha256: "72f6f6faa0f4c2ef3a63b3f0a7c6bc0a16f9be6cb03225850e4d5d4b22193b30"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="test-fixtures" data-pplx-source-anchor="true"></a>
# Accesorios de prueba

`tests/fixtures/` contiene **datos simulados** deterministas con forma de API para el
[conjunto de pruebas](testing.md). Las entradas modelan estructuras representativas de hilos y flujos de trabajo;
sus productos renderizados se confirman como instantáneas doradas.

<a id="source-contract" data-pplx-source-anchor="true"></a>
## Contrato de fuente

<!-- audit:contract fixture-source=simulated -->

El contenido actual de los accesorios confirmados es simulado:

- Los accesorios nuevos o actualizados deben construirse como datos simulados; los contribuyentes
  no deben poblarlos importando `web_archive/`, datos de cuentas de usuario, respuestas
  de API en vivo o archivos privados.
- Los nombres, identidades, identificadores, indicaciones, respuestas, cargas útiles de flujo de trabajo, rutas
  y URL en los archivos confirmados son marcadores de posición de prueba.
- El JSON refleja los esquemas de respuesta y archivo de producción solo para ejercitar
  el comportamiento del analizador, renderizador, estado y relaciones.
- El repositorio no confirma un mapeo inverso de marcadores de posición a
  identificadores privados.

Los términos **accesorio de modo completo** y **accesorio de escenario reducido** describen la cobertura
  de prueba y la forma de entrada, no la procedencia. Ambos son datos simulados.

<a id="directory-contract" data-pplx-source-anchor="true"></a>
## Contrato de directorio

Cada directorio de accesorio contiene entradas simuladas con forma de respuesta sin procesar y,
donde se necesita comparación de instantáneas, un árbol `golden/`:

| Ruta | Función |
|---|---|
| `raw_entries.json` | entradas de hilo simuladas en la forma de respuesta de producción |
| `raw_blocks.json` | bloques de flujo de trabajo simulados; ausente cuando el modo no tiene respuesta de bloque |
| `thread.json` | metadatos de hilo archivado simulados |
| `golden/conversation.md` + `golden/turns/turn_*.md` | productos generados a partir de las entradas simuladas y comparados byte por byte |

Las convenciones deterministas actuales incluyen:

- cuentas de marcador de posición `alice` / `bob`, identidades de ejemplo, un espacio BOT
  de marcador de posición y un `read_write_token` fijo de marcador de posición;
- identificadores derivados de uuid5 etiquetados con `5cbeef00`, preservando referencias
  cruzadas intencionales entre registros simulados;
- identificadores `toolu_` simulados de longitud fija etiquetados con `5crub0`;
- indicaciones, títulos, texto de flujo de trabajo y rutas de archivo genéricos; y
- cadenas de consulta de URL firmadas eliminadas.

Estas convenciones hacen que los residuos accidentales específicos del entorno sean fáciles de detectar;
no implican que los identificadores simulados se derivaron de objetos
en vivo.

<a id="inventory" data-pplx-source-anchor="true"></a>
## Inventario

<!-- audit:inventory fixture-directories -->

<a id="full-mode-fixtures" data-pplx-source-anchor="true"></a>
### Accesorios de modo completo

Estas son conversaciones simuladas completas para cada modo compatible:

| Accesorio | Cobertura |
|---|---|
| `search_demo` | búsqueda, un turno; bloque de código R y código en línea |
| `deep_research_demo` | investigación profunda; conversión de delimitadores matemáticos de extremo a extremo |
| `computer_demo` | computer, renderizado de flujo de trabajo de siete turnos |
| `council_demo` | renderizado del comité de modelo council con una carga útil anidada grande |
| `study_demo` | renderizado del modo de estudio |

<a id="reduced-scenario-fixtures" data-pplx-source-anchor="true"></a>
### Accesorios de escenario reducido

Estas son cargas útiles simuladas enfocadas que contienen solo las entradas y
relaciones necesarias para una regresión. “Reducido” no significa extraído de un
hilo real.

| Accesorio | Cobertura |
|---|---|
| `scenario_computer_answer_fallback` | recuperar la respuesta de un bloque de flujo de trabajo esquematizado cuando la ruta FINAL simple no está disponible |
| `scenario_subagent_fallback` | renderizar un titular de subagente y sus propios elementos cuando no existe una coincidencia de fondo |
| `scenario_user_response` | renderizado de pregunta/respuesta `WORKFLOW_ITEM_USER_RESPONSE` |
| `scenario_subagent_stub` | ventana de asociación de diez segundos para un stub de resultado de subagente no anclado |
| `scenario_workflow_item_nested` | renderizado de bloque colapsado `WORKFLOW_ITEM_WORKFLOW` anidado |
| `scenario_limit_interrupted` | interrupción de límite de gasto, cascada de atribución, colocación de apéndice y sin doble renderizado |
| `scenario_canceled` | anotación `WORKFLOW_CANCELED` |

<!-- /audit:inventory fixture-directories -->

<a id="maintaining-fixtures" data-pplx-source-anchor="true"></a>
## Mantenimiento de accesorios

`tests/scrub_fixtures.py` normaliza los datos simulados, regenera los productos
dorados a través del renderizador de producción fuera de línea y aplica una compuerta de residuos:

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **Regeneración** — cada accesorio se renderiza en un directorio temporal a través de
  `pplx_export.commands.rerender_cmd.rerender`; las discrepancias en el recuento de turnos abortan.
- **Normalización determinista** — el texto de marcador de posición, los UUID, los valores `toolu_`,
  los tokens y las URL firmadas se normalizan idempotentemente.
- **Las entradas de seguridad no son procedencia** — la `tests/scrub_pairs.local.json` local opcional
  y la configuración de cuenta a nivel de usuario solo extienden
  los reemplazos y las comprobaciones de residuos. No deben usarse como entradas para
  construir escenarios de accesorios.
- **Modo de verificación** — `--check` no realiza escrituras y falla en residuos configurados,
  rutas absolutas locales o credenciales de URL firmadas.

Ejecute la herramienta de mantenimiento después de cambiar el JSON de entrada simulado o la salida del renderizador,
y ejecute `--check` antes de confirmar cambios en los accesorios.

<a id="golden-snapshot-authority" data-pplx-source-anchor="true"></a>
## Autoridad de instantánea dorada

El JSON simulado confirmado es la autoridad de entrada. El Markdown dorado es la salida
derivada: se regenera a partir de ese JSON con la ruta de re-renderizado de producción actual
y luego se confirma para la comparación de regresión a nivel de byte. No debe editarse
como una fuente de verdad independiente.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Véase también

- [Pruebas](testing.md) — cómo el conjunto consume los accesorios
- [Arquitectura del sistema de prueba](testing-architecture.md) — capas
  de regresión y garantías
- `tests/fixtures/README.md` — inventario de accesorios local del repositorio
