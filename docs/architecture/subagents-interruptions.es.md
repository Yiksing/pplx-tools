---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/subagents-interruptions.md"
translation_source_sha256: "8a27d8a0d7fb796910f5fb70f1f1dc94effcb373796124c374f0e953076f43ee"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="subagents-and-interruptions" data-pplx-source-anchor="true"></a>
# Subagentes e interrupciones

---

<a id="attribution-waterfall-deterministic-attribution-of-background-subagent-payloads" data-pplx-source-anchor="true"></a>
## Cascada de atribución (atribución determinista de cargas útiles de subagentes en segundo plano)

Cada `workflow_payload` anidado en segundo plano se renderiza exactamente en un lugar, nunca dos; aquí se fundamenta en funciones de decisión y estructuras de datos. Los tres niveles residen en `parsers.py`; el punto de montaje es
`adapter.get_thread` (adapter.py:150-157, solo computer/council):

```mermaid
flowchart TD
    BG["top-level nested workflow_payload of background_entries<br/>(_iter_top_wf_payloads, parsers.py:343<br/>top level only, no recursion — nested payloads render with their parent, preventing double counting)"]

    BG --> L1{"① main-entry anchor hit?<br/>_anchored_payload_ids (parsers.py:369)<br/>run_subagent steps of main entries<br/>carry a workflow_payload with the same id"}
    L1 -->|"yes"| R1["rendered inside the initiating turn<br/>adapter.sub_agents builds sub_map (adapter.py:207-270)<br/>render_wf_step → render_subagent (render.py:404,363)<br/>prompt=objective_chunks concatenation<br/>steps/answer/sources from plain background_entries"]
    L1 -->|"no"| L2{"② subagent_result stub-turn 10s window hit?<br/>match_stub_workflows (parsers.py:385)"}
    L2 -->|"yes"| R2["the stub turn's \"## 子代理工作\" (Subagent work) section<br/>turn.stub_wfs (models.py:131)<br/>_render_nested_wf collapsible block (render.py:46)<br/>answer not backfilled; Answer stays （无）(none)"]
    L2 -->|"no"| R3["③ thread-appendix fallback<br/>collect_unconsumed_background (parsers.py:491)<br/>conv.unconsumed_bgs (models.py:170)<br/>end of conversation.md, \"## 后台任务（未归入轮次）\"<br/>(Background tasks (unassigned to turns))<br/>render_bg_appendix (render.py:601)"]

    R1 -.-> ONE(["each payload lands in exactly one place<br/>never rendered twice"])
    R2 -.-> ONE
    R3 -.-> ONE
```

Detalles de niveles:

- **① Ancla**: `_anchored_payload_ids` usa `_iter_wf_payloads` (parsers.py:327,
  descenso recursivo) para recolectar todos los ids de carga útil ya anclados por las entradas principales. El estado real de un subagente proviene del lado de segundo plano —
  `adapter.sub_agents` llena `SubAgent.status/locked_reason` desde la entrada de segundo plano `workflow_block.status`/`locked_reason`
  (adapter.py:227-244), porque el estado del lado del ancla puede estar desactualizado
  (observado cfca382d: ancla COMPLETED mientras segundo plano CANCELED).
- **② Ventana de stub**: un turno stub = `trigger=="subagent_result"` y los bloques no contienen pasos de flujo de trabajo
  (parsers.py:422). Los candidatos son las cargas útiles de nivel superior restantes después de ①; todos los pares con `|background completion time − stub creation time| ≤ 10s`
  se emparejan de manera codiciosa en orden ascendente de diferencia temporal; el conjunto `used_cand` garantiza que **cada segundo plano se consume como máximo una vez**
  (parsers.py:452-467); un stub puede absorber múltiples agentes. El tiempo de finalización toma `payload.completed_at`,
  recurriendo al tiempo de actualización de la entrada de segundo plano cuando falta (las ejecuciones interrumpidas necesariamente no tienen notificación de finalización, parsers.py:444-446).
- **③ Apéndice**: `collect_unconsumed_background` archiva textualmente cada carga útil de nivel superior restante después de la doble exclusión de
  las ancladas de ① y las consumidas de ② (parsers.py:491-532) — las tareas de segundo plano interrumpidas
  no producen notificación de finalización de subagent_result, por lo que los dos primeros niveles necesariamente fallan; estado sin restricciones
  (AWAITING/CANCELED/COMPLETED/valores futuros). Posición fija al final de conversation.md,
  sin adivinación de atribución temporal, nada se añade a turns/ (el apéndice es a nivel de hilo, render.py:601-638).

---

<a id="interruption-semantics-state-diagram" data-pplx-source-anchor="true"></a>
## Diagrama de estados de semántica de interrupción

Fuente de verdad unificada `parsers.classify_wf_status` (parsers.py:263-284): estado del flujo de trabajo +
locked_reason → cinco clases. Tres rutas de consumo comparten el mismo resultado de clasificación; COMPLETED nunca se anota
(los hilos saludables obtienen cero diff).

```mermaid
stateDiagram-v2
    state "completed" as c1
    state "limit_interrupted" as c2
    state "awaiting" as c3
    state "canceled" as c4
    state "other (unknown value)" as c5
    state "silent: no annotation / no registration / no alert" as quiet
    state "annotation: wf_status_tag (parsers.py:294-299)" as tag
    state "render consumption: work-process headings (render.py:540-541) / subagent headings (render.py:367-368) / nested details summary (render.py:116-119)" as consume1
    state "registration consumption: thread.json.interruptions (parsers.py:535; written fs_writer.py:242-244; key absent without interruptions)" as consume2
    state "alert consumption: scan_wf_anomalies → log.warning (parsers.py:646; adapter.py:131-134)" as consume3
    state "resume overwrite: lastUpdated change → plan_incremental judges updated → incremental re-fetch (no special-case code)" as cont

    [*] --> c1 : status empty / COMPLETED / WORKFLOW_COMPLETED (parsers.py:278-279)
    [*] --> c2 : WORKFLOW_AWAITING_NEXT_STEPS + locked_reason=spending_limit_exceeded (parsers.py:280-281)
    [*] --> c3 : WORKFLOW_AWAITING_NEXT_STEPS without locked_reason
    [*] --> c4 : WORKFLOW_CANCELED (parsers.py:282-283)
    [*] --> c5 : other unknown values (parsers.py:284)

    c1 --> quiet
    c5 --> quiet : no annotation (enum uncovered; rendering undisturbed)
    c2 --> tag : ⏸ limit-interrupted (content stops at the interruption point)
    c3 --> tag : ⏸ interrupted, pending continuation
    c4 --> tag : ⛔ canceled
    tag --> consume1
    tag --> consume2
    c2 --> consume3
    c3 --> consume3
    c4 --> consume3
    c5 --> consume3
    consume2 --> cont : continued by the user after interruption
```

Fuentes de datos y distribución observada (ver [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) §5.1):

- `locked_reason` aparece en tres niveles: thread_metadata / entries / background_entries;
  el único valor observado es `spending_limit_exceeded`; `parse_turn` almacena el valor a nivel de entrada en
  `turn.metadata["locked_reason"]` (parsers.py:205-208).
- **Fuentes de estado** para puntos de anotación: a nivel de turno usa `turn.metadata["wf_status"]`
  (montado por attach_workflow_blocks, parsers.py:256); los subagentes usan el estado real del lado de segundo plano
  (`SubAgent.status`, adapter.py:257-260); las entradas del apéndice usan el estado propio de la carga útil.
- Cada entrada `thread.json.interruptions` es `{location, kind, headline, status}`;
  ubicación con forma de `turn_0007` / `turn_0011/subagent` / `turn_0024/subagent_stub` /
  `background_unassigned` (parsers.py:535-583).
- re-render `--thread-json` puede agregar/eliminar esta clave fuera de línea en el lugar (rerender_cmd.py:141-169, ver [§12](offline-operations.md)).
