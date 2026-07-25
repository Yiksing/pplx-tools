---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/index.zh-CN.md"
translation_source_sha256: "36473d77356f8d36bd928e79c8c3584fc1e4e8a7c0e269b00dbb63bef56b458c"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="使用指南" data-pplx-source-anchor="true"></a>
# 使用ガイド

タスク指向の `pplx-export` と `pplx-ask` のインストール、設定、実行に関するドキュメント。

<a id="开始使用" data-pplx-source-anchor="true"></a>
## はじめに

- [クイックスタート](getting-started.md)——インストールコマンド、初期設定、初回エクスポートの実行。
- [設定](configuration.md)——アカウント、Cookie のソース、出力ルートディレクトリ、BOT スペース。

<a id="命令参考" data-pplx-source-anchor="true"></a>
## コマンドリファレンス

- [pplx-export](pplx-export.md)——インデックス、シングルスレッドエクスポート、バッチアーカイブ。
- [pplx-ask](pplx-ask.md)——search、deep-research、council、study のストリーミング質問。
- [メンテナンスコマンド](maintenance-commands.md)——再レンダリング、補完、関係図、同期操作。

<a id="归档与同步" data-pplx-source-anchor="true"></a>
## アーカイブと同期

- [アーカイブ構造](archive-layout.md)——ファイル、インデックス、ステータス、保持された生のレスポンス。
- [セッションモード](modes.md)——各サポートモードの成果物の境界。
- [インクリメンタル同期](incremental-sync.md)——早期停止、チェックポイント、中断再開のセマンティクス。

<a id="运行与排错" data-pplx-source-anchor="true"></a>
## 実行とトラブルシューティング

- [レート制限の規律](rate-limiting.md)——安全なリクエストのペースとスケジューリング。
- [トラブルシューティング](troubleshooting.md)——一般的な問題と復旧手順。

実装の仕組みを理解する必要がある場合は、[システムアーキテクチャのロードマップ](../architecture/index.md)を参照してください。
