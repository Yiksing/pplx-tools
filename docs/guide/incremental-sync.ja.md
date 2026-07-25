---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/incremental-sync.zh-CN.md"
translation_source_sha256: "ca6b70d4ac1b77d992fbc2d801238b670a1652dcf4ffc577e52d3f09fd404fee"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="增量同步" data-pplx-source-anchor="true"></a>
# インクリメンタル同期

`pplx-export batch` は高頻度実行向けに設計されています。各ラウンドでは新規または変更された会話のみをエクスポートし、中断された実行によるギャップを自動的に修復し、プラットフォームがすでに削除したスレッドには決して触れません。「何がエクスポートされたか」の唯一の信頼できる情報源は `index/batch_state.json`（`BatchState`、`pplx_export/core/state.py:63`）であり、スレッドをエクスポートするたびに更新されます。シャドウコピーは維持されません。

<a id="前置条件与基本用法" data-pplx-source-anchor="true"></a>
## 前提条件と基本的な使い方

```bash
pplx-export index --account alice   # 先刷新 index/library_alice.json
pplx-export batch --account alice   # 增量导出（早停 + 断点续跑）
```

インデックスが存在しない場合、`batch` は実行を拒否します（`pplx_export/commands/batch_cmd.py:79-81`）。
`--limit N` と `--mode <mode>` は計画の前にインデックス行をフィルタリングします。`entryUUID` がない不正な行は警告のみでスキップされ、実行全体がクラッシュすることはありません（`batch_cmd.py:95-100`）。

<a id="增量计划如何工作" data-pplx-source-anchor="true"></a>
## インクリメンタル計画の仕組み

1. **ソート。** インデックス行は `lastUpdated` の新しい順にソートされます（`batch_cmd.py:89`）。
   新しい会話と「再開された古い会話」（`lastUpdated` が新しくなり、位置が上に移動）は両方とも上部に配置されます。この順序は早期停止の安全性の前提です。
2. **分類。** `plan_incremental`（`pplx_export/hooks/incremental.py:36-87`）
   ——`batch` と `schedule` が共有する純粋関数——は各行に正確に1つのアクションを割り当てます：

   | アクション | 条件 | batch の処理 |
   |---|---|---|
   | `new` | `batch_state` でその uuid を一度も見たことがない | エクスポート |
   | `updated` | `lastUpdated` と記録された値が異なる、または `--force` が付いている | 再エクスポート |
   | `done` | ステータスが `ok` で `lastUpdated` が変更されていない | スキップ |
   | `expired` | 以前のエクスポートでプラットフォームが `ENTRY_EXPIRED` を返した | スキップ——最終状態、再試行しない |
   | `deleted` | `sync-deleted` がリモート削除を確認済み | スキップ——最終状態、再試行しない |

3. **早期停止。** デフォルト（`--full` も `--force` も指定しない）では、末尾の最長の最終状態連続セグメント（`done` / `expired` / `deleted`）を切り捨て、切り捨てた数を `n_stopped` として記録します（`incremental.py:83-87`）。リストは新しい順であり、変更されていないエントリの下にあるものはさらに古く、変更されていないため、スキャンを続けても時間の無駄です。

   ```mermaid
   flowchart TD
       IDX["library 索引行<br/>按 lastUpdated 从新到旧排序"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → 导出"]
       PLAN --> UPD["updated → 重导"]
       PLAN --> DONE["done → 跳过"]
       PLAN --> TERM["expired / deleted → 跳过（终态）"]
       DONE --> STOP["早停：截掉尾部终态连续段"]
       TERM --> STOP
   ```

4. **実行。** スレッドをエクスポートするたびにすぐにマークを付け（`mark_ok` / `mark_error` /
   `mark_expired` / `mark_deleted`）、各項目の後にステートファイルをディスクに書き込みます（`batch_cmd.py:154-201`）。`KeyboardInterrupt` も保存してから上位に伝播します（`batch_cmd.py:158-161`）。書き込みはアトミックです——一時ファイルと `os.replace`（`state.py:145-152`）を使用するため、中断によって切り詰められた JSON が残ることはありません。

<a id="中断后的缺口修复" data-pplx-source-anchor="true"></a>
## 中断後のギャップ修復

早期停止はギャップを埋めません。失敗（ステータス `error`）したスレッドやまだ処理されていないスレッドは最終状態のサフィックス**より上**にあり、次のラウンドで `updated` / `new` として再計画され、早期停止ポイントに達する前にエクスポートされます（`incremental.py:12-14`、`batch_cmd.py:206-208`）。項目ごとのディスク書き込みと組み合わせることで、batch 実行は任意の時点で中断でき、そのまま再実行するだけで済みます。

`batch_state.json` 自体が破損した場合、静かに空にされることはありません。元のファイルは `batch_state.json.corrupt-<timestamp>` に名前が変更され、記録された最終状態は失われず、不必要な再試行は行われません（`state.py:68-81`）。

<a id="-full-与-force" data-pplx-source-anchor="true"></a>
## `--full` と `--force`

| オプション | 効果 | 最終状態 | 適用シナリオ |
|---|---|---|---|
| *（デフォルト）* | 末尾の最終状態連続セグメントで早期停止 | スキップ | 通常/定期実行ごと |
| `--full` | 全スキャン、早期停止なし。変更されていないスレッドは `done` としてスキップ | スキップ | 定期的なセーフティネット、またはアーカイブにギャップが疑われる場合 |
| `--force` | 変更されていないスレッドを含むすべてを再エクスポート | それでも除外——再試行しない | パイプライン修復後に raw データを再取得する必要がある場合 |

最終状態が `--force` によって除外されるのは意図的です。期限切れまたはリモートで削除されたスレッドを再試行すると、リクエストとバックオフ予算が無駄になります（`batch_cmd.py:120-127`）。

関連項目：[`status`](maintenance-commands.md#status)：ゼロネットワーク出力ステートアカウントと、同じ `plan_incremental` セマンティクスに基づいて計算された変更計画（new/updated/早期停止数）。

`lastUpdated` 比較では、小数秒部分の末尾のゼロを切り捨てます（`.18033Z` と `.180330Z` は同一と判定され、`state.py:23-55`）。プラットフォームが末尾のゼロを失うことがあるため、正確な文字列比較は「変更された」と誤判定し、重複エクスポートを引き起こす可能性があります。

<a id="终态expired-与-deleted" data-pplx-source-anchor="true"></a>
## 最終状態：`expired` と `deleted`

| | `expired` | `deleted` |
|---|---|---|
| 意味 | プラットフォームがスレッドをクリア（約3か月の保持期間）。エクスポート試行が `ENTRY_EXPIRED` を返す | ユーザー/リモート削除、`sync-deleted` によって確認 |
| 記録者 | `batch` 自身（`mark_expired`、`state.py:131-134`） | `pplx-export sync-deleted --online`（`mark_deleted`、`state.py:136-143`） |
| 再試行？ | 決してしない——`--force` も | 決してしない——`--force` も |
| 証拠 | `ENTRY_EXPIRED` 応答 | `note` フィールド：インデックス消失 + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted确认远端删除" data-pplx-source-anchor="true"></a>
### sync-deleted：リモート削除の確認

```bash
pplx-export sync-deleted --account alice            # 离线 dry-run：只列候选
pplx-export sync-deleted --account alice --online   # 逐候选在线验证
```

1. **候補判定（オフライン、ゼロネットワーク）。** `batch_state` でステータスが `ok` のスレッドが、**すべての** `index/library_*.json` アカウントインデックスの `entryUUID` 和集合から消失している場合、リモート削除の疑いがある候補とみなされます（`pplx_export/commands/sync_deleted_cmd.py:148-212`）。
   アカウント間の和集合が必要です：`bob` が所有し、共有スペースを介して `alice` によってエクスポートされたスレッドは、`alice` 自身のインデックスには決して表示されません。単一アカウントの差分では、これらのスレッドすべてが誤って報告されます。すべてのインデックスが利用できない場合、候補はすべて安全にスキップされ、理由が正直に記録されます。
2. **デフォルト dry-run。** `--online` を指定しない場合、候補をリストするのみ——ネットワークアクセスなし、ファイル変更なし。
3. **`--online` 確認。** 候補ごとに `GET /rest/thread/<uuid>` を実行し、候補の `thread.json` にある `export_via` アカウント（cookie 自動切り替え）を使用します：

   | 結果 | 処置 |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | 確認：`batch_state` が最終状態 `deleted` をマーク（`note` が理由を記録）、各スレッドディレクトリの `thread.json` に `remote_deleted` タイムスタンプをその場で追加 |
   | スレッドがまだ存在する | 誤検出：正直に報告（インデックスが完全に更新されていない可能性あり——`index` を再実行後に再確認）、状態は変更しない |
   | 5xx / ネットワークエラー | 状態を変更せず、次のラウンドに持ち越し |
   | 連続3回の 401/403 | fail-fast 中止——cookie が無効な場合、バックオフでは回復できず、空回りでアクティブなスレッドを誤ってマークする可能性がある（`sync_deleted_cmd.py:333-337`） |

   確認マークは項目ごとにディスクに書き込まれます：`--online` 実行が中断しても確認済み項目は失われず、再実行は冪等です（`sync_deleted_cmd.py:254-256`）。

<a id="墓碑原则" data-pplx-source-anchor="true"></a>
## 墓石の原則

!!! warning "ローカルアーカイブは決して削除しない"
    このリポジトリは、エクスポートされた会話のバックアップアーカイブ（backup of record）です。`sync-deleted` は「識別 + マーク」（tombstone）のみを行います：**アーカイブファイルを決して削除したり移動したりしません**。確認は2か所のみを変更します——`batch_state` の状態と `thread.json` の1つのマークキー：

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    このマークは冪等です：既存の `remote_deleted` キーは上書きも時間の置き換えも行いません（`sync_deleted_cmd.py:215-244`）。

<a id="幂等与离线重渲" data-pplx-source-anchor="true"></a>
## 冪等性とオフライン再レンダリング

- インデックスが変更されていない状態で `batch` を再実行しても、何もエクスポートされません。すべての行が `done` に分類され、実行は早期停止ポイントで停止します。
  状態書き込みはアトミック、マークはスレッドごと、削除確認の重複実行で `remote_deleted` が重複してマークされることはありません。
- アーカイブは raw API ペイロード（`raw_entries.json` / `raw_blocks.json`）を保存しており、レンダリング成果物はいつでもゼロネットワークで再生成可能です：

  ```bash
  pplx-export re-render                 # 全量重建 conversation.md + turns/
  pplx-export re-render --dry-run       # 只列出将处理的线程目录
  pplx-export re-render --thread-json   # 同时同步 interruptions / answer_variants 键
  ```

  `re-render` は現在のレンダラーを使用して raw JSON を再解析します
  （`pplx_export/commands/rerender_cmd.py:105-190`）：`conversation.md`
  と `turns/turn_*.md` を書き換え、現在のラウンド番号より大きい番号の残存ラウンドファイルを削除します。sources、assets、
  `report.md` と `thread.json` はそのまま変更されません。レンダリング層の修正はこのようにして、ゼロリクエストでアーカイブ全体に適用されます。

<a id="另见" data-pplx-source-anchor="true"></a>
## 関連項目

- [pplx-export.md](pplx-export.md) —— `batch` 完全コマンドリファレンス（`--mode`、`--limit`、間隔パラメータ）
- [maintenance-commands.md](maintenance-commands.md) —— `sync-deleted`、`re-render` と各種 backfill コマンド
- [archive-layout.md](archive-layout.md) —— `batch_state.json` と `thread.json` の場所
- [rate-limiting.md](rate-limiting.md) —— スレッド間隔、バックオフ、認証 fail-fast
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) —— 完全なエクスポートパイプライン
- [../architecture/offline-operations.md](../architecture/offline-operations.md) —— オフライン再構築パイプラインの詳細
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) —— エラー分類と最終状態処理
