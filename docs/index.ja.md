---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/index.zh-CN.md"
translation_source_sha256: "49d67dcdb3d8715b15c05689069b96ae47f030e3c8c86ece51558818b535fc14"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="perplexity-命令行工具集" data-pplx-source-anchor="true"></a>
# Perplexity コマンドラインツールセット

<p class="homepage-scope-note" role="note">
  <strong>既存のサブスクリプションに適用され、従量課金APIには適用されません</strong>
</p>

Perplexity 会話履歴のアーカイブと対話型クエリツール（`pplx-export` / `pplx-ask` の2つのコマンド）。

ブラウザのCookieを介してPerplexity REST/GraphQL APIに直接接続し、会話（手順、引用、深層研究レポート、
computerアセット、サブエージェントワークフローを含む）を完全にローカルのMarkdown + JSONとしてアーカイブします。エクスポートが成功すると、元のレスポンスとレンダリング成果物の両方が保持されるため、再取得せずにオフラインで再レンダリングできます。

<a id="简介" data-pplx-source-anchor="true"></a>
## はじめに

過去の会話をアーカイブするだけでなく、このプロジェクトの目的は、データに近く、より強力な計算能力を持つローカルエージェントに、ある程度のPerplexity Computer能力を提供することです。ワークループ内でPerplexity深層研究モードで生成されたレポートに直接アクセスすることで、ローカルエージェントは高品質な情報を利用してコード内の重要なパラメータをより正確に調整し、既存のPerplexity Maxサブスクリプションをより有効活用できます。

> 7月20日時点で、PerplexityはUnix系環境向けの公式CLIを提供していません。
> 7月23日に、公式がComputerモードで使用されるpplxツールの公開バージョンをリリースしたことに注目していますが、このツールは依然として従量課金です。

ただし、これはComputerモードの完全な代替ではありません。再現できない2つの機能があります：

- 深層研究スキルではモデルを自由に指定できます。
- モデル委員会スキルでは、複数の異なるモデルを指定してそれぞれ深層研究を行い、レポートを出力し、直接比較できます。

リポジトリ内の [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context)
ディレクトリには、Computerのワークフローの一部をローカルで近似するためのシステムプロンプトや実行ルールがアーカイブされており、深層研究モードの選択やサブエージェントモデルの選択が含まれます。

<a id="功能概览" data-pplx-source-anchor="true"></a>
## 機能概要

<a id="pplx-export-归档你的-library" data-pplx-source-anchor="true"></a>
### `pplx-export` —— ライブラリのアーカイブ

- ライブラリインデックスとスペースインデックス
- シングルスレッド/バッチエクスポート（増分早期停止 + 中断再開）
- アセットの修復と使用量の補完
- 会話関係グラフ
- オフラインレンダリング（`re-render`、ネットワーク不要）
- 定期的な増分cronスニペット

<a id="pplx-ask-在命令行发问" data-pplx-source-anchor="true"></a>
### `pplx-ask` —— コマンドラインでの質問

- SSEストリーミング質問（search / deep-research / council / studyの4モード）
- 完了後、自動的にBOTスペースに移動、既読通知
- 作成されたスレッドは自動的にアーカイブされ、他のエージェントがリアルタイム情報を取得するために利用可能

5つのモードの成果物の境界（引用/レポート/アセット/サブエージェント）については[モード](guide/modes.md)を参照。レンダリングの忠実性の原則については[エクスポートパイプライン](architecture/export-pipeline.md)を参照。

!!! note "ドキュメントの出典"

    MkDocsサイトのほとんどのページは、現在のコードとテストに基づいて生成または再構築されています。一部のページは、以前にエージェントと議論した設計の背景、観察記録、決定事項も保持しています。ドキュメントの記述と実装が一致しない場合は、現在のコードとテストが優先されます。

<a id="接下来去哪" data-pplx-source-anchor="true"></a>
## 次にどこへ

- **ツールの使用**——タスクに応じて[使用ガイド](guide/index.md)を読んでください。
- **実装の理解**——[システムアーキテクチャの読み取りマップ](architecture/index.md)から始めてください。
- **観測されたWebインターフェースの処理**——[Web APIリファレンス](reference/api/index.md)を参照してください。
- **プロジェクトの安全な変更**——[メンテナーガイド](development/index.md)に従ってください。
