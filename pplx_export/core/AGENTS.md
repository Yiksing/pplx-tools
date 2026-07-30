# Sensitive core boundary

These instructions apply to `pplx_export/core/**`.

- This is the sensitive core shared by `pplx-export` and `pplx-ask`: auth,
  cookies, HTTP transports, filesystem writes, logging, state, throttling,
  models, registry, and relation assembly live here.
- Treat cookie values, session tokens, CSRF or auth headers, login emails, user
  IDs, account registry data, browser profile paths, and cached credentials as
  sensitive. Do not log, commit, snapshot, or serialize real values.
- Keep configuration and credential material external to the repository. Tests
  must use fake cookies, fake transports, temporary directories, and isolated
  environment or config patches.
- Cookie and credential cache writes must remain atomic, owner-only (`0o600`)
  where applicable, and safe across interrupted runs.
- Transport changes must preserve auth, rate-limit, retry, deletion, expiration,
  and ordinary failure semantics. Do not silently convert authentication or
  remote-state errors into success or terminal archive state.
- Preserve the raw-first archive contract when core helpers feed command or site
  adapters: derived Markdown or JSON must not become the only durable source of
  truth.
- Any change touching `auth.py`, `cookies/**`, `http/**`, credential caching, or
  transport construction needs targeted offline tests for the sensitive path and
  a privacy check before public release.
