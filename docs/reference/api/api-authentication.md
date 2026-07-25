# Authentication model

> This page introduces the API reference area — the pplx_export project's field-tested record of Perplexity's private web API.
> Audience: maintainers and users of this project. All endpoints were verified via WebBridge network capture + direct cookie-authenticated requests (2026-07).
> **Any change or addition to API knowledge must be synced into these pages** (explicit user requirement).
> Last updated: 2026-07-23
>
> The reference area is split into: **1. Authentication model** (this page) · [2. GraphQL (persisted queries / APQ)](api-graphql.md) · [3. REST endpoints (grouped by purpose)](api-rest-endpoints.md) · [4–5. Response structure & error semantics](api-responses-errors.md) · [6–8. TBD items, endpoint discovery & roadmap](api-discovery-roadmap.md) — for the surrounding system design, see the [architecture reading map](../../architecture/index.md).

---

## Authentication model

### Cookie session
- All API requests need only the browser session cookie (no CSRF token required; both GET and POST verified working via direct requests).
- Key cookie: `__Secure-next-auth.session-token` (session token of the **currently active account**).
- Cloudflare sits in front: `cf_clearance`/`__cf_bm` are bound to the browser TLS fingerprint — **bare curl requests get 403**;
  the tool passes with Python urllib + cookies imported from the browser (UA masqueraded as desktop Chrome).

### Multi-account (discovered 2026-07-20)
- When multiple accounts are logged into the same browser, each account holds its own `__Secure-pplx.session.<user_id>` cookie
  (domain www.perplexity.ai; the value rolls forward with responses).
- The value of `__Secure-next-auth.session-token` = the value of the active account's per-account cookie.
- **Switching accounts on the web** = navigating to `https://www.perplexity.ai/?pplx_account=<user_id>`; the server rewrites the active token.
- **Tool-side automatic switching** (implemented in pplx_export): enumerate the browser's `__Secure-pplx.session.*` cookies,
  replace `__Secure-next-auth.session-token` with each in turn, and probe `/api/auth/session` until the target email matches.
- `GET /api/auth/linked-accounts` returns `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`,
  but **returns the full account list only while the primary account is active** (only the current account when a non-primary is active) — so the tool does not rely on it.
- Registered account examples (the real account table lives in user-level `config.toml`; placeholders shown here):
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa` (Max);
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb` (Pro, primary).
