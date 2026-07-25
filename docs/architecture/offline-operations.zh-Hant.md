---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/offline-operations.zh-CN.md"
translation_source_sha256: "6e8895877b590f5376436f80c97d687a04542d16a47ada59bffdf70c284de6a4"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="离线操作" data-pplx-source-anchor="true"></a>
# 離線操作

`pplx_export` 的零網路一側：raw JSON 離線再生、relations 離線重建管線、索引富化回填、
遠端刪除狀態機與 answer_variants 檢測鏈。小節保留[架構總覽](overview.md)的原始編號。

---

<a id="离线再生re-render" data-pplx-source-anchor="true"></a>
## 離線再生（re-render）

渲染層修復後，從 raw JSON **零網路**冪等再生全部產物。實現：
`commands/rerender_cmd.py`（單執行緒 `rerender` rerender_cmd.py:105-190；
批次 `cmd_rerender` rerender_cmd.py:193-212）。

```mermaid
flowchart TD
    IN[("&lt;out&gt;/*/*/*/raw_entries.json<br/>glob 全部线程目录（rerender_cmd.py:199）")] --> CHK{"raw_entries.json 存在？"}
    CHK -->|"否"| SKIP["跳过（计 skipped）"]
    CHK -->|"是"| P1["parse_turn 逐 entry（parsers.py:173）<br/>按 created_us 排序、重编 index<br/>（rerender_cmd.py:57-60）"]
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

紀律：

- **零網路**：`PerplexityAdapter(None)` 只複用純資料組裝方法，任何線上方法
  （get_thread 等）不會被呼叫。
- **冪等**：產物只由 raw + 渲染器決定；重跑結果位元組一致（快照回歸測試保證，[§13](../development/testing-architecture.md)）。
- **不動其他檔案**：sources、report.md、assets 原樣；thread.json 預設不動，
  `--thread-json` 時僅增刪 interruptions / answer_variants 兩個鍵。
- `--dry-run` 只列目錄不寫檔案（rerender_cmd.py:204-206）；`--limit N` 取前 N 個。

---

<a id="relations-离线重建管线" data-pplx-source-anchor="true"></a>
## relations 離線重建管線

`cmd_relations`（misc_cmd.py:16）從歸檔 raw **零網路**重建全庫對話關係圖：
複用 re-render 的離線重建管線 `load_archived_conversation`（rerender_cmd.py:34）
還原 Conversation（turns 解析/排序/編號、_plain/_blocks 掛載），逐執行緒經
`adapter.sub_agents` 填會話級 `conv.sub_agents`（misc_cmd.py:70-73；
匯出管線不回填該欄位，models.py:178-182）；computer 的答案兜底
（`wf_block_answer`）在本層回填 `turn.answer`，擴大 references 掃描面
（misc_cmd.py:74-79）。無 raw 的執行緒退化為 thread.json + conversation.md 殼
（僅 same_space / 裸 uuid 可判，misc_cmd.py:61-66）。

```mermaid
flowchart LR
    RAW["web_archive/*/*/*/raw_entries.json<br/>+ raw_blocks.json"] --> LA["load_archived_conversation<br/>（rerender_cmd.py:34，零网络）"]
    LA --> SUB["adapter.sub_agents → conv.sub_agents<br/>（misc_cmd.py:70-73）"]
    LA --> FB["wf_block_answer 回填 turn.answer<br/>（misc_cmd.py:74-79）"]
    SUB --> BE["build_edges（relations.py:200）"]
    FB --> BE
    BE --> SS["same_space：同一空间<br/>dst = space:&lt;slug&gt;"]
    BE --> SP["same_prompt：首问归一化全等<br/>（normalize_query，relations.py:111）<br/>簇内按 created_us 链式连边（非团簇）<br/>query_source 区分定时任务重跑 vs 人工重发<br/>（parsers.py:209-215）"]
    BE --> RF["references：答案文本 / 引文 URL<br/>引用库内其他线程（含裸 uuid）"]
    BE --> SA["subagent_of：主线程 → 子代理运行<br/>dst = toolu_X 运行 id（非线程 uuid）<br/>已归档子代理线程记入 evidence"]
    SS --> OUT[("web_archive/relations/<br/>edges.jsonl + graph.md")]
    SP --> OUT
    RF --> OUT
    SA --> OUT
```

定案紀律（2026-07-23）：`branch_of` 機制確認但全庫無實例、不建邊；
`related_query` 不可從現有資料解析、不建邊——寧可缺邊，不建猜測邊。
實測規模：全庫 772 邊 / 21 簇（same_space 559 / subagent_of 154 /
same_prompt 49 / references 10）。

---

## search-mode-backfill（索引 search_mode 富化）

`cmd_search_mode_backfill`（search_mode_backfill_cmd.py:81）把平台權威欄位
`search_mode` 富化進 `index/library_<account>.json`：**本地 raw 優先**
（已歸檔執行緒從 raw_entries.json 的 `entries[].search_mode` 提取，零網路），
無本地 raw 才線上兜底抓 thread；寫盤時合併保留既有索引欄位
（refresh 語義：富化鍵覆蓋、其餘原樣），冪等可續跑、`--limit` 可取子集。
富化後的索引行使 batch 的 `--mode` 過濾成為權威過濾：
`index_row_matches_mode`（batch_cmd.py:46）優先按索引 search_mode
（SEARCH_MODE_MAP，normalize.py:50）判定，缺失才回退啟發式。

---

<a id="sync-deleted-远端删除状态机" data-pplx-source-anchor="true"></a>
## sync-deleted 遠端刪除狀態機

`cmd_sync_deleted`（sync_deleted_cmd.py:262）識別「平台側已被使用者/遠端刪除」
的執行緒並落終態，與 expired 並列。候選判定是**全帳戶索引並集 diff**：
已歸檔 ok 執行緒在**所有** `index/library_*.json` 中均消失才算候選
（跨帳戶 export_via 執行緒只出現在擁有者索引，單帳戶 diff 會誤報；
find_candidates，sync_deleted_cmd.py:148）；索引缺失/不可讀時安全跳過並
如實記錄原因。預設離線 dry-run 僅列候選（不聯網、不改檔案）；`--online`
逐條 GET thread 驗證：`ENTRY_DELETED` / `ENTRY_EXPIRED` / 404 → 確認刪除，
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

錯誤類型分層：`EntryDeletedError` 繼承 `EntryExpiredError`（400 且 body 含
ENTRY_DELETED 的判定先於 ENTRY_EXPIRED，cookie_transport.py:93-98）；batch
捕獲順序須先子後父（batch_cmd.py:163-174 先於 175-183），否則 deleted 會被
誤記為 expired。刪除 API 本身：`DELETE /rest/thread/delete_thread_by_entry_uuid`
（read_write_token 取 `entries[].read_write_token` 首個非空；
已對自建測試執行緒與 BOT 空間執行緒實戰驗證 10/10 刪除成功）。

---

<a id="answer_variants-答案重写变体检测链" data-pplx-source-anchor="true"></a>
## answer_variants 答案改寫變體檢測鏈

平台「答案改寫 / A-B 實驗」中被替換的變體在 API 側不可見——選中的 answer
可見，落選 sibling 僅剩 `entries[].side_by_side_metadata` 痕跡，且或將被平台
清理（sibling 死鏈已實證：403 VIEW_THREAD_NOT_ALLOWED + SPA 重新導向首頁，
見 [API 參考 §5.2](../reference/api/api-responses-errors.md)）。檢測鏈讓「改寫發生過」可觀測、可追溯：

```mermaid
flowchart LR
    E["entries[].side_by_side_metadata<br/>收窄判据"] --> CAV["parsers.collect_answer_variants<br/>（parsers.py:589）"]
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

- **判據收窄**：只認 side_by_side_metadata 的權威訊號，記錄全量定位欄位
  （thread 全量 uuid + uuid8、標題、entry_uuid、sibling_uuid、selection_status、
  experiment_role）與處置指引，格式見 `format_detection`（variant_log.py:53）。
- **冪等**：jsonl 按 (web_uuid, entry_uuid) 去重，線上（source=online）/離線
  （source=offline）兩路重複登記不產生重複行；rerender 僅在 variants 內容
  變化時告警，全庫重跑不洗版。
- **處置流程**：命中後第一時間人工確認備選答案並補錄（備選或將被平台清理，
  API 不可補救），完整流程見 [API 參考 §5.2](../reference/api/api-responses-errors.md)。
