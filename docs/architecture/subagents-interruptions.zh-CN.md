# 子代理与中断

---

## 归属瀑布图（后台子代理负载的确定性归属）

每条后台嵌套 `workflow_payload` 只渲染一处、绝不双渲染；此处落到判定函数与数据结构。三级全部在 `parsers.py`，挂载点在
`adapter.get_thread`（adapter.py:150-157，仅 computer/council 执行）：

```mermaid
flowchart TD
    BG["background_entries 顶层嵌套 workflow_payload<br/>（_iter_top_wf_payloads，parsers.py:342<br/>只取顶层不递归——嵌套随父负载整体渲染，防双重计入）"]

    BG --> L1{"① 主 entry 锚点命中？<br/>_anchored_payload_ids（parsers.py:368）<br/>主 entries 的 run_subagent 步骤<br/>含同 id 的 workflow_payload"}
    L1 -->|"是"| R1["发起轮内渲染<br/>adapter.sub_agents 建 sub_map（adapter.py:210-273）<br/>render_wf_step → render_subagent（render.py:404,363）<br/>prompt=objective_chunks 拼接<br/>steps/answer/sources 取自 plain background_entries"]
    L1 -->|"否"| L2{"② subagent_result 桩轮 10s 窗命中？<br/>match_stub_workflows（parsers.py:384）"}
    L2 -->|"是"| R2["桩轮「## 子代理工作」段<br/>turn.stub_wfs（models.py:131）<br/>_render_nested_wf 折叠块（render.py:46）<br/>答案不回填，Answer 保持 （无）"]
    L2 -->|"否"| R3["③ 线程附录兜底<br/>collect_unconsumed_background（parsers.py:490）<br/>conv.unconsumed_bgs（models.py:170）<br/>conversation.md 末尾「## 后台任务（未归入轮次）」<br/>render_bg_appendix（render.py:601）"]

    R1 -.-> ONE(["每条负载只落一处<br/>绝不双渲染"])
    R2 -.-> ONE
    R3 -.-> ONE
```

各级判定细节：

- **① 锚点**：`_anchored_payload_ids` 用 `_iter_wf_payloads`（parsers.py:326，
  递归下钻）收集主 entry 已锚定的全部 payload id。子代理的真实状态以后台侧为准——
  `adapter.sub_agents` 用后台 entry 的 `workflow_block.status`/`locked_reason`
  填 `SubAgent.status/locked_reason`（adapter.py:230-247），因为锚点侧 status 可能
  滞后（实测 cfca382d 锚点 COMPLETED 而后台 CANCELED）。
- **② 桩窗**：桩轮 = `trigger=="subagent_result"` 且 blocks 无任何 workflow steps
  （parsers.py:421）。候选为排除①后的顶层 payload；`|后台完成时间 − 桩创建时间| ≤ 10s`
  的全部配对按时间差升序贪心，`used_cand` 集合保证**每个后台只被消费一次**
  （parsers.py:451-466），一桩可收多代理。完成时间取 `payload.completed_at`，
  缺失退后台 entry 更新时间（中断场景必然没有完成通知，parsers.py:443-445）。
- **③ 附录**：`collect_unconsumed_background` 在①的 anchored 与②的 consumed
  双排除后，凡剩余顶层负载一律如实归档（parsers.py:490-531）——中断的后台任务
  不产生 subagent_result 完成通知，前两级必然落空；状态不限
  （AWAITING/CANCELED/COMPLETED/未来取值）。位置恒定在 conversation.md 末尾、
  不做时间归属猜测、turns/ 不追加（附录属线程级，render.py:601-638）。

---

## 中断语义状态图

统一真源 `parsers.classify_wf_status`（parsers.py:262-283）：workflow status +
locked_reason → 五类。三条消费路径共用同一分类结果，COMPLETED 一律不加注
（健康线程零 diff）。

```mermaid
stateDiagram-v2
    state "completed 完成" as c1
    state "limit_interrupted 限额中断" as c2
    state "awaiting 中断待续" as c3
    state "canceled 已取消" as c4
    state "other 未知取值" as c5
    state "静默：不加注/不登记/不告警" as quiet
    state "标注：wf_status_tag（parsers.py:293-298）" as tag
    state "渲染消费：工作过程标题（render.py:540-541）/ 子代理标题（render.py:367-368）/ 嵌套 details summary（render.py:116-119）" as consume1
    state "登记消费：thread.json.interruptions（parsers.py:534；写入 fs_writer.py:242-244；无中断不出现该键）" as consume2
    state "告警消费：scan_wf_anomalies → log.warning（parsers.py:645；adapter.py:131-134）" as consume3
    state "续跑覆盖：lastUpdated 变化 → plan_incremental 判 updated → 增量重抓（无需特例代码）" as cont

    [*] --> c1 : status 为空 / COMPLETED / WORKFLOW_COMPLETED（parsers.py:277-278）
    [*] --> c2 : WORKFLOW_AWAITING_NEXT_STEPS + locked_reason=spending_limit_exceeded（parsers.py:279-280）
    [*] --> c3 : WORKFLOW_AWAITING_NEXT_STEPS 无 locked_reason
    [*] --> c4 : WORKFLOW_CANCELED（parsers.py:281-282）
    [*] --> c5 : 其他未知取值（parsers.py:283）

    c1 --> quiet
    c5 --> quiet : 无标注（枚举未覆盖，不打扰渲染）
    c2 --> tag : 「⏸ 限额中断（内容截至中断点）」
    c3 --> tag : 「⏸ 中断待续」
    c4 --> tag : 「⛔ 已取消」
    tag --> consume1
    tag --> consume2
    c2 --> consume3
    c3 --> consume3
    c4 --> consume3
    c5 --> consume3
    consume2 --> cont : 中断后被用户继续
```

数据来源与实测分布（详见 [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) §5.1）：

- `locked_reason` 出现于 thread_metadata / entries / background_entries 三层，
  实测唯一取值 `spending_limit_exceeded`；`parse_turn` 把 entry 级值存入
  `turn.metadata["locked_reason"]`（parsers.py:204-207）。
- 中断标注加注点的**状态来源**：轮级用 `turn.metadata["wf_status"]`
  （attach_workflow_blocks 挂载，parsers.py:255）；子代理用后台侧真实状态
  （`SubAgent.status`，adapter.py:260-263）；附录条目用 payload 自身 status。
- `thread.json.interruptions` 每条 `{location, kind, headline, status}`，
  location 形如 `turn_0007` / `turn_0011/subagent` / `turn_0024/subagent_stub` /
  `background_unassigned`（parsers.py:534-582）。
- re-render `--thread-json` 可离线就地增删该键（rerender_cmd.py:141-169，见 [§12](offline-operations.md)）。
