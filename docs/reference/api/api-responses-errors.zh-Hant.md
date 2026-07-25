---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-responses-errors.zh-CN.md"
translation_source_sha256: "cc96e525443d1f8445d81a3997cc8f26178730ef0541a33d0774f40c3fe70b89"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-响应结构与错误语义" data-pplx-source-anchor="true"></a>
# API 回應結構與錯誤語義

*本文是 Perplexity Web API 參考的一部分——全圖見 [API 索引](index.md)。*

<a id="响应结构要点解析纪律" data-pplx-source-anchor="true"></a>
## 回應結構要點（解析紀律）

- **成功歸檔保留原始資料**：`raw_entries.json`（plain）與
  `raw_blocks.json`（schematized，實際抓取時）會和渲染產物一併保存，
  解析/渲染可離線重跑（`pplx-export re-render`），不重抓。
- **欄位提取集中** `sites/perplexity/parsers.py`（schema 漂移只改一處）。
- 模式的識別（`normalize.detect_mode`，決策樹見 [export-pipeline.md](../../architecture/export-pipeline.md)）：最高優先級信號為
  任一 entry 的 **`search_mode`** 欄位（映射見 [§3.9](api-rest-endpoints.md) 末）；全滅時回退——computer = URL
  `/computer/tasks/` 或 metadata.mode=="4" 或索引 mode∈{ASI,COMPUTER}；council = 存在
  COUNCIL_RESEARCH 步驟；deep-research = 存在 RESEARCH_ANSWER 步驟（按內容，不依賴中文標籤）；
  其餘 search。
- computer 的 UI 全部摺疊——**一律以 API 的 entries/blocks 為準**，不用 UI 文字做內容邊界。
- 子代理雙通道（2026-07-19 探明）：prompt 在 schematized `workflow_payload.objective_chunks`；
  步驟/結論在 plain `background_entries`；經 `workflow_payload.id`（`toolu_X`）關聯。
- `WORKFLOW_ITEM_SOURCES` 項除 `sources_payload.sources`（連結列表）外常攜帶 `text_payload`
  （子代理對頁面的提取正文/對比表，全庫實測 450 處，408 處在 background 巢狀負載內）；
  同一內容會同時出現在 plain 後台 entry 的 `text` 內嵌步驟 JSON 與 schematized 巢狀負載中——
  錨定子代理經 plain 路徑渲染即已保留正文（2026-07-22 全庫核對 408/408 無缺失）。
- **`related_queries` / `related_query_items`（2026-07-23 定案）**：每條 entry 攜帶的
  **下一問 prompt 推薦**——平台為已完成答案生成的追問建議；`related_queries` 為推薦文字陣列，
  `related_query_items` 為結構化項（含 uuid/upsell_type 等）。取證結論：item 的 uuid
  **不是執行緒 uuid**（與全庫執行緒 uuid 交叉 0/988），推薦文字與其他執行緒 query 零重合——
  **暫不可解析為執行緒間關係**；存在「預分配執行緒 uuid（點擊後物化）」的未驗證假設。
  資料天然保留在歸檔 `raw_entries.json`（某歸檔庫過半執行緒命中），無需額外採集動作；
  relations 圖不為它建邊。

<a id="错误与风控语义" data-pplx-source-anchor="true"></a>
## 錯誤與風控語義

| 現象 | 含義/處置 |
|---|---|
| 403（帶 cf 挑戰頁） | Cloudflare 攔截（TLS 指紋/頻控）——退避；urllib+瀏覽器 cookie 一般不觸發 |
| 401 / API 層 403（無 cf 挑戰頁） | 會話 cookie 過期/失效——工具立即拋出、不退避；batch 連續 3 次鑑權失敗即 fail-fast（需更新 cookie） |
| 429 | 頻控——指數退避（工具已實現） |
| 5xx（500/502/503/504） | 服務端瞬態錯誤（504 常見於 Cloudflare 逾時）——退避重試（工具已實現） |
| ENTRY_EXPIRED | 平台已清除（約 3 個月）——終態，不重試 |
| ENTRY_DELETED | 使用者/遠端已刪除（同為 HTTP 400，code 不同）——終態 `deleted`，不重試 |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED`（HTTP 200） | 當前帳戶無權查看該空間——換可見帳戶重試 |
| `error_code: VIEW_THREAD_NOT_ALLOWED`（HTTP 403） | 當前帳戶無權查看該執行緒（2026-07-23 實測：sibling 變體 uuid 探測；物件存在但不可存取，非「不存在」） |
| `status:"failed"` 空資料 | 同上類（get_collection 的失敗形態） |

**限頻紀律（防封號，使用者明確要求）**：批次執行緒間隨機 10–20s、無並發、429/403 退避、5xx 退避重試；
翻頁 ≥3s；schematized 補抓 ≥4s；空間元資料抓取 ≥3s。單執行緒匯出 = 1–2 請求 ≈ 開啟一次頁面。

<a id="中断语义实测取值2026-07-22分类真源-parsersclassify_wf_status" data-pplx-source-anchor="true"></a>
### 中斷語義實測取值（2026-07-22，分類真源 `parsers.classify_wf_status`）

`locked_reason` 欄位：出現於 `thread_metadata` / `entries[]` / `background_entries[]`
（plain 與 schematized 兩側都有）。實測唯一取值：

| locked_reason | 含義 | 實測分佈 |
|---|---|---|
| `spending_limit_exceeded` | 限額中斷（額度耗盡，工作流停在中斷點） | 全檔恰好 1 個執行緒（raw_entries 與 raw_blocks 兩側均有標記） |

workflow 狀態欄位（`workflow_block.status` 與巢狀 `workflow_payload.status` 同一列舉）實測取值：

| status | 語義 | 渲染標註（COMPLETED 不加註） |
|---|---|---|
| `WORKFLOW_COMPLETED` | 正常完成 | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | 等待下一步；配合 `locked_reason=spending_limit_exceeded` 即**限額中斷**（內容截至中斷點），無 locked_reason 則為中斷待續 | `⏸ 限额中断（内容截至中断点）` / `⏸ 中断待续` |
| `WORKFLOW_CANCELED` | 已取消（使用者/平台中止） | `⛔ 已取消` |

- `WORKFLOW_CANCELED` 實測 19 處（16 主 + 3 巢狀），分佈 7 個 computer 執行緒
  （a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff）。
- 注意：主 entry 錨點 payload 的 status 可能滯後（實測錨點 COMPLETED 而後台實際 CANCELED）——
  子代理真實狀態以後台側 `workflow_block.status` 為準。
- 中斷的後台任務不產生 subagent_result 完成通知；未消費的後台負載由執行緒附錄兜底
  （見 [subagents-interruptions.md](../../architecture/subagents-interruptions.md)「歸屬瀑布」）。
- computer 模式空答案（2026-07 雙重證實，不可恢復）：computer 模式下部分輪次的答案為空，
  因為服務端本來就沒有答案——API 重抓得到的資料與歸檔完全一致，且在 UI 上展開
  「已完成 N 步驟」摺疊條觸發零資料請求（純客戶端渲染，UI 與 API 同源），API 無法補救。
  這類空答案輪次中只有一部分與 `locked_reason=spending_limit_exceeded` 相關，其餘在服務端沒有任何原因標記。

<a id="side_by_side_metadata答案重写变体信号2026-07-23-定案" data-pplx-source-anchor="true"></a>
### `side_by_side_metadata`：答案重寫變體訊號（2026-07-23 定案）

欄位路徑：`entries[].side_by_side_metadata`（plain `/rest/thread/<uuid>` 回應）。
平台對同一條 query 生成多版答案（A/B 實驗或重寫）時，在當前生效 entry 上留下的
唯一痕跡——**被替換的變體本體（文字/步驟/引文）不在執行緒 API 回應中**（真例
b2d2632b：回應僅 1 條 entry、1 個 FINAL，變體 2 完全不可見）。

觀測到的鍵與取值（b2d2632b raw 為證，全庫 2442 條 entry 掃描）：

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| 鍵 | 語義（觀測/假設） |
|---|---|
| `sibling_uuid` | 指向同 query 的**兄弟答案變體**（另一版 entry/context 標識）。全庫 7 執行緒命中；**在線取證（2026-07-23）確認為死鏈**：雙帳戶 `GET /rest/thread/<sibling_uuid>` 均 403 `VIEW_THREAD_NOT_ALLOWED`（非 404/ENTRY_EXPIRED——服務端識別為存在但無權檢視的物件），瀏覽器（屬主帳戶）開啟 `/search/<sibling_uuid>` 被 SPA 重新導向回首頁——被替換變體不可經 sibling_uuid 恢復 |
| `selection_status` | `SELECTED` = 本 entry 的答案是被選中展示的一版；對照組實例均為 `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | 實驗角色。對照組帶 `[control]` 前綴（全庫 6 例：`[control]default-model-class:gpt41` 等）；真例無前綴（`override-default-model-class:qwen3_instruct-01f7f`，即模型覆蓋實驗的實驗組） |
| `experiment_override` | 實驗覆蓋參數（如 `override-default-model-class: qwen3_instruct`）；僅實驗組實例觀測到 |
| `execution_log` | 觀測值為空物件，語義未明 |

**收窄判據**（區分「真實重寫並保留雙版本」與「常規 A/B 對照」）：
`sibling_uuid` 非空 且（`selection_status` 非空且非 `SELECTION_STATUS_UNSPECIFIED`，
或 `experiment_role` 無 `[control]` 前綴）→ 全庫 2442 條 entry 中**僅命中 b2d2632b 一條**
（已確認的唯一真例；precision/recall 在本庫均為 1，樣本量 1 不能外推保證）。

工具行為：`parsers.collect_answer_variants` 提取命中條目，`adapter.get_thread`
log.warning 告警 + 寫入 `thread.json.answer_variants`（無命中不出現該鍵）；
`re-render --thread-json` 就地增刪（冪等）。時間佐證：真例 entry `created→updated`
差 53.66 s（17:13 生成後重寫/選定），且重寫推動了執行緒級 `lastUpdated`（增量重導
能觸發重抓，但重抓到的回應仍只含當前生效答案，舊變體不可恢復）。

**檢測日誌與處置流程（2026-07-23，`sites/perplexity/variant_log.py`）**：

- **日誌標記**：命中即 WARNING 級單行，統一可 grep 標記 `ANSWER_VARIANT_DETECTED`，
  含全部定位欄位與處置指引，形如：
  `ANSWER_VARIANT_DETECTED thread=<全量uuid> uuid8=<8位> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | 处置：…`
  在線路徑（`adapter.get_thread`）每次實際抓取命中都輸出；離線 `re-render`
  **僅在登記內容新增/變化時**輸出（冪等重跑不洗版）；`batch` 末尾摘要另透出一行
  命中計數提醒（不破壞現有摘要格式）。
- **集中登記處**：`<out>/index/answer_variants_log.jsonl`（**入庫檔案**，不在
  gitignore 的 `logs/` 之下）——每行一條 JSON（detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role），按 (web_uuid, entry_uuid) 去重，重複匯出/重渲不無限追加，
  detected_at 保留首見時間。
- **命中後建議動作**：sibling 已實證多為死鏈（見上表），備選答案通常**無法經 API
  補救**——儘快人工確認備選答案是否仍可取得（平台會話側/使用者記憶/截圖），可取得則
  補錄為執行緒目錄下的 `rewritten_answer_variant.md` 同款人工檔案；不可取得則以 `thread.json.answer_variants` +
  jsonl 登記作為最終可追溯痕跡。
