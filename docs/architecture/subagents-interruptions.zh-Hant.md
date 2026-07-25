---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/subagents-interruptions.zh-CN.md"
translation_source_sha256: "e3bae47fb087a5cbbfd36002d9dfa36a37fd00989afcd6a1ba84182017dc1968"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="子代理与中断" data-pplx-source-anchor="true"></a>
# 子代理與中斷

---

<a id="归属瀑布图后台子代理负载的确定性归属" data-pplx-source-anchor="true"></a>
## 歸屬瀑布圖（後台子代理負載的確定性歸屬）

每條後台巢狀 `workflow_payload` 只渲染一處、絕不雙渲染；此處落到判定函數與資料結構。三級全部在 `parsers.py`，掛載點在
`adapter.get_thread`（adapter.py:150-157，僅 computer/council 執行）：

```mermaid
flowchart TD
    BG["background_entries 顶层嵌套 workflow_payload<br/>（_iter_top_wf_payloads，parsers.py:343<br/>只取顶层不递归——嵌套随父负载整体渲染，防双重计入）"]

    BG --> L1{"① 主 entry 锚点命中？<br/>_anchored_payload_ids（parsers.py:369）<br/>主 entries 的 run_subagent 步骤<br/>含同 id 的 workflow_payload"}
    L1 -->|"是"| R1["发起轮内渲染<br/>adapter.sub_agents 建 sub_map（adapter.py:207-270）<br/>render_wf_step → render_subagent（render.py:404,363）<br/>prompt=objective_chunks 拼接<br/>steps/answer/sources 取自 plain background_entries"]
    L1 -->|"否"| L2{"② subagent_result 桩轮 10s 窗命中？<br/>match_stub_workflows（parsers.py:385）"}
    L2 -->|"是"| R2["桩轮「## 子代理工作」段<br/>turn.stub_wfs（models.py:131）<br/>_render_nested_wf 折叠块（render.py:46）<br/>答案不回填，Answer 保持 （无）"]
    L2 -->|"否"| R3["③ 线程附录兜底<br/>collect_unconsumed_background（parsers.py:491）<br/>conv.unconsumed_bgs（models.py:170）<br/>conversation.md 末尾「## 后台任务（未归入轮次）」<br/>render_bg_appendix（render.py:601）"]

    R1 -.-> ONE(["每条负载只落一处<br/>绝不双渲染"])
    R2 -.-> ONE
    R3 -.-> ONE
```

各級判定細節：

- **① 錨點**：`_anchored_payload_ids` 用 `_iter_wf_payloads`（parsers.py:327，
  遞迴下鑽）收集主 entry 已錨定的全部 payload id。子代理的真實狀態以後台側為準——
  `adapter.sub_agents` 用後台 entry 的 `workflow_block.status`/`locked_reason`
  填 `SubAgent.status/locked_reason`（adapter.py:227-244），因為錨點側 status 可能
  滯後（實測 cfca382d 錨點 COMPLETED 而後台 CANCELED）。
- **② 樁窗**：樁輪 = `trigger=="subagent_result"` 且 blocks 無任何 workflow steps
  （parsers.py:422）。候選為排除①後的頂層 payload；`|后台完成时间 − 桩创建时间| ≤ 10s`
  的全部配對按時間差升序貪心，`used_cand` 集合保證**每個後台只被消費一次**
  （parsers.py:452-467），一樁可收多代理。完成時間取 `payload.completed_at`，
  缺失退後台 entry 更新時間（中斷場景必然沒有完成通知，parsers.py:444-446）。
- **③ 附錄**：`collect_unconsumed_background` 在①的 anchored 與②的 consumed
  雙排除後，凡剩餘頂層負載一律如實歸檔（parsers.py:491-532）——中斷的後台任務
  不產生 subagent_result 完成通知，前兩級必然落空；狀態不限
  （AWAITING/CANCELED/COMPLETED/未來取值）。位置恆定在 conversation.md 末尾、
  不做時間歸屬猜測、turns/ 不追加（附錄屬執行緒級，render.py:601-638）。

---

<a id="中断语义状态图" data-pplx-source-anchor="true"></a>
## 中斷語義狀態圖

統一真源 `parsers.classify_wf_status`（parsers.py:263-284）：workflow status +
locked_reason → 五類。三條消費路徑共用同一分類結果，COMPLETED 一律不加註
（健康執行緒零 diff）。

```mermaid
stateDiagram-v2
    state "completed 完成" as c1
    state "limit_interrupted 限额中断" as c2
    state "awaiting 中断待续" as c3
    state "canceled 已取消" as c4
    state "other 未知取值" as c5
    state "静默：不加注/不登记/不告警" as quiet
    state "标注：wf_status_tag（parsers.py:294-299）" as tag
    state "渲染消费：工作过程标题（render.py:540-541）/ 子代理标题（render.py:367-368）/ 嵌套 details summary（render.py:116-119）" as consume1
    state "登记消费：thread.json.interruptions（parsers.py:535；写入 fs_writer.py:242-244；无中断不出现该键）" as consume2
    state "告警消费：scan_wf_anomalies → log.warning（parsers.py:646；adapter.py:131-134）" as consume3
    state "续跑覆盖：lastUpdated 变化 → plan_incremental 判 updated → 增量重抓（无需特例代码）" as cont

    [*] --> c1 : status 为空 / COMPLETED / WORKFLOW_COMPLETED（parsers.py:278-279）
    [*] --> c2 : WORKFLOW_AWAITING_NEXT_STEPS + locked_reason=spending_limit_exceeded（parsers.py:280-281）
    [*] --> c3 : WORKFLOW_AWAITING_NEXT_STEPS 无 locked_reason
    [*] --> c4 : WORKFLOW_CANCELED（parsers.py:282-283）
    [*] --> c5 : 其他未知取值（parsers.py:284）

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

資料來源與實測分佈（詳見 [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) §5.1）：

- `locked_reason` 出現於 thread_metadata / entries / background_entries 三層，
  實測唯一取值 `spending_limit_exceeded`；`parse_turn` 把 entry 級值存入
  `turn.metadata["locked_reason"]`（parsers.py:205-208）。
- 中斷標註加註點的**狀態來源**：輪級用 `turn.metadata["wf_status"]`
  （attach_workflow_blocks 掛載，parsers.py:256）；子代理用後台側真實狀態
  （`SubAgent.status`，adapter.py:257-260）；附錄條目用 payload 自身 status。
- `thread.json.interruptions` 每條 `{location, kind, headline, status}`，
  location 形如 `turn_0007` / `turn_0011/subagent` / `turn_0024/subagent_stub` /
  `background_unassigned`（parsers.py:535-583）。
- re-render `--thread-json` 可離線就地增刪該鍵（rerender_cmd.py:141-169，見 [§12](offline-operations.md)）。
