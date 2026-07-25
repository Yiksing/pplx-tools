---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-authentication.zh-CN.md"
translation_source_sha256: "406c7c3482391bd37729d04f0ef0d57990bf5540a96837da279ae0429277d588"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="认证模型" data-pplx-source-anchor="true"></a>
# 認証モデル

> このページは API リファレンスセクションのトップページです——pplx_export プロジェクトによる Perplexity 非公開 Web API の実測記録です。
> 読者：本プロジェクトのメンテナーと利用者。すべてのエンドポイントは WebBridge ネットワークキャプチャ + cookie 直接接続による実測検証済み（2026-07）。
> **API の認識を変更・追加する際は、これらのページを必ず同時に更新してください**（ユーザーからの明確な要求）。
> 最終更新：2026-07-23
>
> リファレンスセクションは以下のように分割されています：**1. 認証モデル**（本ページ）· [2. GraphQL（永続化クエリ APQ）](api-graphql.md) · [3. REST エンドポイント（用途別グループ）](api-rest-endpoints.md) · [4–5. レスポンス構造とエラーセマンティクス](api-responses-errors.md) · [6–8. 未確認項目、エンドポイント発見、ロードマップ](api-discovery-roadmap.md)——周辺システム設計については[システムアーキテクチャ読解マップ](../../architecture/index.md)を参照してください。

---

<a id="认证模型_1" data-pplx-source-anchor="true"></a>
## 認証モデル

<a id="cookie-会话" data-pplx-source-anchor="true"></a>
### cookie セッション
- すべての API リクエストはブラウザセッション cookie のみ必要（CSRF トークン不要；GET/POST ともに実測で直接接続成功）。
- 重要な cookie：`__Secure-next-auth.session-token`（**現在有効なアカウント**のセッショントークン）。
- Cloudflare 前段：`cf_clearance`/`__cf_bm` はブラウザの TLS フィンガープリントにバインド——**curl の生リクエストは 403 になります**；
  ツールは Python urllib + ブラウザからインポートした cookie を使用することで正常に通過可能（UA はデスクトップ Chrome に偽装）。

<a id="多账户2026-07-20-探明" data-pplx-source-anchor="true"></a>
### マルチアカウント（2026-07-20 確認）
- 同一ブラウザで複数アカウントにログインする場合、各アカウントはそれぞれ独自の `__Secure-pplx.session.<user_id>` cookie を持ちます
  （ドメイン www.perplexity.ai；値はレスポンスに応じてローテーション更新）。
- `__Secure-next-auth.session-token` の値 = 有効なアカウントの per-account cookie の値。
- **Web でのアカウント切り替え** = `https://www.perplexity.ai/?pplx_account=<user_id>` をナビゲートし、サーバー側で有効トークンを書き換え。
- **ツール側での自動切り替え**（pplx_export で実装済み）：ブラウザ内の `__Secure-pplx.session.*` を列挙し、
  順次 `__Secure-next-auth.session-token` を置き換えて `/api/auth/session` をプローブし、対象の email と一致するまで実行。
- `GET /api/auth/linked-accounts` は `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]` を返しますが、
  **primary アカウントが有効な場合のみ全アカウントを返します**（非 primary 有効時は現在のアカウントのみ）——そのためツールはこれに依存しません。
- 登録済みアカウントの例（実際のアカウントテーブルはユーザーレベルの `config.toml` として外部化、ここではプレースホルダ）：
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa`（Max）；
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb`（Pro、primary）。
