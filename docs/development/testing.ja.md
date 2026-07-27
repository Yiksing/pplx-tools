---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/testing.zh-CN.md"
translation_source_sha256: "6135b1f3741f588961c302bffc7d049b47ff6c6df0c8797a8888b56edc1cf7a5"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试" data-pplx-source-anchor="true"></a>
# テスト

テストスイートは `tests/`（`pplx_export` パッケージ外）にあり、完全にオフラインで動作します。API 形状の
入力は、リポジトリに `tests/fixtures/` でコミットされた決定論的なモックデータです。テストはオンラインサービスや
実際のユーザーレベルの設定に依存しません。

このページでは、現在のテストモジュール一覧とコントリビューションの流れを管理します。回帰設計については
[テストシステムアーキテクチャ](testing-architecture.md)、入力データ契約については
[テストフィクスチャ](fixtures.md)を参照してください。

<a id="运行测试" data-pplx-source-anchor="true"></a>
## テストの実行

```bash
uv run pytest tests
```

pytest は宣言された開発依存関係です。テストスイートは以下を保証します：

- **ゼロネットワーク**——モック入力はリポジトリに格納済み。ネットワーク向けパスは fake、`tmp_path`、
  `monkeypatch` でカバーされます。
- **実際のユーザー設定を読み込まない**——`tests/conftest.py` は、本番モジュールをインポートする前に
  プロセスレベルの一時設定を作成し、`PPLX_EXPORT_CONFIG` を上書きします。その後、各テストは独立した
  `alice` / `bob` プレースホルダ設定を取得し、終了後にプロセスレベルのプレースホルダ設定を復元します。サブプロセスの回帰テストでは、
  呼び出し元の設定が存在しないか破損していても、テスト収集が失敗しないことを検証します。
- **高速フィードバック**——このプロジェクトでは、2026-07-25 時点で 32 個の `test_*.py` モジュールから
  435 件のテストが観測されました。ローカル検証での完全実行は約 13～25 秒です。数値は日付付きのリポジトリスナップショットであり、
  開発に伴い増加します。

よく使う選択：

| コマンド | 効果 |
|---|---|
| `uv run pytest tests` | 完全スイート |
| `uv run pytest tests/test_units.py` | 単一モジュール |
| `uv run pytest tests -k snapshot` | node id が `snapshot` に一致するテスト |
| `uv run pytest tests -x -q` | 最初の失敗で停止、静かな出力 |
| `uv run pytest --collect-only -q` | 収集ケース数を更新 |

<a id="当前模块清单" data-pplx-source-anchor="true"></a>
## 現在のモジュール一覧

一覧は **2026-07-27** にリポジトリと同期済み：

<!-- audit:inventory test-modules -->

| 機能ファミリ | モジュール | 用途 |
|---|---|---|
| レンダリングスナップショット | `test_render_snapshots.py` | すべてのモックされた完全モードと簡略シナリオフィクスチャを再レンダリングし、コミット済み成果物とバイト単位で比較 |
| コアと共有ユーティリティ | `test_units.py` | 状態、スロットリング、計画、正規化、アセット命名、モード判定、安全なパス、およびクロスカッティング回帰 |
| ドキュメント契約、スキル、ローカライゼーション | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | リポジトリローカルスキル契約、および読み取り専用ドキュメント監査人と機械翻訳パイプライン向けの隔離されたミニリポジトリテスト |
| 設定、認証、初期化 | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | 外部設定の隔離、クッキー由来の設定、資格情報の選択と初期化 |
| レンダリングとワークフローセマンティクス | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | ワークフローの帰属、中断状態、回答バリアント、監査ログ、関係エッジ |
| オフラインアーカイブとインデックスメンテナンス | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | エンリッチメント、再実行/べき等動作、クロスアカウント削除判定、最終状態、およびオフライン状態台帳/変更レポートの階層出力 |
| レビュー回帰 | 下表に示す 16 個の `test_fix_*.py` モジュール | レビュー発見に由来する修正。モジュール名はレビューの lineage を保持 |

<a id="评审回归-lineage" data-pplx-source-anchor="true"></a>
### レビュー回帰 lineage

レビュー番号は回帰テストが存在する理由を説明しますが、テストスイートの主要なアーキテクチャではありません。マッピングは多対多を明示的に許可します：
1 つのモジュールが複数の発見をカバーすることも、1 つの発見が既存のトピックモジュールにテストケースを追加することもあります。

| Lineage | 専用モジュール |
|---|---|
| N ラウンドレビュー | `test_fix_n01_inline_assets.py`、`test_fix_n02_spaces_link.py`、`test_fix_n03_n12.py`、`test_fix_n04_cookies.py`、`test_fix_n05_n06_n09.py`、`test_fix_n07_usage_checkpoint.py`、`test_fix_n08_throttle_overflow.py`、`test_fix_n10_table_header.py`、`test_fix_n11_batch_total.py` |
| V3 ラウンドレビュー | `test_fix_v301_nested_sources_text.py`、`test_fix_v305_export_products.py` |
| V4 ラウンドレビュー | `test_fix_v401_thread_dir_migration.py`、`test_fix_v402_manifest_count.py`、`test_fix_v403_handle_assets_idempotency.py`、`test_fix_v405_ask_post_steps.py` |
| V5 ラウンドレビュー | `test_fix_v5_review.py`、および既存のトピックモジュールへのピンポイント追加 |
| V6 ラウンドレビュー | `test_fix_v6_atomic_writes.py` |

<!-- /audit:inventory test-modules -->

各モジュールの docstring は、対応する発見の以前の動作、修正された動作、および回帰境界に関する信頼できる情報源です。

<a id="快照测试如何复用生产重渲路径" data-pplx-source-anchor="true"></a>
## スナップショットテストが本番再レンダリングパスを再利用する方法

スナップショットテストは別のレンダラーを実装しません：

1. `tests/conftest.py` 内の `render_fixture` が、フィクスチャのモックされた
   `raw_entries.json`、オプションの `raw_blocks.json`、`thread.json` を一時ディレクトリにコピーします。
2. それは `pplx_export.commands.rerender_cmd.rerender` を呼び出します。これは
   `pplx-export re-render` が使用するのと同じ関数です。
3. `rendered` フィクスチャファクトリは、新しい出力とフィクスチャ内のコミット済み `golden/` ディレクトリを返します。
4. テストは `conversation.md` とすべての `turns/turn_*.md` をバイト単位で比較します。

バイト等価性に加えて、コンテンツ不変条件があります：回答が空のプレースホルダ `(无)` に退化してはならず、`{'type': ...`
のような dict-repr の残骸がレンダリングテキストに漏れてはなりません。

<a id="新增测试" data-pplx-source-anchor="true"></a>
## 新しいテストの追加

- **既存のロジック**——対応するトピックモジュールにテストを追加します。`tmp_path`、fake、
  `monkeypatch` を使用します。ネットワークや実際の `~/.config` にアクセスしてはいけません。
- **バグ回帰**——優先的に対応するトピックモジュールに追加します。レビュー lineage を保持することでトレーサビリティが明らかに向上する場合にのみ、
  新しい `test_fix_<lineage>_<slug>.py` を作成します。1 つの発見が 1 つのモジュールに対応すると想定しないでください。
- **レンダリング回帰**——新しいモックフィクスチャを追加するか、既存のものを簡略化し、メンテナンスツールで golden を再生成し、
  それを `test_render_snapshots.py` に登録するか、シナリオ固有のアサーションを追加します。

周囲のコードスタイルに従います：型アノテーション、`from __future__ import annotations`、およびバイリンガルモジュールの
docstring。

<a id="另见" data-pplx-source-anchor="true"></a>
## 関連項目

- [テストフィクスチャ](fixtures.md)——モック入力、golden 成果物、メンテナンス契約
- [テストシステムアーキテクチャ](testing-architecture.md)——テスト階層と回帰保証
- [オフライン操作](../architecture/offline-operations.md)——スナップショットテストが再利用する本番再レンダリングパス
