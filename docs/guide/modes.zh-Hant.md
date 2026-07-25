---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/modes.zh-CN.md"
translation_source_sha256: "902b8570a856deeeb385f0d0babe3d22af5388a78c1cb546c595ece011aacade"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="会话模式" data-pplx-source-anchor="true"></a>
# 會話模式

Perplexity 會話有五種模式：`search` / `deep-research` / `computer` / `council` / `study`。
匯出時按執行緒判定模式；它決定抓取哪些 API 回應、執行緒目錄裡落什麼內容、以及執行緒進入
哪條[歸檔路徑](archive-layout.md)（`<账户>/<模式>/…`）。判定結果記錄在
`thread.json`（`mode` 鍵），並用於 `pplx-export batch --mode` 過濾。`pplx-ask`
也能以五種模式中的四種（除 `computer` 外）**建立**新執行緒——見 [pplx-ask](pplx-ask.md)。

<a id="五种模式一览" data-pplx-source-anchor="true"></a>
## 五種模式一覽

| 模式 | UI 名稱 / 模型 | 輪次內容 | 引文 | 產物 | 抓取 schematized blocks |
|---|---|---|---|---|---|
| `search` | 「Best」（`pplx_pro`；labs 的 `STUDIO`/`pplx_beta` 也歸入此） | Query + Answer，文字步驟 | 輪次級 + 全執行緒 `sources.*` | — | 否（無 `raw_blocks.json`） |
| `deep-research` | 「Deep research」（`pplx_alpha`，固定不可選） | 研究步驟，含 `RESEARCH_ANSWER` | 有 | `report.md`（完整報告） | 是 |
| `computer` | Computer（`pplx_asi_opus`、`pplx_asi_opus_thinking`） | 完整 `workflow_block`：旁白、工具呼叫、子代理 prompt/步驟、逐步引文 | 逐步 + 輪次 + 全執行緒 | `assets/` 多版本檔案 + 子代理執行 | 是 |
| `council` | 模型委員會（`pplx_agentic_research`；預設三個模型） | `COUNCIL_RESEARCH` 步驟；各模型巢狀 `LLM_COUNCIL` 工作流程摺進 `<details>`（檢索輪次、全部來源、完整單模型答案） | 單模型 + 聚合 | 多模型答案並排比較 | 是 |
| `study` | Study（`pplx_study`） | 經 blocks 提供步驟/引文（實測亦含資產） | 有 | 存在時有資產 | 是 |

## 模式如何判定

判別權威是平台自己的欄位 **`entry.search_mode`**（`SEARCH_MODE_MAP`，
`normalize.py:50-59`），對全部 entries 遍歷收集（`normalize.py:106-115`）。
已對官方模型配置（`GET /rest/models/config/v2`）驗證：
`default_models.search=pplx_pro`（UI「Best」）、`default_models.research=pplx_alpha`
（UI「Deep research」），取值與會話模式一一對應：

| `search_mode` 取值 | 模式 |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`、`STUDIO` | `search` |

衝突規則（`detect_mode`，`normalize.py:66-128`）：

- **執行緒內模式切換**（entries 不一致）：依特異性取最高——
  **computer > council > study > deep-research > search**（`_MODE_SPECIFICITY`，
  `normalize.py:63`）——並 `log.warning`。
- **與下游訊號衝突**（步驟名 / `display_model`）：`search_mode` 勝出，
  `log.warning`（`normalize.py:120-123`）。
- **`search_mode` 完全缺失** → 走原鏈：URL 含 `/computer/tasks/` 或
  `metadata.mode == '4'` 或索引 mode ∈ `ASI`/`COMPUTER` → `computer`；存在
  `COUNCIL_RESEARCH` 步驟 → `council`；存在 `RESEARCH_ANSWER` 步驟 → `deep-research`；
  冗餘訊號 `display_model`（`DISPLAY_MODEL_MODE`，`normalize.py:32-37`）衝突時勝出；
  全部未命中 → 預設 `search`。
- **訊號全滅不下 search 定論**：管線仍兜底抓取 schematized blocks
  （`adapter.py:83-89`），平台欄位漂移不會讓 `raw_blocks.json` 靜默遺失。

!!! note "為什麼 `pplx_alpha` 不是判別依據"
    `pplx_alpha` 是 RESEARCH 專屬模型——它是本分類器要判出的**目標**、而非判別證據，
    因此被刻意排除在映射表之外（`normalize.py:15-31` 註解）。

含全部分支的完整決策樹：[匯出管線——模式判定](../architecture/export-pipeline.md)。

<a id="子代理负载的落点" data-pplx-source-anchor="true"></a>
## 子代理負載的落點

computer/council 執行會產生後台子代理工作流程。每個後台 `workflow_payload`
**恰好落在一個位置，絕不渲染兩次**；使用者層面的三個可能落點：

1. **錨定——落入發起輪次**：發起子代理的輪次攜帶相同 payload id，因此該執行內聯渲染在
   這一輪的工作過程中（`turns/turn_NNNN.md`），含 prompt、步驟、答案與來源。
2. **stub 輪次——「子代理工作」小節**：10 秒完成視窗內的 `subagent_result` stub 輪次
   吸收該負載；答案不回填。
3. **執行緒附錄——`conversation.md` 末尾**：剩餘全部負載（中斷的執行沒有完成通知，前兩級
   必然漏接）如實歸檔在「## 後台任務（未歸入輪次）」之下——不做時間歸屬猜測，
   任何狀態都接受。

匹配規則、資料結構與單次消費保證：
[子代理與中斷](../architecture/subagents-interruptions.md)。

<a id="中断非-completed-工作流" data-pplx-source-anchor="true"></a>
## 中斷：非 COMPLETED 工作流程

未完成的工作流程在其渲染處內聯標註——工作過程標題、子代理標題與巢狀 `<details>`
摘要。三種標註（`parsers.classify_wf_status`，`parsers.py:263-284`）：

| 標註 | 條件 | 含義 |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | 額度耗盡，工作流程中途停擺 |
| `⏸ 中断待续` | `WORKFLOW_AWAITING_NEXT_STEPS` 且無 `locked_reason` | 已中斷，可在平台上繼續 |
| `⛔ 已取消` | `WORKFLOW_CANCELED` | 使用者或平台取消 |

- `COMPLETED` 永不標註（健康執行緒零 diff）；未知的未來狀態值保持靜默。
- 每個被標註的情形同時登記進 `thread.json.interruptions`，形如
  `{location, kind, headline, status}`——location 形如 `turn_0007`、
  `turn_0011/subagent`、`turn_0024/subagent_stub`、`background_unassigned`
  （`parsers.py:535-583`；健康執行緒不出現該鍵）。
- **續接無需特例**：在平台上繼續被中斷的執行緒後，其 `lastUpdated` 變化，下一次增量匯出
  重新抓取，工作流程完成後標註自然消失。見[增量同步](incremental-sync.md)。

實測狀態取值與分佈：[API 回應與錯誤](../reference/api/api-responses-errors.md)；
狀態機：[子代理與中斷](../architecture/subagents-interruptions.md)。

<a id="答案重写变体answer_variants" data-pplx-source-anchor="true"></a>
## 答案重寫變體（answer_variants）

平台重寫答案（A/B 實驗）時，被取代的變體在 API 側不可見——只回傳被選中的答案，
落選的兄弟版本僅在 `entries[].side_by_side_metadata` 留下痕跡，且之後可能被平台清除
（死鏈已證實：403 `VIEW_THREAD_NOT_ALLOWED`）。工具讓「發生過重寫」可觀測：

- **登記**：收窄判據命中寫入 `thread.json.answer_variants`（`fs_writer.py:247-252`；
  無命中不出現該鍵），並追加到集中登記處 `index/answer_variants_log.jsonl`，
  按（執行緒, entry）去重，冪等（`variant_log.py:76`）。
- **告警**：每次線上命中輸出單行可 grep 的 WARNING `ANSWER_VARIANT_DETECTED`，
  含完整定位欄位（執行緒 uuid/uuid8、entry_uuid、sibling_uuid、selection_status、
  experiment_role）；`re-render` 離線重新登記，僅在內容新增或變化時告警，
  全庫重跑不洗版；batch 摘要追加 ⚠ 命中數。
- **人工補歸檔**：兄弟變體實測是死鏈，備選答案通常**無法經 API 恢復**。命中後請儘快
  人工確認備選答案（平台介面、自己的記錄、截圖）；拿到了就記錄為執行緒目錄內的
  `rewritten_answer_variant.md`；拿不到，`thread.json.answer_variants` 加 jsonl
  登記處就是最終可追溯記錄。

檢測鏈與離線重登記：[離線操作](../architecture/offline-operations.md)；欄位語義與
死鏈證據：[API 回應與錯誤](../reference/api/api-responses-errors.md)。

<a id="渲染保真原则" data-pplx-source-anchor="true"></a>
## 渲染保真原則

無論哪種模式，渲染遵循同一份保真契約：

- **答案完整呈現，絕不截斷**——舊的 `[:4000]` 截斷會切斷句子，已移除
  （`render.py:645-647`）。
- **表格絕不截斷**——`WORKFLOW_ITEM_TABLE` 渲染全部行列，表頭與儲存格中的 `|`
  和換行被跳脫，Markdown 結構不破壞（`render.py:211-243`）。
- **引文完整**——三個收集通道（`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`），按 URL 去重匯入 `sources.*`；引用過的不丟。
- **API raw JSON 是內容邊界**——渲染的一切都來自 `raw_entries.json` /
  `raw_blocks.json`；API 不回傳的（如被取代的答案變體）無法渲染，轉而透過登記鍵
  呈現，絕不臆造。
- **UI 摺疊處，歸檔全展開**——web UI 藏在摺疊與點擊之後的細節（computer 工作流程旁白與
  工具輸入輸出、council 單模型執行、子代理步驟）全部完整渲染；用 `<details>`
  摺疊區塊保持文件大綱可讀且不丟資訊（`render.py:46`、`render.py:404-413`）。
- **結構穩健性**——程式碼圍欄按內容定長（`_fence_for`，`render.py:28-43`），自帶圍欄的
  工具輸出不會讓配對翻轉；LaTeX 分隔符正規化為 `$$` / `$`，程式碼段受保護
  （`normalize_math_delims`）。

保留的原始回應如何讓這一切可離線重新產生：
[匯出管線](../architecture/export-pipeline.md)與[離線操作](../architecture/offline-operations.md)。

<a id="另见" data-pplx-source-anchor="true"></a>
## 另見

- [歸檔目錄結構](archive-layout.md)——各模式檔案的落點
- [pplx-ask](pplx-ask.md)——以各模式建立新執行緒
- [增量同步](incremental-sync.md)——續接執行緒的重抓
- [匯出管線](../architecture/export-pipeline.md)——完整模式判定決策樹
- [子代理與中斷](../architecture/subagents-interruptions.md)——歸屬瀑布與狀態機
- [API 回應與錯誤](../reference/api/api-responses-errors.md)——欄位實測取值
