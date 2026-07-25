---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/modes.md"
translation_source_sha256: "dda1cfaf9d60ef912d922e65babafb68ec80cd1cdf046d661960d0de47ab77ff"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="conversation-modes" data-pplx-source-anchor="true"></a>
# Modos de conversación

Perplexity las conversaciones vienen en cinco modos: `search` / `deep-research` / `computer` /
`council` / `study`. El modo se detecta por hilo durante la exportación; decide qué
respuestas de la API se obtienen, qué termina en el directorio del hilo y qué
[ruta de archivo](archive-layout.md) recibe el hilo (`<account>/<mode>/…`). El modo detectado se
registra en `thread.json` (clave `mode`) y lo utiliza el filtrado de `pplx-export batch --mode`.
`pplx-ask` también puede *crear* nuevos hilos en cuatro de los cinco modos (todos excepto
`computer`); consulte [pplx-ask](pplx-ask.md).

<a id="the-five-modes-at-a-glance" data-pplx-source-anchor="true"></a>
## Los cinco modos de un vistazo

| Modo | Nombre en UI / modelo | Contenido de turno | Citas | Productos | Bloques esquematizados obtenidos |
|---|---|---|---|---|---|
| `search` | "Mejor" (`pplx_pro`; labs `STUDIO`/`pplx_beta` también se asigna aquí) | Consulta + Respuesta, pasos de texto | a nivel de turno + a nivel de hilo `sources.*` | — | No (`raw_blocks.json` ausente) |
| `deep-research` | "Deep research" (`pplx_alpha`, fijo, sin selector) | pasos de investigación incl. `RESEARCH_ANSWER` | sí | `report.md` (informe completo) | Sí |
| `computer` | Computer (`pplx_asi_opus`, `pplx_asi_opus_thinking`) | `workflow_block` completo: narración, llamadas a herramientas, indicaciones/pasos de subagente, citas por paso | por paso + turno + hilo | archivos versionados en `assets/` + ejecuciones de subagente | Sí |
| `council` | consejo de modelos (`pplx_agentic_research`; tres modelos por defecto) | paso `COUNCIL_RESEARCH`; flujo de trabajo `LLM_COUNCIL` anidado de cada modelo plegado en `<details>` (rondas de búsqueda, todas las fuentes, respuesta completa por modelo) | por modelo + agregado | respuestas por modelo comparadas lado a lado | Sí |
| `study` | Study (`pplx_study`) | pasos/citas a través de bloques (verificado que también contiene activos) | sí | activos cuando están presentes | Sí |

<a id="how-the-mode-is-decided" data-pplx-source-anchor="true"></a>
## Cómo se decide el modo

La autoridad de detección es el propio campo de la plataforma **`entry.search_mode`**
(`SEARCH_MODE_MAP`, `normalize.py:50-59`), recopilado en todas las entradas
(`normalize.py:106-115`). Se verificó contra la configuración oficial del modelo
(`GET /rest/models/config/v2`): `default_models.search=pplx_pro` (UI "Mejor"),
`default_models.research=pplx_alpha` (UI "Deep research"), y los valores se asignan uno a uno a
los modos de conversación:

| Valor de `search_mode` | Modo |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`, `STUDIO` | `search` |

Reglas de conflicto (`detect_mode`, `normalize.py:66-128`):

- **Cambio de modo dentro de un mismo hilo** (entradas en desacuerdo): tomar el de mayor especificidad —
  **computer > council > study > deep-research > search** (`_MODE_SPECIFICITY`,
  `normalize.py:63`) — y `log.warning`.
- **Conflicto con señales posteriores** (nombres de paso / `display_model`): `search_mode` gana,
  `log.warning` (`normalize.py:120-123`).
- **`search_mode` completamente ausente** → la cadena original: la URL contiene `/computer/tasks/` o
  `metadata.mode == '4'` o el modo de índice ∈ `ASI`/`COMPUTER` → `computer`; un paso `COUNCIL_RESEARCH`
  → `council`; un paso `RESEARCH_ANSWER` → `deep-research`; señal `display_model` redundante
  (`DISPLAY_MODEL_MODE`, `normalize.py:32-37`) gana en conflicto; nada coincide →
  `search` por defecto.
- **La ausencia total de señales no concluye búsqueda**: el pipeline aún obtiene los bloques
  esquematizados (`adapter.py:83-89`) para que una deriva del campo de la plataforma no pueda eliminar
  silenciosamente `raw_blocks.json`.

!!! nota "Por qué `pplx_alpha` no es una pista de detección"
    `pplx_alpha` es el modelo dedicado a RESEARCH — es el *objetivo* que el clasificador debe
    detectar, no evidencia para la detección, por lo que se excluye deliberadamente de la tabla de
    mapeo (comentario `normalize.py:15-31`).

El árbol de decisión completo con cada rama: [Pipeline de exportación — detección de modo](../architecture/export-pipeline.md).

<a id="where-sub-agent-payloads-land" data-pplx-source-anchor="true"></a>
## Dónde terminan las cargas útiles de subagentes

Las ejecuciones de Computer/council generan flujos de trabajo de subagentes en segundo plano. Cada
`workflow_payload` de fondo se renderiza en **exactamente un lugar, nunca dos**; a nivel de usuario los
tres lugares posibles de aterrizaje son:

1. **Anclado — dentro del turno iniciador**: el turno que inició el subagente lleva un
   id de carga útil coincidente, por lo que la ejecución se renderiza en línea en el proceso de trabajo de ese turno
   (`turns/turn_NNNN.md`), con indicación, pasos, respuesta y fuentes.
2. **Turno stub — sección "子代理工作" (Trabajo de subagente)**: un turno stub `subagent_result` dentro de una
   ventana de finalización de 10 segundos absorbe la carga útil; la respuesta no se rellena.
3. **Apéndice del hilo — final de `conversation.md`**: todo lo restante (las ejecuciones interrumpidas
   no producen notificación de finalización, por lo que los dos primeros niveles necesariamente fallan) se archiva
   textualmente bajo "## 后台任务（未归入轮次）" (Tareas en segundo plano (no asignadas a turnos)) — sin
   adivinación de atribución de tiempo, cualquier estado aceptado.

Reglas de coincidencia, estructuras de datos y garantías de consumo único:
[Subagentes e interrupciones](../architecture/subagents-interruptions.md).

<a id="interruptions-non-completed-workflows" data-pplx-source-anchor="true"></a>
## Interrupciones: flujos de trabajo no COMPLETADOS

Los flujos de trabajo que no se completaron se anotan en línea dondequiera que se rendericen — en encabezados
  de proceso de trabajo, encabezados de subagente y resúmenes `<details>` anidados. Las tres anotaciones
  (`parsers.classify_wf_status`, `parsers.py:263-284`):

| Anotación | Condición | Significado |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` (interrumpido por límite — el contenido se detiene en el punto de interrupción) | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | límite de gasto agotado; el flujo de trabajo se detuvo a mitad de ejecución |
| `⏸ 中断待续` (interrumpido, pendiente de continuación) | `WORKFLOW_AWAITING_NEXT_STEPS` sin `locked_reason` | interrumpido, se puede continuar en la plataforma |
| `⛔ 已取消` (cancelado) | `WORKFLOW_CANCELED` | cancelado por el usuario o la plataforma |

- `COMPLETED` nunca se anota (los hilos saludables obtienen cero diferencias); los valores de estado
  futuros desconocidos permanecen en silencio.
- Cada caso anotado también se registra en `thread.json.interruptions` como
  `{location, kind, headline, status}` — las ubicaciones se ven como `turn_0007`,
  `turn_0011/subagent`, `turn_0024/subagent_stub`, `background_unassigned`
  (`parsers.py:535-583`; clave ausente en hilos saludables).
- **La reanudación no necesita un caso especial**: cuando continúas un hilo interrumpido en la
  plataforma, su `lastUpdated` cambia, la siguiente exportación incremental lo vuelve a obtener y las
  anotaciones simplemente desaparecen una vez que el flujo de trabajo se completa. Consulte
  [Sincronización incremental](incremental-sync.md).

Valores de estado observados y distribución: [Respuestas y errores de la API](../reference/api/api-responses-errors.md);
máquina de estados: [Subagentes e interrupciones](../architecture/subagents-interruptions.md).

<a id="answer-rewrite-variants-answer_variants" data-pplx-source-anchor="true"></a>
## Variantes de reescritura de respuesta (answer_variants)

Cuando la plataforma reescribe una respuesta (experimentos A/B), la variante reemplazada es invisible en
la API — solo se devuelve la respuesta seleccionada, mientras que la hermana perdedora deja un rastro en
`entries[].side_by_side_metadata` y puede ser purgada más tarde (enlaces hermanos muertos confirmados:
403 `VIEW_THREAD_NOT_ALLOWED`). La herramienta hace observable "ocurrió una reescritura":

- **Registro**: las coincidencias de criterios restringidos se escriben en `thread.json.answer_variants`
  (`fs_writer.py:247-252`; clave ausente sin coincidencias) y se agregan al registro central
  `index/answer_variants_log.jsonl`, deduplicado por (hilo, entrada) e idempotente
  (`variant_log.py:76`).
- **Alertas**: una única línea WARNING grepeable `ANSWER_VARIANT_DETECTED` con campos completos de
  localización (thread uuid/uuid8, entry_uuid, sibling_uuid, selection_status, experiment_role) en
  cada coincidencia en línea; `re-render` vuelve a registrar fuera de línea y advierte solo cuando se agrega o cambia contenido,
  por lo que las reejecuciones en toda la biblioteca permanecen silenciosas; el resumen por lotes agrega un recuento de ⚠.
- **Re-archivado manual**: las variantes hermanas son enlaces muertos empíricamente, por lo que la respuesta
  alternativa generalmente **no se puede recuperar a través de la API**. Ante una coincidencia, confirme rápidamente la respuesta
  alternativa manualmente (UI de la plataforma, sus propios registros, capturas de pantalla); si la obtiene, regístrela como
  `rewritten_answer_variant.md` dentro del directorio del hilo. Si no,
  `thread.json.answer_variants` más el registro jsonl son el registro final trazable.

Cadena de detección y nuevo registro fuera de línea: [Operaciones fuera de línea](../architecture/offline-operations.md);
semántica de campos y evidencia de enlaces muertos: [Respuestas y errores de la API](../reference/api/api-responses-errors.md).

<a id="rendering-fidelity-principles" data-pplx-source-anchor="true"></a>
## Principios de fidelidad de renderizado

Independientemente del modo, el renderizado sigue el mismo contrato de fidelidad:

- **Respuestas completas, nunca truncadas** — el antiguo límite `[:4000]` se eliminó porque cortaba
  oraciones a la mitad (`render.py:645-647`).
- **Tablas nunca truncadas** — `WORKFLOW_ITEM_TABLE` renderiza cada fila y columna, escapando
  `|` y saltos de línea en encabezados y celdas para que la estructura Markdown sobreviva
  (`render.py:211-243`).
- **Citas completas** — tres canales de recopilación (`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`), deduplicados por URL en `sources.*`; nada citado se descarta.
- **El JSON sin procesar de la API es el límite del contenido** — todo lo renderizado proviene de
  `raw_entries.json` / `raw_blocks.json`; lo que la API no devuelve (por ejemplo, una variante de respuesta
  reemplazada) no se puede renderizar, y se muestra a través de registros en lugar de inventarse.
- **Pliegues de la UI, el archivo expande** — el detalle que la UI web oculta detrás de pliegues y clics
  (narración del flujo de trabajo de Computer y E/S de herramientas, ejecuciones por modelo de council, pasos de subagente) se
  renderiza por completo; los bloques `<details>` mantienen el esquema del documento legible sin perder
  información (`render.py:46`, `render.py:404-413`).
- **Robustez estructural** — los bloques de código se dimensionan a su contenido (`_fence_for`,
  `render.py:28-43`) para que la salida de la herramienta que contiene sus propios bloques no pueda invertir el emparejamiento, y
  los delimitadores LaTeX se normalizan a `$$` / `$` con segmentos de código protegidos
  (`normalize_math_delims`).

Cómo las respuestas sin procesar retenidas hacen que todo esto sea regenerable fuera de línea:
[Pipeline de exportación](../architecture/export-pipeline.md) y [Operaciones fuera de línea](../architecture/offline-operations.md).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Véase también

- [Estructura del archivo](archive-layout.md) — dónde terminan los archivos de cada modo
- [pplx-ask](pplx-ask.md) — creación de nuevos hilos en cada modo
- [Sincronización incremental](incremental-sync.md) — reobtención de hilos continuados
- [Pipeline de exportación](../architecture/export-pipeline.md) — árbol de decisión completo de detección de modo
- [Subagentes e interrupciones](../architecture/subagents-interruptions.md) — cascada de atribución y máquina de estados
- [Respuestas y errores de la API](../reference/api/api-responses-errors.md) — valores de campo observados
