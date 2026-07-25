---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-discovery-roadmap.zh-CN.md"
translation_source_sha256: "d2ef3b082d6320ba6a0ba74a978305c5c362c8fa56c8ee0dbf357470df97cebd"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="端点发现方法与改进路线图" data-pplx-source-anchor="true"></a>
# 端點發現方法與改進路線圖

*本文是 Perplexity Web API 參考的一部分——全圖見 [API 索引](index.md)。*

<a id="已知未探索待确认项" data-pplx-source-anchor="true"></a>
## 已知未探索/待確認項

- `list_collection_threads` 的排序字段與 `total_threads` 精確語義
  （2026-07 實時賬戶快照：報告 99 vs 頂層 27 項）。
- `threadAccess`/`access`/`user_permission` 數值全譜（2026-07 觀測樣本：
  threadAccess 5 常規、1 帶 🔒；collection access 1；permission 4 所有者 /
  2 可編輯；assets data 亦含 thread_access）。
- `list_ask_threads`、`list_scheduled_computer_tasks` 的正確參數形態（直接 GET 400）。
- `collections/*/request-access-info`、`spaces/<uuid>/recurring_tasks`、`assets/<id>/members` 響應結構。
- 儀表板 GraphQL 操作為何未註冊（PERSISTED_QUERY_NOT_FOUND）：版本錯位 or 上下文門檻，
  需要時以線上網絡捕獲的實時哈希為準重新提取。
- `frontend_uuid` vs `uuid` vs `context_uuid` 三者在 computer 線程中的分工。
- 跨賬戶空間共享分叉線程（branch_of）的 API 信號字段（父線程指針/分叉標記）——
  機制已確認（[§3.3](api-rest-endpoints.md) 末），截至 2026-07-23 尚無歸檔實例，
  待首例出現時驗證記錄。

<a id="端点发现方法前端-bundle-静态分析零-api-成本2026-07-20-建立" data-pplx-source-anchor="true"></a>
## 端點發現方法：前端 bundle 靜態分析（零 API 成本，2026-07-20 建立）

一次發現 **147 個 `/rest/` 端點**，方法可復用（前端改版後重跑即可）：

1. 頁面加載的入口 `_spa/assets/index.html-*.js` 引 `bootstrap-*.js`（運行時含全部 chunk 映射）；
2. 從 bootstrap 提取 682 個 chunk 文件名（模式 `<name>-<hash8>.js`），按名稱篩 API 相關
   （client/api/thread/collection/space/computer…）；
3. 從公共 CDN `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js` 直接下載
   （無需 cookie）；中樞模塊：`platform-core-*`（API client）、`spa-shell-*`、`spa-metadata-*`；
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` 得端點清單（147 個）；
5. chunk 同時洩露調用形態（如 export 的 `format:'md'` 與 `file_content_64`）。
6. 另有 sourcemap：`https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map`（未深入）。

<a id="附录147-个端点按类分组与归档相关性标注" data-pplx-source-anchor="true"></a>
### 附錄：147 個端點按類分組（與歸檔相關性標註）

- **thread**：`/rest/thread/{entry_uuid_or_slug}`、`/rest/thread/export`★、`/rest/thread/{uuid}/members`、
  `/rest/thread/list_recent`、`/rest/thread/list_ask_threads`、`/rest/thread/list_pinned_ask_threads`、
  `/rest/thread/list_scheduled_computer_tasks`、`/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★：見 [§3.3](api-rest-endpoints.md) 全表（含 batch_move/batch_remove、list_user_collections、request-access-info、
  recurring_tasks、pins/threads、scheduled_threads）
- **assets**★：`/rest/assets/{asset_id}/data`、`/rest/assets/{asset_id}/members`、
  `/rest/assets/{asset_id}/published-access`、`/rest/assets/sites/{site_id}/publish-info`
- **analytics**：`/rest/analytics/computer/usage`、`/rest/analytics/computer/usage/members`
  （均 403 NOT_ORG_MEMBER——組織賬戶專用）
- **models/skills**：`/rest/models/config(/v2)`、`/rest/skills`、`/rest/skills/selectable`、
  `/rest/skills/grants`、`/rest/skills/submissions(/source)`
- **files/uploads**：`/rest/file-repository/*`（list/download/get-file-upload-urls/delete-files…）、
  `/rest/files/list(/list-infinite/list-errors)`、`/rest/uploads/(batch_)create_upload_url(s)`、
  `/rest/connectors/attachments/upload`
- **tasks/computer**：`/rest/tasks/`、`/rest/tasks/{task_id}`、`/rest/tasks/shortcuts/mentions`、
  `/rest/tasks/shortcuts/paste/{copy_token}`、`/rest/computer/asset`、`/rest/computer/menu`、
  `/rest/computer/onboarding_cards`
- **user/auth**：`/rest/user/settings`、`/rest/user/get_user_ai_profile`、`/rest/user/promotions`、
  `/rest/user/site-instructions`、`/rest/auth/get_special_profile`、`/rest/visitor/*`
- **billing/stripe**：`/rest/billing/*`（credits/paypal/subscription…）、`/rest/stripe/*`
- **enterprise/org**：`/rest/enterprise/*`、`/rest/organizations/{id}/credit-limits*`、
  `/rest/pplx-api/v2/enterprise-api-org`
- **sse**：`/rest/sse/attachment_processing/subscribe`、`/rest/sse/index_files`、
  `/rest/sse/perplexity_terminate`、`/rest/sse/related-queries/{entry_uuid}`
- **verticals**（與歸檔無關）：`/rest/finance/*`、`/rest/sports/*`、`/rest/travel/hotels/{slug}`、
  `/rest/health-assistant/*`、`/rest/article/{uuid_or_slug}`
- **misc**：`/rest/pins`、`/rest/rate-limit/(all|status)`、`/rest/notifications/web-push/*`、
  `/rest/attribution/*`、`/rest/homepage-widgets/upsell`、`/rest/ntp/upsell/`、`/rest/sidebar/upsell/`、
  `/rest/incentives/comet-activation`、`/rest/connector-service/usage`

（★ = 與歸檔直接相關）

<a id="端点-工具能力状态与路线图" data-pplx-source-anchor="true"></a>
## 端點 → 工具能力狀態與路線圖

下表的實現狀態已於 **2026-07-24** 對照當前代碼與測試套件同步。API 證據沿用原始
實時觀測或靜態分析的日期與範圍；本次文檔同步未重新探測私有端點。賬戶/歸檔數量
均為快照，不是平台範圍的恆定保證。

狀態含義：

- **已實現**——當前 CLI 或生產路徑已將端點用於表中所述能力。
- **部分實現**——端點已在使用，但路線圖中的下游能力尚未完成。
- **已實測、未集成**——線上 API 行為已有觀測，但工具沒有消費路徑。
- **計劃中**——已有證據，但尚未開始實現。
- **受阻**——存在明確的上游或協議阻塞。
- **已關閉**——證據已否定原用途，或該用途已確定不在範圍內。

<a id="能力状态矩阵" data-pplx-source-anchor="true"></a>
### 能力狀態矩陣

| 端點 / 操作 | 驗證依據 | 當前集成 | 狀態 | 剩餘缺口 |
|---|---|---|---|---|
| `collections/get_collection` | 實時觀測 + 當前代碼 | `spaces --fetch-meta` 構建空間所有者/成員索引 | **已實現** | — |
| `collections/list_collection_threads` | 實時觀測 + 當前代碼 | `space-index` 默認 REST，含 context_uuid 雙 ID 映射；WebBridge 為備用 | **已實現** | 排序與 `total_threads` 精確語義仍待確認 |
| `assets/<uuid>/data` | 2026-07-20 線上實測 + 當前代碼 | `assets-backfill --online` 為真實 asset UUID 刷新簽名 URL | **已實現** | 本端點不覆蓋 `toolu_` 雲工作區句柄 |
| `LibraryThreadsRelayQuery` 與翻頁查詢 | 已捕獲 APQ + 當前代碼 | `index`/`batch` 提供全量索引與增量早停 | **已實現** | 儀表板按模式查詢另行受阻 |
| `collections/list_user_collections` | 2026-07 線上觀測 + 當前代碼 | `init` 按標題精確匹配並發現 BOT 空間 | **部分實現** | 建立賬戶級權威空間註冊表，供新空間發現和 `spaces` 重建 |
| `credits/thread-usage` | 2026-07-20 線上實測 + 當前代碼 | `usage-backfill` 寫入 `index/credit_usage_<account>.json` | **部分實現** | 決定是否在不製造雙真源的前提下富化 `thread.json` 和/或 library 索引行 |
| `models/config/v2` | 2026-07-21 線上實測 + 當前代碼 | `pplx-ask models` 列模型/默認值；規範化常量據此交叉核驗 | **部分實現** | 如確有價值，再把穩定模型顯示元數據寫入歸檔/索引 |
| `POST /rest/thread/export` | 2026-07-20 已實測 md/pdf/docx | 無 CLI 集成 | **已實測、未集成** | 多格式歸檔與官方 Markdown 對賬 |
| `rate-limit/status` | 頁面加載觀測；響應語義未探索 | 無 | **計劃中** | 用於自適應限頻前先驗證語義 |
| `file-repository/list-files` | 僅前端靜態分析 | 無 | **計劃中** | 驗證能否枚舉/救援 `toolu_` 句柄；2026-07 歸檔快照記錄 270 個無下載通道句柄 |
| `pins`、`tasks/{id}` | 前端靜態分析 / 頁面加載觀測 | 無 | **計劃中** | 置頂狀態與 computer 任務時長富化 |
| `thread/<uuid>/members` | 2026-07 線上實測 | 無 | **計劃中** | 為 relations 圖提供線程級共享關係 |
| 儀表板 GraphQL `threadGroup` + 模式過濾 | 直調返回 `PERSISTED_QUERY_NOT_FOUND` | 無 | **受阻** | 恢復實時 persisted-query 哈希，或確認所需上下文 |
| `related_queries` / `sse/related-queries` | 2026-07-23 全庫取證定案 | 明確不生成關係邊 | **已關閉** | 僅在新證據能建立可解析線程身份時重開 |

<a id="活跃路线" data-pplx-source-anchor="true"></a>
### 活躍路線

<a id="p0官方导出集成" data-pplx-source-anchor="true"></a>
#### P0——官方導出集成

- **多格式歸檔**：可選保留 `POST /rest/thread/export` 返回的 PDF/DOCX 產物。
- **渲染器對賬**：以官方整線程 Markdown 對比 `conversation.md`，作為獨立回歸信號。

<a id="p1空间发现" data-pplx-source-anchor="true"></a>
#### P1——空間發現

- 將 `list_user_collections` 從 BOT 標題查找提升為賬戶級權威空間註冊表，用於
  新空間發現與 `spaces` 重建。

<a id="p2元数据风控与资产救援" data-pplx-source-anchor="true"></a>
#### P2——元數據、風控與資產救援

- 明確積分用量的真源邊界：只保留專用 `credit_usage_<account>.json`，還是同時
  富化 `thread.json` / library 索引行。
- 僅在端點語義穩定時加入模型顯示元數據、置頂狀態、computer 任務時長和線程共享關係。
- 設計自適應限頻前先驗證 `rate-limit/status`。
- 先驗證 `file-repository/list-files` 是否可作為 `toolu_` 救援路徑，再增加任何
  歸檔寫操作。

<a id="p3受阻的发现能力" data-pplx-source-anchor="true"></a>
#### P3——受阻的發現能力

- 僅當按模式增量索引的價值足以覆蓋維護成本時，重新捕獲儀表板 GraphQL 的
  persisted-query 哈希。

<a id="已关闭决定-不采用" data-pplx-source-anchor="true"></a>
### 已關閉決定 / 不採用

- **用官方 export 端點獲取報告正文**：已證偽。該端點返回整線程 Markdown，
  不含報告正文；簽名 URL 鏈仍是 `report.md` 的官方來源
  （[§3.6](api-rest-endpoints.md)）。
- **由 `related_queries` 建關係邊**：2026-07-23 已證偽。item UUID 不是線程 UUID，
  推薦文本也不能解析到歸檔 query；不建關係邊（[§4](api-responses-errors.md)）。
- `analytics/computer/usage(/members)`：測試賬戶觀測為組織專用
  （`403 NOT_ORG_MEMBER`）。
- `thread/request-access-info`：實測為組織加入相關，並非 `threadAccess` 信號。
- billing/Stripe/enterprise 與 finance/sports 等垂類不在歸檔工具範圍內。

---

*本文檔與 [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md)（工具架構）、[overview.md](../../architecture/overview.md)（系統設計）互補。*
