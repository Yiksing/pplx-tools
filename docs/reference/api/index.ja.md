---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/index.zh-CN.md"
translation_source_sha256: "6e3c3f3adb7e4fa7d731b9d510aacd07fb9c71885c4618222a12f066997cd316"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-参考" data-pplx-source-anchor="true"></a>
# Web API リファレンス

`pplx-export` と `pplx-ask` が使用する Perplexity REST および GraphQL の動作観察記録。

!!! warning "観察されたインターフェースであり、安定性の約束ではない"

    本セクションは、プロジェクトが Web アプリケーション、アーカイブ応答、フロントエンドバンドル、および現在の実装から観察した動作に基づいてまとめられています。
    Perplexity の公式 API 契約ではありません。ネットワークコードを変更する前に、日付付きの観察結果を再検証してください。

<a id="推荐阅读顺序" data-pplx-source-anchor="true"></a>
## 推奨読書順序

1. [認証モデル](api-authentication.md)——セッション Cookie、トークン、関連アカウントと ID。
2. [GraphQL](api-graphql.md)——永続化クエリ、APQ 識別子、使用中の操作。
3. [REST エンドポイント](api-rest-endpoints.md)——目的別にグループ化された観察済みエンドポイント。
4. [応答とエラーセマンティクス](api-responses-errors.md)——応答形式、解析の規律、終端状態、リスク管理動作。
5. [発見方法とロードマップ](api-discovery-roadmap.md)——エンドポイント発見方法と未確認の問題。

<a id="相关实现文档" data-pplx-source-anchor="true"></a>
## 関連実装ドキュメント

- [pplx-ask とマルチアカウント](../../architecture/ask-and-accounts.md)
- [レート制限とエラー処理](../../architecture/rate-limiting-errors.md)
- [トラブルシューティング](../../guide/troubleshooting.md)
