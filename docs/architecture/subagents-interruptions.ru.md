---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/subagents-interruptions.md"
translation_source_sha256: "8a27d8a0d7fb796910f5fb70f1f1dc94effcb373796124c374f0e953076f43ee"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="subagents-and-interruptions" data-pplx-source-anchor="true"></a>
# Под-агенты и прерывания

---

<a id="attribution-waterfall-deterministic-attribution-of-background-subagent-payloads" data-pplx-source-anchor="true"></a>
## Водопад атрибуции (детерминированная атрибуция полезных нагрузок фоновых под-агентов)

Каждый фоновый вложенный `workflow_payload` отображается ровно в одном месте, никогда не дважды; здесь он обоснован в функциях принятия решений и структурах данных. Все три уровня находятся в `parsers.py`; точка монтирования —
`adapter.get_thread` (adapter.py:150-157, только computer/council):

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

Детали уровней:

- **① Якорь**: `_anchored_payload_ids` использует `_iter_wf_payloads` (parsers.py:327,
  рекурсивный спуск) для сбора всех идентификаторов полезных нагрузок, уже закрепленных основными записями. Истинный статус под-агента поступает с фоновой стороны —
  `adapter.sub_agents` заполняет `SubAgent.status/locked_reason` из фоновой записи `workflow_block.status`/`locked_reason`
  (adapter.py:227-244), потому что статус со стороны якоря может отставать
  (наблюдалось cfca382d: якорь COMPLETED, а фон CANCELED).
- **② Окно заглушек**: оборот заглушки = `trigger=="subagent_result"`, и блоки не содержат шагов рабочего процесса
  (parsers.py:422). Кандидаты — это полезные нагрузки верхнего уровня, оставшиеся после ①; все пары с `|background completion time − stub creation time| ≤ 10s`
  жадно сопоставляются в порядке возрастания разницы времени; набор `used_cand` гарантирует, что **каждый фон потребляется не более одного раза**
  (parsers.py:452-467); одна заглушка может поглотить несколько агентов. Время завершения берется из `payload.completed_at`,
  с возвратом к времени обновления фоновой записи, если оно отсутствует (прерванные запуски не имеют уведомления о завершении, parsers.py:444-446).
- **③ Приложение**: `collect_unconsumed_background` архивирует дословно каждую оставшуюся полезную нагрузку верхнего уровня после двойного исключения
  закрепленных в ① и потребленных в ② (parsers.py:491-532) — прерванные фоновые задачи
  не генерируют уведомление о завершении subagent_result, поэтому первые два уровня обязательно пропускают их; статус не ограничен
  (AWAITING/CANCELED/COMPLETED/будущие значения). Позиция фиксирована в конце conversation.md,
  никаких догадок по временной атрибуции, ничего не добавляется в turns/ (приложение находится на уровне потока, render.py:601-638).

---

<a id="interruption-semantics-state-diagram" data-pplx-source-anchor="true"></a>
## Диаграмма состояний семантики прерываний

Единый источник истины `parsers.classify_wf_status` (parsers.py:263-284): статус рабочего процесса +
locked_reason → пять классов. Три пути потребления используют один и тот же результат классификации; COMPLETED никогда не аннотируется
(здоровые потоки получают нулевую разницу).

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

Источники данных и наблюдаемое распределение (см. [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) §5.1):

- `locked_reason` появляется на трех уровнях: thread_metadata / entries / background_entries;
  единственное наблюдаемое значение — `spending_limit_exceeded`; `parse_turn` хранит значение уровня записи в
  `turn.metadata["locked_reason"]` (parsers.py:205-208).
- **Источники статуса** для точек аннотации: на уровне оборота используется `turn.metadata["wf_status"]`
  (монтируется attach_workflow_blocks, parsers.py:256); под-агенты используют истинный статус с фоновой стороны
  (`SubAgent.status`, adapter.py:257-260); записи приложения используют собственный статус полезной нагрузки.
- Каждая запись `thread.json.interruptions` является `{location, kind, headline, status}`;
  местоположение имеет вид `turn_0007` / `turn_0011/subagent` / `turn_0024/subagent_stub` /
  `background_unassigned` (parsers.py:535-583).
- Повторный рендеринг `--thread-json` может добавить/удалить этот ключ офлайн на месте (rerender_cmd.py:141-169, см. [§12](offline-operations.md)).
