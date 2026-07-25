---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/modes.zh-CN.md"
translation_source_sha256: "902b8570a856deeeb385f0d0babe3d22af5388a78c1cb546c595ece011aacade"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="会话模式" data-pplx-source-anchor="true"></a>
# セッションモード

Perplexity セッションには5つのモードがあります：`search` / `deep-research` / `computer` / `council` / `study`。
エクスポート時はスレッド単位でモードが判定されます。これにより、どのAPIレスポンスを取得するか、スレッドディレクトリに何を出力するか、スレッドがどの[アーカイブパス](archive-layout.md)（`<账户>/<模式>/…`）に入るかが決まります。判定結果は
`thread.json`（`mode` キー）に記録され、`pplx-export batch --mode` フィルタリングに使用されます。`pplx-ask`
は5つのモードのうち4つ（`computer` を除く）で新しいスレッドを**作成**することもできます。[pplx-ask](pplx-ask.md) を参照してください。

<a id="五种模式一览" data-pplx-source-anchor="true"></a>
## 5つのモード一覧

| モード | UI名 / モデル | ラウンド内容 | 引用 | 成果物 | schematized blocksの取得 |
|---|---|---|---|---|---|
| `search` | 「Best」（`pplx_pro`；labsの `STUDIO`/`pplx_beta` もこれに含む） | Query + Answer、テキストステップ | ラウンドレベル + 全スレッド `sources.*` | — | いいえ（`raw_blocks.json` なし） |
| `deep-research` | 「Deep research」（`pplx_alpha`、固定で選択不可） | 研究ステップ、`RESEARCH_ANSWER` を含む | あり | `report.md`（完全なレポート） | はい |
| `computer` | Computer（`pplx_asi_opus`、`pplx_asi_opus_thinking`） | 完全な `workflow_block`：ナレーション、ツール呼び出し、サブエージェントのプロンプト/ステップ、ステップごとの引用 | ステップ + ラウンド + 全スレッド | `assets/` 複数バージョンファイル + サブエージェント実行 | はい |
| `council` | モデル委員会（`pplx_agentic_research`；デフォルト3モデル） | `COUNCIL_RESEARCH` ステップ；各モデルのネストされた `LLM_COUNCIL` ワークフローが `<details>`（検索ラウンド、全ソース、完全な単一モデル回答）に折りたたまれる | 単一モデル + 集約 | 複数モデルの回答を並べて比較 | はい |
| `study` | Study（`pplx_study`） | blocksを介してステップ/引用を提供（実際にはアセットも含む） | あり | 存在する場合はアセット | はい |

<a id="模式如何判定" data-pplx-source-anchor="true"></a>
## モードの判定方法

判定の権威はプラットフォーム自身のフィールド **`entry.search_mode`**（`SEARCH_MODE_MAP`、
`normalize.py:50-59`）であり、すべてのエントリを走査して収集します（`normalize.py:106-115`）。
公式モデル設定（`GET /rest/models/config/v2`）で検証済み：
`default_models.search=pplx_pro`（UI「Best」）、`default_models.research=pplx_alpha`
（UI「Deep research」）。値はセッションモードと一対一で対応します：

| `search_mode` の値 | モード |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`、`STUDIO` | `search` |

競合ルール（`detect_mode`、`normalize.py:66-128`）：

- **スレッド内モード切り替え**（エントリが不一致）：特異性が最も高いものを採用——
  **computer > council > study > deep-research > search**（`_MODE_SPECIFICITY`、
  `normalize.py:63`）——そして `log.warning`。
- **下流シグナルとの競合**（ステップ名 / `display_model`）：`search_mode` が優先され、
  `log.warning`（`normalize.py:120-123`）。
- **`search_mode` が完全に欠落** → フォールバックチェーン：URLに `/computer/tasks/` または
  `metadata.mode == '4'` が含まれる、またはインデックス mode ∈ `ASI`/`COMPUTER` → `computer`；`COUNCIL_RESEARCH` ステップが存在 → `council`；`RESEARCH_ANSWER` ステップが存在 → `deep-research`；
  冗長シグナル `display_model`（`DISPLAY_MODEL_MODE`、`normalize.py:32-37`）が競合時に優先；
  すべて該当なし → デフォルト `search`。
- **シグナルが完全に欠落しても search と断定しない**：パイプラインは引き続き schematized blocks を
  取得（`adapter.py:83-89`）、プラットフォームフィールドの変動によって `raw_blocks.json` が
  静かに失われることはありません。

!!! note "`pplx_alpha` が判定基準にならない理由"
    `pplx_alpha` は RESEARCH 専用モデルです——これは分類器が判定すべき**ターゲット**であり、
    判定の証拠ではないため、マッピングテーブルから意図的に除外されています（`normalize.py:15-31` コメント）。

すべての分岐を含む完全な決定木：[エクスポートパイプライン——モード判定](../architecture/export-pipeline.md)。

<a id="子代理负载的落点" data-pplx-source-anchor="true"></a>
## サブエージェントペイロードの配置場所

computer/council の実行では、バックグラウンドでサブエージェントワークフローが生成されます。各バックグラウンド `workflow_payload`
は**正確に1つの場所に配置され、2回レンダリングされることはありません**。ユーザー側の3つの可能な配置場所：

1. **アンカー——発行ラウンドに配置**：サブエージェントを発行したラウンドは同じペイロードIDを持つため、その実行は
   このラウンドの作業プロセスにインラインでレンダリングされます（`turns/turn_NNNN.md`）。プロンプト、ステップ、回答、ソースを含みます。
2. **スタブラウンド——「サブエージェント作業」セクション**：10秒完了ウィンドウ内の `subagent_result` スタブラウンドが
   そのペイロードを吸収します。回答はバックフィルされません。
3. **スレッド付録——`conversation.md` の末尾**：残りのすべてのペイロード（中断された実行には完了通知がなく、
   前の2つのレベルで必ず見逃される）は、「## バックグラウンドタスク（ラウンド未割り当て）」の下にそのままアーカイブされます。
   時間の帰属は推測せず、任意のステータスを受け入れます。

マッチングルール、データ構造、および1回限りの消費保証：
[サブエージェントと中断](../architecture/subagents-interruptions.md)。

<a id="中断非-completed-工作流" data-pplx-source-anchor="true"></a>
## 中断：COMPLETED 以外のワークフロー

未完了のワークフローは、そのレンダリング場所にインラインで注釈が付けられます——作業プロセスタイトル、サブエージェントタイトル、ネストされた `<details>`
サマリー。3つの注釈（`parsers.classify_wf_status`、`parsers.py:263-284`）：

| 注釈 | 条件 | 意味 |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | クォータを使い果たし、ワークフローが途中で停止 |
| `⏸ 中断待续` | `WORKFLOW_AWAITING_NEXT_STEPS` かつ `locked_reason` なし | 中断済み、プラットフォームで続行可能 |
| `⛔ 已取消` | `WORKFLOW_CANCELED` | ユーザーまたはプラットフォームによるキャンセル |

- `COMPLETED` は決して注釈されません（正常なスレッドは差分ゼロ）。未知の将来ステータス値は静かに保持されます。
- 注釈された各ケースは同時に `thread.json.interruptions` に登録され、形式は
  `{location, kind, headline, status}`——location は `turn_0007`、
  `turn_0011/subagent`、`turn_0024/subagent_stub`、`background_unassigned` の形式です
  （`parsers.py:535-583`；正常なスレッドではこのキーは出現しません）。
- **続行に特別な処理は不要**：プラットフォームで中断されたスレッドを続行すると、その `lastUpdated` が変化し、
  次の差分エクスポートで再取得され、ワークフローが完了すると注釈は自然に消えます。[差分同期](incremental-sync.md) を参照してください。

実際のステータス値と分布：[APIレスポンスとエラー](../reference/api/api-responses-errors.md)；
ステートマシン：[サブエージェントと中断](../architecture/subagents-interruptions.md)。

<a id="答案重写变体answer_variants" data-pplx-source-anchor="true"></a>
## 回答書き換えバリアント（answer_variants）

プラットフォームが回答を書き換える（A/Bテスト）場合、置き換えられたバリアントはAPI側では見えません——選択された回答のみが返され、
選ばれなかった兄弟バージョンは `entries[].side_by_side_metadata` に痕跡を残すだけで、その後プラットフォームによって削除される可能性があります
（デッドリンク確認済み：403 `VIEW_THREAD_NOT_ALLOWED`）。ツールは「書き換えが発生したこと」を観測可能にします：

- **登録**：絞り込み条件に一致すると `thread.json.answer_variants`（`fs_writer.py:247-252`；
  一致なしではこのキーは出現しない）に書き込まれ、集中登録所 `index/answer_variants_log.jsonl` に追加されます。
  （スレッド, エントリ）で重複排除され、冪等です（`variant_log.py:76`）。
- **警告**：オンラインで一致するたびに、grep可能な1行のWARNING `ANSWER_VARIANT_DETECTED` を出力します。
  完全な位置特定フィールド（スレッド uuid/uuid8、entry_uuid、sibling_uuid、selection_status、
  experiment_role）を含みます。`re-render` オフラインで再登録し、コンテンツが新規または変更された場合のみ警告します。
  全データベースの再実行では画面が埋め尽くされません。バッチサマリーに ⚠ 一致数が追加されます。
- **手動による補完アーカイブ**：兄弟バリアントは実際にデッドリンクであり、代替回答は通常**API経由では復元できません**。
  一致後は、できるだけ早く手動で代替回答を確認してください（プラットフォームUI、自身の記録、スクリーンショット）。
  取得できた場合は、スレッドディレクトリ内の `rewritten_answer_variant.md` として記録します。
  取得できない場合、`thread.json.answer_variants` にjsonl
  登録所が最終的な追跡可能な記録となります。

検出チェーンとオフライン再登録：[オフライン操作](../architecture/offline-operations.md)；フィールドセマンティクスと
デッドリンクの証拠：[APIレスポンスとエラー](../reference/api/api-responses-errors.md)。

<a id="渲染保真原则" data-pplx-source-anchor="true"></a>
## レンダリング忠実度の原則

どのモードでも、レンダリングは同じ忠実度契約に従います：

- **回答は完全に表示され、決して切り詰められない**——古い `[:4000]` の切り詰めは文を切断するため、
  削除されました（`render.py:645-647`）。
- **テーブルは決して切り詰められない**——`WORKFLOW_ITEM_TABLE` はすべての行と列をレンダリングし、ヘッダーとセル内の `|`
  と改行はエスケープされ、Markdown構造は破壊されません（`render.py:211-243`）。
- **引用は完全**——3つの収集チャネル（`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`）により、URLで重複排除して `sources.*` に統合。参照されたものは失われません。
- **API raw JSON がコンテンツの境界**——レンダリングされるものはすべて `raw_entries.json` /
  `raw_blocks.json` から取得されます。APIが返さないもの（置き換えられた回答バリアントなど）はレンダリングできず、
  代わりに登録キーを通じて提示され、決して捏造されません。
- **UIで折りたたまれているものは、アーカイブでは完全に展開**——Web UIで折りたたみやクリックの背後に隠れている詳細
  （computerワークフローのナレーションとツール入出力、councilの単一モデル実行、サブエージェントステップ）はすべて完全にレンダリングされます。`<details>`
  折りたたみブロックを使用して、ドキュメントのアウトラインを読みやすく保ちつつ情報を失いません（`render.py:46`、`render.py:404-413`）。
- **構造の堅牢性**——コードフェンスはコンテンツに応じて長さが決められ（`_fence_for`、`render.py:28-43`）、
  フェンスを含むツール出力によってペアが反転することはありません。LaTeX区切り文字は `$$` / `$` に正規化され、コードセクションは保護されます
  （`normalize_math_delims`）。

保持された生のレスポンスが、これらすべてをオフラインで再生成可能にする方法：
[エクスポートパイプライン](../architecture/export-pipeline.md) と [オフライン操作](../architecture/offline-operations.md)。

<a id="另见" data-pplx-source-anchor="true"></a>
## 関連項目

- [アーカイブディレクトリ構造](archive-layout.md)——各モードのファイルの配置場所
- [pplx-ask](pplx-ask.md)——各モードで新しいスレッドを作成
- [差分同期](incremental-sync.md)——続行スレッドの再取得
- [エクスポートパイプライン](../architecture/export-pipeline.md)——完全なモード判定決定木
- [サブエージェントと中断](../architecture/subagents-interruptions.md)——帰属ウォーターフォールとステートマシン
- [APIレスポンスとエラー](../reference/api/api-responses-errors.md)——フィールドの実際の値
