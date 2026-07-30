---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/pplx-export.zh-CN.md"
translation_source_sha256: "034e8bd756bb6d23543186e05d426b609a314dad13d0a0e288257175956f0753"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` はアーカイブCLIです：Perplexity から会話インデックスを取得し、スレッドをローカルアーカイブにエクスポートし、派生ビュー（スペースインデックス、cronスニペット）を維持します。このページでは、収集側のサブコマンド——`index`、`space-index`、`export`、`batch`、`spaces`、`sync-space`、`schedule`——に加えて、1回限りの初期化コマンド `init` をカバーします。補完/修復系のサブコマンドについては [maintenance-commands.zh-CN.md](maintenance-commands.md) を、クエリCLIについては [pplx-ask.zh-CN.md](pplx-ask.md) を参照してください。

<a id="通用选项" data-pplx-source-anchor="true"></a>
## 共通オプション

すべてのサブコマンドは以下のパラメータを受け付けます（`pplx_export/commands/common.py` で一元的に定義）：

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--account NAME` | ターゲットアカウント。cookieの帰属メールと登録メールが一致しない場合、ブラウザ内の各アカウントセッショントークンを自動的に列挙して切り替え | ユーザー設定の `default_account` |
| `--config PATH` | ユーザー設定ファイル（アカウントレジストリ）。優先順位：`--config` > 環境変数 `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | デフォルトの検索チェーン |
| `--skip-auth-check` | 起動時のアカウント帰属セッションプローブをスキップし、現在のログインを信頼。ネットワークが悪いときの最初の長時間待機を回避；`batch` はエラーが蓄積したときに遅延アカウント検証を行う——[設定](configuration.md)を参照 | オフ |
| `--site NAME` | サイトアダプター | `perplexity` |
| `--out DIR` | アーカイブ出力ルートディレクトリ | `--out` > 設定 `archive_root` > `./web_archive` |
| `--cookies-from BROWSER` | 指定したブラウザからcookieをインポート（`edge`/`chrome`/`firefox`/`safari`/`brave`…） | — |
| `--cookies FILE` | Netscape cookieファイルまたはJSON cookieファイル | — |
| `--transport MODE` | `cookie` = cookie直接リクエスト；`webbridge` = ブラウザページコンテキスト内でfetchを発行 | `cookie` |
| `-v`, `--verbose` | DEBUG出力（リクエストトレース、内部判定）；繰り返し可能 | オフ |
| `--log-file [PATH]` | フルログをディスクに書き込み；値なしの場合は自動で `<out>/index/logs/<cmd>-<timestamp>.log` に書き込み | オフ |

- `--cookies-from` / `--cookies` と `--transport webbridge` は排他的——bridgeはページコンテキストで動作し、ブラウザのcookieを自動的に持ち込みます。
- `pplx-export --version` はパッケージバージョンを表示して終了（トップレベルのみ、サブコマンドのパラメータではありません）。
- アカウント登録、cookieソース、マルチアカウント切り替えについては [configuration.zh-CN.md](configuration.md) を参照；各ファイルの書き込み場所については [archive-layout.zh-CN.md](archive-layout.md) を参照。

## init

ブラウザのcookieからアカウントを自動検出し、ユーザー設定に書き込みます——手動で `config.example.toml` をコピーする以外の自動的な方法です（[configuration.zh-CN.md](configuration.md) を参照）。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--force` | 既存の設定ファイルを上書き | オフ（上書き拒否） |
| `--create-bot-space [标题]` | スペースタイトルが一致しない場合、API経由でBOTスペースを作成（アカウントへの1回の書き込み操作）；明示的なタイトルが指定された場合、マッチングと作成の両方でそのタイトルを使用。それ以外の場合、タイトルは `--bot-title` から取得；このフラグがない場合、`[bot_space]` は空のまま書き込まれる | オフ |
| `--bot-title TITLE` | 既存スペースのマッチングと作成時の命名の両方に使用されるスペースタイトル | `BOT` |
| *（共通オプション適用）* | cookieソースフラグがアカウント検出の場所を決定；`init` の場合のみ、`--config` は**書き込み**パス（strict設定ロードをスキップ） | |

重要な動作：

- トークン列挙：ブラウザライブラリから各アカウントのセッションcookieを収集（`__Secure-pplx.session.<uid>`）；`--cookies FILE` が指定された場合、代わりにそのcookieファイルをスキャン（完全エクスポートは複数のアカウントを含む可能性あり）。列挙可能なトークンがない場合、現在のアクティブセッションのみのプローブにフォールバック。
- セッションプローブ：各トークンに対して `GET /api/auth/session` にリクエストし、アカウントのメール/表示名を取得；失敗した場合やメールが返されなかったトークンはwarningでスキップ。
- レジストリアセンブリ：アカウントキーはメールのローカル部分から派生（名前の衝突時は `-2`/`-3`… のサフィックスを追加）；`default_account` は現在のアクティブアカウントを取得し、それ以外の場合は最初に見つかったアカウントを取得。
- BOTスペース：`list_user_collections` 経由でタイトルを完全一致（大文字小文字を区別しない）；一致しない場合、`--create-bot-space [标题]` がその場で作成（明示的なタイトルは `--bot-title` を上書きし、マッチングと作成の両方で使用）、それ以外の場合は `[bot_space]` は空のまま。
- TOMLアトミック書き込み（一時ファイル＋リネーム）、パーミッション0600；既存ファイルは `--force` なしでは決して上書きしない。コマンド終了時に要約JSONを1行出力：設定パス、アカウントキー、デフォルトアカウント、BOTスペースのuuid/slug。
- `--transport webbridge` は拒否される——ページコンテキストチャネルでは各アカウントのトークンを列挙できません。

```bash
pplx-export init                          # 写入默认 ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [标题]  # 无标题匹配时创建 BOT 空间（可附自定义标题）
pplx-export init --config /path/to/config.toml --force   # 自定义路径，允许覆盖
```

## index

アカウントの会話リストメインインデックス `index/library_<account>.json` を更新します——他のすべてのコマンドの比較ベースラインです。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--full` | 全ページを取得し、インデックス全体を書き換え；増分カウンタをリセット | 増分 |

重要な動作：

- **デフォルト増分**：最新のものからページを取得し、「連続した1ページ全体（`_STOP_RUN`）が既知で変更なし」に遭遇したら停止。取得した先頭部分を既存のインデックスにマージ——より古い行はそのまま保持（失わない）。初回実行時や既存インデックスがない場合は全量として動作。
- **`--full`** 全ページを取得し、インデックス全体を書き換え；定期的な調整の前提として使用。
- **増分パスの盲点**：古いスレッドのリモートでの*削除*と*スペース変更*は取得した先頭部分には現れないため、見えません。削除の権威は依然として `sync-deleted --online` です。インデックスドキュメントは `incremental_runs_since_full` を記録；連続して複数回の増分を行った後は、`--full`（および `sync-deleted --online` と組み合わせて）を実行するよう促します。
- `search-mode-backfill` によって書き込まれた `search_mode` のリッチ化を保持し、`entryUUID` に従ってマージして戻します。
- `batch`、`sync-space`、`sync-deleted` を実行する前にこれを実行してください——それらの比較結果はインデックスの新鮮さに依存します。

```bash
pplx-export index --account alice          # 增量刷新
pplx-export index --account alice --full   # 全量对账前置
```

## sync

高頻度同期の便利なエントリポイント：**増分 `index` + 増分 `batch`**、会話のみに焦点を当てます。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--full` | 全量調整：全量 `index` + `batch` フルスキャン（以下の削除/スペースステップを実行） | オフ |
| `--check-deleted` | `sync-deleted --online` を付帯：リモートで削除されたスレッドを検証してマーク | オフ |
| `--refresh-spaces` | `spaces --fetch-meta` と `sync-space` を付帯 | オフ |
| `--limit N` / `--mode X` / `--delay-min` / `--delay-max` | `batch` フェーズに透過的に渡す | — |

重要な動作：

- デフォルトでは新規/更新された会話のみを取得し、**削除検出とスペース更新をスキップ**——高頻度同期で最も効率的。
- 削除/スペースの調整はオプション（`--check-deleted` / `--refresh-spaces`）または `--full` によって一緒に完了。`index` のカウント（`incremental_runs_since_full`）はセーフティネット：期限が来ると、`--full` の調整を実行するよう促します。

```bash
pplx-export sync --account alice                     # 只关注对话（快）
pplx-export sync --account alice --full              # 定期全量对账
pplx-export sync --account alice --check-deleted     # 顺带标记远端删除
```

## space-index

特定のスペースの「すべての」会話リストを抽出——共有スペースの他のメンバーのスレッドも含む——`index/space_<slug>.json` に書き込みます。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `SPACE_URL`（位置パラメータ） | スペースページのURL | 必須 |
| `--transport webbridge` | 古いブラウザレンダリングパスをRESTの代わりに使用 | `cookie`（REST直接接続） |

重要な動作：

- デフォルトはREST直接接続：cookieチャネル経由で `list_collection_threads` を呼び出し、offsetページネーション；行には `context_uuid` と `answer_preview` が含まれます。
- `--transport webbridge` の場合、スクロールレンダリングスペースページにフォールバックし、行属性を取得する古いパス——REST構造変更時の代替チャネル。
- 行は `lastUpdated` に従って新しいものから古いものへとディスクに書き込まれます。

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

単一のスレッド（URLまたはベアUUID）をアーカイブディレクトリ `<out>/<account-folder>/<mode>/<thread-dir>/` にエクスポートします。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `THREAD`（位置パラメータ） | スレッドのURLまたはUUID | 必須 |
| `--force` | `lastUpdated` が変更されていなくても強制的に再エクスポート | オフ |

重要な動作：

- アーカイブコピーが既に最新の場合はスキップし、ファイルは書き込まれません；`--force` はこのチェックを上書きします。
- スレッドがローカルライブラリインデックスに行を持つ場合、`lastUpdated` はインデックス値を取得（`batch` と同じセマンティクス、同じフォーマット）。それ以外の場合はプラットフォームの真の値にフォールバック。
- 終了状態は優雅に記録され、tracebackはスローされません：`ENTRY_DELETED` は `batch_state.json` に `deleted` をマークし、`ENTRY_EXPIRED` は `expired` をマーク——どちらの場合も、ローカルの既存アーカイブはそのまま保持されます。
- エクスポートが成功すると、`ok` が `index/batch_state.json` に書き込まれ、増分計画はこれに基づいてそのスレッドを「エクスポート済みで変更なし」とカウントします。
- スレッドディレクトリ内のファイル構成については [archive-layout.zh-CN.md](archive-layout.md) を参照；エクスポートパイプライン自体については [../architecture/export-pipeline.zh-CN.md](../architecture/export-pipeline.md) を参照。

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

アカウントのスレッドをバッチエクスポート——日常の主力コマンドで、増分早期停止と中断再開機能を備えています。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--force` | すべてのスレッドを再エクスポート（終了状態を除く） | オフ |
| `--full` | フルスキャン：変更のないスレッドはスキップされるが、早期停止はしない | オフ |
| `--limit N` | リストの先頭N件のみ処理（新しいものから古いものへ） | すべて |
| `--mode MODE` | `search` / `deep-research` / `computer` / `council` / `study` スレッドのみエクスポート | すべてのモード |
| `--delay-min SEC` | スレッド間のランダム間隔の下限 | `10` |
| `--delay-max SEC` | スレッド間のランダム間隔の上限 | `20` |

重要な動作：

- `index/library_<account>.json` に依存——最初に `index` を実行。
- デフォルトは**増分早期停止**：リストは新しいものから古いものへとソートされ、末尾の「エクスポート済みで変更なし」の連続セグメント全体が切り捨てられます；前回の中断で残ったギャップ（error/未エクスポート）は終了状態サフィックスの上にあり、依然として修復されます。`--full` は早期停止をオフにします（定期的なセーフティネットとして、またはアーカイブにギャップが疑われる場合に使用）；`--force` は終了状態を除くすべてのスレッドを再エクスポートし、終了状態は決して再試行されません。完全なセマンティクスについては [incremental-sync.zh-CN.md](incremental-sync.md) を参照。
- `--mode` フィルタリング：インデックス行が `search_mode`（`search-mode-backfill` でリッチ化されたプラットフォーム権威フィールド）を持つ場合、`SEARCH_MODE_MAP` で完全一致——このパスでは `--mode search` はもはや deep-research/council/study スレッドを混入しません。`search_mode` がない行はインデックスフィールドのヒューリスティックにフォールバック：`computer` = mode `COMPUTER`；`deep-research` = displayModel `pplx_alpha`；`council` = `pplx_agentic_research`；`study` = `pplx_study`；`search` = 残りのmodeが `SEARCH` の行（上記3種類を含む——正確に除外するには対応するモードで個別にエクスポートしてください）。
- スレッドをエクスポートするたびに、状態が `index/batch_state.json` に書き込まれます——いつでも中断して再実行できます。
- 認証の高速失敗：連続3回の401/403で中止（cookieが無効な場合、バックオフでは自己修復できず、空回りで数百のスレッドがそれぞれ失敗するだけです）。
- ペース：スレッド間のランダム間隔 `--delay-min`–`--delay-max`；429/5xxはトランスポート層のバックオフによって処理されます。詳細は [rate-limiting.zh-CN.md](rate-limiting.md) を参照。
- 回答の書き換えバリアントにヒットしたスレッドは `index/answer_variants_log.jsonl` に登録され、警告が表示されます。速やかに手動で対処する必要があります（[../reference/api/api-responses-errors.zh-CN.md](../reference/api/api-responses-errors.md) を参照）。

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

ローカルライブラリインデックスからスペースビューインデックスを再構築——スペースごとに1つのMarkdownページと、`spaces.json` レジストリ。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| `--fetch-meta` | 再構築前に所有者/メンバーメタデータを更新 | オフ |

重要な動作：

- `--fetch-meta` なしの場合は純粋にローカル（ゼロネットワーク）：すべての `library_*.json` にわたってスペースslugでスレッドを集約し、参加アカウント統計とエクスポートされたスレッドディレクトリへのバックリンクを含みます。
- 出力は現在の作業ディレクトリの `./spaces/` に出力されます——`web_archive/` を含むディレクトリで実行してください。そうしないと、スペースページ内のバックリンクが正しく解決されません。
- `--fetch-meta` は最初に `get_collection` 経由で各スペースの所有者/メンバーキャッシュを更新（スペースごとに1リクエスト、3秒間隔）し、`index/space_meta.json` に書き込みます；現在のアカウントに表示権限がないスペースは、自動的に表示可能なアカウントで再試行（cookie自動切り替え）。

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

アーカイブ済み `thread.json` の `space` フィールドを現在のインデックスと同期——純粋にローカル、ゼロネットワーク。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| *（共通オプションのみ；`--out` のみが機能）* | | |

重要な動作：

- 前提条件：最初に `index` を実行——更新後の `library_*.json` が現在のスペース帰属の真のソースです。
- スレッドごとにスペースslugを比較し、差異がある場合はその場で `thread.json` にパッチを適用；最初の30件の変更はログに記録されます。
- 変更があった場合、自動的に `spaces/` インデックスの再構築を連動させます。

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

今回の増分エクスポート計画を計算し、システムのcronから直接呼び出し可能なコマンドスニペットを生成します。

| パラメータ | 意味 | デフォルト値 |
|---|---|---|
| *（共通オプションのみ）* | | |

重要な動作：

- リアルタイムインデックスを取得し、総数/新規/更新で計画を報告。`batch` と同じ早期停止純粋関数（`plan_incremental`）を使用——[incremental-sync.zh-CN.md](incremental-sync.md) を参照。
- `<out>/index/cron_snippet.txt` に書き込み、内容は1行の `17 3 * * *` 行で、形式は `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'`——パスは絶対パスで引用符付き。なぜならcronのcwdとPATHは予測できないからです。実行可能ファイルのパスは `shutil.which` 経由で解決され、解決に失敗した場合はベアコマンド名 `pplx-export` にフォールバックします。
- 定時バッチ実行は設計上、増分のみを実行；`batch --full` は定期的なセーフティネットとして手動で実行します。

```bash
pplx-export schedule --account alice
```
