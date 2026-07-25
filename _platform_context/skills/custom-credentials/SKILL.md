# Custom Credentials

Custom credentials let the user bring their own API key for a third-party HTTPS service that has no built-in connector. They can be scoped to **this session only** or saved to the user's Credentials vault. Vault credentials are reusable across conversations; by default they require approval before use in each session, but the user can set a saved credential to **Always allow**.

## Tools, one decision

In main-agent sessions, all credential tools are dispatched via `pplx-tool`. Run `pplx-tool <tool> --describe` once per tool to fetch the schema before first use.

- `pplx-tool list_credentials` — read the current set. Call this first whenever you're unsure what's already saved. Each returned row includes a stable `credential_uuid`.
- `pplx-tool request_credential` — open a secure in-session form for the user to add a credential. Only call this after `list_credentials` confirmed nothing matches the host you need.
- `pplx-tool approve_credential` — approve a Credentials vault or project entry for this session. Only call this when `list_credentials` returns `requires_approval=true`; pass `name`, `host`, and `credential_uuid` from the same listed row when available. The user's Always allow selection makes that saved credential available to future sessions without another prompt.
- `pplx-tool revoke_credential` — revoke a credential for the current session. Session-scoped credentials are revoked; approved vault credentials are detached from this session only. Only call it on explicit user request; pass `name`, `host`, and `credential_uuid` from the same listed row when available.

Scheduled background runs cannot ask the user to add or approve credentials, and interactive credential tools are unavailable there. If the scheduled task references an already-approved custom credential, pass the exact `custom-cred:<host>` handle in `api_credentials` when making the API request. If a credential is missing or no matching handle is known, report that the scheduled run needs the user to approve or add the credential in the original conversation.

## When the user has not provided the credential yet

If the user wants to use a third-party HTTPS API without connector support, route them to the secure credential form instead of asking them to paste the key in chat. This includes prompts like "use the OpenWeather API," "connect to the Acme API with my key," "configure an Authorization header," or "fix this 401 from api.example.com."

First run `pplx-tool list_credentials`. If no saved credential matches the API host, identify the host and likely auth scheme from the user's request or public API docs, then run `pplx-tool request_credential` so the user can enter the secret securely. After submission, proceed with `api_credentials=['custom-cred:<host>']`.

A matching `list_credentials` entry with `requires_approval=true` needs `pplx-tool approve_credential` before its handle is passed to downstream tools. An entry with `requires_approval=false` is already session-scoped, already approved, or set to Always allow; use the handle directly.

## When the user already pasted a credential

If the user pasted a token, API key, password, or headers JSON and asks you to use, test, curl, or call a third-party API, treat the pasted value as a credential that must be reviewed in the secure form before use. Do not put the raw value in `bash`, curl flags, headers, env vars, files, logs, or messages.

First run `pplx-tool list_credentials`. If no saved credential matches the API host, run `pplx-tool request_credential` and pass the pasted value as `credential_value` so the matching masked field is prefilled. This applies even when the user explicitly asks you to curl with the token: surface the form first, then proceed with `api_credentials=['custom-cred:<host>']` once submitted.

## Using a saved credential from `bash`

Pass `api_credentials=['custom-cred:<host>']` on the `bash` call that issues the request. Auth is injected automatically through an HTTPS proxy — never paste the credential value into the command.

Use `curl`, Python `requests`, `httpx` (sync or `httpx.AsyncClient`), `urllib`, or vendor SDKs that delegate to those — they all read `HTTPS_PROXY` and pick up the injected auth automatically. **Don't use `aiohttp`** — it ignores `HTTPS_PROXY` by default and the request goes out unauthenticated. For async work, prefer `httpx.AsyncClient`.

Footguns:

- **Non-HTTPS protocols are not intercepted** — websockets, raw TCP, gRPC over h2c. `api_credentials` won't help; the request goes out unauthenticated.
- **SDKs that pin their own HTTP transport** can bypass the proxy. If a request mysteriously 401s with `api_credentials` set, fall back to `httpx`/`requests` directly.

## Using a saved credential from website backends

For `start_server`, pass `api_credentials=['custom-cred:<host>']` using the returned `host`. For `publish_website`, pass `credentials={'custom-cred:<host>': ''}`. Use the exact `website_url_env_var` and `website_token_env_var` names returned by `list_credentials`; the backend should call the URL env var and send the token env var as `x-api-key`.

## Filling out `request_credential`

- **`host`** — hostname only. No scheme, no path, no port unless the service requires one. `api.openweathermap.org`, not `https://api.openweathermap.org/data/2.5/`.
- **`credential_type`** — pick the closest fit:
  - `BearerCred` for `Authorization: Bearer <token>`
  - `HeaderCred` for a single named header (e.g. `X-API-Key: <key>`)
  - `BasicCred` for username + password
  - `QueryParamCred` for `?api_key=<key>` query strings
  - `HeadersCred` for multi-header schemes
- **`auth_param_name`** — for `HeaderCred` and `QueryParamCred`, prefill the exact key name (e.g. `X-API-Key`, `api_key`) when you're confident from public API docs. Leave unset when unsure, or for `BearerCred`/`BasicCred` where it doesn't apply.
- **`credential_value`** — set only when the user already pasted the token, API key, password, or headers JSON into chat. This prefills the matching masked secret field so the user can review and submit the form. Never ask the user to paste a secret just to fill this field.
- **`reason`** — one short sentence saying what you'll do with the credential for the user's current session. Don't restate the service or credential type (the form already shows them).

## Stale state from in-UI changes

The user can add or revoke credentials directly in the credentials pane without telling you. So:

- Re-run `pplx-tool list_credentials` before relying on results from earlier in the conversation.
- Definitely re-list before retrying a request that just 401'd — the credential may have been revoked.
- If the user says "I already added it," list first instead of re-prompting with `request_credential`.

## Privacy

`list_credentials` returns metadata and safe usage hints only; it never returns the secret. Don't ask the user to paste raw credential values into chat — direct them to the form opened by `request_credential`, or to the credentials pane. If the user already pasted a secret unprompted, put it in `credential_value` so the masked form is prefilled, and never echo it back or use it directly in shell commands.