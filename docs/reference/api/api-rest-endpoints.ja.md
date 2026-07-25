---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-rest-endpoints.zh-CN.md"
translation_source_sha256: "38129b3e7bf3833341615d818dc6e81c57bb7f290df912c314acd50a0de08772"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-参考rest-端点" data-pplx-source-anchor="true"></a>
# API リファレンス：REST エンドポイント

<a id="rest-端点按用途分组" data-pplx-source-anchor="true"></a>
## REST エンドポイント（用途別グループ）

規約：`?version=2.18&source=default` は汎用クエリ文字列（ほとんどのエンドポイントで必須）。

<a id="线程内容导出主路径" data-pplx-source-anchor="true"></a>
### スレッドコンテンツ（エクスポートのメインパス）
| エンドポイント | 説明 |
|---|---|
| `GET /rest/thread/<uuid>` | **プレーン応答**：`entries[]`（各ラウンド、`text` は全ステップテキストを含む）、`background_entries[]`（**サブエージェント完全ワークフロー**）、`thread_metadata`。`?cursor=` ページネーション対応（`has_next_page`/`next_cursor`） |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **スキーマ化応答**：`entries[].blocks[]`（`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`）、サブエージェントプロンプト（`workflow_payload.objective_chunks`）、アセット署名URL、ファイル内容を含む。ユースケースは `rest.py:SCHEMATIZED_USE_CASES`（workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown）を参照 |
| `GET /rest/thread/list_recent` | 最近のスレッド一覧（ホームページサイドバー用；`unread` フィールドを含む） |
| **`POST /rest/thread/mark_viewed`** | **既読レシート（2026-07-21 解明）**：body `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`、未読は即座に反転。サイドバークリックでスレッドに入るときにフロントエンドがこのエンドポイントを呼び出す。注意：アナリティクスの "thread viewed" イベントは未読を**反転しない**（複数回の実測で確認） |
| `GET /rest/thread/<uuid>/members` | **スレッドレベルの共有メンバー**（実測済み）：`{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | `{"will_request_org_join": bool, "org_display_name": str|null}` を返す——組織参加関連、**threadAccess セマンティクスとは無関係**（実測で確認） |
| `GET /rest/thread/list_ask_threads`、`/rest/thread/list_scheduled_computer_tasks` | 静的解析で存在確認；直接 GET は 400（パラメータ形式未確認） |

<a id="资产元数据2026-07-20-探明过期资产救星" data-pplx-source-anchor="true"></a>
### アセットメタデータ（2026-07-20 解明、**期限切れアセットの救世主**）

- **`GET /rest/assets/<asset_uuid>/data`** → アセット完全メタデータ（実測 200）：
  - `asset_data.<类型>.url` と `asset_data.download_info[].url`：**新しい CloudFront 署名 URL**——
    アーカイブ時に元の署名 URL が期限切れの場合、asset_uuid を使ってダウンロードアドレスを再取得可能（アセットがプラットフォームによって削除されていない場合）；
  - 同時に `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    （アセット → スレッド逆引きチェーン）を提供；
  - `signed_url: null`、`read_write_token`、`allow_remix` などのフィールド。
- **適用範囲（実測済み）**：実際のアセット UUID は使用可能；**`toolu_` プレフィックスのクラウドワークスペースハンドル（DOC_FILE/CODE_FILE
  URL 形式なし）は 404 ASSET_NOT_FOUND を返す**；`file-repository/download` は実際の URL が必要、
  `file:repo/...` ハンドルは受け付けない（400 failed to parse）。toolu 系アセットには現在 API ダウンロードチャネルなし。
- 関連：`/rest/assets/<id>/members`、`/rest/assets/<id>/published-access`（静的解析で存在確認、未実測）。
- 実装：ツールは `pplx-export assets-backfill` を実装済み（インライン抽出 + 本エンドポイントでのオンラインリフレッシュ、[§4](api-responses-errors.md) 実装ツールを参照）。

- **ENTRY_EXPIRED**：約 3 ヶ月前のスレッド/アーティファクトがプラットフォームによって削除され、リクエストは特定のエラーボディを返す——ツールは最終状態としてマークし再試行しない。
- **スレッド削除（2026-07-23 WebBridge + chunk 調査実測）**：
  `DELETE /rest/thread/delete_thread_by_entry_uuid`、body `{entry_uuid, read_write_token}`、
  成功時 `200 {"status":"success"}`；重複削除は冪等で依然 200；存在しない UUID の削除 → 404 `THREAD_NOT_FOUND`；
  **`read_write_token` の取得（同日実戦検証）**：`GET /rest/thread/<uuid>` 応答の
  `entries[].read_write_token` の最初の非空値が使用可能（アクティブスレッドで 10/10 削除成功を確認）；
  **書き込み操作は www ドメイン経由で行う必要がある**（ベアドメインは DELETE に 301 を返す）。GraphQL mutation なし、バッチ削除エンドポイントなし
  （UI のバッチ削除はフロントエンドが一件ずつループ）。削除はスレッドレベルの破棄で復元不可、スレッドは自動的に所属スペースから消える
  （事前に `batch_remove_collection_threads` で移動する必要なし）。
  ソフトな方法：`POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  （body `{context_uuids:[...]}`、静的のみで未実測）。
- **ENTRY_DELETED**：スレッド削除後、`GET /rest/thread/<uuid>` は HTTP 400 `ENTRY_DELETED` を返す
  （ENTRY_EXPIRED と同じ 400 だが code が異なる）——ツールは `EntryDeletedError`
  （`EntryExpiredError` サブクラス）にマッピングし、batch_state を最終状態 `deleted` としてマーク。
- 各ラウンドのエントリには `context_uuid`（= プラットフォームの `past_session_contexts` UUID、二重 ID 名前空間マッピングのキー）が含まれる。

<a id="空间collections" data-pplx-source-anchor="true"></a>
### スペース（コレクション）
| エンドポイント | 説明 |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **スペースメタデータ**：`uuid/title/emoji/access/max_contributors`、`owner_user{username,email,name,permission}`、`contributor_users[]`、`user_permission`。permission 実測：4=所有者、2=編集可能。閲覧権限がない場合、`status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` を返す（HTTP は依然 200） |
| `POST /rest/collections/create_collection` | **スペース作成**（2026-07-21 WebBridge キャプチャ実測）：body `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → 完全なコレクション（uuid/slug/url/user_permission=4）を返す。BOT スペースはこれで作成される |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **スペーススレッド一覧（cookie 直接接続、ブラウザ版 space-index の代替可能）**：応答は配列で、各項目に `uuid`(=entryUUID)、`context_uuid`、`frontend_uuid`、`author_username`、`title`、`mode`、`last_query_datetime`、`thread_access`、`answer_preview` などを含む。**ページネーション：`&offset=N`（1 ページ 20 件）**、`has_next_page` は各項目にあり；`total_threads` のセマンティクスはやや大きい（computer サブスレッドを含む、観測値 99 vs トップレベル 27） |
| `POST /rest/collections/batch_move_threads` | **スレッドをスペースに移動**（実測 succeeded）：body `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}`——**context_uuid を使用し、entryUUID ではない** |
| `POST /rest/collections/batch_remove_collection_threads` | スペースからの一括移動（body `{items:[{collection_uuid,...}]}`、未実測） |
| `GET /rest/collections/list_user_collections` | **現在のアカウントのスペース一覧**（実測 16 個）：各項目に `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page` などを含み、list_recent より情報が豊富 |
| `GET /rest/collections/list_recent` | 現在のアカウントの最近のスペース一覧（`title/uuid/emoji/is_pinned/link`、実測 5 項目） |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | スペースアクセス申請情報（未実測） |
| `GET /rest/collections/<uuid>/join-requests` | 参加申請（未詳細） |
| `GET /rest/spaces/<uuid>/tasks` | `{"tasks":[]}` を返す——観測では空；スペースの定期/computer タスクの可能性があり、スレッド一覧ではない |
| `GET /rest/spaces/<uuid>/recurring_tasks` | 定期タスク（未実測） |
| `GET /rest/spaces/<uuid>/pins/threads`、`/scheduled_threads` | スペース固定/定期スレッド（ページ読み込み時に呼び出される、未詳細） |

- **クロスアカウントフォーク（branch_of、ユーザー実測認識 2026-07-23）**：スペース共有されたスレッドは、別のメンバーアカウントによって
  「続行」され、**そのアカウントのみに表示され、そのアカウントによって続行される**フォークスレッドになる——A アカウントのスレッドがスペース共有された後、
  B は B プライベートフォークを続行できる。アーカイブライブラリにはまだインスタンスがなく、relations エッジは当面実装しない；フォークスレッドの API シグナルフィールド
  （親スレッドポインタ/フォークマーク）は最初の事例が現れたときに検証記録する。

<a id="账户会话" data-pplx-source-anchor="true"></a>
### アカウント/セッション
| エンドポイント | 説明 |
|---|---|
| `GET /api/auth/session` | 現在のセッション `{user:{email,...}}`——アカウント検証と自動切り替え検出用 |
| `GET /api/auth/linked-accounts` | [§1.2](api-authentication.md) を参照（primary が有効な場合のみフル） |
| `GET /rest/user/info`、`/rest/user/settings` | ユーザープロフィール/設定（未詳細） |

<a id="积分用量2026-07-20-探明" data-pplx-source-anchor="true"></a>
### クレジット使用量（2026-07-20 解明）

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → 単一スレッドのクレジット使用量（実測 200）：
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **注意**：`thread_id` には **context_uuid**（psc_uuid）が必要で、entryUUID を渡すと 403
  `thread_usage_forbidden`（"Thread does not belong to the current user"、実際は ID 形式の誤り）。
- context_uuid の取得元：`list_collection_threads`（space-index REST 版で 27/27 カバレッジ）、
  スレッドエントリの `context_uuid` フィールド（アーカイブ thread.json の `psc_uuid`）。
- 自分のアカウントのスレッドのみ照会可能（クロスアカウントは 403）——マルチアカウント取得にはアカウントごとの自動切り替えが必要。
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`：一覧版、2 つのアカウントで実測したが両方とも空を返した
  （組織請求専用の可能性あり、保留）。
- その他の billing エンドポイント（`/rest/billing/credits/balance` など）は [§7 付録](api-discovery-roadmap.md) を参照、未詳細。

<a id="官方导出页面导出按钮的后端2026-07-20-探明" data-pplx-source-anchor="true"></a>
### 公式エクスポート（ページの「エクスポート」ボタンのバックエンド、2026-07-20 解明）

- **`POST /rest/thread/export`**、body：`{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<名称>"}`
- 応答：`{"file_content_64": "<base64>", "filename": "..."}`
- 実測 format：**`md`**（ロゴ `<img>` ヘッダー付き公式マークダウン）、**`pdf`**（%PDF バイナリ ~880KB）、
  **`docx`**（PK zip ~350KB）——すべて HTTP 200。他のフォーマット値は未試行。
- **内容の境界（実測確認）**：返されるのは**スレッド全体**のマークダウン（query + answer 要約 + `[^1_N]` 脚注引用）、
  **RESEARCH_REPORT レポート本文は含まない**——ディープリサーチレポート本体は署名 URL 経由でのみ取得可能（§3.7）、
  つまり現在の report.md の署名 URL チェーンが**公式レポートソース**である（ページのアーティファクトパネルダウンロードと同一起源）、本エンドポイントを使う必要はない。
- 価値：公式スレッド版マークダウンは会話レベルのクロス検証ソースとして使用可能（公式レンダリングの引用脚注/フォーマット）。

<a id="资产报告下载" data-pplx-source-anchor="true"></a>
### アセット/レポートダウンロード
- スキーマ化応答内の **CloudFront 署名 URL**（`d2z0o16i8xm8ak.cloudfront.net`）：urllib で直接ダウンロード、
  cookie/認証不要；複数バージョンファイルは `created_at` でソート番号付け。
- 研究レポートの代替ソース：RESEARCH_ANSWER ステップの S3 URL（`ppl-ai-file-upload.s3.amazonaws.com`、**期限切れあり**）；
  さらに代替としてページレンダリング抽出（KaTeX `<annotation>`）。
- **約 3 ヶ月で削除**：アーティファクト/レポートソースリンクは期限切れで復元不可——エクスポートはタイムリーに行う必要がある。

<a id="其他观测到的端点页面加载未深入" data-pplx-source-anchor="true"></a>
### その他観測されたエンドポイント（ページ読み込み、未詳細）
`/rest/models/config(/v2)`、`/rest/sources`、`/rest/rate-limit/status`、`/rest/assets/pins`、
`/rest/file-repository/list-files`、`/rest/files/list`、`/rest/notifications/in-app/unread-count`、
`/rest/billing/*`、`/rest/sse/recent_thread_updates`（SSE）、`/api/version`。

<a id="消息提交与遥测2026-07-20-webbridge-cdp-探明" data-pplx-source-anchor="true"></a>
### メッセージ送信とテレメトリー（2026-07-20 WebBridge + CDP 解明）

<a id="提交端点post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### 送信エンドポイント：`POST /rest/sse/perplexity_ask`
- 完全なリクエストボディサンプル（合成例）は `docs/perplexity-api-samples/` を参照：
  - `ask_envelope_deep_research.json`——deep-research 継続ラウンド（2026-07-20；39 個の params + query_str）：
    `model_preference: "pplx_alpha"`、`query_source: "followup"` + `last_backend_uuid` 継続チェーン
  - `ask_envelope_search.json`——標準検索、ホームページから新規会話開始（2026-07-21；35 個の params + query_str）：
    `model_preference: "pplx_pro"`、`query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json`——モデル委員会、ホームページから新規会話開始（2026-07-21；36 個の params + query_str）：
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- キーフィールド（deep-research 継続ラウンド実測）：
  - `mode: "copilot"`（ディープリサーチ）；`model_preference: "pplx_alpha"`
  - **会話チェーンの継続**：`last_backend_uuid`（前ラウンドの backend uuid）+ `query_source: "followup"`
  - `frontend_uuid`（今回の新しい uuid）、`read_write_token`、`target_collection_uuid`（所属スペース）、
    `target_thread_access_level: 1`
  - `search_focus: internet`、`sources: ["web"]`、`language: zh-CN`、`timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`**（最初のキー入力から送信までのミリ秒——行動テレメトリーが送信とともに報告される）
  - `use_schematized_api: true`、`supported_block_use_cases`（完全なブロックリスト、§3.1 スキーマ化と対応）、
    `supported_features: ["browser_agent_permission_banner_v1.1"]`、`skip_search_enabled: true`
- 応答は SSE ストリーム（フロントエンドは fetch-event-source `getReader()` で消費——app モジュール初期化時に fetch 参照を固定、
  **ページロード後の fetch/XHR hook は無効**；さらに**ストリーム応答ボディはブラウザに保持されない**（`Network.getResponseBody` は
  No data found を返す）——パケットキャプチャは CDP `Network.getRequestPostData` のみ可能（リクエストボディは使用可能）。
- ストリームコンテンツの最終状態は `/rest/thread/<uuid>` の entries/blocks（同じデータ、インクリメンタル配信）——
  エクスポートツールはストリームを読む必要はなく、最終状態を直接取得すればよい。

<a id="遥测post-resteventanalytics批量高频" data-pplx-source-anchor="true"></a>
#### テレメトリー：`POST /rest/event/analytics`（バッチ、高頻度）
実測イベント（event_data の要点を含む）：
| event_name | キーフィールド | 説明 |
|---|---|---|
| `thread viewed` | `authorId`、`authorUsername`、`isThreadCreator`、`contextUUID` | ページビューイベント——**未読を反転しない**（実測で確認；実際の既読レシートは `POST /rest/thread/mark_viewed`、§3.1 参照） |
| `thread entry exited` | `entryUUID`、`timeOnEntryMs`（**そのラウンドの読了滞在ミリ秒**）、`userId`、`isPro`、`deviceInfo`（同時実行数/画面/色深度） | 読了時間テレメトリー（未読を反転しない、実測で確認） |
| `ask input submit button clicked` | `querySource: followup`、`searchMode: research`、`isFollowUp` | 送信アクション |
| `query first llm token` | `startLLMTokenElapsed`（最初のトークン遅延）、完全な `queryStr` | パフォーマンステレメトリー |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`、完全な `queryStr` | 成功レシート |
| `ask input model selector opened` | `searchMode: "agentic_research"`、`multiple: true`、`selectedModels` | 委員会モデルセレクターインタラクション |
| `ask context pane viewed` | `pane_mode`、`context_uuid` | 右側パネル表示 |
- イベント共通フィールド：`userId`、`visitor_id`、`timezone`、`language`、`screen`、`device_info`（hardwareConcurrency/画面/色深度/architecture）、`isBrowserExtension`、`web_platform`。
- **注意**：実測であるイベントが持つ `userId` は**別のアカウント**の uid だった（uid はアカウント A に属するが、セッションは既にアカウント B）——
  テレメトリー SDK のプロファイル ID にはキャッシュの遅延があり、テレメトリーの userId で現在のアカウントを判断できない。
- 別途 datadog RUM（`browser-intake-datadoghq.com/api/v2/rum`）が高頻度で報告（スクロール/マウス/パフォーマンス、内容未解析）。

<a id="模式与模型选择2026-07-21-付费账户实测" data-pplx-source-anchor="true"></a>
#### モードとモデル選択（2026-07-21 有料アカウント実測）
- **`GET /rest/models/config/v2` = 権威モデル一覧**：`models{id→{label,mode,provider}}`、
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`、`agentic_research_compare_models`（委員会デフォルト 3 モデル）。
  `pplx-ask models` はこのエンドポイントを呼び出す。
  - 公式対応（実測）：**search = `pplx_pro`（UI 名「ベスト」）、research = `pplx_alpha`
    （UI 名「Deep research」）**。
  - search モード UI で選択可能なモデル一覧（Deep research なし）：ベスト（pplx_pro）、Sonar 2、
    GPT-5.6 Terra、GPT-5.6 Sol、Gemini 3.1 Pro、Claude Sonnet 5、Claude Opus 4.8、
    GLM 5.2、Kimi K2.6、Grok 4.5、Nemotron 3 Ultra。
- **`mode` フィールドは常に `"copilot"`、モード判別フィールドではない**（検索/ディープリサーチ/モデル委員会すべて同じ）。
- 判別は **`model_preference`**：
  - 検索：`pplx_pro`（またはユーザー選択モデル ID、例：`experimental`=Sonar 2、`gpt56_sol`…）
  - ディープリサーチ：`pplx_alpha`（**UI にモデルセレクターなし**、固定）
  - **モデル委員会**：`pplx_agentic_research` + **`compare_model_preferences: [<2-3 模型>]`**
    （実測デフォルト `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`；
    UI は**スロットごとに単一選択**、フォローアップ時モデル数は 2 になる）。
  - ステップバイステップ学習：`pplx_study`；Computer：`pplx_asi*` シリーズ。
- 作成エリアのモデルセレクター（モデル ⌄）と委員会「N 個のモデル ⌄」セレクターはそれぞれ上記フィールドに対応；
  テレメトリーイベント `ask input model selector opened` は `searchMode: "agentic_research"`、
  `multiple: true`、`selectedModels` を持つ（以前のディープリサーチスレッドは `searchMode: "research"`）。
- 新規会話：`query_source: "home"`、`last_backend_uuid` なし、`frontend_context_uuid` あり；
  継続会話：`query_source: "followup"` + `last_backend_uuid` 継続チェーン。

<a id="entrysearch_mode会话模式的权威记录字段2026-07-22-定案" data-pplx-source-anchor="true"></a>
#### entry.search_mode：会話モードの権威記録フィールド（2026-07-22 確定）
`/rest/thread/<uuid>` の**各エントリ**には `search_mode` が付属し、プラットフォームによるそのラウンドの会話モードの権威記録である
（モード判別の最優先シグナル、`normalize.SEARCH_MODE_MAP`）：

| search_mode | 意味（UI/モデル） | アーカイブモード |
|---|---|---|
| `SEARCH` | 通常検索（default_models.search=pplx_pro「ベスト」および UI 選択可能モデル） | search |
| `STUDIO` | labs セッション（pplx_beta）、UI では search 側に分類 | search |
| `RESEARCH` | Deep research（default_models.research=pplx_alpha、UI 固定でセレクターなし） | deep-research |
| `AGENTIC_RESEARCH` | モデル委員会（pplx_agentic_research + compare_model_preferences） | council |
| `STUDY` | ステップバイステップ学習（pplx_study） | study |
| `ASI` | Computer（pplx_asi*） | computer |

- アーカイブ全量取得実測：6 種類の値すべてが実際のアーカイブライブラリにインスタンスあり、SEARCH と RESEARCH が大多数を占め、
  STUDIO が次、ASI / STUDY / AGENTIC_RESEARCH は少数。
- **pplx_alpha ⟺ RESEARCH 相互検証**：アーカイブした百以上のプラットフォーム SEARCH エントリ + pplx_alpha スレッドは 100%
  `search_mode=RESEARCH`；百以上の純粋な pplx_pro スレッドはすべて `search_mode=SEARCH`——
  「pplx_alpha は通常 search でよく使われるモデル」という古い統計は実際には分類器の誤判定サンプルであり、成立しない。
- スレッド内で複数の値が出現可能（モード切り替え、実測 SEARCH+RESEARCH 混合）：判別は特異度順に
  computer>council>study>deep-research>search で最も高いものを採用。

<a id="模型委员会输出结构与展开行为" data-pplx-source-anchor="true"></a>
#### モデル委員会の出力構造と展開動作
- 単一ラウンドの出力 = N 個のモデルそれぞれの「Council: <モデル名>」ブロック（各々検索語/ソース/回答を含む）+ 統合部分：
  **Where Models Agree**（コンセンサスマトリックス、各 Finding に 3 モデル✓対照 + Evidence）、
  **Where Models Disagree**（相違表、各モデルの立場 + 差異の理由）、
  **Unique Discoveries**（各モデルの独自の発見）、最後に関連質問の推奨——**すべて同じ SSE ストリームで配信される**。
- 展開動作（**生成中**の展開を含む）：展開行は「>」シェブロン付きの行（ステップ行/「ソース」行/Council 行）、
  クリックで展開、**純粋なクライアントサイドレンダリング、コンテンツリクエストはゼロ**——本セッションの 1208 リクエスト中 921 は favicon/フォントなどの静的リソース、
  展開動作自体は favicon 読み込みと /api/version のみをトリガーする。ストリーム中の展開はストリームの継続配信を妨げない。
- 最初のトークン遅延実測 ~204s（3 モデル並列生成、単一モデルより明らかに長い）；ソース数実測 236。
- 作成エリア（Lexical）自動化の要点：テキストは CDP `Input.insertText` で注入する必要がある（execCommand/fill 後
  Lexical 内部状態が同期せず、Enter が無効）；送信は CDP Enter または aria-label="送信" のボタンクリックで可能
  （委員会モードには明示的な送信矢印がある）。

<a id="续历史对话的行为特征2026-07-20-实测" data-pplx-source-anchor="true"></a>
#### 履歴会話の継続の動作特性（2026-07-20 実測）
1. スレッドページ読み込み → `session`、`assets/pins`、`billing/credits/computer-submit-gate`、`cdn-cgi/trace`。
2. フォローアップ送信 → `rate-limit/status` → `sse/perplexity_ask`（`last_backend_uuid` 継続チェーン付き）→ 高頻度 analytics。
3. 生成中 → SSE ストリームでインクリメンタルレンダリング；完了後さらに analytics のバッチ（`thread entry exited` 読了時間を含む）。
4. deep-research 継続ラウンドもレポート構造を生成（今回のラウンドは 5 ステップで完了）。
