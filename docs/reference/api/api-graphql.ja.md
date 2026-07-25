---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-graphql.zh-CN.md"
translation_source_sha256: "8abe002576d89da5b7dbcdbba673ce6423cf94c8944606f70e60addcf6268ac0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-参考graphql" data-pplx-source-anchor="true"></a>
# API リファレンス：GraphQL

<a id="graphql持久化查询-apq" data-pplx-source-anchor="true"></a>
## GraphQL（永続化クエリ APQ）

- **エンドポイント**：`POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **形式**：persisted query——body に operationName + variables + sha256 ハッシュを含む（クエリテキスト不要）。
- 実装：`pplx_export/sites/perplexity/graphql.py`。

<a id="librarythreadsrelayquery列表首页" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery（リストトップ）
- sha256：`a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- 変数：`{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- レスポンスパス：`data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- node フィールド（アダプター使用）：`name(title)`、`entryId(entryUUID)`、`slug(href)`、`mode`、`displayModel.modelID`、
  `updatedAt(lastUpdated)`、`status`、`space{spaceUuid,title,slug}`
- **アーカイブ側契約（2026-07-22 V5-01）**：`web_archive/**/thread.json` の `lastUpdated` は本フィールドと常に等しい
  （ISO 全精度でそのまま保存）；バッチ/単一エクスポートの冪等比較（`is_unchanged`）はこれを基準とし、
  レンダリング層の表示形式（`YYYY-MM-DD HH:MM UTC`）は使用しない。
- **アーカイブ側エンリッチメント（2026-07-23）**：インデックス保存行（`index/library_*.json`）の `search_mode` キーは
  アーカイブ側エンリッチメントフィールド——本クエリの node は search_mode を含まず、`pplx-export search-mode-backfill` が
  スレッドレベルデータ（`GET /rest/thread/<uuid>` の `entries[].search_mode`）から補完する（ローカル raw 優先、
  ネットワークでフォールバック）；`index` リフレッシュは entryUUID でマージ保持。`batch --mode` フィルタリングは
  このフィールドの信頼できるマッピングを優先する。

<a id="libraryrecentthreadspaginationquery翻页" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery（ページネーション）
- sha256：`4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- 変数：トップ変数 + `{cursor, count}`（**変数名は cursor/count、after/first ではない**）
- レスポンス構造は同上。`hasNextPage` が真で `endCursor` が空の場合は停止する必要がある（そうしないと同じページが繰り返される）。

<a id="computer-仪表盘操作组2026-07-20-从-route-chunk-提取服务器未注册" data-pplx-source-anchor="true"></a>
### Computer ダッシュボード操作グループ（2026-07-20 route chunk から抽出、**サーバー未登録**）

`ComputerDashboardPage-*.js` chunk に Relay 完全クエリテキスト + persisted id が埋め込まれている（抽出方法は [§7](api-discovery-roadmap.md) 参照）。
構造の要点：`viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
——すなわち threadGroup + mode でフィルタリングされたスレッドリスト；node は `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread` を含む。

| 操作 | persisted id（先頭 16 桁） |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…`（WebSocket サブスクリプション） |

**実測**：これらの id で `/rest/perplexity_ask/graphql` を呼び出すと `PERSISTED_QUERY_NOT_FOUND` が返る
（現在のデプロイでは未登録——バージョン不一致またはダッシュボードコンテキストが必要；完全クエリテキストと id は `/tmp` 探索記録に保存済み、
必要に応じてテキスト直接送信またはオンライン bundle から再抽出可能）。

<a id="注意事项" data-pplx-source-anchor="true"></a>
### 注意事項
- Web 版のスペースページ/トップページでは graphql 呼び出しは見られない（すべて /rest 経由）；graphql は /library リストと computer ダッシュボードで使用されることが確認されている。
- sha256 ハッシュはフロントエンドバージョンによって変更される可能性がある；無効化は `PERSISTED_QUERY_NOT_FOUND` として現れる——その場合はブラウザの
  ネットワークキャプチャから再抽出する（WebBridge `network` ツールで `perplexity_ask/graphql` をフィルタリング）、またはオンライン bundle から再抽出する（[§7](api-discovery-roadmap.md)）。

<a id="已提取的仪表盘-connection-keysrelay-缓存键调试用" data-pplx-source-anchor="true"></a>
### 抽出済みダッシュボード connection keys（Relay キャッシュキー、デバッグ用）
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
