---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-rest-endpoints.zh-CN.md"
translation_source_sha256: "38129b3e7bf3833341615d818dc6e81c57bb7f290df912c314acd50a0de08772"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-参考rest-端点" data-pplx-source-anchor="true"></a>
# API 參考：REST 端點

<a id="rest-端点按用途分组" data-pplx-source-anchor="true"></a>
## REST 端點（按用途分組）

約定：`?version=2.18&source=default` 為通用查詢字串（多數端點必需）。

<a id="线程内容导出主路径" data-pplx-source-anchor="true"></a>
### 執行緒內容（匯出主路徑）
| 端點 | 說明 |
|---|---|
| `GET /rest/thread/<uuid>` | **普通（plain）回應**：`entries[]`（每輪，`text` 含全部步驟文字）、`background_entries[]`（**子代理完整工作流程**）、`thread_metadata`。支援 `?cursor=` 翻頁（`has_next_page`/`next_cursor`） |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **schematized 回應**：`entries[].blocks[]`（`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`），含子代理提示（`workflow_payload.objective_chunks`）、資產簽名 URL、檔案內容。使用案例見 `rest.py:SCHEMATIZED_USE_CASES`（workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown） |
| `GET /rest/thread/list_recent` | 最近執行緒列表（首頁側邊欄用；含 `unread` 欄位） |
| **`POST /rest/thread/mark_viewed`** | **已讀回條（2026-07-21 破解）**：body `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`，unread 立即翻轉。側邊欄點擊進入執行緒時前端即調用此端點。注意：analytics 的 "thread viewed" 事件**不翻轉** unread（多次實測排除） |
| `GET /rest/thread/<uuid>/members` | **執行緒級共享成員**（已實測）：`{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | 返回 `{"will_request_org_join": bool, "org_display_name": str|null}`——是組織加入相關，**與 threadAccess 語義無關**（已實測排除） |
| `GET /rest/thread/list_ask_threads`、`/rest/thread/list_scheduled_computer_tasks` | 靜態分析存在；直接 GET 實測 400（參數型態待確認） |

<a id="资产元数据2026-07-20-探明过期资产救星" data-pplx-source-anchor="true"></a>
### 資產元數據（2026-07-20 探明，**過期資產救星**）

- **`GET /rest/assets/<asset_uuid>/data`** → 資產完整元數據（實測 200）：
  - `asset_data.<类型>.url` 與 `asset_data.download_info[].url`：**新鮮 CloudFront 簽名 URL**——
    歸檔時若原簽名 URL 已過期，可憑 asset_uuid 重新取回下載地址（資產未被平台清除的前提下）；
  - 同時給出 `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    （asset → 執行緒反查鏈）；
  - `signed_url: null`、`read_write_token`、`allow_remix` 等欄位。
- **適用邊界（已實測）**：真 asset uuid 可用；**`toolu_` 前綴的雲工作區句柄（DOC_FILE/CODE_FILE
  無 URL 型態）返回 404 ASSET_NOT_FOUND**；`file-repository/download` 需真 URL，不接受
  `file:repo/...` 句柄（400 failed to parse）。toolu 類資產暫無 API 下載通道。
- 關聯：`/rest/assets/<id>/members`、`/rest/assets/<id>/published-access`（靜態分析存在，未實測）。
- 落地：工具已實現 `pplx-export assets-backfill`（內聯提取 + 本端點在線刷新，見 [§4](api-responses-errors.md) 落地工具）。

- **ENTRY_EXPIRED**：約 3 個月前的執行緒/工件被平台清除，請求返回特定錯誤體——工具標記終態不再重試。
- **刪除執行緒（2026-07-23 WebBridge + chunk 調研實測）**：
  `DELETE /rest/thread/delete_thread_by_entry_uuid`，body `{entry_uuid, read_write_token}`，
  成功 `200 {"status":"success"}`；重複刪除冪等仍 200；刪不存在的 uuid → 404 `THREAD_NOT_FOUND`；
  **`read_write_token` 獲取（同日實戰驗證）**：`GET /rest/thread/<uuid>` 回應的
  `entries[].read_write_token` 首個非空值即可用（已對活執行緒驗證 10/10 刪除成功）；
  **寫操作必須走 www 域**（裸域對 DELETE 返回 301）。無 GraphQL mutation、無批量刪除端點
  （UI 批量刪除是前端逐條循環）。刪除即執行緒級銷毀、不可恢復，執行緒自動從所在空間消失
  （無需先 `batch_remove_collection_threads` 移出）。
  軟方案：`POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  （body `{context_uuids:[...]}`，僅靜態未實測）。
- **ENTRY_DELETED**：執行緒被刪除後 `GET /rest/thread/<uuid>` 返回 HTTP 400 `ENTRY_DELETED`
  （與 ENTRY_EXPIRED 同為 400 但 code 不同）——工具映射為 `EntryDeletedError`
  （`EntryExpiredError` 子類），batch_state 標記終態 `deleted`。
- 每輪 entry 含 `context_uuid`（= 平台 `past_session_contexts` UUID，雙 ID 命名空間映射的關鍵）。

<a id="空间collections" data-pplx-source-anchor="true"></a>
### 空間（collections）
| 端點 | 說明 |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **空間元數據**：`uuid/title/emoji/access/max_contributors`、`owner_user{username,email,name,permission}`、`contributor_users[]`、`user_permission`。permission 實測：4=所有者、2=可編輯。無權查看時返回 `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"`（HTTP 仍 200） |
| `POST /rest/collections/create_collection` | **建立空間**（2026-07-21 WebBridge 捕獲實測）：body `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → 返回完整 collection（uuid/slug/url/user_permission=4）。BOT 空間即此所建 |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **空間執行緒列表（cookie 直連，可替代瀏覽器版 space-index）**：回應為陣列，每項含 `uuid`(=entryUUID)、`context_uuid`、`frontend_uuid`、`author_username`、`title`、`mode`、`last_query_datetime`、`thread_access`、`answer_preview` 等。**分頁：`&offset=N`（每頁 20）**，`has_next_page` 在每項上；`total_threads` 語義偏大（含 computer 子執行緒，觀測 99 vs 頂層 27） |
| `POST /rest/collections/batch_move_threads` | **移動執行緒入空間**（實測 succeeded）：body `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}`——**用 context_uuid 不是 entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | 批量移出空間（body `{items:[{collection_uuid,...}]}`，未實測） |
| `GET /rest/collections/list_user_collections` | **當前帳戶空間列表**（實測 16 個）：每項含 `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page` 等，比 list_recent 資訊全 |
| `GET /rest/collections/list_recent` | 當前帳戶最近空間列表（`title/uuid/emoji/is_pinned/link`，實測 5 項） |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | 空間訪問申請資訊（未實測） |
| `GET /rest/collections/<uuid>/join-requests` | 加入申請（未深入） |
| `GET /rest/spaces/<uuid>/tasks` | 返回 `{"tasks":[]}`——觀測為空；疑為空間的定時/computer 任務，非執行緒列表 |
| `GET /rest/spaces/<uuid>/recurring_tasks` | 週期任務（未實測） |
| `GET /rest/spaces/<uuid>/pins/threads`、`/scheduled_threads` | 空間置頂/定時執行緒（頁面載入時調用，未深入） |

- **跨帳戶分叉（branch_of，用戶實測認知 2026-07-23）**：空間共享的執行緒可被另一成員帳戶
  「繼續」為一個**僅該帳戶可見、由該帳戶繼續**的分叉執行緒——A 帳戶執行緒經空間共享後，
  B 可繼續生成 B 私有分叉。歸檔庫尚無實例，relations 邊暫不實現；分叉執行緒的 API 信號欄位
  （父執行緒指標/分叉標記）待首例出現時驗證記錄。

<a id="账户会话" data-pplx-source-anchor="true"></a>
### 帳戶/會話
| 端點 | 說明 |
|---|---|
| `GET /api/auth/session` | 當前會話 `{user:{email,...}}`——帳戶校驗與自動切換探測用 |
| `GET /api/auth/linked-accounts` | 見 [§1.2](api-authentication.md)（primary 生效時才全量） |
| `GET /rest/user/info`、`/rest/user/settings` | 用戶資料/設定（未深入） |

<a id="积分用量2026-07-20-探明" data-pplx-source-anchor="true"></a>
### 積分用量（2026-07-20 探明）

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → 單執行緒積分用量（實測 200）：
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **注意**：`thread_id` 要 **context_uuid**（psc_uuid），傳 entryUUID 會 403
  `thread_usage_forbidden`（"Thread does not belong to the current user"，實為 id 型態錯誤）。
- context_uuid 來源：`list_collection_threads`（space-index REST 版已 27/27 覆蓋）、
  執行緒條目 `context_uuid` 欄位（歸檔 thread.json 的 `psc_uuid`）。
- 僅本帳戶執行緒可查（跨帳戶 403）——多帳戶抓取需逐帳戶自動切換。
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`：列表版，兩個帳戶實測均返回空
  （疑組織帳單專用，待用）。
- 其他 billing 端點（`/rest/billing/credits/balance` 等）見 [§7 附錄](api-discovery-roadmap.md)，未深入。

<a id="官方导出页面导出按钮的后端2026-07-20-探明" data-pplx-source-anchor="true"></a>
### 官方匯出（頁面「匯出」按鈕的後端，2026-07-20 探明）

- **`POST /rest/thread/export`**，body：`{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<名称>"}`
- 回應：`{"file_content_64": "<base64>", "filename": "..."}`
- 實測 format：**`md`**（帶 logo `<img>` 頭的官方 markdown）、**`pdf`**（%PDF 二進位 ~880KB）、
  **`docx`**（PK zip ~350KB）——均 HTTP 200。其他格式值未試。
- **內容邊界（實測核實）**：返回的是**整執行緒** markdown（query + answer 摘要 + `[^1_N]` 腳註引文），
  **不含 RESEARCH_REPORT 報告正文**——深研報告本體只能經其簽名 URL 取得（§3.7），
  即當前 report.md 的簽名 URL 鏈路**就是官方報告源**（與頁面工件面板下載同源），無需改用本端點。
- 價值：官方執行緒版 markdown 可作 conversation 級交叉驗證源（官方渲染的引文腳註/格式）。

<a id="资产报告下载" data-pplx-source-anchor="true"></a>
### 資產/報告下載
- schematized 回應中的 **CloudFront 簽名 URL**（`d2z0o16i8xm8ak.cloudfront.net`）：urllib 直連下載，
  無需 cookie/鑑權；多版本檔案按 `created_at` 排序編號。
- 研究報告備用源：RESEARCH_ANSWER 步驟的 S3 URL（`ppl-ai-file-upload.s3.amazonaws.com`，**會過期**）；
  再備用頁面渲染提取（KaTeX `<annotation>`）。
- **約 3 個月清除**：工件/報告源連結過期不可恢復——匯出必須及時。

<a id="其他观测到的端点页面加载未深入" data-pplx-source-anchor="true"></a>
### 其他觀測到的端點（頁面載入，未深入）
`/rest/models/config(/v2)`、`/rest/sources`、`/rest/rate-limit/status`、`/rest/assets/pins`、
`/rest/file-repository/list-files`、`/rest/files/list`、`/rest/notifications/in-app/unread-count`、
`/rest/billing/*`、`/rest/sse/recent_thread_updates`（SSE）、`/api/version`。

<a id="消息提交与遥测2026-07-20-webbridge-cdp-探明" data-pplx-source-anchor="true"></a>
### 訊息提交與遙測（2026-07-20 WebBridge + CDP 探明）

<a id="提交端点post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### 提交端點：`POST /rest/sse/perplexity_ask`
- 完整請求體樣本（合成示例）見 `docs/perplexity-api-samples/`：
  - `ask_envelope_deep_research.json`——deep-research 續輪（2026-07-20；39 個 params + query_str）：
    `model_preference: "pplx_alpha"`、`query_source: "followup"` + `last_backend_uuid` 續鏈
  - `ask_envelope_search.json`——標準搜尋、首頁發起新對話（2026-07-21；35 個 params + query_str）：
    `model_preference: "pplx_pro"`、`query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json`——模型委員會、首頁發起新對話（2026-07-21；36 個 params + query_str）：
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- 關鍵欄位（deep-research 續輪實測）：
  - `mode: "copilot"`（深度研究）；`model_preference: "pplx_alpha"`
  - **續對話鏈**：`last_backend_uuid`（上一輪 backend uuid）+ `query_source: "followup"`
  - `frontend_uuid`（本輪新 uuid）、`read_write_token`、`target_collection_uuid`（所在空間）、
    `target_thread_access_level: 1`
  - `search_focus: internet`、`sources: ["web"]`、`language: zh-CN`、`timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`**（從首次鍵入到提交的毫秒——行為遙測隨提交一併上報）
  - `use_schematized_api: true`、`supported_block_use_cases`（完整區塊列表，與 §3.1 schematized 對應）、
    `supported_features: ["browser_agent_permission_banner_v1.1"]`、`skip_search_enabled: true`
- 回應為 SSE 流（前端以 fetch-event-source `getReader()` 消費——app 模組初始化時固化 fetch 引用，
  **頁面後掛 fetch/XHR hook 無效**；且**流式回應體瀏覽器不保留**（`Network.getResponseBody` 返回
  No data found）——抓包只能靠 CDP `Network.getRequestPostData`（請求體可用）。
- 流內容最終態即 `/rest/thread/<uuid>` 的 entries/blocks（同一份資料，增量投遞）——
  匯出工具無需讀流，直接拉終態即可。

<a id="遥测post-resteventanalytics批量高频" data-pplx-source-anchor="true"></a>
#### 遙測：`POST /rest/event/analytics`（批量、高頻）
實測事件（含 event_data 要點）：
| event_name | 關鍵欄位 | 說明 |
|---|---|---|
| `thread viewed` | `authorId`、`authorUsername`、`isThreadCreator`、`contextUUID` | 頁面檢視事件——**不翻轉 unread**（已實測排除；真正已讀回條是 `POST /rest/thread/mark_viewed`，見 §3.1） |
| `thread entry exited` | `entryUUID`、`timeOnEntryMs`（**該輪閱讀停留毫秒**）、`userId`、`isPro`、`deviceInfo`（並發數/螢幕/色深） | 閱讀時長遙測（不翻轉 unread，已實測排除） |
| `ask input submit button clicked` | `querySource: followup`、`searchMode: research`、`isFollowUp` | 提交動作 |
| `query first llm token` | `startLLMTokenElapsed`（首 token 延遲）、完整 `queryStr` | 效能遙測 |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`、完整 `queryStr` | 成功回條 |
| `ask input model selector opened` | `searchMode: "agentic_research"`、`multiple: true`、`selectedModels` | 委員會模型選擇器互動 |
| `ask context pane viewed` | `pane_mode`、`context_uuid` | 右側面板檢視 |
- 事件公共欄位：`userId`、`visitor_id`、`timezone`、`language`、`screen`、`device_info`（hardwareConcurrency/螢幕/色深/architecture）、`isBrowserExtension`、`web_platform`。
- **注意**：實測某事件攜帶的 `userId` 為**另一帳戶**的 uid（uid 屬帳戶 A，而 session 已是帳戶 B）——
  遙測 SDK 的 profile id 有快取滯後，不能憑遙測 userId 判斷當前帳戶。
- 另有 datadog RUM（`browser-intake-datadoghq.com/api/v2/rum`）高頻上報（滾動/滑鼠/效能，內容未解析）。

<a id="模式与模型选择2026-07-21-付费账户实测" data-pplx-source-anchor="true"></a>
#### 模式與模型選擇（2026-07-21 付費帳戶實測）
- **`GET /rest/models/config/v2` = 權威模型總表**：`models{id→{label,mode,provider}}`、
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`、`agentic_research_compare_models`（委員會預設三模型）。
  `pplx-ask models` 即調用此端點。
  - 官方對應（實測）：**search = `pplx_pro`（UI 名「最佳」）、research = `pplx_alpha`
    （UI 名「Deep research」）**。
  - search 模式 UI 可選模型清單（無 Deep research）：最佳（pplx_pro）、Sonar 2、
    GPT-5.6 Terra、GPT-5.6 Sol、Gemini 3.1 Pro、Claude Sonnet 5、Claude Opus 4.8、
    GLM 5.2、Kimi K2.6、Grok 4.5、Nemotron 3 Ultra。
- **`mode` 欄位恆為 `"copilot"`，不是模式判別欄位**（搜尋/深度研究/模型委員會都一樣）。
- 判別在 **`model_preference`**：
  - 搜尋：`pplx_pro`（或用戶所選模型 id，如 `experimental`=Sonar 2、`gpt56_sol`…）
  - 深度研究：`pplx_alpha`（**UI 無模型選擇器**，固定）
  - **模型委員會**：`pplx_agentic_research` + **`compare_model_preferences: [<2-3 模型>]`**
    （實測預設 `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`；
    UI 為**逐槽位單選**，追問時模型數變 2）。
  - 逐步學習：`pplx_study`；Computer：`pplx_asi*` 系列。
- 撰寫區模型選擇器（模型 ⌄）與委員會「N 個模型 ⌄」選擇器分別對應上述欄位；
  遙測事件 `ask input model selector opened` 攜帶 `searchMode: "agentic_research"`、
  `multiple: true`、`selectedModels`（此前深研執行緒為 `searchMode: "research"`）。
- 新對話：`query_source: "home"`、無 `last_backend_uuid`、有 `frontend_context_uuid`；
  續對話：`query_source: "followup"` + `last_backend_uuid` 續鏈。

<a id="entrysearch_mode会话模式的权威记录字段2026-07-22-定案" data-pplx-source-anchor="true"></a>
#### entry.search_mode：會話模式的權威記錄欄位（2026-07-22 定案）
`/rest/thread/<uuid>` 的**每條 entry** 自帶 `search_mode`，是平台對該輪會話模式的權威記錄
（模式判別最高優先級訊號，`normalize.SEARCH_MODE_MAP`）：

| search_mode | 含義（UI/模型） | 歸檔模式 |
|---|---|---|
| `SEARCH` | 普通搜尋（default_models.search=pplx_pro「最佳」及 UI 可選模型） | search |
| `STUDIO` | labs 會話（pplx_beta），UI 歸在 search 側 | search |
| `RESEARCH` | Deep research（default_models.research=pplx_alpha，UI 固定無選擇器） | deep-research |
| `AGENTIC_RESEARCH` | 模型委員會（pplx_agentic_research + compare_model_preferences） | council |
| `STUDY` | 逐步學習（pplx_study） | study |
| `ASI` | Computer（pplx_asi*） | computer |

- 歸檔全量取值實測：六種取值在真實歸檔庫中均有實例，SEARCH 與 RESEARCH 佔絕大多數，
  STUDIO 次之，ASI / STUDY / AGENTIC_RESEARCH 為少數。
- **pplx_alpha ⟺ RESEARCH 互證**：歸檔百餘個平台 SEARCH 入口+pplx_alpha 執行緒 100%
  `search_mode=RESEARCH`；百餘個純 pplx_pro 執行緒全為 `search_mode=SEARCH`——
  「pplx_alpha 是普通 search 常用模型」的舊統計實為分類器誤判樣本，不成立。
- 執行緒內可出現多值（模式切換，如實測 SEARCH+RESEARCH 混合）：判別按特異性
  computer>council>study>deep-research>search 取最高。

<a id="模型委员会输出结构与展开行为" data-pplx-source-anchor="true"></a>
#### 模型委員會輸出結構與展開行為
- 單輪產出 = N 個模型各自的「Council: <模型名>」區塊（各含檢索詞/來源/答案）+ 綜合部分：
  **Where Models Agree**（共識矩陣，逐條 Finding 三模型✓對照 + Evidence）、
  **Where Models Disagree**（分歧表，各模型立場 + 差異原因）、
  **Unique Discoveries**（各模型獨特發現），最後附相關問題推薦——**全部在同一個 SSE 流中下發**。
- 展開行為（含**生成中**展開）：展開行是帶「>」chevron 的行（步驟行/「來源」行/Council 行），
  點擊即展開，**純客戶端渲染，零內容請求**——本會話 1208 個請求中 921 個是 favicon/字體等靜態資源，
  展開動作本身只觸發 favicon 載入與 /api/version。串流期間展開不干擾串流的繼續下發。
- 首 token 延遲實測 ~204s（三模型並行生成，明顯長於單模型）；來源計數實測 236。
- 撰寫區（Lexical）自動化要點：文字須用 CDP `Input.insertText` 注入（execCommand/fill 後
  Lexical 內部狀態不同步、Enter 無效）；提交可用 CDP Enter 或點 aria-label="提交" 的按鈕
  （委員會模式有顯式提交箭頭）。

<a id="续历史对话的行为特征2026-07-20-实测" data-pplx-source-anchor="true"></a>
#### 續歷史對話的行為特徵（2026-07-20 實測）
1. 載入執行緒頁 → `session`、`assets/pins`、`billing/credits/computer-submit-gate`、`cdn-cgi/trace`。
2. 提交追問 → `rate-limit/status` → `sse/perplexity_ask`（帶 `last_backend_uuid` 續鏈）→ 高頻 analytics。
3. 生成中 → SSE 流增量渲染；完成後再一批 analytics（含 `thread entry exited` 閱讀時長）。
4. deep-research 續輪同樣產出報告結構（本輪 5 步驟完成）。
