---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/subagents-interruptions.zh-CN.md"
translation_source_sha256: "e3bae47fb087a5cbbfd36002d9dfa36a37fd00989afcd6a1ba84182017dc1968"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="子代理与中断" data-pplx-source-anchor="true"></a>
# サブエージェントと中断

---

<a id="归属瀑布图后台子代理负载的确定性归属" data-pplx-source-anchor="true"></a>
## 帰属ウォーターフォール図（バックグラウンドサブエージェント負荷の決定論的帰属）

各バックグラウンドネスト `workflow_payload` は1箇所のみレンダリングされ、二重レンダリングは決して行われません。ここでは判定関数とデータ構造に焦点を当てます。3レベルすべてが `parsers.py` 内にあり、マウントポイントは
`adapter.get_thread`（adapter.py:150-157、computer/council のみ実行）です：

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

各レベルの判定詳細：

- **① アンカー**：`_anchored_payload_ids` は `_iter_wf_payloads`（parsers.py:327、
  再帰的ドリルダウン）を使用して、メインエントリにアンカーされたすべてのペイロードIDを収集します。サブエージェントの実際のステータスはバックエンド側を基準とします——
  `adapter.sub_agents` はバックエンドエントリの `workflow_block.status`/`locked_reason` を使用して
  `SubAgent.status/locked_reason`（adapter.py:227-244）を埋めます。アンカー側のステータスは遅延する可能性があるためです（実測では cfca382d でアンカーが COMPLETED でもバックエンドは CANCELED）。
- **② スタブウィンドウ**：スタブラウンド = `trigger=="subagent_result"` かつブロックにワークフローステップが存在しない（parsers.py:422）。候補は①を除外したトップレベルペイロードです。`|后台完成时间 − 桩创建时间| ≤ 10s`
  のすべてのペアは時間差の昇順で貪欲にマッチングされ、`used_cand` 集合により**各バックエンドは1回のみ消費される**ことを保証します（parsers.py:452-467）。1つのスタブが複数のエージェントを受け取ることができます。完了時間は `payload.completed_at` を使用し、欠落時はバックエンドエントリの更新時刻にフォールバックします（中断シナリオでは完了通知が存在しないため、parsers.py:444-446）。
- **③ 付録**：`collect_unconsumed_background` は、①のアンカーと②の消費済みの両方を除外した後、残ったすべてのトップレベルペイロードをそのままアーカイブします（parsers.py:491-532）——中断されたバックグラウンドタスクは subagent_result 完了通知を生成しないため、最初の2レベルは必ず失敗します。ステータスは問いません（AWAITING/CANCELED/COMPLETED/将来の値）。位置は常に conversation.md の末尾、時間帰属の推測は行わず、turns/ には追加しません（付録はスレッドレベル、render.py:601-638）。

---

<a id="中断语义状态图" data-pplx-source-anchor="true"></a>
## 中断セマンティクス状態図

統一真実源 `parsers.classify_wf_status`（parsers.py:263-284）：workflow status +
locked_reason → 5つのカテゴリ。3つの消費パスは同じ分類結果を共有し、COMPLETED には注釈を追加しません（正常スレッドでは差分ゼロ）。

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

データソースと実測分布（詳細は [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) §5.1 を参照）：

- `locked_reason` は thread_metadata / entries / background_entries の3層に出現し、
  実測で唯一の値は `spending_limit_exceeded`；`parse_turn` はエントリレベルの値を
  `turn.metadata["locked_reason"]`（parsers.py:205-208）に格納します。
- 中断注釈の**ステータスソース**：ラウンドレベルでは `turn.metadata["wf_status"]`
  （attach_workflow_blocks によりマウント、parsers.py:256）；サブエージェントではバックエンド側の実際のステータス
  （`SubAgent.status`、adapter.py:257-260）；付録エントリではペイロード自身の status。
- `thread.json.interruptions` 各 `{location, kind, headline, status}`、
  location は `turn_0007` / `turn_0011/subagent` / `turn_0024/subagent_stub` /
  `background_unassigned` の形式（parsers.py:535-583）。
- 再レンダリング `--thread-json` はオフラインでその場でキーを追加/削除できます（rerender_cmd.py:141-169、[§12](offline-operations.md) 参照）。
