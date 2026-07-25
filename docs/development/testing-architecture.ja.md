---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/testing-architecture.zh-CN.md"
translation_source_sha256: "7e7e01902d3e8e45e0929e728479bc7adbd556f2b2706972fecec4a9b9f5b77f"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试架构" data-pplx-source-anchor="true"></a>
# テストアーキテクチャ

`pplx_export` テストシステムは完全にオフラインで動作し、チェックインされたモックデータを使用し、スナップショットでレンダラーの動作を固定します。このページでは、アーキテクチャと保証について説明します。現在のモジュールのリストは[テスト](../development/testing.md)で、フィクスチャの詳細は[テストフィクスチャ](../development/fixtures.md)で管理されています。

セクションは[アーキテクチャ概要](../architecture/overview.md)の番号に従います。

---

<a id="测试体系" data-pplx-source-anchor="true"></a>
## テストシステム

`uv run pytest tests` を使用してスイートを実行します。テスト数は現在の実行結果に基づいて報告され、アーキテクチャの定数ではありません。

<a id="层次" data-pplx-source-anchor="true"></a>
### 階層

| 階層 | 代表モジュール | 契約 |
|---|---|---|
| 純粋なユニット動作 | `test_units.py`、認証情報/cookie/設定テスト | モック入力で関数、クラス、検証、正規化を分離 |
| コンポーネントセマンティクス | 中断、スタブワークフロー、回答バリアント、リレーションテスト | ネットワークゼロ条件下でパーサー、レンダラー、状態、インデックスコードの連携をカバー |
| オフラインコマンドと状態動作 | backfill、削除同期、初期化、レビュー回帰 | 一時ディレクトリとfakeトランスポートでコマンドパスを実行 |
| レンダリングスナップショット | `test_render_snapshots.py` | API形状のモックJSONを本番再レンダリングパスに送り、すべてのMarkdownをコミットされたゴールデンとバイト単位で比較 |

N、V3、V4、V5などのレビュー番号は階層をまたがるトレーサビリティメタデータであり、独立した実行アーキテクチャを定義するものではなく、テストモジュールと一対一で対応する必要もありません。

<a id="快照数据流" data-pplx-source-anchor="true"></a>
### スナップショットデータフロー

1. モックフィクスチャが `raw_entries.json`、オプションの `raw_blocks.json` と `thread.json` を提供します。
2. `tests/conftest.py::render_fixture` がこれらのファイルを `tmp_path` にコピーします。
3. フィクスチャが `commands.rerender_cmd.rerender` を呼び出します。これは本番オフライン再構築パスです。
4. 新しく生成された `conversation.md` と `turns/turn_*.md` が、コミットされた `golden/` 成果物とバイト単位で比較されます。

ゴールデンは生成された期待結果であり、独立したデータソースではありません。成果物のバイトを変更するレンダラーの変更は、レビューされ意図的にゴールデンを再生成するまでスナップショットスイートを失敗させます。

<a id="隔离与信任边界" data-pplx-source-anchor="true"></a>
### 分離と信頼境界

- **フィクスチャソース** — コミットされたすべてのフィクスチャ入力はモックデータであり、オンラインアカウント、ライブAPIレスポンス、`web_archive/`、またはプライベートアーカイブからコピーされたものではありません。
- **ネットワーク境界** — テストはfakeとオフラインパスを使用します。チェックインされたフィクスチャは認証情報やネットワークを必要としません。
- **設定境界** — autuseフィクスチャがプレースホルダアカウント設定をインストールし、開発者の実際の `~/.config` がテスト結果を決定しません。
- **ファイルシステム境界** — コマンドと移行動作は `tmp_path` の下で実行され、ユーザーアーカイブをテスト対象としません。
- **残留境界** — `tests/scrub_fixtures.py --check` はファイルを変更せずに、設定された環境依存文字列、ローカル絶対パス、署名付きURL認証情報を拒否します。

ユニットアサーション、コンポーネントセマンティクス、コマンド状態テスト、バイトレベルのスナップショットが、局所的なロジックとエンドツーエンドの再レンダリング契約を共同で保護します。
