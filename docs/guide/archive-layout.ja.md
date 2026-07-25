---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/archive-layout.zh-CN.md"
translation_source_sha256: "87d25ea40af1217fcbcddafae7c173aebca9a6669c09a8f77ccb2e8eee557782"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="归档目录结构" data-pplx-source-anchor="true"></a>
# アーカイブディレクトリ構造

`pplx-export` がダウンロードするすべてのコンテンツは、単一の出力ツリーに格納されます。デフォルトは `./web_archive/` です（`--out` で上書き可能）。このページはそのツリーのガイドです。各ディレクトリとファイルの説明、`thread.json` が持つキー、およびセッションが日をまたいで継続される際にツールがスレッドごとに1つのディレクトリを保証する方法について説明します。すべてのコンテンツはツールによって生成されます。メカニズムの詳細は[データモデルとディレクトリ契約](../architecture/data-model.md)および[エクスポートパイプライン](../architecture/export-pipeline.md)を参照してください。

<a id="输出目录树" data-pplx-source-anchor="true"></a>
## 出力ディレクトリツリー

```
web_archive/
├── alice/                                # 每账户一个文件夹（作者显示名）
│   ├── search/                           # 模式：search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # 每线程一个目录
│   │       ├── thread.json               # 元数据 + 可选登记键
│   │       ├── conversation.md           # 简版：逐轮 Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # 完整版：完整工作过程细节
│   │       │   └── ...
│   │       ├── sources.json              # 全线程引文（按 url 去重）
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research 报告（有才存在）
│   │       ├── raw_entries.json          # plain API 响应，原样落盘（恒存在）
│   │       ├── raw_blocks.json           # schematized API 响应（search 无此文件）
│   │       └── assets/
│   │           ├── assets_manifest.json  # 多版本清单
│   │           └── files/                # 已下载的资产文件体
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # 状态文件与索引（见下）
├── relations/                            # edges.jsonl + graph.md（由 `pplx-export relations` 重建）
├── crosscheck/                           # 交叉核验报告（人工/评审产物）
└── bob/ ...
```

<a id="线程目录" data-pplx-source-anchor="true"></a>
## スレッドディレクトリ

各スレッドは正確に1つのディレクトリに対応し、`thread_dir_for`（`fs_writer.py:58-72`）によって計算されます：

```
<账户显示名>/<模式>/<YYYY-MM-DD>_<标题slug>_<uuid8>/
```

| 構成要素 | ソース | 説明 |
|---|---|---|
| `<账户显示名>` | スレッド作成者、`author_folder` → `_safe_folder` でクリーニング（`fs_writer.py:40-51`） | パス区切り文字とWindowsの不正文字（`:*?"<>\|`）は `_` に置き換えられます。`.`/`..` は拒否されます（共有スペースのパストラバーサル防止）。その他の文字（スペースを含む）はそのまま保持されます。 |
| `<模式>` | `detect_mode` | 5つのモードのいずれか。[セッションモード](modes.md)を参照。 |
| `<YYYY-MM-DD>` | `thread.json` の `lastUpdated` 日付プレフィックス | プラットフォーム側の最終更新日。**エクスポート日ではありません**。継続されたスレッドが更新されると変更されます（以下の移行を参照）。 |
| `<标题slug>` | `slugify(title)`（`normalize.py:261-263`） | 最大40文字。非単語文字は `-` に変換。空のタイトルは `untitled` になります。 |
| `<uuid8>` | `web_uuid[:8]` | スレッドUUIDの最初の8文字。ディレクトリのIDアンカー。 |

<a id="线程目录内的文件" data-pplx-source-anchor="true"></a>
## スレッドディレクトリ内のファイル

<a id="threadjson元数据与登记信息" data-pplx-source-anchor="true"></a>
### thread.json — メタデータとレジストリ情報

`write_thread`（`fs_writer.py:224-253`）によって書き込まれます。常に存在するキー：

| キー | 内容 |
|---|---|
| `web_uuid` | web entryUUID — スレッドURL内のUUID、スレッドのID |
| `psc_uuid` | プラットフォームの `context_uuid`（null可。最初の非nullラウンドの値を取得）— スペースインデックスで使用される二重ID |
| `url` | スレッドの正規URL |
| `title` | スレッドのタイトル |
| `mode` | 判定されたモード（`search` / `deep-research` / `computer` / `council` / `study`） |
| `author` | 作成者アカウントの表示名 |
| `export_via` | エクスポートを実行したアカウントのユーザー名。自分のアカウントからエクスポートされた共有スペーススレッドで特に重要。 |
| `space` | `{"uuid", "title", "slug"}` または `null` |
| `lastUpdated` | プラットフォームの最終更新タイムスタンプ（増分同期のマシン比較契約） |
| `threadAccess` | プラットフォームのアクセスフラグ |
| `n_turns` | ラウンド数 |
| `n_sources` | スレッド全体の引用数 |
| `metadata` | API応答内の `thread_metadata`、そのまま保持 |
| `report_info` | `{"title", "file_name", "url"}` または `null` |
| `exported_at` | エクスポート時間（UTC ISO 8601） |

オプションのキー — 対応するコンテンツがない場合は表示されません：

| キー | 書き込まれるタイミング | 内容 |
|---|---|---|
| `interruptions` | 完了していないワークフローが存在する場合（`fs_writer.py:242-244`） | `{location, kind, headline, status}` のリスト。[セッションモード — 中断マーキング](modes.md)を参照。 |
| `answer_variants` | 回答書き換えバリアントが検出された場合（`fs_writer.py:247-252`） | 絞り込み基準の `side_by_side_metadata` ロケーションフィールド。[セッションモード — 回答書き換えバリアント](modes.md)を参照。 |
| `remote_deleted` | `pplx-export sync-deleted --online` がリモート削除を確認した場合 | 墓石タイムスタンプ。その場で書き込み、冪等（既存の値は上書きされません。`sync_deleted_cmd.py:215-244`）。ローカルアーカイブ自体は保持されます。 |

<a id="conversationmd简版" data-pplx-source-anchor="true"></a>
### conversation.md — 簡易版

`render_conversation`（`render.py:641`）：ヘッダー（モード / 作成者 / ラウンド / 引用数）、その後各ラウンドに `### Query` + `### Answer` のペア。回答は完全に表示されます。存在する場合、スレッドレベルのバックグラウンドタスクの付録が末尾に付きます。これは最初に開くべきファイルです。ラウンドごとの作業プロセスは `turns/` にあります。

<a id="turnsturn_nnnnmd完整版" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md — 完全版

`render_turn`（`render.py:596`）：各ラウンドに1つのファイル（`turn_0001.md` …）。完全な作業プロセス（ステップ、ツール呼び出し、サブエージェント実行、テーブル、このラウンドの引用）を含みます。スレッドのラウンド数が減少した場合、番号が大きすぎる古い `turn_*.md` のみが削除され、変更されていないファイルのmtimeは保持されます（`fs_writer.py:287-301`）。

### sources.json / sources.md

スレッド全体の引用。URLで重複排除（`fs_writer.py:270-278`）。`sources.json` は `{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}` です。`sources.md` は同じリストの番号付きMarkdownリンク版です。

### report.md

deep-research のレポート成果物。スレッドがレポートを持っている場合のみ書き込まれます（`fs_writer.py:308-316`）：レポートタイトル、元の成果物ファイル名、その後に完全なレポートMarkdown。

<a id="raw_entriesjson-raw_blocksjson原始保真" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json — 元の忠実度

API応答が**解析前**にそのままディスクに書き込まれます（`fs_writer.py:257-266`）：

- `raw_entries.json` — plain 応答：`{"thread_metadata", "entries", "background_entries"}`。常に存在します。
- `raw_blocks.json` — schematized 応答、構造は同上。`search` スレッドにはこのファイルはありません（blocksを取得しません）。他の4つのモードはすべて取得し、モード判別信号がすべて欠落している場合もフォールバックとして取得します。

これら2つのファイルはアーカイブ全体の忠実度アンカーです。解析、レンダリング、レジストリ情報はこれらからオフラインで再構築でき、ネットワークは不要です。[オフライン操作](../architecture/offline-operations.md)を参照。

<a id="assets产物与清单" data-pplx-source-anchor="true"></a>
### assets/ — 成果物とマニフェスト

ダウンロード可能な成果物（Computer モードファイルおよびAPIにリストされているその他のアセット）は、CloudFront署名付きURLを介して `assets/files/` にダウンロードされます。拡張子はダウンロード時にURLパス、コンテンツマジックナンバー、またはアセットタイプに基づいて決定されます。`assets/assets_manifest.json`（`fs_writer.py:320-330`）は各バージョンを記録します：

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` は常に**バージョンの総数**（Σ `len(versions)`）であり、ファイルグループの数ではありません。ファイルグループの数には `len(files)` を使用してください。

<a id="index-层" data-pplx-source-anchor="true"></a>
## index/ 層

`web_archive/index/` はツールが管理する状態とインデックスを格納します。手動で編集しないでください：

| ファイル | 書き込み元 | セマンティクス |
|---|---|---|
| `library_<account>.json` | `pplx-export index`（`index_cmd.py:17-43`） | アカウントの全スレッドインデックス（GraphQL）。batch / スケジュール / スペースインデックスの入力。 |
| `batch_state.json` | `BatchState`（`state.py`） | 再開可能なチェックポイント：uuid → 状態（ok/error/expired/deleted）+ lastUpdated。アトミック書き込み。破損したファイルは自動的に `.corrupt-<ts>` にバックアップされます。 |
| `.cookies.json` | Cookieキャッシュ（`common.py:111`、`common.py:150`） | 12時間の鮮度を持つCookieキャッシュ。ソースとアカウントメールを含みます。最初に `0o600` に一時ファイルとして書き込まれ、その後アトミックに置き換えられます（セッション資格情報は所有者のみ読み取り可能）。 |
| `space_<slug>.json` | `pplx-export space-index`（`spaces_cmd.py:106-167`） | 単一スペースのスレッドリスト。`context_uuid` 二重IDマッピングを含みます。 |
| `space_meta.json` | `pplx-export spaces --fetch-meta`（`spaces_cmd.py:299-330`） | スペースのowner/memberキャッシュ。再構築時に再利用されます。 |
| `credit_usage_<account>.json` | `pplx-export usage-backfill`（`usage_backfill_cmd.py:17`） | スレッドごとのクォータ使用量（冪等、再開可能、25エントリごとにディスクに書き込み）。 |
| `cron_snippet.txt` | `pplx-export schedule`（`scheduler.py:48-78`） | cron呼び出しスニペット（絶対パス）。 |
| `answer_variants_log.jsonl` | `variant_log.append_registry`（`variant_log.py:76`） | 回答書き換えバリアントの集中レジストリ。（スレッド, entry）で重複排除、冪等。 |
| `logs/` | `--log-file`（`common.py:218-229`） | 完全なDEBUGログ。 |

<a id="spaces-层" data-pplx-source-anchor="true"></a>
## spaces/ 層

`pplx-export spaces` は `index/library_*.json` を集約してスペースインデックスを再構築します（`spaces_cmd.py:259-389`）：各スペースに1つの `<slug>.md`（参加アカウントの集約、owner/memberヘッダー、スレッドテーブル、エクスポート場所へのバックリンク）、さらに `spaces.json` レジストリ。

!!! note "出力場所"
    `spaces/` は現在の作業ディレクトリを基準に書き出されます（`spaces_cmd.py:332`）— **従いません** `--out`。
    手動で編集しないでください。次回の再構築で上書きされます。

<a id="跨天续接按-uuid-身份的目录迁移" data-pplx-source-anchor="true"></a>
## 日をまたぐ継続：UUID IDによるディレクトリ移行

ディレクトリ名には `lastUpdated` 日付が埋め込まれているため、スレッドを翌日継続すると、単純計算では**新しい**ディレクトリになります。writerはUUID IDによって重複を防ぎます（`thread_dir_for`、`fs_writer.py:58-72`）：

1. **検索**：`find_thread_dirs`（`fs_writer.py:74-105`）は、`_<uuid8>` で終わるディレクトリを全ライブラリから検索します。アカウント間、モード間。候補ディレクトリは、その `thread.json` が存在し、解析可能で、`web_uuid` が完全に一致する場合にのみ受け入れられます。欠落、破損、または一致しないディレクトリはすべてそのままにされます（移行漏れは許容しても、誤ったマージは避ける）。
2. **マージ**：`_merge_into`（`fs_writer.py:107-178`）は古いディレクトリを新しいディレクトリにマージします。ファイルは和集合を取ります（古いディレクトリにのみ存在するファイルは失われません）。同名で同じ内容のものはスキップされます。同名の競合は**常にターゲット側を保持**します（セマンティックに更新された側）。各コピーファイルはsha256で検証された後にのみ古いディレクトリから削除されます。失敗した場合、古いディレクトリはそのまま残り、再試行は冪等です。
3. **履歴の重複をクリーンアップ**：`consolidate_uuid`（`fs_writer.py:180-209`）は、同じUUIDを持つ重複した日付ディレクトリを全ライブラリでマージし、`lastUpdated` が最大のものを保持します。これは、古いバージョンで残された重複ディレクトリのためのフォールバック手段です。

同じUUIDの厳密性はスペースインデックスのバックリンクも保護します：`thread.json` が欠落、破損、または一致しない候補ディレクトリはリンクされません。

<a id="可手改与工具托管" data-pplx-source-anchor="true"></a>
## 手動編集可能とツール管理

- **ツール管理（手動編集禁止）**：スレッドディレクトリ内のすべて、および `index/`、`spaces/`、`relations/`。
  内容に問題がある場合はツールを修正して再生成してください。レンダリングの修正は `pplx-export re-render` を、データの修正は対応するbackfillコマンド（[メンテナンスコマンド](maintenance-commands.md)を参照）を使用してください。すべての成果物がrawから再現可能であることを確認してください。
- **手動編集可能**：ドキュメントと `web_archive/crosscheck/` レビューレポート。ユーザーレベルの例外：手動で救出された代替回答は、スレッドディレクトリ内の `rewritten_answer_variant.md` として記録できます。[セッションモード — 回答書き換えバリアント](modes.md)を参照。

<a id="另见" data-pplx-source-anchor="true"></a>
## 関連項目

- [セッションモード](modes.md) — 5つのモードとそれぞれの成果物
- [増分同期](incremental-sync.md) — `lastUpdated` が再エクスポートを駆動する方法
- [メンテナンスコマンド](maintenance-commands.md) — re-render、backfill、sync-deleted
- [データモデルとディレクトリ契約](../architecture/data-model.md) — 基盤となるdataclass
- [エクスポートパイプライン](../architecture/export-pipeline.md) — これらのファイルがどのように書き出されるか
- [オフライン操作](../architecture/offline-operations.md) — `raw_*.json` からすべてを再構築する方法
