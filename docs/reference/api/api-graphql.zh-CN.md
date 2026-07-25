# API 参考：GraphQL

## GraphQL（持久化查询 APQ）

- **端点**：`POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **形式**：persisted query——body 含 operationName + variables + sha256 哈希（无需 query 文本）。
- 实现：`pplx_export/sites/perplexity/graphql.py`。

### LibraryThreadsRelayQuery（列表首页）
- sha256：`a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- 变量：`{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- 响应路径：`data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- node 字段（适配器使用）：`name(title)`、`entryId(entryUUID)`、`slug(href)`、`mode`、`displayModel.modelID`、
  `updatedAt(lastUpdated)`、`status`、`space{spaceUuid,title,slug}`
- **归档侧契约（2026-07-22 V5-01）**：`web_archive/**/thread.json` 的 `lastUpdated` 恒等于本字段
  （ISO 全精度原样落盘）；批量/单导幂等比对（`is_unchanged`）以此为基准，不再使用
  渲染层展示格式（`YYYY-MM-DD HH:MM UTC`）。
- **归档侧富化（2026-07-23）**：索引落盘行（`index/library_*.json`）的 `search_mode` 键为
  归档侧富化字段——本查询的 node 不含 search_mode，由 `pplx-export search-mode-backfill`
  从线程级数据（`GET /rest/thread/<uuid>` 的 `entries[].search_mode`）补全（本地 raw 优先，
  联网兜底）；`index` 刷新按 entryUUID 合并保留。`batch --mode` 过滤优先走该字段的权威映射。

### LibraryRecentThreadsPaginationQuery（翻页）
- sha256：`4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- 变量：首页变量 + `{cursor, count}`（**变量名是 cursor/count，不是 after/first**）
- 响应结构同上。`hasNextPage` 为真但 `endCursor` 为空时必须停止（否则重复同页）。

### Computer 仪表盘操作组（2026-07-20 从 route chunk 提取，**服务器未注册**）

`ComputerDashboardPage-*.js` chunk 内嵌 Relay 完整查询文本 + persisted id（提取方法见 [§7](api-discovery-roadmap.md)）。
结构要点：`viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
——即按 threadGroup + mode 过滤的线程列表；node 含 `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`。

| operation | persisted id（前 16 位） |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…`（WebSocket 订阅） |

**实测**：以这些 id 调 `/rest/perplexity_ask/graphql` 返回 `PERSISTED_QUERY_NOT_FOUND`
（当前部署未注册——版本错位或需仪表盘上下文；完整查询文本与 id 已存 `/tmp` 探索记录，
需要时可改用 text 直发或重新从线上 bundle 提取）。

### 注意事项
- 网页端空间页/首页均未见 graphql 调用（全走 /rest）；graphql 确认用于 /library 列表与 computer 仪表盘。
- sha256 哈希随前端版本可能变化；失效表现为 `PERSISTED_QUERY_NOT_FOUND`——届时从浏览器
  网络捕获重新提取（WebBridge `network` 工具过滤 `perplexity_ask/graphql`），或从线上 bundle 重新提取（[§7](api-discovery-roadmap.md)）。

### 已提取的仪表盘 connection keys（Relay 缓存键，调试用）
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
