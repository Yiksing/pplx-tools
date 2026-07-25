# 认证模型

> 本页是 API 参考区的首页——pplx_export 项目对 Perplexity 非公开 Web API 的实测记录。
> 读者：本项目的维护者与使用者。所有端点均经 WebBridge 网络捕获 + cookie 直连实测验证（2026-07）。
> **修改/新增 API 认知时必须同步更新这些页面**（用户明确要求）。
> 最后更新：2026-07-23
>
> 参考区拆分为：**1. 认证模型**（本页）· [2. GraphQL（持久化查询 APQ）](api-graphql.md) · [3. REST 端点（按用途分组）](api-rest-endpoints.md) · [4–5. 响应结构与错误语义](api-responses-errors.md) · [6–8. 待确认项、端点发现与路线图](api-discovery-roadmap.md)——外围系统设计见[系统架构阅读地图](../../architecture/index.md)。

---

## 认证模型

### cookie 会话
- 所有 API 请求只需浏览器会话 cookie（无 CSRF token 要求；GET/POST 均实测直连成功）。
- 关键 cookie：`__Secure-next-auth.session-token`（**当前生效账户**的会话令牌）。
- Cloudflare 前置：`cf_clearance`/`__cf_bm` 与浏览器 TLS 指纹绑定——**curl 裸请求会被 403**；
  工具用 Python urllib + 从浏览器导入的 cookie 可正常通过（UA 伪装为桌面 Chrome）。

### 多账户（2026-07-20 探明）
- 同浏览器登录多账户时，每账户各持一条 `__Secure-pplx.session.<user_id>` cookie
  （域 www.perplexity.ai；值随响应滚动刷新）。
- `__Secure-next-auth.session-token` 的值 = 生效账户那条 per-account cookie 的值。
- **网页切换账户** = 导航 `https://www.perplexity.ai/?pplx_account=<user_id>`，服务端改写生效令牌。
- **工具侧自动切换**（pplx_export 已实现）：枚举浏览器中的 `__Secure-pplx.session.*`，
  逐个替换 `__Secure-next-auth.session-token` 并探测 `/api/auth/session` 至目标 email 匹配。
- `GET /api/auth/linked-accounts` 返回 `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`，
  但**仅在 primary 账户生效时返回全部账户**（非 primary 生效时只返回当前账户）——故工具不依赖它。
- 已登记账户示例（真实账户表外置为用户级 `config.toml`，此处为占位符）：
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa`（Max）；
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb`（Pro，primary）。
