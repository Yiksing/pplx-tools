---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/maintenance-commands.zh-CN.md"
translation_source_sha256: "ed280b2fa84c7dfed83da45f6fa05dbee6191c9ce3542ffaca92686cb1fab5fc"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="维护命令" data-pplx-source-anchor="true"></a>
# メンテナンスコマンド

`pplx-export` のメンテナンス系サブコマンドは、既存のアーカイブを健全に保つ役割を担います。レンダリングレイヤー修復後のページ再レンダリング、アセット・クレジット使用量・モードメタデータの補完、リモートで削除されたスレッドへの墓石マーキング、関係グラフの再構築などを行います。ほとんどのコマンドはオフラインファーストです。オンラインフェーズでは、`batch` と同じレート制限の規律に従います（[rate-limiting.zh-CN.md](rate-limiting.md) 参照）。すべてのコマンドは[共通オプション](pplx-export.md)（`--account`、`--out`、`--cookies-from`、`--transport` など）を受け付けます。

- ローカルアーカイブ保持の原則：いかなるメンテナンスコマンドも、アーカイブされたスレッドコンテンツを削除したり移動したりしません。アーカイブはバックアップです。
- オフラインコマンド（`re-render`、`relations`、`sync-space`、`--fetch-meta` なしの `spaces`、および以下の各コマンドのデフォルトフェーズ）はデータパスをまったく必要としません。[../architecture/offline-operations.zh-CN.md](../architecture/offline-operations.md) を参照してください。

## re-render

アーカイブされた元の JSON（`raw_entries.json` / `raw_blocks.json`）から `conversation.md` と `turns/` を再生成します。ネットワークはゼロ、その他のファイルは一切変更しません。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--limit N` | 最初の N 個のスレッドディレクトリのみ処理 | すべて |
| `--dry-run` | 処理するディレクトリを一覧表示するのみで、ファイルは書き込まない | オフ |
| `--thread-json` | 同時に `thread.json` の `interruptions` キーと `answer_variants` キーをその場で追加/削除 | オフ |

重要な動作：

- エクスポートと同じパイプラインを使用してターンをオフラインで再構築：解析、`created_us` によるソート、引用の重複排除。computer/council ではさらにワークフローブロック、サブエージェントマッピング、未消費のバックグラウンド付録を追加します。
- `conversation.md` と `turns/turn_*.md` のみを（再）書き込みます。`sources*`、`assets/`、`report.md`、`thread.json` はそのまま残します。現在のラウンド番号より大きい番号の残存 `turn_*.md` は削除されます。それ以外は変更せず、変更のないファイルは mtime を保持します。
- `--thread-json` は内容に変更があった場合のみディスクに書き込まれます。`answer_variants` が新規または変更された場合、`ANSWER_VARIANT_DETECTED` で警告し、`index/answer_variants_log.jsonl` に追記登録します（冪等な再実行では画面が埋まりません）。
- `raw_entries.json` がないスレッドディレクトリはスキップされ、カウントされます。

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

アーカイブ時に署名付き URL を取得できなかったアセットを救済します。3段階の救済：ブロックの再取得、オフラインインライン抽出、オプションのオンラインリフレッシュ。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--fetch-blocks` | 最初に欠落している `raw_blocks.json` とその署名付き URL アセットを再取得（オンライン） | オフ |
| `--online` | 欠落/無効なアセットのオンラインリフレッシュを有効化 | オフ（オフラインインライン抽出のみ、リクエストゼロ） |
| `--limit N` | 最初の N 個のスレッドディレクトリのみ処理 | すべて |

重要な動作：

- デフォルトフェーズ（オフライン、リクエストゼロ）：`raw_blocks.json` からインラインアセット（`ASSET_DIFF` / `CODE_ASSET`）を抽出し、`assets/files/*.md` としてディスクに保存します。また、クラウドワークスペースハンドルクラス（`DOC_FILE` / `CODE_FILE` / `UNKNOWN` — 現在ダウンロードチャネルなし）を `assets/assets_manifest.json` に登録します。冪等：既知のレコードは uuid → file_handle で重複チェック。同名の複数バージョンファイルには uuid の短いプレフィックスを追加し、再実行しても競合しません。
- `--fetch-blocks`（オンライン）：deep-research/computer/council/study スレッドで欠落している `raw_blocks.json` とそのダウンロード可能なアセットを再取得します。スレッドはアカウントディレクトリごとにグループ化され、アカウントごとにアダプターが遅延構築され（cookie 自動切り替え）、スレッド間隔は 3 秒です。
- `--online`：マニフェスト内で `downloaded_to` が欠落または無効なバージョンについて、`/rest/assets/<uuid>/data` を介して新しい署名付き URL を取得し（API シリアル、間隔 3 秒）、CDN から再ダウンロードします（6 スレッド同時、遅延なし — CDN は API ではありません）。404 `ASSET_NOT_FOUND` は `asset_expired` 最終状態マークを設定します。アカウント間の 403 は、アーカイブ所有アカウントで 1 回再試行します。
- 書き戻すたびに、マニフェストの `count` をバージョン総数として再計算します。

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

アカウントのアーカイブされた全スレッドのクレジット使用量レコード（`credits/thread-usage`）を補完し、`index/credit_usage_<account>.json` に書き込みます。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--limit N` | 最初の N 個のスレッドのみ処理 | すべて |

重要な動作：

- アーカイブされた各スレッドに対して 1 回の GET（`thread_id` でスレッドの `psc_uuid` を取得）、間隔 3 秒。冪等 — 出力ファイルに既に記録されているスレッドはスキップされます。
- 403（`thread_usage_forbidden`、つまりアカウント間スレッド）は `error` として記録され、再試行されません。その他の失敗は次のラウンドに持ち越されます。25 スレッド処理ごとに中間保存が行われます。
- 複数アカウント：各アカウントで `--account` を使用して 1 回ずつ実行 — cookie は実行間で自動的に切り替わります。

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

`index/library_<account>.json` の各行に、プラットフォームの信頼できる `search_mode` フィールドを補完します。これにより、`batch --mode` がヒューリスティックに頼らずに正確にフィルタリングできるようになります。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--limit N` | 最初の N 行の未補完行のみ処理 | すべて |
| `--offline` | ローカル抽出のみ — ローカルに raw がない行は次のラウンドに持ち越し、ネットワークにフォールバックしない | オフ |
| `--delay-min SEC` | ネットワークフォールバック時のスレッド間ランダム間隔の下限 | `10` |
| `--delay-max SEC` | ネットワークフォールバック時のスレッド間ランダム間隔の上限 | `20` |

重要な動作：

- プラットフォームの元の値を保存します（`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…）。スレッド内で複数の値がある場合は、特異性の高い順（computer > council > study > deep-research > search）で最も高いものを採用します。
- ローカル優先：アーカイブされたスレッドから `raw_entries.json` を抽出します。ネットワークはゼロ。純粋にローカルで解決できる場合は、transport すら構築しません（セッション検出も行いません）。
- ローカルに raw がない行のみネットワークフォールバック：`GET /rest/thread/<uuid>`、10～20 秒のランダム間隔。`expired` 最終状態の行はスキップされ、そのまま記録されます。オンラインで新たに expired/deleted と判明したスレッドは `batch_state.json` にマークされ、次のラウンドではリクエストされません。
- 冪等で再実行可能：既に `search_mode` がある行はスキップされ、25 行ごとに中間保存されます。その後、`index` のリフレッシュでは、リッチ化結果が保持されます（`entryUUID` でマージバックされます）。

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

リモートライブラリから消失したスレッド（ユーザーによる削除またはプラットフォームによるクリア）を識別し、墓石マークを付けます。アーカイブファイルを削除したり移動したりすることは決してありません。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--online` | 候補をオンラインで検証 | オフ（オフライン dry-run：候補を一覧表示するのみ） |
| `--limit N` | 最初の N 個の候補のみ処理 | すべて |
| `--delay-min SEC` | 候補間のランダム間隔の下限 | `10` |
| `--delay-max SEC` | 候補間のランダム間隔の上限 | `20` |

重要な動作：

- 候補判定はオフラインかつアカウント間：`batch_state` の状態が `ok` であるスレッドが、**すべて**の `index/library_*.json` の `entryUUID` 統合セットから消失している場合にのみ候補となります。いずれかのインデックスに存在すれば生存とみなされるため、共有スペースを介してアカウント間でエクスポートされたスレッドが誤検出されることはありません。利用可能なインデックスがない場合は、すべて安全にスキップされ、最初に `index` を実行するよう促すメッセージが表示されます。
- デフォルトはオフライン dry-run：候補と安全にスキップされた理由のみを一覧表示します。ネットワークはゼロ、ファイルは一切変更しません。
- `--online` は、候補 `thread.json` の `export_via` アカウントを使用して、候補ごとに `GET /rest/thread/<uuid>` で検証します（cookie は候補ごとに自動切り替え）。
- `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 確認 → `batch_state` マークを最終状態 `deleted` に設定します（`expired` と同じセマンティクス：再試行なし、`--force` でも再エクスポートしません。[incremental-sync.zh-CN.md](incremental-sync.md) 参照）。また、そのスレッドの各 `thread.json` にその場で `remote_deleted` タイムスタンプを追加します（冪等 — 既にキーが存在する場合は上書きしません）。
- スレッドがまだ存在する場合 → 誤検出：そのまま報告し、`index` の再実行を促します。状態は一切変更しません。転送エラーは次のラウンドに持ち越されます。認証失敗が 3 回連続すると中止され、生存スレッドの誤マークを防ぎます。

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

最初の行は候補の一覧表示のみ（オフライン dry-run）。2 行目はオンラインで検証し、確認されたスレッドにマークを付けます。

## status

アーカイブ状態の台帳と増分変更計画を出力します。ネットワークはゼロ、読み取り専用。「アーカイブの現状は？次の `batch` は何をする？」に答え、ネットワークには一切触れません。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--account X` | 1 つのアカウントのみ報告 | `index/library_*.json` を持つすべてのアカウント |
| `--json` | 機械可読な完全レポート（stdout に単一行 JSON、-v レベルは無視） | オフ（人間可読なログ行） |

重要な動作：

- データソースはすべてローカル：`index/library_*.json`（各アカウントのインデックス行）と `index/batch_state.json`（エクスポート状態の唯一の真のソース）。変更分類は、`batch`/`schedule` と同じ `plan_incremental` 純粋関数を再利用します。`new`/`updated`/`done`/`expired`/`deleted` のセマンティクスは、`batch` の計算と完全に一致します。
- デフォルトの INFO 出力：アカウントごとに 1 行のサマリー（インデックスエントリ数と鮮度、`ok/expired/deleted/error` 状態カウント、`new/updated` 変更カウント、早期停止数）。末尾に 1 行のグローバルな `batch_state` 状態台帳（例：`559 ok + 13 expired + 12 deleted`）。
- 詳細レベルは既存の `-v` カウントフラグに直接対応：`-v` は new/updated/error スレッドのタイトルを追加（最初の行、60 文字で切り捨て）。`-vv` は done/expired/deleted スレッドを追加し、`lastUpdated`/`exported_at` を添付。`-vvv` は完全出力で切り捨てなし、インデックスの `mode`/`search_mode` フィールドと state-only リスト（`batch_state` には存在するが、すべてのアカウントインデックスには存在しないレコード — リモート削除の可能性があり、[sync-deleted](#sync-deleted) で照合可能）を添付。
- ガード：`index/` またはライブラリファイルが欠落 → エラーで `pplx-export index` を指摘。`batch_state.json` が欠落している場合は空の状態として扱います（すべて new と判定）。ユーザーレベルの設定は不要。アカウント名はライブラリファイル名から列挙されます。
- `--json` は stdout に完全レポートを出力します（accounts/changes/threads/state_only/totals の単一行 JSON）。`pplx-ask` と同じ契約スタイルです。

```bash
pplx-export status                 # 全部账户摘要
pplx-export status -vv             # 五态线程明细
pplx-export status --account alice --json
```

## relations

エクスポートされたスレッドから会話関係グラフを再構築し、アーカイブルートの `relations/edges.jsonl` と、人間可読なサマリー `relations/graph.md` を出力します。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| *（共通オプションのみ。`--out` のみ有効）* | | |

重要な動作：

- 完全オフライン、ネットワークゼロ、アーカイブに対して読み取り専用：re-render のオフライン再構築パイプライン（`raw_entries.json` / `raw_blocks.json`）を再利用します。`sub_agents`、`query_source`、引用などのシグナルもエッジ検出に使用できます。
- raw データがないスレッドは、`thread.json` + `conversation.md` のシェルに退化します。`same_space` と裸の uuid 参照エッジのみをトリガーできます。

```bash
pplx-export relations
```

## debug-js

ローカルの WebBridge デーモン（`127.0.0.1:10086`）を介して、現在のブラウザページのコンテキストで JavaScript を実行し、結果を JSON で出力します。デバッグ用の非常口です。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `JS代码`（位置パラメータ） | ページコンテキストで実行する JavaScript コード | 必須 |

重要な動作：

- WebBridge デーモンが到達可能であり、ブラウザで対象の Perplexity ページが開かれている必要があります。コードスニペットはページ自身のセッション内で実行されます。
- 出力される JSON は 5000 文字に切り詰められます。

```bash
pplx-export debug-js 'document.title'
```
