---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/index.zh-CN.md"
translation_source_sha256: "11e03bf1d56e3cd6e14277369f8369ceba6af4385ecb25765fe3c05980c9c5c6"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="系统架构阅读地图" data-pplx-source-anchor="true"></a>
# システムアーキテクチャ読解マップ

pplx-tools（`pplx-export` / `pplx-ask`）のメカニズム層リファレンス：依存関係、実行パイプライン、
状態機械、データ契約、信頼性境界。タスク指向の説明は[使用ガイド](../guide/index.md)から始めてください。

!!! note "範囲と事実の出典"

    このセクションは、プロジェクトを引き継ぐエージェントやエンジニアを対象として、`pplx_export/` のシステムアーキテクチャを説明します。
    行番号の参照は `file.py:NN` を使用し、すべて `pplx_export/` を基準とします。ページ内容は
    2026-07-23 にリポジトリと照合して確認済みです（`__version__ = "0.1.0"`、
    `pplx_export/__init__.py:31`）。現在のコードとテストが最終的な事実の出典です。

<a id="从系统地图开始" data-pplx-source-anchor="true"></a>
## システムマップから始める

- [アーキテクチャ概要](overview.md)——階層構造、モジュールの責務、実際のインポート依存関係グラフ。

<a id="沿运行流程阅读" data-pplx-source-anchor="true"></a>
## 実行フローに沿って読む

- [エクスポートパイプライン](export-pipeline.md)——スクレイピング、生レスポンスの保持、モード認識、Markdown
  レンダリング。
- [サブエージェントと中断](subagents-interruptions.md)——バックグラウンド成果物の帰属と中断/再開のセマンティクス。
- [pplx-ask とマルチアカウント](ask-and-accounts.md)——ストリーミング質問とマルチアカウント Cookie 切り替え。

<a id="理解数据与可靠性" data-pplx-source-anchor="true"></a>
## データと信頼性を理解する

- [データモデルとディレクトリ契約](data-model.md)——モデル、書き込み境界、ディスクアーカイブ契約。
- [レート制限とエラー処理](rate-limiting-errors.md)——スロットリング、バックオフ、終端状態、エラーの振り分け。
- [オフライン運用メカニズム](offline-operations.md)——ネットワークなしでの再レンダリング、関係グラフ再構築、ローカルメンテナンスパイプライン。

<a id="相关参考" data-pplx-source-anchor="true"></a>
## 関連リファレンス

- [Web API リファレンス](../reference/api/index.md)——観測された REST/GraphQL 契約、レスポンスセマンティクス、
  発見記録。
- [メンテナーガイド](../development/index.md)——テストアーキテクチャ、コントリビューターワークフロー、モックフィクスチャ契約。
