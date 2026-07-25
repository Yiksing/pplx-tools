---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/fixtures.zh-CN.md"
translation_source_sha256: "a34e1db385d79a8f56c92b6dfccfd6c90c76ec38feef5af63c4393418d02dc81"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试-fixtures" data-pplx-source-anchor="true"></a>
# テストフィクスチャ

`tests/fixtures/` は、[テストスイート](testing.md)に決定論的で API 構造を持つ
**モックデータ**を提供します。入力は代表的なスレッドとワークフロー構造をシミュレートするために使用され、そのレンダリング成果物はゴールデンスナップショットとしてリポジトリにコミットされます。

<a id="来源契约" data-pplx-source-anchor="true"></a>
## ソース契約

<!-- audit:contract fixture-source=simulated -->

現在コミットされているフィクスチャの内容はすべてモックデータです：

- 新しいフィクスチャを追加または更新する際は、モックデータを構築する必要があります。`web_archive/`、ユーザーアカウントデータ、リアルタイム API レスポンス、またはプライベートアーカイブをインポートして入力してはいけません。
- コミットされたファイル内の名前、ID、識別子、プロンプト、回答、ワークフローペイロード、パス、URL はすべてテスト用のプレースホルダーコンテンツです。
- JSON は、パーサー、レンダラー、状態、および関係の動作をカバーするためにのみ、本番レスポンスとアーカイブスキーマを模倣しています。
- リポジトリは、プレースホルダーからプライベート識別子への逆マッピングをコミットしません。

**フルモードフィクスチャ**と**スリムシナリオフィクスチャ**は、カバレッジ範囲と入力形状を説明するものであり、データソースを説明するものではありません。両方ともモックデータです。

<a id="目录契约" data-pplx-source-anchor="true"></a>
## ディレクトリ契約

各フィクスチャディレクトリには、元のレスポンス形状を持つモック入力が含まれ、スナップショット比較が必要な場合は `golden/` ツリーも含まれます：

| パス | 役割 |
|---|---|
| `raw_entries.json` | 本番レスポンス形状に一致するモックスレッドエントリ |
| `raw_blocks.json` | モックワークフローブロック。このモードにブロックレスポンスがない場合は欠落 |
| `thread.json` | モックアーカイブスレッドメタデータ |
| `golden/conversation.md` + `golden/turns/turn_*.md` | モック入力から生成され、バイト単位で比較される成果物 |

現在の決定論的規則には以下が含まれます：

- プレースホルダーアカウント `alice` / `bob`、サンプル ID、プレースホルダー BOT スペース、および固定の `read_write_token`；
- `5cbeef00` タグ付きの uuid5 派生識別子。モックレコード間の意図的な相互参照を保持；
- `5crub0` タグ付きの固定長モック `toolu_` 識別子；
- 汎用プロンプト、タイトル、ワークフローテキスト、ファイルパス；
- クエリ文字列が削除された署名付き URL。

これらの規則は、偶発的に混入した環境依存の残骸を発見しやすくするためのものです。モック識別子が本番オブジェクトに由来することを示すものではありません。

<a id="清单" data-pplx-source-anchor="true"></a>
## インベントリ

<!-- audit:inventory fixture-directories -->

<a id="完整模式-fixtures" data-pplx-source-anchor="true"></a>
### フルモードフィクスチャ

サポートされている各モードには、完全なモックセッションのセットがあります：

| フィクスチャ | カバレッジ |
|---|---|
| `search_demo` | search、シングルターン。R コードフェンスとインラインコード |
| `deep_research_demo` | deep research。エンドツーエンドの数式デリミタ変換 |
| `computer_demo` | computer、7ターンのワークフローレンダリング |
| `council_demo` | council モデル委員会レンダリングと大きなネストペイロード |
| `study_demo` | study モードレンダリング |

<a id="精简场景-fixtures" data-pplx-source-anchor="true"></a>
### スリムシナリオフィクスチャ

これらはピンポイントのモックペイロードであり、特定の回帰に必要なエントリと関係のみを保持します。「スリム」は実際のスレッドから抽出されたことを意味しません。

| フィクスチャ | カバレッジ |
|---|---|
| `scenario_computer_answer_fallback` | 通常の FINAL パスが利用できない場合に、パターン化されたワークフローブロックから回答を復元 |
| `scenario_subagent_fallback` | background マッチがない場合のサブエージェントタイトルと自身のエントリのレンダリング |
| `scenario_user_response` | `WORKFLOW_ITEM_USER_RESPONSE` Q&A レンダリング |
| `scenario_subagent_stub` | アンカーなしの subagent-result スタブを持つ10秒の関連ウィンドウ |
| `scenario_workflow_item_nested` | ネストされた `WORKFLOW_ITEM_WORKFLOW` 折りたたみブロックレンダリング |
| `scenario_limit_interrupted` | クレジット割り込み、帰属ウォーターフォール、付録配置、重複レンダリング禁止 |
| `scenario_canceled` | `WORKFLOW_CANCELED` アノテーション |

<!-- /audit:inventory fixture-directories -->

<a id="维护-fixtures" data-pplx-source-anchor="true"></a>
## フィクスチャのメンテナンス

`tests/scrub_fixtures.py` は、モックデータの正規化、本番オフラインレンダラーによるゴールデンの再生成、および残骸ゲートの実行を担当します：

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **再生成**——各フィクスチャは一時ディレクトリで `pplx_export.commands.rerender_cmd.rerender` を通じてレンダリングされます。ターン数が一致しない場合は中止されます。
- **決定論的正規化**——プレースホルダーテキスト、UUID、`toolu_` 値、トークン、署名付き URL はすべて冪等に正規化されます。
- **安全な入力はデータソースではない**——オプションのローカル `tests/scrub_pairs.local.json` とユーザーレベルのアカウント設定は、置換と残骸チェックのみを拡張します。これらをフィクスチャシナリオ構築の入力として使用してはいけません。
- **チェックモード**——`--check` はファイルを書き込みません。設定された残骸、ローカルの絶対パス、または署名付き URL のクレデンシャルを検出すると失敗します。

モック入力 JSON またはレンダラー出力を変更した後はメンテナンスツールを実行し、フィクスチャの変更をコミットする前に `--check` を実行してください。

<a id="golden-快照的权威边界" data-pplx-source-anchor="true"></a>
## ゴールデンスナップショットの権威境界

コミットされたモック JSON が入力の真のソースです。ゴールデンマークダウンは派生成果物です。現在の本番再レンダリングパスによってモック JSON から再生成され、バイトレベルの回帰比較のためにコミットされます。独立した真のソースとして手動でメンテナンスしてはいけません。

<a id="另见" data-pplx-source-anchor="true"></a>
## 関連項目

- [テスト](testing.md)——スイートがフィクスチャを消費する方法
- [テストシステムアーキテクチャ](testing-architecture.md)——回帰階層と保証
- `tests/fixtures/README.zh-CN.md`——リポジトリ内のフィクスチャインベントリ
