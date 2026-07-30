# 离线操作

`pplx_export` 的零网络一侧：raw JSON 离线再生、relations 离线重建管线、索引富化回填、
远端删除状态机与 answer_variants 检测链。小节保留[架构总览](overview.md)的原始编号。

---

## 离线再生（re-render）

渲染层修复后，从 raw JSON **零网络**幂等再生全部产物。实现：
`commands/rerender_cmd.py`（单线程 `rerender` rerender_cmd.py:105-190；
批量 `cmd_rerender` rerender_cmd.py:193-212）。

```mermaid
flowchart TD
    IN[("&lt;out&gt;/*/*/*/raw_entries.json<br/>glob 全部线程目录（rerender_cmd.py:199）")] --> CHK{"raw_entries.json 存在？"}
    CHK -->|"否"| SKIP["跳过（计 skipped）"]
    CHK -->|"是"| P1["parse_turn 逐 entry（parsers.py:172）<br/>按 created_us 排序、重编 index<br/>（rerender_cmd.py:57-60）"]
    P1 --> P2["Conversation 重建<br/>metadata = thread_metadata（rerender_cmd.py:65-70）<br/>conv._plain = doc"]
    P2 --> P3{"raw_blocks.json 存在？"}
    P3 -->|"是"| P4["conv._blocks 载入（rerender_cmd.py:91）<br/>PerplexityAdapter(None).sub_agents 建 sub_map<br/>（None-transport 纯数据组装，rerender_cmd.py:84-88,138）"]
    P3 -->|"否"| P5["sub_map = {}"]
    P4 --> P6{"mode ∈ computer/council？"}
    P6 -->|"是"| P7["attach_workflow_blocks（rerender_cmd.py:93）<br/>attach_stub_workflows（rerender_cmd.py:97）<br/>collect_unconsumed_background（rerender_cmd.py:101）"]
    P6 -->|"否"| P8
    P5 --> P8["render_conversation → conversation.md<br/>render_turn × N → turns/turn_NNNN.md<br/>（rerender_cmd.py:170,189）"]
    P7 --> P8
    P8 --> TJ{"--thread-json？"}
    TJ -->|"否"| OUT(("完成：不动其他文件"))
    TJ -->|"是"| TJ1["collect_interruptions(conv, sub_map)（rerender_cmd.py:150）<br/>answer_variants 随 load_archived 同实现重建（rerender_cmd.py:83）"]
    TJ1 --> TJ2{"与现有 thread.json<br/>interruptions / answer_variants 两键比较"}
    TJ2 -->|"内容有变"| TJ3["就地增删两键后写盘，其余字段原样（round-trip indent=1）<br/>（rerender_cmd.py:141-169）<br/>variants 新增/变化时告警 + 追加 jsonl 登记<br/>（rerender_cmd.py:163-166，见 §18）"]
    TJ2 -->|"无变化"| TJ4["不写盘——避免全库 mtime/diff 噪音"]
```

纪律：

- **零网络**：`PerplexityAdapter(None)` 只复用纯数据组装方法，任何在线方法
  （get_thread 等）不会被调用。
- **幂等**：产物只由 raw + 渲染器决定；重跑结果字节一致（快照回归测试保证，[§13](../development/testing-architecture.md)）。
- **不动其他文件**：sources、report.md、assets 原样；thread.json 默认不动，
  `--thread-json` 时仅增删 interruptions / answer_variants 两个键。
- `--dry-run` 只列目录不写文件（rerender_cmd.py:204-206）；`--limit N` 取前 N 个。

---

## relations 离线重建管线

`cmd_relations`（misc_cmd.py:16）从归档 raw **零网络**重建全库对话关系图：
复用 re-render 的离线重建管线 `load_archived_conversation`（rerender_cmd.py:34）
还原 Conversation（turns 解析/排序/编号、_plain/_blocks 挂载），逐线程经
`adapter.sub_agents` 填会话级 `conv.sub_agents`（misc_cmd.py:70-73；
导出管线不回填该字段，models.py:178-182）；computer 的答案兜底
（`wf_block_answer`）在本层回填 `turn.answer`，扩大 references 扫描面
（misc_cmd.py:74-79）。无 raw 的线程退化为 thread.json + conversation.md 壳
（仅 same_space / 裸 uuid 可判，misc_cmd.py:61-66）。

```mermaid
flowchart LR
    RAW["web_archive/*/*/*/raw_entries.json<br/>+ raw_blocks.json"] --> LA["load_archived_conversation<br/>（rerender_cmd.py:34，零网络）"]
    LA --> SUB["adapter.sub_agents → conv.sub_agents<br/>（misc_cmd.py:70-73）"]
    LA --> FB["wf_block_answer 回填 turn.answer<br/>（misc_cmd.py:74-79）"]
    SUB --> BE["build_edges（relations.py:200）"]
    FB --> BE
    BE --> SS["same_space：同一空间<br/>dst = space:&lt;slug&gt;"]
    BE --> SP["same_prompt：首问归一化全等<br/>（normalize_query，relations.py:111）<br/>簇内按 created_us 链式连边（非团簇）<br/>query_source 区分定时任务重跑 vs 人工重发<br/>（parsers.py:208-214）"]
    BE --> RF["references：答案文本 / 引文 URL<br/>引用库内其他线程（含裸 uuid）"]
    BE --> SA["subagent_of：主线程 → 子代理运行<br/>dst = toolu_X 运行 id（非线程 uuid）<br/>已归档子代理线程记入 evidence"]
    SS --> OUT[("web_archive/relations/<br/>edges.jsonl + graph.md")]
    SP --> OUT
    RF --> OUT
    SA --> OUT
```

定案纪律（2026-07-23）：`branch_of` 机制确认但全库无实例、不建边；
`related_query` 不可从现有数据解析、不建边——宁可缺边，不建猜测边。
实测规模：全库 772 边 / 21 簇（same_space 559 / subagent_of 154 /
same_prompt 49 / references 10）。

---

## search-mode-backfill（索引 search_mode 富化）

`cmd_search_mode_backfill`（search_mode_backfill_cmd.py:81）把平台权威字段
`search_mode` 富化进 `index/library_<account>.json`：**本地 raw 优先**
（已归档线程从 raw_entries.json 的 `entries[].search_mode` 提取，零网络），
无本地 raw 才在线兜底抓 thread；写盘时合并保留既有索引字段
（refresh 语义：富化键覆盖、其余原样），幂等可续跑、`--limit` 可取子集。
富化后的索引行使 batch 的 `--mode` 过滤成为权威过滤：
`index_row_matches_mode`（batch_cmd.py:46）优先按索引 search_mode
（SEARCH_MODE_MAP，normalize.py:50）判定，缺失才回退启发式。

---

## sync-deleted 远端删除状态机

`cmd_sync_deleted`（sync_deleted_cmd.py:262）识别「平台侧已被用户/远端删除」
的线程并落终态，与 expired 并列。候选判定是**全账户索引并集 diff**：
已归档 ok 线程在**所有** `index/library_*.json` 中均消失才算候选
（跨账户 export_via 线程只出现在所有者索引，单账户 diff 会误报；
find_candidates，sync_deleted_cmd.py:148）；索引缺失/不可读时安全跳过并
如实记录原因。默认离线 dry-run 仅列候选（不联网、不改文件）；`--online`
逐条 GET thread 验证：`ENTRY_DELETED` / `ENTRY_EXPIRED` / 404 → 确认删除，
`state.mark_deleted`（state.py:136）+ thread.json 墓碑
（mark_thread_json_remote_deleted，sync_deleted_cmd.py:215）。

```mermaid
stateDiagram-v2
    [*] --> ok : 已归档（batch_state = ok）
    ok --> candidate : 全账户索引并集均消失<br/>（find_candidates，sync_deleted_cmd.py:148）
    candidate --> skipped : 索引缺失/不可读<br/>安全跳过并记录原因
    candidate --> listed : 离线 dry-run 仅列出<br/>（不联网、不改文件）
    listed --> deleted : --online 逐条验证<br/>ENTRY_DELETED / ENTRY_EXPIRED / 404<br/>（_confirm_deleted，sync_deleted_cmd.py:247）
    deleted --> [*] : 终态 mark_deleted（state.py:136）+ thread.json 墓碑<br/>plan_incremental 与 expired 同等截尾<br/>（incremental.py:74-75,84）
```

错误类型分层：`EntryDeletedError` 继承 `EntryExpiredError`（400 且 body 含
ENTRY_DELETED 的判定先于 ENTRY_EXPIRED，cookie_transport.py:93-98）；batch
捕获顺序须先子后父（batch_cmd.py:163-174 先于 175-183），否则 deleted 会被
误记为 expired。删除 API 本身：`DELETE /rest/thread/delete_thread_by_entry_uuid`
（read_write_token 取 `entries[].read_write_token` 首个非空；
已对自建测试线程与 BOT 空间线程实战验证 10/10 删除成功）。

---

## answer_variants 答案重写变体检测链

平台「答案重写 / A-B 实验」中被替换的变体在 API 侧不可见——选中的 answer
可见，落选 sibling 仅剩 `entries[].side_by_side_metadata` 痕迹，且或将被平台
清理（sibling 死链已实证：403 VIEW_THREAD_NOT_ALLOWED + SPA 重定向首页，
见 [API 参考 §5.2](../reference/api/api-responses-errors.md)）。检测链让「重写发生过」可观测、可追溯：

```mermaid
flowchart LR
    E["entries[].side_by_side_metadata<br/>收窄判据"] --> CAV["parsers.collect_answer_variants<br/>（parsers.py:588）"]
    CAV --> AD["adapter.get_thread 在线命中即告警<br/>（adapter.py:141-147）"]
    CAV --> RR["re-render 离线重建<br/>仅新增/变化才告警（rerender_cmd.py:163-166）"]
    AD --> LOG["variant_log.warn_detections（variant_log.py:65）<br/>WARNING 单行 ANSWER_VARIANT_DETECTED（variant_log.py:45）<br/>全量定位字段 + 处置指引，可 grep"]
    RR --> LOG
    AD --> TJ["thread.json.answer_variants 登记<br/>（fs_writer.py:247-252）"]
    RR --> TJ
    TJ --> JSONL[("index/answer_variants_log.jsonl<br/>append_registry（variant_log.py:76）<br/>按 (web_uuid, entry_uuid) 去重幂等")]
    LOG --> B["batch 摘要 ⚠ 透出命中线程数<br/>（batch_cmd.py:214-223）"]
    JSONL --> B
```

- **判据收窄**：只认 side_by_side_metadata 的权威信号，记录全量定位字段
  （thread 全量 uuid + uuid8、标题、entry_uuid、sibling_uuid、selection_status、
  experiment_role）与处置指引，格式见 `format_detection`（variant_log.py:53）。
- **幂等**：jsonl 按 (web_uuid, entry_uuid) 去重，在线（source=online）/离线
  （source=offline）两路重复登记不产生重复行；rerender 仅在 variants 内容
  变化时告警，全库重跑不刷屏。
- **处置流程**：命中后第一时间人工确认备选答案并补录（备选或将被平台清理，
  API 不可补救），完整流程见 [API 参考 §5.2](../reference/api/api-responses-errors.md)。
