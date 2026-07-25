---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-graphql.zh-CN.md"
translation_source_sha256: "8abe002576d89da5b7dbcdbba673ce6423cf94c8944606f70e60addcf6268ac0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-参考graphql" data-pplx-source-anchor="true"></a>
# API 參考：GraphQL

<a id="graphql持久化查询-apq" data-pplx-source-anchor="true"></a>
## GraphQL（持久化查詢 APQ）

- **端點**：`POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **形式**：persisted query——body 含 operationName + variables + sha256 雜湊（無需 query 文字）。
- 實現：`pplx_export/sites/perplexity/graphql.py`。

<a id="librarythreadsrelayquery列表首页" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery（列表首頁）
- sha256：`a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- 變數：`{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- 回應路徑：`data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- node 欄位（配接器使用）：`name(title)`、`entryId(entryUUID)`、`slug(href)`、`mode`、`displayModel.modelID`、
  `updatedAt(lastUpdated)`、`status`、`space{spaceUuid,title,slug}`
- **歸檔側契約（2026-07-22 V5-01）**：`web_archive/**/thread.json` 的 `lastUpdated` 恆等於本欄位
  （ISO 全精度原樣落盤）；批次/單導冪等比對（`is_unchanged`）以此為基準，不再使用
  渲染層展示格式（`YYYY-MM-DD HH:MM UTC`）。
- **歸檔側富化（2026-07-23）**：索引落盤行（`index/library_*.json`）的 `search_mode` 鍵為
  歸檔側富化欄位——本查詢的 node 不含 search_mode，由 `pplx-export search-mode-backfill`
  從執行緒層級資料（`GET /rest/thread/<uuid>` 的 `entries[].search_mode`）補全（本地 raw 優先，
  聯網兜底）；`index` 重新整理按 entryUUID 合併保留。`batch --mode` 過濾優先走該欄位的權威對應。

<a id="libraryrecentthreadspaginationquery翻页" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery（翻頁）
- sha256：`4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- 變數：首頁變數 + `{cursor, count}`（**變數名是 cursor/count，不是 after/first**）
- 回應結構同上。`hasNextPage` 為真但 `endCursor` 為空時必須停止（否則重複同頁）。

<a id="computer-仪表盘操作组2026-07-20-从-route-chunk-提取服务器未注册" data-pplx-source-anchor="true"></a>
### Computer 儀表板操作組（2026-07-20 從 route chunk 提取，**伺服器未註冊**）

`ComputerDashboardPage-*.js` chunk 內嵌 Relay 完整查詢文字 + persisted id（提取方法見 [§7](api-discovery-roadmap.md)）。
結構要點：`viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
——即按 threadGroup + mode 過濾的執行緒列表；node 含 `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`。

| operation | persisted id（前 16 位） |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…`（WebSocket 訂閱） |

**實測**：以這些 id 調 `/rest/perplexity_ask/graphql` 返回 `PERSISTED_QUERY_NOT_FOUND`
（當前部署未註冊——版本錯位或需儀表板上下文；完整查詢文字與 id 已存 `/tmp` 探索記錄，
需要時可改用 text 直發或重新從線上 bundle 提取）。

<a id="注意事项" data-pplx-source-anchor="true"></a>
### 注意事項
- 網頁端空間頁/首頁均未見 graphql 呼叫（全走 /rest）；graphql 確認用於 /library 列表與 computer 儀表板。
- sha256 雜湊隨前端版本可能變化；失效表現為 `PERSISTED_QUERY_NOT_FOUND`——屆時從瀏覽器
  網路捕獲重新提取（WebBridge `network` 工具過濾 `perplexity_ask/graphql`），或從線上 bundle 重新提取（[§7](api-discovery-roadmap.md)）。

<a id="已提取的仪表盘-connection-keysrelay-缓存键调试用" data-pplx-source-anchor="true"></a>
### 已提取的儀表板 connection keys（Relay 快取鍵，偵錯用）
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
