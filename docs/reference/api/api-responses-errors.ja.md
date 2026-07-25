---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-responses-errors.zh-CN.md"
translation_source_sha256: "cc96e525443d1f8445d81a3997cc8f26178730ef0541a33d0774f40c3fe70b89"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-响应结构与错误语义" data-pplx-source-anchor="true"></a>
# API レスポンス構造とエラーセマンティクス

*本稿は Perplexity Web API リファレンスの一部です。全体像は [API インデックス](index.md) を参照してください。*

<a id="响应结构要点解析纪律" data-pplx-source-anchor="true"></a>
## レスポンス構造の要点（解析の規律）

- **成功アーカイブは生データを保持**：`raw_entries.json`（plain）と
  `raw_blocks.json`（schematized、実際の取得時）はレンダリング成果物とともに保存され、
  解析/レンダリングはオフラインで再実行可能（`pplx-export re-render`）、再取得は不要。
- **フィールド抽出は集中** `sites/perplexity/parsers.py`（スキーマのずれは一箇所のみ修正）。
- モードの識別（`normalize.detect_mode`、決定木は [export-pipeline.md](../../architecture/export-pipeline.md) 参照）：最優先シグナルは
  いずれかのエントリの **`search_mode`** フィールド（マッピングは [§3.9](api-rest-endpoints.md) 末尾参照）；全滅時はフォールバック——computer = URL
  `/computer/tasks/` または metadata.mode=="4" またはインデックス mode∈{ASI,COMPUTER}；council = 存在する
  COUNCIL_RESEARCH ステップ；deep-research = 存在する RESEARCH_ANSWER ステップ（内容に基づき、中国語ラベルに依存しない）；
  それ以外は search。
- computer の UI はすべて折りたたみ——**常に API の entries/blocks を基準とし**、UI テキストをコンテンツ境界として使用しない。
- サブエージェント二重チャネル（2026-07-19 確認）：プロンプトは schematized `workflow_payload.objective_chunks` 内；
  ステップ/結論は plain `background_entries` 内；`workflow_payload.id`（`toolu_X`）で関連付け。
- `WORKFLOW_ITEM_SOURCES` 項目は `sources_payload.sources`（リンクリスト）を除き、多くの場合 `text_payload`
  （サブエージェントによるページ抽出本文/比較表、全ライブラリ実測 450 箇所中 408 箇所が background ネストペイロード内）を伴う；
  同一コンテンツは plain バックグラウンドエントリの `text` 内蔵ステップ JSON と schematized ネストペイロードの両方に同時に現れる——
  サブエージェントを plain パス経由でレンダリングすれば本文は保持される（2026-07-22 全ライブラリ確認 408/408 で欠落なし）。
- **`related_queries` / `related_query_items`（2026-07-23 確定）**：各エントリが持つ
  **次の質問プロンプト推奨**——プラットフォームが完了した回答生成に対して提供するフォローアップ質問の提案；`related_queries` は推奨テキストの配列、
  `related_query_items` は構造化項目（uuid/upsell_type 等を含む）。調査結論：項目の uuid
  **はスレッド uuid ではない**（全ライブラリのスレッド uuid との重複 0/988）、推奨テキストは他のスレッドのクエリとゼロ重複——
  **現時点ではスレッド間関係として解析不可**；「事前割り当てされたスレッド uuid（クリック後に具体化）」という未検証の仮説が存在。
  データはアーカイブ `raw_entries.json` に自然に保持される（あるアーカイブライブラリの過半数のスレッドが該当）、追加の収集アクションは不要；
  relations グラフはこれに対してエッジを生成しない。

<a id="错误与风控语义" data-pplx-source-anchor="true"></a>
## エラーとリスク管理のセマンティクス

| 現象 | 意味/対処 |
|---|---|
| 403（cf チャレンジページあり） | Cloudflare によるブロック（TLS フィンガープリント/レート制限）——バックオフ；urllib+ブラウザ cookie は通常トリガーしない |
| 401 / API レイヤーの 403（cf チャレンジページなし） | セッション cookie の期限切れ/無効——ツールは即座にスロー、バックオフしない；バッチで連続 3 回認証失敗で fail-fast（cookie 更新が必要） |
| 429 | レート制限——指数バックオフ（ツールで実装済み） |
| 5xx（500/502/503/504） | サーバー側の一時的エラー（504 は Cloudflare タイムアウトで頻出）——バックオフ再試行（ツールで実装済み） |
| ENTRY_EXPIRED | プラットフォームが削除（約 3 ヶ月）——最終状態、再試行しない |
| ENTRY_DELETED | ユーザー/リモートが削除（同じく HTTP 400、コードは異なる）——最終状態 `deleted`、再試行しない |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED`（HTTP 200） | 現在のアカウントにそのスペースを表示する権限がない——表示可能なアカウントで再試行 |
| `error_code: VIEW_THREAD_NOT_ALLOWED`（HTTP 403） | 現在のアカウントにそのスレッドを表示する権限がない（2026-07-23 実測：sibling バリアント uuid のプローブ；オブジェクトは存在するがアクセス不可、「存在しない」ではない） |
| `status:"failed"` 空データ | 上記と同様（get_collection の失敗形態） |

**レート制限の規律（アカウント停止防止、ユーザー明確要求）**：バッチスレッド間でランダム 10–20 秒、並行処理なし、429/403 でバックオフ、5xx でバックオフ再試行；
ページネーション ≥3 秒；schematized 補完取得 ≥4 秒；スペースメタデータ取得 ≥3 秒。単一スレッドエクスポート = 1–2 リクエスト ≈ 1 ページの表示に相当。

<a id="中断语义实测取值2026-07-22分类真源-parsersclassify_wf_status" data-pplx-source-anchor="true"></a>
### 中断セマンティクスの実測値（2026-07-22、分類真ソース `parsers.classify_wf_status`）

`locked_reason` フィールド：`thread_metadata` / `entries[]` / `background_entries[]`
（plain と schematized の両側）に出現。実測された唯一の値：

| locked_reason | 意味 | 実測分布 |
|---|---|---|
| `spending_limit_exceeded` | クォータ中断（クォータ枯渇、ワークフローは中断ポイントで停止） | 全アーカイブでちょうど 1 スレッド（raw_entries と raw_blocks の両側にマークあり） |

workflow ステータスフィールド（`workflow_block.status` とネストされた `workflow_payload.status` は同じ列挙型）の実測値：

| status | セマンティクス | レンダリング注釈（COMPLETED は注釈なし） |
|---|---|---|
| `WORKFLOW_COMPLETED` | 正常完了 | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | 次のステップを待機；`locked_reason=spending_limit_exceeded` と組み合わせると**クォータ中断**（コンテンツは中断ポイントまで）、locked_reason なしの場合は中断保留中 | `⏸ 限额中断（内容截至中断点）` / `⏸ 中断待续` |
| `WORKFLOW_CANCELED` | キャンセル済み（ユーザー/プラットフォームによる中止） | `⛔ 已取消` |

- `WORKFLOW_CANCELED` 実測 19 箇所（16 メイン + 3 ネスト）、7 つの computer スレッドに分布
  （a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff）。
- 注意：メインエントリアンカーペイロードの status は遅延する可能性あり（実測でアンカー COMPLETED だがバックグラウンドは実際には CANCELED）——
  サブエージェントの実際の状態はバックグラウンド側の `workflow_block.status` を基準とする。
- 中断されたバックグラウンドタスクは subagent_result 完了通知を生成しない；未消費のバックグラウンドペイロードはスレッド付録で補完される
  （[subagents-interruptions.md](../../architecture/subagents-interruptions.md)「帰属ウォーターフォール」参照）。
- computer モードの空回答（2026-07 二重確認、回復不可）：computer モードでは一部のターンの回答が空である。
  これはサーバー側にそもそも回答がないため——API 再取得で得られるデータはアーカイブと完全に一致し、UI で
  「完了 N ステップ」折りたたみバーを展開してもゼロデータリクエストが発生する（純粋なクライアントサイドレンダリング、UI と API は同一起源）、API では救済不可。
  このような空回答ターンの一部のみが `locked_reason=spending_limit_exceeded` に関連し、残りはサーバー側に原因マークがない。

<a id="side_by_side_metadata答案重写变体信号2026-07-23-定案" data-pplx-source-anchor="true"></a>
### `side_by_side_metadata`：回答書き換えバリアントシグナル（2026-07-23 確定）

フィールドパス：`entries[].side_by_side_metadata`（plain `/rest/thread/<uuid>` レスポンス）。
プラットフォームが同一クエリに対して複数バージョンの回答を生成する（A/B 実験または書き換え）場合、現在有効なエントリに残る
唯一の痕跡——**置き換えられたバリアント本体（テキスト/ステップ/引用）はスレッド API レスポンスに含まれない**（実例
b2d2632b：レスポンスは 1 エントリ、1 FINAL のみ、バリアント 2 は完全に不可視）。

観測されたキーと値（b2d2632b raw が証拠、全ライブラリ 2442 エントリスキャン）：

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| キー | セマンティクス（観測/仮説） |
|---|---|
| `sibling_uuid` | 同一クエリの**兄弟回答バリアント**（別バージョンのエントリ/コンテキスト識別子）を指す。全ライブラリ 7 スレッドが該当；**オンライン調査（2026-07-23）でデッドリンク確認**：二重アカウント `GET /rest/thread/<sibling_uuid>` ともに 403 `VIEW_THREAD_NOT_ALLOWED`（404/ENTRY_EXPIRED ではない——サーバーは存在するが表示権限のないオブジェクトとして認識）、ブラウザ（所有者アカウント）で `/search/<sibling_uuid>` を開くと SPA によりホームページにリダイレクト——置き換えられたバリアントは sibling_uuid から回復不可 |
| `selection_status` | `SELECTED` = このエントリの回答は表示用に選択されたバージョン；対照群のインスタンスはすべて `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | 実験の役割。対照群は `[control]` プレフィックスを持つ（全ライブラリ 6 例：`[control]default-model-class:gpt41` 等）；実例はプレフィックスなし（`override-default-model-class:qwen3_instruct-01f7f`、すなわちモデルカバレッジ実験の実験群） |
| `experiment_override` | 実験カバレッジパラメータ（例：`override-default-model-class: qwen3_instruct`）；実験群のインスタンスのみ観測 |
| `execution_log` | 観測値は空オブジェクト、セマンティクスは不明 |

**絞り込み判定基準**（「実際の書き換えで二重バージョンが保持されている」と「通常の A/B 対照」を区別）：
`sibling_uuid` が非空 かつ（`selection_status` が非空かつ `SELECTION_STATUS_UNSPECIFIED` ではない、
または `experiment_role` に `[control]` プレフィックスがない）→ 全ライブラリ 2442 エントリ中**b2d2632b の 1 エントリのみ該当**
（確認済み唯一の実例；本ライブラリ内での precision/recall はともに 1、サンプルサイズ 1 のため外挿は保証されない）。

ツールの動作：`parsers.collect_answer_variants` が該当エントリを抽出、`adapter.get_thread`
log.warning で警告 + `thread.json.answer_variants` に書き込み（該当なしの場合はキーは出現しない）；
`re-render --thread-json` でその場で追加/削除（冪等）。時間的証拠：実例エントリ `created→updated`
の差は 53.66 秒（17:13 に生成後書き換え/選択）、かつ書き換えによりスレッドレベルの `lastUpdated` が更新された（増分再誘導で
再取得はトリガーされるが、再取得されたレスポンスには現在有効な回答のみが含まれ、古いバリアントは回復不可）。

**検出ログと対処フロー（2026-07-23、`sites/perplexity/variant_log.py`）**：

- **ログマーク**：該当時は WARNING レベルの単一行、統一 grep 可能なマーク `ANSWER_VARIANT_DETECTED`、
  すべての位置情報フィールドと対処ガイダンスを含む、形式例：
  `ANSWER_VARIANT_DETECTED thread=<全量uuid> uuid8=<8位> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | 处置：…`
  オンラインパス（`adapter.get_thread`）では実際の取得時に毎回該当時に出力；オフライン `re-render`
  **は登録コンテンツが新規/変更された場合のみ**出力（冪等な再実行では画面が埋まらない）；`batch` 末尾のサマリーには別途
  該当件数の注意書きが出力される（既存のサマリー形式を壊さない）。
- **集中登録所**：`<out>/index/answer_variants_log.jsonl`（**入库ファイル**、
  gitignore 配下ではない `logs/`）——1 行 1 JSON（detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role）、(web_uuid, entry_uuid) で重複排除、重複エクスポート/再レンダリングで無限追加されず、
  detected_at は初回検出時刻を保持。
- **該当後の推奨アクション**：sibling は実証済みの通り多くがデッドリンク（上表参照）、代替回答は通常**API で救済不可**——
  速やかに人手で代替回答がまだ取得可能か確認（プラットフォームセッション側/ユーザーの記憶/スクリーンショット）、取得可能なら
  スレッドディレクトリ下に `rewritten_answer_variant.md` と同種の手動ファイルとして追録；取得不可なら `thread.json.answer_variants` +
  jsonl 登録を最終的な追跡可能な痕跡とする。
