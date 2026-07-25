---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-discovery-roadmap.zh-CN.md"
translation_source_sha256: "d2ef3b082d6320ba6a0ba74a978305c5c362c8fa56c8ee0dbf357470df97cebd"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="端点发现方法与改进路线图" data-pplx-source-anchor="true"></a>
# エンドポイント発見方法と改善ロードマップ

*本記事は Perplexity Web API リファレンスの一部です。全体像については [API インデックス](index.md) を参照してください。*

<a id="已知未探索待确认项" data-pplx-source-anchor="true"></a>
## 未探索・未確認項目

- `list_collection_threads` のソートフィールドと `total_threads` の正確なセマンティクス
  （2026-07 リアルタイムアカウントスナップショット：報告 99 件 vs トップレベル 27 件）。
- `threadAccess`/`access`/`user_permission` の値の全スペクトル（2026-07 観測サンプル：
  threadAccess 5 通常、1 つ 🔒；collection access 1；permission 4 所有者 /
  2 編集可能；assets data にも thread_access 含む）。
- `list_ask_threads`、`list_scheduled_computer_tasks` の正しいパラメータ形式（直接 GET で 400）。
- `collections/*/request-access-info`、`spaces/<uuid>/recurring_tasks`、`assets/<id>/members` のレスポンス構造。
- ダッシュボード GraphQL 操作が未登録の理由（PERSISTED_QUERY_NOT_FOUND）：バージョンの不一致またはコンテキストのしきい値。
  必要に応じて、オンラインネットワークキャプチャで取得したリアルタイムハッシュを使用して再抽出。
- `frontend_uuid` vs `uuid` vs `context_uuid` の computer スレッドにおける役割分担。
- クロスアカウントスペース共有フォークスレッド（branch_of）の API シグナルフィールド（親スレッドポインタ/フォークマーカー）——
  メカニズムは確認済み（[§3.3](api-rest-endpoints.md) 末尾）、2026-07-23 時点でアーカイブインスタンスなし、
  初回発生時に検証・記録予定。

<a id="端点发现方法前端-bundle-静态分析零-api-成本2026-07-20-建立" data-pplx-source-anchor="true"></a>
## エンドポイント発見方法：フロントエンドバンドル静的解析（API コストゼロ、2026-07-20 確立）

一度に **147 個の `/rest/` エンドポイント** を発見。手法は再利用可能（フロントエンド改版後に再実行可能）：

1. ページロードのエントリ `_spa/assets/index.html-*.js` が `bootstrap-*.js` を参照（実行時に全チャンクマッピングを含む）；
2. bootstrap から 682 個のチャンクファイル名（パターン `<name>-<hash8>.js`）を抽出し、名前で API 関連をフィルタ
   （client/api/thread/collection/space/computer…）；
3. パブリック CDN `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js` から直接ダウンロード
   （cookie 不要）；中枢モジュール：`platform-core-*`（API client）、`spa-shell-*`、`spa-metadata-*`；
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` でエンドポイントリスト（147 個）を取得；
5. チャンクは同時に呼び出し形式を漏洩（例：export の `format:'md'` と `file_content_64`）。
6. さらに sourcemap：`https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map`（未深掘り）。

<a id="附录147-个端点按类分组与归档相关性标注" data-pplx-source-anchor="true"></a>
### 付録：147 エンドポイントのカテゴリ別グループ（アーカイブ関連性の注記付き）

- **thread**：`/rest/thread/{entry_uuid_or_slug}`、`/rest/thread/export`★、`/rest/thread/{uuid}/members`、
  `/rest/thread/list_recent`、`/rest/thread/list_ask_threads`、`/rest/thread/list_pinned_ask_threads`、
  `/rest/thread/list_scheduled_computer_tasks`、`/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★：[§3.3](api-rest-endpoints.md) の全表参照（batch_move/batch_remove、list_user_collections、request-access-info、
  recurring_tasks、pins/threads、scheduled_threads を含む）
- **assets**★：`/rest/assets/{asset_id}/data`、`/rest/assets/{asset_id}/members`、
  `/rest/assets/{asset_id}/published-access`、`/rest/assets/sites/{site_id}/publish-info`
- **analytics**：`/rest/analytics/computer/usage`、`/rest/analytics/computer/usage/members`
  （いずれも 403 NOT_ORG_MEMBER——組織アカウント専用）
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
- **verticals**（アーカイブ非関連）：`/rest/finance/*`、`/rest/sports/*`、`/rest/travel/hotels/{slug}`、
  `/rest/health-assistant/*`、`/rest/article/{uuid_or_slug}`
- **misc**：`/rest/pins`、`/rest/rate-limit/(all|status)`、`/rest/notifications/web-push/*`、
  `/rest/attribution/*`、`/rest/homepage-widgets/upsell`、`/rest/ntp/upsell/`、`/rest/sidebar/upsell/`、
  `/rest/incentives/comet-activation`、`/rest/connector-service/usage`

（★ = アーカイブに直接関連）

<a id="端点-工具能力状态与路线图" data-pplx-source-anchor="true"></a>
## エンドポイント → ツール機能の状態とロードマップ

以下の表の実装状態は **2026-07-24** 時点で現在のコードとテストスイートに照らして同期済みです。API エビデンスは元の
リアルタイム観測または静的解析の日付と範囲をそのまま使用；今回のドキュメント同期ではプライベートエンドポイントの再探索は行っていません。アカウント/アーカイブ数
はすべてスナップショットであり、プラットフォーム全体の恒常的な保証ではありません。

状態の意味：

- **実装済み**——現在の CLI または本番パスが、表に記載された機能のためにエンドポイントを使用している。
- **一部実装**——エンドポイントは使用中だが、ロードマップの下流機能が未完了。
- **実測済み、未統合**——オンライン API の動作は観測済みだが、ツールに消費パスがない。
- **計画中**——エビデンスはあるが、実装未着手。
- **ブロック中**——明確な上流またはプロトコルのブロックが存在する。
- **クローズ**——エビデンスが元の用途を否定した、またはその用途が範囲外と確定した。

<a id="能力状态矩阵" data-pplx-source-anchor="true"></a>
### 機能状態マトリックス

| エンドポイント / 操作 | 検証根拠 | 現在の統合 | 状態 | 残存ギャップ |
|---|---|---|---|---|
| `collections/get_collection` | リアルタイム観測 + 現在のコード | `spaces --fetch-meta` がスペース所有者/メンバーインデックスを構築 | **実装済み** | — |
| `collections/list_collection_threads` | リアルタイム観測 + 現在のコード | `space-index` デフォルト REST、context_uuid による二重 ID マッピング含む；WebBridge は代替 | **実装済み** | ソートと `total_threads` の正確なセマンティクスは未確認 |
| `assets/<uuid>/data` | 2026-07-20 オンライン実測 + 現在のコード | `assets-backfill --online` が実際の asset UUID に対して署名付き URL をリフレッシュ | **実装済み** | 本エンドポイントは `toolu_` クラウドワークスペースハンドルをカバーしない |
| `LibraryThreadsRelayQuery` とページネーションクエリ | APQ キャプチャ済み + 現在のコード | `index`/`batch` が全量インデックスと増分早期停止を提供 | **実装済み** | ダッシュボードのモード別クエリは別途ブロック中 |
| `collections/list_user_collections` | 2026-07 オンライン観測 + 現在のコード | `init` がタイトル完全一致で BOT スペースを発見 | **一部実装** | アカウントレベルの権威スペースレジストリを確立し、新スペース発見と `spaces` 再構築に使用 |
| `credits/thread-usage` | 2026-07-20 オンライン実測 + 現在のコード | `usage-backfill` が `index/credit_usage_<account>.json` に書き込み | **一部実装** | 二重真実源を作らずに `thread.json` および/または library インデックス行をリッチ化するか決定 |
| `models/config/v2` | 2026-07-21 オンライン実測 + 現在のコード | `pplx-ask models` がモデル/デフォルト値をリスト；正規化定数はこれに基づき相互検証 | **一部実装** | 価値があると判断された場合、安定モデル表示メタデータをアーカイブ/インデックスに書き込み |
| `POST /rest/thread/export` | 2026-07-20 実測済み md/pdf/docx | CLI 統合なし | **実測済み、未統合** | マルチフォーマットアーカイブと公式 Markdown の照合 |
| `rate-limit/status` | ページロード観測；レスポンスセマンティクス未探索 | なし | **計画中** | 適応型レート制限に使用する前にセマンティクスを検証 |
| `file-repository/list-files` | フロントエンド静的解析のみ | なし | **計画中** | `toolu_` ハンドルの列挙/救出が可能か検証；2026-07 アーカイブスナップショットではダウンロード不可のハンドル 270 件を記録 |
| `pins`、`tasks/{id}` | フロントエンド静的解析 / ページロード観測 | なし | **計画中** | ピン留め状態と computer タスク所要時間のリッチ化 |
| `thread/<uuid>/members` | 2026-07 オンライン実測 | なし | **計画中** | relations グラフにスレッドレベルの共有関係を提供 |
| ダッシュボード GraphQL `threadGroup` + モードフィルタ | 直接呼び出しで `PERSISTED_QUERY_NOT_FOUND` を返す | なし | **ブロック中** | リアルタイムの persisted-query ハッシュを復元するか、必要なコンテキストを確認 |
| `related_queries` / `sse/related-queries` | 2026-07-23 全データベースフォレンジックで確定 | 関係エッジを生成しないことを明確化 | **クローズ** | 解決可能なスレッド ID を確立できる新しいエビデンスがある場合のみ再開 |

<a id="活跃路线" data-pplx-source-anchor="true"></a>
### アクティブロードマップ

<a id="p0官方导出集成" data-pplx-source-anchor="true"></a>
#### P0——公式エクスポート統合

- **マルチフォーマットアーカイブ**：オプションで `POST /rest/thread/export` が返す PDF/DOCX 成果物を保持。
- **レンダラ照合**：公式スレッド全体 Markdown と `conversation.md` を比較し、独立した回帰シグナルとして使用。

<a id="p1空间发现" data-pplx-source-anchor="true"></a>
#### P1——スペース発見

- `list_user_collections` を BOT タイトル検索からアカウントレベルの権威スペースレジストリに昇格させ、
  新スペース発見と `spaces` 再構築に使用。

<a id="p2元数据风控与资产救援" data-pplx-source-anchor="true"></a>
#### P2——メタデータ、リスク管理、アセット救出

- クレジット使用量の真実源の境界を明確化：専用の `credit_usage_<account>.json` のみ保持するか、
  同時に `thread.json` / library インデックス行もリッチ化するか。
- エンドポイントのセマンティクスが安定した場合のみ、モデル表示メタデータ、ピン留め状態、computer タスク所要時間、スレッド共有関係を追加。
- 適応型レート制限を設計する前に `rate-limit/status` を検証。
- `file-repository/list-files` が `toolu_` の救出パスとして使用可能か検証してから、アーカイブ書き込み操作を追加。

<a id="p3受阻的发现能力" data-pplx-source-anchor="true"></a>
#### P3——ブロックされた発見能力

- モード別増分インデックスの価値がメンテナンスコストを上回る場合のみ、ダッシュボード GraphQL の
  persisted-query ハッシュを再キャプチャ。

<a id="已关闭决定-不采用" data-pplx-source-anchor="true"></a>
### クローズ決定 / 不採用

- **公式エクスポートエンドポイントをレポート本文の取得に使用**：反証済み。このエンドポイントはスレッド全体の Markdown を返し、
  レポート本文は含まない；署名付き URL チェーンが引き続き `report.md` の公式ソース
  （[§3.6](api-rest-endpoints.md)）。
- **`related_queries` からの関係エッジ構築**：2026-07-23 に反証済み。item UUID はスレッド UUID ではなく、
  推奨テキストもアーカイブクエリに解決できない；関係エッジは構築しない（[§4](api-responses-errors.md)）。
- `analytics/computer/usage(/members)`：テストアカウントで組織専用と観測
  （`403 NOT_ORG_MEMBER`）。
- `thread/request-access-info`：実測の結果、組織参加関連であり、`threadAccess` シグナルではない。
- billing/Stripe/enterprise および finance/sports などの垂直カテゴリはアーカイブツールの範囲外。

---

*本ドキュメントは [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md)（ツールアーキテクチャ）、[overview.md](../../architecture/overview.md)（システム設計）と補完関係にあります。*
