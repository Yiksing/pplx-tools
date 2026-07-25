---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-authentication.zh-CN.md"
translation_source_sha256: "406c7c3482391bd37729d04f0ef0d57990bf5540a96837da279ae0429277d588"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="认证模型" data-pplx-source-anchor="true"></a>
# 認證模型

> 本頁是 API 參考區的首頁——pplx_export 專案對 Perplexity 非公開 Web API 的實測記錄。
> 讀者：本專案的維護者與使用者。所有端點均經 WebBridge 網路捕獲 + cookie 直連實測驗證（2026-07）。
> **修改/新增 API 認知時必須同步更新這些頁面**（用戶明確要求）。
> 最後更新：2026-07-23
>
> 參考區拆分為：**1. 認證模型**（本頁）· [2. GraphQL（持久化查詢 APQ）](api-graphql.md) · [3. REST 端點（按用途分組）](api-rest-endpoints.md) · [4–5. 回應結構與錯誤語義](api-responses-errors.md) · [6–8. 待確認項、端點發現與路線圖](api-discovery-roadmap.md)——外圍系統設計見[系統架構閱讀地圖](../../architecture/index.md)。

---

<a id="认证模型_1" data-pplx-source-anchor="true"></a>
## 認證模型

<a id="cookie-会话" data-pplx-source-anchor="true"></a>
### cookie 會話
- 所有 API 請求只需瀏覽器會話 cookie（無 CSRF token 要求；GET/POST 均實測直連成功）。
- 關鍵 cookie：`__Secure-next-auth.session-token`（**當前生效帳戶**的會話令牌）。
- Cloudflare 前置：`cf_clearance`/`__cf_bm` 與瀏覽器 TLS 指紋綁定——**curl 裸請求會被 403**；
  工具用 Python urllib + 從瀏覽器導入的 cookie 可正常通過（UA 偽裝為桌面 Chrome）。

<a id="多账户2026-07-20-探明" data-pplx-source-anchor="true"></a>
### 多帳戶（2026-07-20 探明）
- 同瀏覽器登入多帳戶時，每帳戶各持一條 `__Secure-pplx.session.<user_id>` cookie
  （域 www.perplexity.ai；值隨回應滾動刷新）。
- `__Secure-next-auth.session-token` 的值 = 生效帳戶那條 per-account cookie 的值。
- **網頁切換帳戶** = 導航 `https://www.perplexity.ai/?pplx_account=<user_id>`，服務端改寫生效令牌。
- **工具側自動切換**（pplx_export 已實現）：枚舉瀏覽器中的 `__Secure-pplx.session.*`，
  逐個替換 `__Secure-next-auth.session-token` 並探測 `/api/auth/session` 至目標 email 匹配。
- `GET /api/auth/linked-accounts` 返回 `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`，
  但**僅在 primary 帳戶生效時返回全部帳戶**（非 primary 生效時只返回當前帳戶）——故工具不依賴它。
- 已登記帳戶示例（真實帳戶表外置為用戶級 `config.toml`，此處為佔位符）：
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa`（Max）；
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb`（Pro，primary）。
