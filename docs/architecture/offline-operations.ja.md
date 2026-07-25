---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/offline-operations.zh-CN.md"
translation_source_sha256: "6e8895877b590f5376436f80c97d687a04542d16a47ada59bffdf70c284de6a4"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="离线操作" data-pplx-source-anchor="true"></a>
# オフライン操作

`pplx_export` のネットワークゼロ側：raw JSON オフライン再生成、relations オフライン再構築パイプライン、インデックスリッチ化バックフィル、リモート削除ステートマシン、answer_variants 検出チェーン。各セクションは[アーキテクチャ概要](overview.md)の元の番号を保持します。

---

<a id="离线再生re-render" data-pplx-source-anchor="true"></a>
## オフライン再生成（re-render）

レンダリング層の修正後、raw JSON から**ネットワークゼロ**で冪等に全成果物を再生成します。実装：
`commands/rerender_cmd.py`（シングルスレッド `rerender` rerender_cmd.py:105-190；
バッチ `cmd_rerender` rerender_cmd.py:193-212）。

```mermaid
flowchart TD
    IN[("&lt;out&gt;/*/*/*/raw_entries.json<br/>glob 全部线程目录（rerender_cmd.py:199）")] --> CHK{"raw_entries.json 存在？"}
    CHK -->|"否"| SKIP["跳过（计 skipped）"]
    CHK -->|"是"| P1["parse_turn 逐 entry（parsers.py:173）<br/>按 created_us 排序、重编 index<br/>（rerender_cmd.py:57-60）"]
    P1 --> P2["Conversation 重建<br/>metadata = thread_metadata（rerender_cmd.py:65-70）<br/>conv._plain = doc"]
    P2 --> P3{"raw_blocks.json 存在？"}
    P3 -->|"是"| P4["conv._blocks 载入（rerender_cmd.py:91）<br/>PerplexityAdapter(None).sub_agents 建 sub_map<br/>（None-transport 纯数据组装，rerender_cmd.py:84-88,138）"]
    P3 -->|"否"| P5["sub_map = {}"]
    P4 --> P6{"mode ∈ computer/council？"}
    P6 -->|"是"| P7["attach_workflow_blocks（rerender_cmd.py:93）<br/>attach_stub_workflows（rerender_cmd.py:97）<br/>collect_unconsumed_background（rerender_cmd.py:101）"]
    P6 -->|"否"| P8
    P5 --> P8["render_conversation → conversation.md<br/>render_turn × N → turns/turn_NNNN.md<br/>（rerender_cmd.py:170,189）"]
    P7 --> P8
    P8 --> TJ{"--thread-json？"}
    TJ -->|"否"| OUT(("完成：不动其他文件"))
    TJ -->|"是"| TJ1["collect_interruptions(conv, sub_map)（rerender_cmd.py:150）<br/>answer_variants 随 load_archived 同实现重建（rerender_cmd.py:83）"]
    TJ1 --> TJ2{"与现有 thread.json<br/>interruptions / answer_variants 两键比较"}
    TJ2 -->|"内容有变"| TJ3["就地增删两键后写盘，其余字段原样（round-trip indent=1）<br/>（rerender_cmd.py:141-169）<br/>variants 新增/变化时告警 + 追加 jsonl 登记<br/>（rerender_cmd.py:163-166，见 §18）"]
    TJ2 -->|"无变化"| TJ4["不写盘——避免全库 mtime/diff 噪音"]
```

規律：

- **ネットワークゼロ**：`PerplexityAdapter(None)` は純粋なデータアセンブリメソッドのみを再利用し、オンラインメソッド（get_thread など）は呼び出されません。
- **冪等**：成果物は raw + レンダラーのみで決定され、再実行の結果はバイト単位で一致します（スナップショット回帰テストで保証、[§13](../development/testing-architecture.md)）。
- **他ファイルは変更しない**：sources、report.md、assets はそのまま；thread.json はデフォルトで変更せず、`--thread-json` の場合のみ interruptions / answer_variants の2つのキーを追加/削除します。
- `--dry-run` はディレクトリをリストするのみでファイルは書き込みません（rerender_cmd.py:204-206）；`--limit N` は先頭 N 個を取得します。

---

<a id="relations-离线重建管线" data-pplx-source-anchor="true"></a>
## relations オフライン再構築パイプライン

`cmd_relations`（misc_cmd.py:16）はアーカイブされた raw から**ネットワークゼロ**で全ライブラリの会話関係グラフを再構築します：re-render のオフライン再構築パイプライン `load_archived_conversation`（rerender_cmd.py:34）を再利用して Conversation（turns の解析/ソート/番号付け、_plain/_blocks のマウント）を復元し、スレッドごとに `adapter.sub_agents` を介してセッションレベルの `conv.sub_agents`（misc_cmd.py:70-73；エクスポートパイプラインはこのフィールドをバックフィルしません、models.py:178-182）を入力します；computer の回答フォールバック（`wf_block_answer`）はこの層で `turn.answer` をバックフィルし、references のスキャン範囲を拡大します（misc_cmd.py:74-79）。raw がないスレッドは thread.json + conversation.md シェルに退化します（same_space / 裸の uuid のみ判定可能、misc_cmd.py:61-66）。

```mermaid
flowchart LR
    RAW["web_archive/*/*/*/raw_entries.json<br/>+ raw_blocks.json"] --> LA["load_archived_conversation<br/>（rerender_cmd.py:34，零网络）"]
    LA --> SUB["adapter.sub_agents → conv.sub_agents<br/>（misc_cmd.py:70-73）"]
    LA --> FB["wf_block_answer 回填 turn.answer<br/>（misc_cmd.py:74-79）"]
    SUB --> BE["build_edges（relations.py:200）"]
    FB --> BE
    BE --> SS["same_space：同一空间<br/>dst = space:&lt;slug&gt;"]
    BE --> SP["same_prompt：首问归一化全等<br/>（normalize_query，relations.py:111）<br/>簇内按 created_us 链式连边（非团簇）<br/>query_source 区分定时任务重跑 vs 人工重发<br/>（parsers.py:209-215）"]
    BE --> RF["references：答案文本 / 引文 URL<br/>引用库内其他线程（含裸 uuid）"]
    BE --> SA["subagent_of：主线程 → 子代理运行<br/>dst = toolu_X 运行 id（非线程 uuid）<br/>已归档子代理线程记入 evidence"]
    SS --> OUT[("web_archive/relations/<br/>edges.jsonl + graph.md")]
    SP --> OUT
    RF --> OUT
    SA --> OUT
```

確定規律（2026-07-23）：`branch_of` メカニズムは確認済みだが全ライブラリにインスタンスなし、エッジは作成しない；`related_query` は既存データから解析不可、エッジは作成しない——エッジが欠けても推測エッジは作成しない。実測規模：全ライブラリ 772 エッジ / 21 クラスター（same_space 559 / subagent_of 154 / same_prompt 49 / references 10）。

---

<a id="search-mode-backfill索引-search_mode-富化" data-pplx-source-anchor="true"></a>
## search-mode-backfill（インデックス search_mode リッチ化）

`cmd_search_mode_backfill`（search_mode_backfill_cmd.py:81）はプラットフォームの権威フィールド `search_mode` を `index/library_<account>.json` にリッチ化します：**ローカル raw 優先**（アーカイブ済みスレッドは raw_entries.json の `entries[].search_mode` から抽出、ネットワークゼロ）、ローカル raw がない場合のみオンラインでフォールバックして thread を取得；書き込み時に既存のインデックスフィールドをマージして保持（リフレッシュセマンティクス：リッチ化キーは上書き、その他はそのまま）、冪等で再実行可能、`--limit` でサブセットを取得可能。リッチ化後のインデックスにより、バッチの `--mode` フィルタリングが権威フィルタリングになります：`index_row_matches_mode`（batch_cmd.py:46）はインデックスの search_mode（SEARCH_MODE_MAP、normalize.py:50）を優先して判定し、欠落している場合のみヒューリスティックにフォールバックします。

---

<a id="sync-deleted-远端删除状态机" data-pplx-source-anchor="true"></a>
## sync-deleted リモート削除ステートマシン

`cmd_sync_deleted`（sync_deleted_cmd.py:262）は「プラットフォーム側でユーザー/リモートにより削除された」スレッドを識別し、最終状態に設定します。expired と並列です。候補判定は**全アカウントインデックスの和集合 diff**：アーカイブ済み ok スレッドが**すべて**の `index/library_*.json` で消失した場合のみ候補とみなします（クロスアカウント export_via スレッドは所有者のインデックスにのみ出現するため、単一アカウントの diff は誤検出します；find_candidates、sync_deleted_cmd.py:148）；インデックスが欠落/読み取り不可の場合は安全にスキップし、理由を正確に記録します。デフォルトのオフライン dry-run は候補をリストするのみ（ネットワーク接続なし、ファイル変更なし）；`--online` はスレッドごとに GET で検証：`ENTRY_DELETED` / `ENTRY_EXPIRED` / 404 → 削除確認、`state.mark_deleted`（state.py:136）+ thread.json 墓石（mark_thread_json_remote_deleted、sync_deleted_cmd.py:215）。

```mermaid
stateDiagram-v2
    [*] --> ok : 已归档（batch_state = ok）
    ok --> candidate : 全账户索引并集均消失<br/>（find_candidates，sync_deleted_cmd.py:148）
    candidate --> skipped : 索引缺失/不可读<br/>安全跳过并记录原因
    candidate --> listed : 离线 dry-run 仅列出<br/>（不联网、不改文件）
    listed --> deleted : --online 逐条验证<br/>ENTRY_DELETED / ENTRY_EXPIRED / 404<br/>（_confirm_deleted，sync_deleted_cmd.py:247）
    deleted --> [*] : 终态 mark_deleted（state.py:136）+ thread.json 墓碑<br/>plan_incremental 与 expired 同等截尾<br/>（incremental.py:74-75,84）
```

エラータイプの階層化：`EntryDeletedError` は `EntryExpiredError` を継承（400 かつボディに ENTRY_DELETED を含む場合の判定は ENTRY_EXPIRED より優先、cookie_transport.py:93-98）；バッチのキャッチ順序は子を先に、親を後にしなければなりません（batch_cmd.py:163-174 が 175-183 より先）、そうしないと deleted が誤って expired として記録されます。削除 API 自体：`DELETE /rest/thread/delete_thread_by_entry_uuid`（read_write_token は `entries[].read_write_token` の最初の非空を取得；自前のテストスレッドと BOT スペーススレッドで実際に検証済み、10/10 削除成功）。

---

<a id="answer_variants-答案重写变体检测链" data-pplx-source-anchor="true"></a>
## answer_variants 回答書き換えバリアント検出チェーン

プラットフォームの「回答書き換え / A-B 実験」で置き換えられたバリアントは API 側では見えません——選択された answer は見えますが、選ばれなかった sibling は `entries[].side_by_side_metadata` の痕跡のみ残り、プラットフォームによってクリーンアップされる可能性があります（sibling のデッドリンクは実証済み：403 VIEW_THREAD_NOT_ALLOWED + SPA リダイレクトでトップページへ、[API リファレンス §5.2](../reference/api/api-responses-errors.md) 参照）。検出チェーンにより、「書き換えが発生したこと」を観測可能かつトレース可能にします：

```mermaid
flowchart LR
    E["entries[].side_by_side_metadata<br/>收窄判据"] --> CAV["parsers.collect_answer_variants<br/>（parsers.py:589）"]
    CAV --> AD["adapter.get_thread 在线命中即告警<br/>（adapter.py:141-147）"]
    CAV --> RR["re-render 离线重建<br/>仅新增/变化才告警（rerender_cmd.py:163-166）"]
    AD --> LOG["variant_log.warn_detections（variant_log.py:65）<br/>WARNING 单行 ANSWER_VARIANT_DETECTED（variant_log.py:45）<br/>全量定位字段 + 处置指引，可 grep"]
    RR --> LOG
    AD --> TJ["thread.json.answer_variants 登记<br/>（fs_writer.py:247-252）"]
    RR --> TJ
    TJ --> JSONL[("index/answer_variants_log.jsonl<br/>append_registry（variant_log.py:76）<br/>按 (web_uuid, entry_uuid) 去重幂等")]
    LOG --> B["batch 摘要 ⚠ 透出命中线程数<br/>（batch_cmd.py:214-223）"]
    JSONL --> B
```

- **判定基準の絞り込み**：side_by_side_metadata の権威シグナルのみを認識し、完全な位置特定フィールド（スレッドの完全な uuid + uuid8、タイトル、entry_uuid、sibling_uuid、selection_status、experiment_role）と処置ガイダンスを記録します。形式は `format_detection`（variant_log.py:53）を参照。
- **冪等**：jsonl は (web_uuid, entry_uuid) で重複排除され、オンライン（source=online）/オフライン（source=offline）の2つの経路からの重複登録で重複行は生成されません；rerender は variants の内容が変更された場合のみ警告し、全ライブラリの再実行で画面が埋め尽くされることはありません。
- **処置フロー**：ヒット後、直ちに手動で代替回答を確認し補足記録します（代替回答はプラットフォームによってクリーンアップされる可能性があり、API では救済できません）。完全なフローは [API リファレンス §5.2](../reference/api/api-responses-errors.md) を参照。
