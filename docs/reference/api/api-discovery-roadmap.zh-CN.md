# 端点发现方法与改进路线图

*本文是 Perplexity Web API 参考的一部分——全图见 [API 索引](index.md)。*

## 已知未探索/待确认项

- `list_collection_threads` 的排序字段与 `total_threads` 精确语义
  （2026-07 实时账户快照：报告 99 vs 顶层 27 项）。
- `threadAccess`/`access`/`user_permission` 数值全谱（2026-07 观测样本：
  threadAccess 5 常规、1 带 🔒；collection access 1；permission 4 所有者 /
  2 可编辑；assets data 亦含 thread_access）。
- `list_ask_threads`、`list_scheduled_computer_tasks` 的正确参数形态（直接 GET 400）。
- `collections/*/request-access-info`、`spaces/<uuid>/recurring_tasks`、`assets/<id>/members` 响应结构。
- 仪表盘 GraphQL 操作为何未注册（PERSISTED_QUERY_NOT_FOUND）：版本错位 or 上下文门槛，
  需要时以线上网络捕获的实时哈希为准重新提取。
- `frontend_uuid` vs `uuid` vs `context_uuid` 三者在 computer 线程中的分工。
- 跨账户空间共享分叉线程（branch_of）的 API 信号字段（父线程指针/分叉标记）——
  机制已确认（[§3.3](api-rest-endpoints.md) 末），截至 2026-07-23 尚无归档实例，
  待首例出现时验证记录。

## 端点发现方法：前端 bundle 静态分析（零 API 成本，2026-07-20 建立）

一次发现 **147 个 `/rest/` 端点**，方法可复用（前端改版后重跑即可）：

1. 页面加载的入口 `_spa/assets/index.html-*.js` 引 `bootstrap-*.js`（运行时含全部 chunk 映射）；
2. 从 bootstrap 提取 682 个 chunk 文件名（模式 `<name>-<hash8>.js`），按名称筛 API 相关
   （client/api/thread/collection/space/computer…）；
3. 从公共 CDN `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js` 直接下载
   （无需 cookie）；中枢模块：`platform-core-*`（API client）、`spa-shell-*`、`spa-metadata-*`；
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` 得端点清单（147 个）；
5. chunk 同时泄露调用形态（如 export 的 `format:'md'` 与 `file_content_64`）。
6. 另有 sourcemap：`https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map`（未深入）。

### 附录：147 个端点按类分组（与归档相关性标注）

- **thread**：`/rest/thread/{entry_uuid_or_slug}`、`/rest/thread/export`★、`/rest/thread/{uuid}/members`、
  `/rest/thread/list_recent`、`/rest/thread/list_ask_threads`、`/rest/thread/list_pinned_ask_threads`、
  `/rest/thread/list_scheduled_computer_tasks`、`/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★：见 [§3.3](api-rest-endpoints.md) 全表（含 batch_move/batch_remove、list_user_collections、request-access-info、
  recurring_tasks、pins/threads、scheduled_threads）
- **assets**★：`/rest/assets/{asset_id}/data`、`/rest/assets/{asset_id}/members`、
  `/rest/assets/{asset_id}/published-access`、`/rest/assets/sites/{site_id}/publish-info`
- **analytics**：`/rest/analytics/computer/usage`、`/rest/analytics/computer/usage/members`
  （均 403 NOT_ORG_MEMBER——组织账户专用）
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
- **verticals**（与归档无关）：`/rest/finance/*`、`/rest/sports/*`、`/rest/travel/hotels/{slug}`、
  `/rest/health-assistant/*`、`/rest/article/{uuid_or_slug}`
- **misc**：`/rest/pins`、`/rest/rate-limit/(all|status)`、`/rest/notifications/web-push/*`、
  `/rest/attribution/*`、`/rest/homepage-widgets/upsell`、`/rest/ntp/upsell/`、`/rest/sidebar/upsell/`、
  `/rest/incentives/comet-activation`、`/rest/connector-service/usage`

（★ = 与归档直接相关）

## 端点 → 工具能力状态与路线图

下表的实现状态已于 **2026-07-24** 对照当前代码与测试套件同步。API 证据沿用原始
实时观测或静态分析的日期与范围；本次文档同步未重新探测私有端点。账户/归档数量
均为快照，不是平台范围的恒定保证。

状态含义：

- **已实现**——当前 CLI 或生产路径已将端点用于表中所述能力。
- **部分实现**——端点已在使用，但路线图中的下游能力尚未完成。
- **已实测、未集成**——线上 API 行为已有观测，但工具没有消费路径。
- **计划中**——已有证据，但尚未开始实现。
- **受阻**——存在明确的上游或协议阻塞。
- **已关闭**——证据已否定原用途，或该用途已确定不在范围内。

### 能力状态矩阵

| 端点 / 操作 | 验证依据 | 当前集成 | 状态 | 剩余缺口 |
|---|---|---|---|---|
| `collections/get_collection` | 实时观测 + 当前代码 | `spaces --fetch-meta` 构建空间所有者/成员索引 | **已实现** | — |
| `collections/list_collection_threads` | 实时观测 + 当前代码 | `space-index` 默认 REST，含 context_uuid 双 ID 映射；WebBridge 为备用 | **已实现** | 排序与 `total_threads` 精确语义仍待确认 |
| `assets/<uuid>/data` | 2026-07-20 线上实测 + 当前代码 | `assets-backfill --online` 为真实 asset UUID 刷新签名 URL | **已实现** | 本端点不覆盖 `toolu_` 云工作区句柄 |
| `LibraryThreadsRelayQuery` 与翻页查询 | 已捕获 APQ + 当前代码 | `index`/`batch` 提供全量索引与增量早停 | **已实现** | 仪表盘按模式查询另行受阻 |
| `collections/list_user_collections` | 2026-07 线上观测 + 当前代码 | `init` 按标题精确匹配并发现 BOT 空间 | **部分实现** | 建立账户级权威空间注册表，供新空间发现和 `spaces` 重建 |
| `credits/thread-usage` | 2026-07-20 线上实测 + 当前代码 | `usage-backfill` 写入 `index/credit_usage_<account>.json` | **部分实现** | 决定是否在不制造双真源的前提下富化 `thread.json` 和/或 library 索引行 |
| `models/config/v2` | 2026-07-21 线上实测 + 当前代码 | `pplx-ask models` 列模型/默认值；规范化常量据此交叉核验 | **部分实现** | 如确有价值，再把稳定模型显示元数据写入归档/索引 |
| `POST /rest/thread/export` | 2026-07-20 已实测 md/pdf/docx | 无 CLI 集成 | **已实测、未集成** | 多格式归档与官方 Markdown 对账 |
| `rate-limit/status` | 页面加载观测；响应语义未探索 | 无 | **计划中** | 用于自适应限频前先验证语义 |
| `file-repository/list-files` | 仅前端静态分析 | 无 | **计划中** | 验证能否枚举/救援 `toolu_` 句柄；2026-07 归档快照记录 270 个无下载通道句柄 |
| `pins`、`tasks/{id}` | 前端静态分析 / 页面加载观测 | 无 | **计划中** | 置顶状态与 computer 任务时长富化 |
| `thread/<uuid>/members` | 2026-07 线上实测 | 无 | **计划中** | 为 relations 图提供线程级共享关系 |
| 仪表盘 GraphQL `threadGroup` + 模式过滤 | 直调返回 `PERSISTED_QUERY_NOT_FOUND` | 无 | **受阻** | 恢复实时 persisted-query 哈希，或确认所需上下文 |
| `related_queries` / `sse/related-queries` | 2026-07-23 全库取证定案 | 明确不生成关系边 | **已关闭** | 仅在新证据能建立可解析线程身份时重开 |

### 活跃路线

#### P0——官方导出集成

- **多格式归档**：可选保留 `POST /rest/thread/export` 返回的 PDF/DOCX 产物。
- **渲染器对账**：以官方整线程 Markdown 对比 `conversation.md`，作为独立回归信号。

#### P1——空间发现

- 将 `list_user_collections` 从 BOT 标题查找提升为账户级权威空间注册表，用于
  新空间发现与 `spaces` 重建。

#### P2——元数据、风控与资产救援

- 明确积分用量的真源边界：只保留专用 `credit_usage_<account>.json`，还是同时
  富化 `thread.json` / library 索引行。
- 仅在端点语义稳定时加入模型显示元数据、置顶状态、computer 任务时长和线程共享关系。
- 设计自适应限频前先验证 `rate-limit/status`。
- 先验证 `file-repository/list-files` 是否可作为 `toolu_` 救援路径，再增加任何
  归档写操作。

#### P3——受阻的发现能力

- 仅当按模式增量索引的价值足以覆盖维护成本时，重新捕获仪表盘 GraphQL 的
  persisted-query 哈希。

### 已关闭决定 / 不采用

- **用官方 export 端点获取报告正文**：已证伪。该端点返回整线程 Markdown，
  不含报告正文；签名 URL 链仍是 `report.md` 的官方来源
  （[§3.6](api-rest-endpoints.md)）。
- **由 `related_queries` 建关系边**：2026-07-23 已证伪。item UUID 不是线程 UUID，
  推荐文本也不能解析到归档 query；不建关系边（[§4](api-responses-errors.md)）。
- `analytics/computer/usage(/members)`：测试账户观测为组织专用
  （`403 NOT_ORG_MEMBER`）。
- `thread/request-access-info`：实测为组织加入相关，并非 `threadAccess` 信号。
- billing/Stripe/enterprise 与 finance/sports 等垂类不在归档工具范围内。

---

*本文档与 [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md)（工具架构）、[overview.md](../../architecture/overview.md)（系统设计）互补。*
