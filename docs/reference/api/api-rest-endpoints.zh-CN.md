# API 参考：REST 端点

## REST 端点（按用途分组）

约定：`?version=2.18&source=default` 为通用查询串（多数端点必需）。

### 线程内容（导出主路径）
| 端点 | 说明 |
|---|---|
| `GET /rest/thread/<uuid>` | **普通（plain）响应**：`entries[]`（每轮，`text` 含全部步骤文本）、`background_entries[]`（**子代理完整工作流**）、`thread_metadata`。支持 `?cursor=` 翻页（`has_next_page`/`next_cursor`） |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **schematized 响应**：`entries[].blocks[]`（`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`），含子代理 prompt（`workflow_payload.objective_chunks`）、资产签名 URL、文件内容。use cases 见 `rest.py:SCHEMATIZED_USE_CASES`（workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown） |
| `GET /rest/thread/list_recent` | 最近线程列表（首页侧边栏用；含 `unread` 字段） |
| **`POST /rest/thread/mark_viewed`** | **已读回执（2026-07-21 破解）**：body `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`，unread 立即翻转。侧边栏点击进入线程时前端即调此端点。注意：analytics 的 "thread viewed" 事件**不翻转** unread（多次实测排除） |
| `GET /rest/thread/<uuid>/members` | **线程级共享成员**（已实测）：`{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | 返回 `{"will_request_org_join": bool, "org_display_name": str|null}`——是组织加入相关，**与 threadAccess 语义无关**（已实测排除） |
| `GET /rest/thread/list_ask_threads`、`/rest/thread/list_scheduled_computer_tasks` | 静态分析存在；直接 GET 实测 400（参数形态待确认） |

### 资产元数据（2026-07-20 探明，**过期资产救星**）

- **`GET /rest/assets/<asset_uuid>/data`** → 资产完整元数据（实测 200）：
  - `asset_data.<类型>.url` 与 `asset_data.download_info[].url`：**新鲜 CloudFront 签名 URL**——
    归档时若原签名 URL 已过期，可凭 asset_uuid 重新取回下载地址（资产未被平台清除的前提下）；
  - 同时给出 `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    （asset → 线程反查链）；
  - `signed_url: null`、`read_write_token`、`allow_remix` 等字段。
- **适用边界（已实测）**：真 asset uuid 可用；**`toolu_` 前缀的云工作区句柄（DOC_FILE/CODE_FILE
  无 URL 形态）返回 404 ASSET_NOT_FOUND**；`file-repository/download` 需真 URL，不接受
  `file:repo/...` 句柄（400 failed to parse）。toolu 类资产暂无 API 下载通道。
- 关联：`/rest/assets/<id>/members`、`/rest/assets/<id>/published-access`（静态分析存在，未实测）。
- 落地：工具已实现 `pplx-export assets-backfill`（内联提取 + 本端点在线刷新，见 [§4](api-responses-errors.md) 落地工具）。

- **ENTRY_EXPIRED**：约 3 个月前的线程/工件被平台清除，请求返回特定错误体——工具标记终态不再重试。
- **删除线程（2026-07-23 WebBridge + chunk 调研实测）**：
  `DELETE /rest/thread/delete_thread_by_entry_uuid`，body `{entry_uuid, read_write_token}`，
  成功 `200 {"status":"success"}`；重复删除幂等仍 200；删不存在的 uuid → 404 `THREAD_NOT_FOUND`；
  **`read_write_token` 获取（同日实战验证）**：`GET /rest/thread/<uuid>` 响应的
  `entries[].read_write_token` 首个非空值即可用（已对活线程验证 10/10 删除成功）；
  **写操作必须走 www 域**（裸域对 DELETE 返回 301）。无 GraphQL mutation、无批量删除端点
  （UI 批量删除是前端逐条循环）。删除即线程级销毁、不可恢复，线程自动从所在空间消失
  （无需先 `batch_remove_collection_threads` 移出）。
  软方案：`POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  （body `{context_uuids:[...]}`，仅静态未实测）。
- **ENTRY_DELETED**：线程被删除后 `GET /rest/thread/<uuid>` 返回 HTTP 400 `ENTRY_DELETED`
  （与 ENTRY_EXPIRED 同为 400 但 code 不同）——工具映射为 `EntryDeletedError`
  （`EntryExpiredError` 子类），batch_state 标记终态 `deleted`。
- 每轮 entry 含 `context_uuid`（= 平台 `past_session_contexts` UUID，双 ID 命名空间映射的关键）。

### 空间（collections）
| 端点 | 说明 |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **空间元数据**：`uuid/title/emoji/access/max_contributors`、`owner_user{username,email,name,permission}`、`contributor_users[]`、`user_permission`。permission 实测：4=所有者、2=可编辑。无权查看时返回 `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"`（HTTP 仍 200） |
| `POST /rest/collections/create_collection` | **创建空间**（2026-07-21 WebBridge 捕获实测）：body `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → 返回完整 collection（uuid/slug/url/user_permission=4）。BOT 空间即此所建 |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **空间线程列表（cookie 直连，可替代浏览器版 space-index）**：响应为数组，每项含 `uuid`(=entryUUID)、`context_uuid`、`frontend_uuid`、`author_username`、`title`、`mode`、`last_query_datetime`、`thread_access`、`answer_preview` 等。**分页：`&offset=N`（每页 20）**，`has_next_page` 在每项上；`total_threads` 语义偏大（含 computer 子线程，观测 99 vs 顶层 27） |
| `POST /rest/collections/batch_move_threads` | **移动线程入空间**（实测 succeeded）：body `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}`——**用 context_uuid 不是 entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | 批量移出空间（body `{items:[{collection_uuid,...}]}`，未实测） |
| `GET /rest/collections/list_user_collections` | **当前账户空间列表**（实测 16 个）：每项含 `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page` 等，比 list_recent 信息全 |
| `GET /rest/collections/list_recent` | 当前账户最近空间列表（`title/uuid/emoji/is_pinned/link`，实测 5 项） |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | 空间访问申请信息（未实测） |
| `GET /rest/collections/<uuid>/join-requests` | 加入申请（未深入） |
| `GET /rest/spaces/<uuid>/tasks` | 返回 `{"tasks":[]}`——观测为空；疑为空间的定时/computer 任务，非线程列表 |
| `GET /rest/spaces/<uuid>/recurring_tasks` | 周期任务（未实测） |
| `GET /rest/spaces/<uuid>/pins/threads`、`/scheduled_threads` | 空间置顶/定时线程（页面加载时调用，未深入） |

- **跨账户分叉（branch_of，用户实测认知 2026-07-23）**：空间共享的线程可被另一成员账户
  「继续」为一个**仅该账户可见、由该账户继续**的分叉线程——A 账户线程经空间共享后，
  B 可继续生成 B 私有分叉。归档库尚无实例，relations 边暂不实现；分叉线程的 API 信号字段
  （父线程指针/分叉标记）待首例出现时验证记录。

### 账户/会话
| 端点 | 说明 |
|---|---|
| `GET /api/auth/session` | 当前会话 `{user:{email,...}}`——账户校验与自动切换探测用 |
| `GET /api/auth/linked-accounts` | 见 [§1.2](api-authentication.md)（primary 生效时才全量） |
| `GET /rest/user/info`、`/rest/user/settings` | 用户资料/设置（未深入） |

### 积分用量（2026-07-20 探明）

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → 单线程积分用量（实测 200）：
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **注意**：`thread_id` 要 **context_uuid**（psc_uuid），传 entryUUID 会 403
  `thread_usage_forbidden`（"Thread does not belong to the current user"，实为 id 形态错误）。
- context_uuid 来源：`list_collection_threads`（space-index REST 版已 27/27 覆盖）、
  线程条目 `context_uuid` 字段（归档 thread.json 的 `psc_uuid`）。
- 仅本账户线程可查（跨账户 403）——多账户抓取需逐账户自动切换。
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`：列表版，两个账户实测均返回空
  （疑组织账单专用，待用）。
- 其他 billing 端点（`/rest/billing/credits/balance` 等）见 [§7 附录](api-discovery-roadmap.md)，未深入。

### 官方导出（页面「导出」按钮的后端，2026-07-20 探明）

- **`POST /rest/thread/export`**，body：`{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<名称>"}`
- 响应：`{"file_content_64": "<base64>", "filename": "..."}`
- 实测 format：**`md`**（带 logo `<img>` 头的官方 markdown）、**`pdf`**（%PDF 二进制 ~880KB）、
  **`docx`**（PK zip ~350KB）——均 HTTP 200。其他格式值未试。
- **内容边界（实测核实）**：返回的是**整线程** markdown（query + answer 摘要 + `[^1_N]` 脚注引文），
  **不含 RESEARCH_REPORT 报告正文**——深研报告本体只能经其签名 URL 取得（§3.7），
  即当前 report.md 的签名 URL 链路**就是官方报告源**（与页面工件面板下载同源），无需改用本端点。
- 价值：官方线程版 markdown 可作 conversation 级交叉验证源（官方渲染的引文脚注/格式）。

### 资产/报告下载
- schematized 响应中的 **CloudFront 签名 URL**（`d2z0o16i8xm8ak.cloudfront.net`）：urllib 直连下载，
  无需 cookie/鉴权；多版本文件按 `created_at` 排序编号。
- 研究报告备用源：RESEARCH_ANSWER 步骤的 S3 URL（`ppl-ai-file-upload.s3.amazonaws.com`，**会过期**）；
  再备用页面渲染提取（KaTeX `<annotation>`）。
- **约 3 个月清除**：工件/报告源链接过期不可恢复——导出必须及时。

### 其他观测到的端点（页面加载，未深入）
`/rest/models/config(/v2)`、`/rest/sources`、`/rest/rate-limit/status`、`/rest/assets/pins`、
`/rest/file-repository/list-files`、`/rest/files/list`、`/rest/notifications/in-app/unread-count`、
`/rest/billing/*`、`/rest/sse/recent_thread_updates`（SSE）、`/api/version`。

### 消息提交与遥测（2026-07-20 WebBridge + CDP 探明）

#### 提交端点：`POST /rest/sse/perplexity_ask`
- 完整请求体样本（合成示例）见 `docs/perplexity-api-samples/`：
  - `ask_envelope_deep_research.json`——deep-research 续轮（2026-07-20；39 个 params + query_str）：
    `model_preference: "pplx_alpha"`、`query_source: "followup"` + `last_backend_uuid` 续链
  - `ask_envelope_search.json`——标准搜索、首页发起新对话（2026-07-21；35 个 params + query_str）：
    `model_preference: "pplx_pro"`、`query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json`——模型委员会、首页发起新对话（2026-07-21；36 个 params + query_str）：
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- 关键字段（deep-research 续轮实测）：
  - `mode: "copilot"`（深度研究）；`model_preference: "pplx_alpha"`
  - **续对话链**：`last_backend_uuid`（上一轮 backend uuid）+ `query_source: "followup"`
  - `frontend_uuid`（本轮新 uuid）、`read_write_token`、`target_collection_uuid`（所在空间）、
    `target_thread_access_level: 1`
  - `search_focus: internet`、`sources: ["web"]`、`language: zh-CN`、`timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`**（从首次键入到提交的毫秒——行为遥测随提交一并上报）
  - `use_schematized_api: true`、`supported_block_use_cases`（完整块列表，与 §3.1 schematized 对应）、
    `supported_features: ["browser_agent_permission_banner_v1.1"]`、`skip_search_enabled: true`
- 响应为 SSE 流（前端以 fetch-event-source `getReader()` 消费——app 模块初始化时固化 fetch 引用，
  **页面后挂 fetch/XHR hook 无效**；且**流式响应体浏览器不保留**（`Network.getResponseBody` 返回
  No data found）——抓包只能靠 CDP `Network.getRequestPostData`（请求体可用）。
- 流内容最终态即 `/rest/thread/<uuid>` 的 entries/blocks（同一份数据，增量投递）——
  导出工具无需读流，直接拉终态即可。

#### 遥测：`POST /rest/event/analytics`（批量、高频）
实测事件（含 event_data 要点）：
| event_name | 关键字段 | 说明 |
|---|---|---|
| `thread viewed` | `authorId`、`authorUsername`、`isThreadCreator`、`contextUUID` | 页面查看事件——**不翻转 unread**（已实测排除；真正已读回执是 `POST /rest/thread/mark_viewed`，见 §3.1） |
| `thread entry exited` | `entryUUID`、`timeOnEntryMs`（**该轮阅读停留毫秒**）、`userId`、`isPro`、`deviceInfo`（并发数/屏幕/色深） | 阅读时长遥测（不翻转 unread，已实测排除） |
| `ask input submit button clicked` | `querySource: followup`、`searchMode: research`、`isFollowUp` | 提交动作 |
| `query first llm token` | `startLLMTokenElapsed`（首 token 延迟）、完整 `queryStr` | 性能遥测 |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`、完整 `queryStr` | 成功回执 |
| `ask input model selector opened` | `searchMode: "agentic_research"`、`multiple: true`、`selectedModels` | 委员会模型选择器交互 |
| `ask context pane viewed` | `pane_mode`、`context_uuid` | 右侧面板查看 |
- 事件公共字段：`userId`、`visitor_id`、`timezone`、`language`、`screen`、`device_info`（hardwareConcurrency/屏幕/色深/architecture）、`isBrowserExtension`、`web_platform`。
- **注意**：实测某事件携带的 `userId` 为**另一账户**的 uid（uid 属账户 A，而 session 已是账户 B）——
  遥测 SDK 的 profile id 有缓存滞后，不能凭遥测 userId 判断当前账户。
- 另有 datadog RUM（`browser-intake-datadoghq.com/api/v2/rum`）高频上报（滚动/鼠标/性能，内容未解析）。

#### 模式与模型选择（2026-07-21 付费账户实测）
- **`GET /rest/models/config/v2` = 权威模型总表**：`models{id→{label,mode,provider}}`、
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`、`agentic_research_compare_models`（委员会默认三模型）。
  `pplx-ask models` 即调此端点。
  - 官方对应（实测）：**search = `pplx_pro`（UI 名「最佳」）、research = `pplx_alpha`
    （UI 名「Deep research」）**。
  - search 模式 UI 可选模型清单（无 Deep research）：最佳（pplx_pro）、Sonar 2、
    GPT-5.6 Terra、GPT-5.6 Sol、Gemini 3.1 Pro、Claude Sonnet 5、Claude Opus 4.8、
    GLM 5.2、Kimi K2.6、Grok 4.5、Nemotron 3 Ultra。
- **`mode` 字段恒为 `"copilot"`，不是模式判别字段**（搜索/深度研究/模型委员会都一样）。
- 判别在 **`model_preference`**：
  - 搜索：`pplx_pro`（或用户所选模型 id，如 `experimental`=Sonar 2、`gpt56_sol`…）
  - 深度研究：`pplx_alpha`（**UI 无模型选择器**，固定）
  - **模型委员会**：`pplx_agentic_research` + **`compare_model_preferences: [<2-3 模型>]`**
    （实测默认 `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`；
    UI 为**逐槽位单选**，追问时模型数变 2）。
  - 逐步学习：`pplx_study`；Computer：`pplx_asi*` 系列。
- 撰写区模型选择器（模型 ⌄）与委员会「N 个模型 ⌄」选择器分别对应上述字段；
  遥测事件 `ask input model selector opened` 携带 `searchMode: "agentic_research"`、
  `multiple: true`、`selectedModels`（此前深研线程为 `searchMode: "research"`）。
- 新对话：`query_source: "home"`、无 `last_backend_uuid`、有 `frontend_context_uuid`；
  续对话：`query_source: "followup"` + `last_backend_uuid` 续链。

#### entry.search_mode：会话模式的权威记录字段（2026-07-22 定案）
`/rest/thread/<uuid>` 的**每条 entry** 自带 `search_mode`，是平台对该轮会话模式的权威记录
（模式判别最高优先级信号，`normalize.SEARCH_MODE_MAP`）：

| search_mode | 含义（UI/模型） | 归档模式 |
|---|---|---|
| `SEARCH` | 普通搜索（default_models.search=pplx_pro「最佳」及 UI 可选模型） | search |
| `STUDIO` | labs 会话（pplx_beta），UI 归在 search 侧 | search |
| `RESEARCH` | Deep research（default_models.research=pplx_alpha，UI 固定无选择器） | deep-research |
| `AGENTIC_RESEARCH` | 模型委员会（pplx_agentic_research + compare_model_preferences） | council |
| `STUDY` | 逐步学习（pplx_study） | study |
| `ASI` | Computer（pplx_asi*） | computer |

- 归档全量取值实测：六种取值在真实归档库中均有实例，SEARCH 与 RESEARCH 占绝大多数，
  STUDIO 次之，ASI / STUDY / AGENTIC_RESEARCH 为少数。
- **pplx_alpha ⟺ RESEARCH 互证**：归档百余个平台 SEARCH 入口+pplx_alpha 线程 100%
  `search_mode=RESEARCH`；百余个纯 pplx_pro 线程全为 `search_mode=SEARCH`——
  「pplx_alpha 是普通 search 常用模型」的旧统计实为分类器误判样本，不成立。
- 线程内可出现多值（模式切换，如实测 SEARCH+RESEARCH 混合）：判别按特异性
  computer>council>study>deep-research>search 取最高。

#### 模型委员会输出结构与展开行为
- 单轮产出 = N 个模型各自的「Council: <模型名>」区块（各含检索词/来源/答案）+ 综合部分：
  **Where Models Agree**（共识矩阵，逐条 Finding 三模型✓对照 + Evidence）、
  **Where Models Disagree**（分歧表，各模型立场 + 差异原因）、
  **Unique Discoveries**（各模型独特发现），最后附相关问题推荐——**全部在同一个 SSE 流中下发**。
- 展开行为（含**生成中**展开）：展开行是带「>」chevron 的行（步骤行/「来源」行/Council 行），
  点击即展开，**纯客户端渲染，零内容请求**——本会话 1208 个请求中 921 个是 favicon/字体等静态资源，
  展开动作本身只触发 favicon 加载与 /api/version。流式期间展开不干扰流的继续下发。
- 首 token 延迟实测 ~204s（三模型并行生成，明显长于单模型）；来源计数实测 236。
- 撰写区（Lexical）自动化要点：文本须用 CDP `Input.insertText` 注入（execCommand/fill 后
  Lexical 内部状态不同步、Enter 无效）；提交可用 CDP Enter 或点 aria-label="提交" 的按钮
  （委员会模式有显式提交箭头）。

#### 续历史对话的行为特征（2026-07-20 实测）
1. 加载线程页 → `session`、`assets/pins`、`billing/credits/computer-submit-gate`、`cdn-cgi/trace`。
2. 提交追问 → `rate-limit/status` → `sse/perplexity_ask`（带 `last_backend_uuid` 续链）→ 高频 analytics。
3. 生成中 → SSE 流增量渲染；完成后再一批 analytics（含 `thread entry exited` 阅读时长）。
4. deep-research 续轮同样产出报告结构（本轮 5 步骤完成）。
