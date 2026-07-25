---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-responses-errors.md"
translation_source_sha256: "4a9de23e2a900f4922480decf1b89d417310b94ce8116649dd2b2dd5c77b6bde"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-response-structure-and-error-semantics" data-pplx-source-anchor="true"></a>
# Estructura de la respuesta de la API y semántica de errores

*Parte de la referencia de la API web de Perplexity — mapa completo en el [índice de la API](index.md).*

<a id="response-structure-essentials-parsing-discipline" data-pplx-source-anchor="true"></a>
## Aspectos esenciales de la estructura de la respuesta (disciplina de análisis)

- **Datos sin procesar conservados en archivos exitosos**: `raw_entries.json` (sin formato) y
  `raw_blocks.json` (esquematizados, cuando se obtienen) se almacenan junto con los artefactos
  renderizados; el análisis/renderización se puede volver a ejecutar sin conexión (`pplx-export re-render`)
  sin necesidad de volver a obtenerlos.
- **Extracción de campos centralizada** en `sites/perplexity/parsers.py` (la desviación del esquema solo necesita cambiar un lugar).
- Detección de modo (`normalize.detect_mode`; árbol de decisión en [export-pipeline.md](../../architecture/export-pipeline.md)): la señal de mayor prioridad es el
  campo **`search_mode`** de cualquier entrada (mapeo al final de [§3.9](api-rest-endpoints.md)); cuando todas las señales fallan, se recurre a — computer = URL
  `/computer/tasks/` o metadata.mode=="4" o modo de índice ∈ {ASI,COMPUTER}; council = existe un paso
  COUNCIL_RESEARCH; deep-research = existe un paso RESEARCH_ANSWER (basado en contenido, sin depender de etiquetas en chino);
  de lo contrario, search.
- La interfaz de usuario de computer colapsa todo — **siempre guíese por las entradas/bloques de la API**; nunca use el texto de la interfaz de usuario como límite del contenido.
- Canal dual de subagente (descubierto el 2026-07-19): indicación en `workflow_payload.objective_chunks` esquematizado;
  pasos/conclusión en `background_entries` sin formato; vinculados a través de `workflow_payload.id` (`toolu_X`).
- Los elementos de `WORKFLOW_ITEM_SOURCES` a menudo llevan `text_payload`
  (texto de extracción de página del subagente / tablas de comparación; 450 ocurrencias en toda la biblioteca, 408 dentro de cargas útiles anidadas de fondo)
  además de `sources_payload.sources` (lista de enlaces);
  el mismo contenido aparece tanto en el `text` JSON de paso incrustado de la entrada de fondo sin formato como en la carga útil anidada esquematizada —
  los subagentes anclados renderizados a través de la ruta sin formato ya conservan el texto (verificación en toda la biblioteca 2026-07-22: 408/408 presentes, ninguno faltante).
- **`related_queries` / `related_query_items` (resuelto 2026-07-23)**: cada entrada lleva
  **recomendaciones de indicaciones para la siguiente pregunta** — sugerencias de seguimiento que la plataforma genera para una respuesta completada; `related_queries` es una matriz de textos de recomendación,
  `related_query_items` los elementos estructurados (uuid/upsell_type, etc.). Conclusión forense: el uuid de un elemento
  **no es un uuid de hilo** (0/988 coincidencias cruzadas con uuids de hilo de la biblioteca), y los textos de recomendación no tienen superposición con las consultas de otros hilos —
  **no se puede resolver en relaciones entre hilos por ahora**; la hipótesis de "uuids de hilo preasignados (materializados al hacer clic)" sigue sin verificarse.
  Los datos se conservan naturalmente en el archivo `raw_entries.json` (aciertos en más de la mitad de los hilos de una biblioteca de archivo); no se necesita ninguna acción de recolección adicional;
  el gráfico de relaciones no construye aristas a partir de esto.

<a id="error-and-risk-control-semantics" data-pplx-source-anchor="true"></a>
## Semántica de errores y control de riesgos

| Síntoma | Significado / manejo |
|---|---|
| 403 (con página de desafío cf) | Bloqueo de Cloudflare (huella TLS / control de tasa) — retroceder; urllib + cookies del navegador generalmente no lo desencadenan |
| 401 / 403 a nivel de API (sin página de desafío cf) | Cookie de sesión caducada/inválida — la herramienta se activa inmediatamente, sin retroceso; el lote falla rápidamente después de 3 fallos de autenticación consecutivos (actualizar la cookie) |
| 429 | Limitación de tasa — retroceso exponencial (implementado en la herramienta) |
| 5xx (500/502/503/504) | Errores transitorios del servidor (504 comúnmente un tiempo de espera de Cloudflare) — retroceder y reintentar (implementado en la herramienta) |
| ENTRY_EXPIRED | Purgado por la plataforma (~3 meses) — terminal, no reintentar |
| ENTRY_DELETED | Eliminado por el usuario/remoto (también HTTP 400, código diferente) — terminal `deleted`, no reintentar |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED` (HTTP 200) | La cuenta actual no puede ver el espacio — reintentar con una cuenta que pueda |
| `error_code: VIEW_THREAD_NOT_ALLOWED` (HTTP 403) | La cuenta actual no puede ver el hilo (probado 2026-07-23: sondeo de uuid variante hermano; el objeto existe pero es inaccesible, no "inexistente") |
| `status:"failed"` datos vacíos | Misma clase (la forma de fallo de get_collection) |

**Disciplina de límite de tasa (anti-bloqueo, requisito explícito del usuario)**: aleatorio 10–20 s entre hilos de lote, sin concurrencia, retroceso 429/403, retroceso-reintento 5xx;
paginación ≥3 s; recuperación esquematizada ≥4 s; recuperación de metadatos del espacio ≥3 s. Exportación de un solo hilo = 1–2 solicitudes ≈ abrir la página una vez.

<a id="interruption-semantics-observed-values-2026-07-22-classification-source-of-truth-parsersclassify_wf_status" data-pplx-source-anchor="true"></a>
### Semántica de interrupción — valores observados (2026-07-22; fuente de verdad de clasificación: `parsers.classify_wf_status`)

El campo `locked_reason`: aparece en `thread_metadata` / `entries[]` / `background_entries[]`
(tanto en el lado sin formato como en el esquematizado). Único valor observado:

| locked_reason | Significado | Distribución observada |
|---|---|---|
| `spending_limit_exceeded` | interrupción por límite de gasto (cuota agotada; el flujo de trabajo se detiene en el punto de interrupción) | exactamente un hilo en toda la biblioteca (marcadores tanto en raw_entries como en raw_blocks) |

Campo de estado del flujo de trabajo (`workflow_block.status` y `workflow_payload.status` anidado comparten la misma enumeración) valores observados:

| estado | Semántica | Anotación de renderizado (COMPLETED no tiene ninguna) |
|---|---|---|
| `WORKFLOW_COMPLETED` | finalización normal | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | esperando los siguientes pasos; con `locked_reason=spending_limit_exceeded` es una **interrupción por límite de gasto** (el contenido se detiene en el punto de interrupción); sin locked_reason, interrumpido pendiente de continuación | `⏸ 限额中断（内容截至中断点）` (⏸ interrumpido por límite — el contenido se detiene en el punto de interrupción) / `⏸ 中断待续` (⏸ interrumpido, pendiente de continuación) |
| `WORKFLOW_CANCELED` | cancelado (aborto del usuario/plataforma) | `⛔ 已取消` (⛔ cancelado) |

- `WORKFLOW_CANCELED` observado 19 veces (16 principales + 3 anidadas), en 7 hilos de computer
  (a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff).
- Nota: el estado de la carga útil del ancla de la entrada principal puede retrasarse (se observó ancla COMPLETED mientras que el fondo estaba realmente CANCELED) —
  el verdadero estado de un subagente es el `workflow_block.status` del lado del fondo.
- Las tareas de fondo interrumpidas no producen una notificación de finalización de subagent_result; las cargas útiles de fondo no consumidas vuelven al apéndice del hilo
  (consulte "cascada de atribución" en [subagents-interruptions.md](../../architecture/subagents-interruptions.md)).
- Respuestas vacías en modo computer (doble verificado 2026-07, irrecuperable): en modo computer, algunos turnos tienen una
  respuesta vacía porque el servidor simplemente no tiene ninguna — una recuperación de API devuelve datos idénticos al archivo, y
  expandir la barra de "N pasos completados" de la interfaz de usuario desencadena cero solicitudes de datos (renderizado puro del lado del cliente; la interfaz de usuario y
  la API comparten una fuente), por lo que la API no puede recuperarlos. Solo un subconjunto de dichos turnos está vinculado a
  `locked_reason=spending_limit_exceeded`; el resto no lleva ningún marcador del lado del servidor.

<a id="side_by_side_metadata-answer-rewrite-variant-signal-settled-2026-07-23" data-pplx-source-anchor="true"></a>
### `side_by_side_metadata`: señal de variante de reescritura de respuesta (resuelto 2026-07-23)

Ruta del campo: `entries[].side_by_side_metadata` (respuesta `/rest/thread/<uuid>` sin formato).
Cuando la plataforma genera múltiples versiones de respuesta para la misma consulta (experimento A/B o reescritura), esta es la
única traza que queda en la entrada activa actual — **el cuerpo de la variante reemplazada (texto/pasos/citas) no está en la respuesta de la API del hilo** (caso real
b2d2632b: la respuesta tiene solo 1 entrada, 1 FINAL; la variante 2 completamente invisible).

Claves y valores observados (evidencia: b2d2632b sin procesar; escaneo de toda la biblioteca de 2442 entradas):

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| Clave | Semántica (observada/hipotetizada) |
|---|---|
| `sibling_uuid` | Apunta a la **variante de respuesta hermana** de la misma consulta (otro identificador de entrada/contexto). 7 hilos acertaron en toda la biblioteca; **la investigación forense en línea (2026-07-23) confirma un enlace muerto**: las `GET /rest/thread/<sibling_uuid>` de ambas cuentas devuelven 403 `VIEW_THREAD_NOT_ALLOWED` (no 404/ENTRY_EXPIRED — el servidor lo reconoce como un objeto existente pero no visible), y abrir `/search/<sibling_uuid>` en el navegador (cuenta del propietario) es redirigido por SPA de vuelta al inicio — las variantes reemplazadas no se pueden recuperar a través de sibling_uuid |
| `selection_status` | `SELECTED` = la respuesta de esta entrada es la versión elegida para mostrar; las instancias del grupo de control son todas `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | Rol del experimento. El grupo de control lleva un prefijo `[control]` (6 casos en toda la biblioteca: `[control]default-model-class:gpt41`, etc.); el caso real no tiene prefijo (`override-default-model-class:qwen3_instruct-01f7f`, es decir, el grupo de tratamiento de un experimento de anulación de modelo) |
| `experiment_override` | Parámetros de anulación del experimento (por ejemplo, `override-default-model-class: qwen3_instruct`); observado solo en instancias del grupo de tratamiento |
| `execution_log` | Observado como un objeto vacío; semántica desconocida |

**Criterios de estrechamiento** (distinguir "reescritura genuina que mantiene ambas versiones" de "control A/B rutinario"):
`sibling_uuid` no vacío Y (`selection_status` no vacío y no `SELECTION_STATUS_UNSPECIFIED`,
O `experiment_role` sin el prefijo `[control]`) → **solo b2d2632b acierta** entre las 2442 entradas de toda la biblioteca
(el único caso real confirmado; precisión/recuperación son ambos 1 en esta biblioteca, pero n=1 no se puede extrapolar).

Comportamiento de la herramienta: `parsers.collect_answer_variants` extrae aciertos; `adapter.get_thread`
registra una advertencia + escribe `thread.json.answer_variants` (clave ausente cuando no hay aciertos);
`re-render --thread-json` agrega/elimina en el lugar (idempotente). Evidencia de tiempo: el delta de `created→updated` de la entrada del caso real
es 53.66 s (generado a las 17:13, luego reescrito/seleccionado), y la reescritura avanzó el `lastUpdated` a nivel de hilo (una reexportación incremental
puede desencadenar una recuperación, pero la respuesta recuperada aún contiene solo la respuesta activa; las variantes antiguas son irrecuperables).

**Registro de detección y flujo de manejo (2026-07-23, `sites/perplexity/variant_log.py`)**:

- **Marcador de registro**: cada acierto emite una sola línea WARNING con el marcador greppable uniforme `ANSWER_VARIANT_DETECTED`,
  incluyendo todos los campos de localización y orientación de manejo, con forma:
  `ANSWER_VARIANT_DETECTED thread=<full uuid> uuid8=<8 chars> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | action: …`
  La ruta en línea (`adapter.get_thread`) genera en cada acierto de recuperación real; `re-render` sin conexión
  **genera solo cuando se agrega/cambia contenido registrado** (las ejecuciones idempotentes repetidas no saturan); `batch` también pasa un recordatorio
  de recuento de aciertos de una línea al final del resumen (sin romper el formato de resumen existente).
- **Registro central**: `<out>/index/answer_variants_log.jsonl` (**un archivo verificado**, no bajo el
  `logs/` ignorado por git) — un JSON por línea (detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role), deduplicado por (web_uuid, entry_uuid); las exportaciones/rerenderizaciones repetidas no se agregan sin fin;
  detected_at mantiene la hora de la primera vista.
- **Acción recomendada ante un acierto**: los hermanos son empíricamente enlaces muertos (consulte la tabla anterior); la respuesta alternativa generalmente
  **no se puede recuperar a través de la API** — confirme manualmente de inmediato si la respuesta alternativa aún se puede obtener (conversación de la plataforma / memoria del usuario / capturas de pantalla); si se puede obtener,
  regístrela manualmente como un archivo `rewritten_answer_variant.md` en el directorio del hilo; si no, `thread.json.answer_variants` +
  el registro jsonl sirven como el registro final trazable.
