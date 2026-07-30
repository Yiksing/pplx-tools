# Rate limiting and error handling

## Rate limiting and error handling

Two layers: `Throttle` (core/throttle.py:15) + error routing in `CookieTransport._request`
(core/http/cookie_transport.py:63-126); plus fail-fast at the batch layer.

```mermaid
flowchart TD
    REQ["_request issues the request<br/>max_retries=3 (cookie_transport.py:48)"] --> R{result}
    R -->|"2xx"| OK["throttle.reset clears backoff count<br/>(cookie_transport.py:77)<br/>avoids monotonic accumulation across requests"]
    R -->|"401 / 403"| AUTH["AuthTransportError raised immediately<br/>(cookie_transport.py:82-85)<br/>auth failures can't self-heal by backing off"]
    R -->|"429"| RL["RateLimitError + throttle.backoff<br/>keep retrying (cookie_transport.py:86-92)"]
    R -->|"400 and body contains ENTRY_DELETED"| DEL["EntryDeletedError terminal (cookie_transport.py:93-95)<br/>inherits EntryExpiredError — batch must catch it before<br/>EXPIRED (batch_cmd.py:163-174)<br/>mark_deleted, no more retries (offline-operations.md §17)"]
    R -->|"400 and body contains ENTRY_EXPIRED"| EXP["EntryExpiredError terminal<br/>(cookie_transport.py:96-98)<br/>batch marks mark_expired, no more retries"]
    R -->|"500 / 502 / 503 / 504"| S5["TransportError + backoff<br/>retry at least once with backoff (cookie_transport.py:99-107)<br/>504 is a common Cloudflare transient"]
    R -->|"404 and other codes"| NF["TransportError, break, no retry<br/>(cookie_transport.py:108-116)<br/>never mapped to EntryExpiredError: pplx-ask<br/>may transiently 404 when exporting right after thread creation (propagation delay);<br/>a terminal mark would bury a live thread not yet visible"]
    R -->|"network-layer exceptions"| NET["TransportError + backoff<br/>keep retrying (cookie_transport.py:117-125)"]
    RL --> REQ
    S5 --> REQ
    NET --> REQ

    subgraph THR["Throttle (throttle.py:15-53)"]
        D1["delay: uniform(delay_min, delay_max)<br/>batch default 10–20s (cli.py:125-128)"]
        D2["backoff: delay_max × 3^N<br/>±20% jitter anti-sync, capped at 300s<br/>N = consecutive failure count (throttle.py:38-50)"]
        D3["reset: cleared on success (throttle.py:52)"]
    end

    subgraph BF["batch-layer triple fail-fast (batch_cmd.py)"]
        F1["AuthTransportError: auth_fails += 1<br/>3 consecutive (_AUTH_FAIL_FAST, batch_cmd.py:43)<br/>→ save + SystemExit abort<br/>(spinning with a dead cookie would fail hundreds of threads one by one)"]
        F2["other exceptions: auth_fails cleared<br/>mark_error + throttle.backoff, continue (batch_cmd.py:195-200)"]
        F3["KeyboardInterrupt: save, then raise (batch_cmd.py:158-161)"]
    end

    AUTH --> F1
    DEL --> DONE1
    EXP --> DONE1(["terminal registration"])
    OK --> DONE2(["mark_ok"])

    subgraph LIM["rate-limit discipline (anti-ban red line, explicit user requirement)"]
        L1["random 10–20s between threads, no concurrency"]
        L2["pagination ≥3s (rest.py:38)<br/>≥4s before blocks re-fetch (adapter.py:28,88)<br/>space metadata ≥3s (spaces_cmd.py:328)<br/>usage / backfill metadata ≥3s"]
        L3["0.5s between asset downloads (assets.py:28,103)<br/>backfill online phase: CDN downloads at 6 threads<br/>(CDN is not the API, assets_backfill_cmd.py:459-474)"]
    end
```

- **WebBridgeTransport** aligns 429 backoff and `throttle.reset()` on success
  (bridge_transport.py); error classification aligned with CookieTransport — 401/403 →
  `AuthTransportError`, 400 with body containing ENTRY_EXPIRED → `EntryExpiredError`,
  5xx backoff-retry; batch's auth fail-fast and expired terminal states also apply under
  `--transport webbridge`; daemon non-JSON responses collapse into
  TransportError (URLError/JSONDecodeError/OSError uniformly caught); other non-200s go straight to
  TransportError.
- **Shared Throttle**: batch passes the same instance to CookieTransport (cli.py:279-281),
  unifying backoff counts between transport and batch layers; **rebuilds after account auto-switching don't lose it either**
  (common.py:139 passes it too); single-shot commands that don't pass one get a default instance built by CookieTransport
  (cookie_transport.py:49).
- **Heartbeats (default verbosity).** The three long waits — a `Throttle.backoff`
  sleep, a stalled in-flight request (`CookieTransport._open_read`), and an idle
  `pplx-ask` SSE stream (`ask_api.post_stream`) — now emit INFO "still waiting"
  heartbeats so a wait is never mistaken for a hang. Backoff sleeps in chunks
  (`Throttle._sleep_with_heartbeat`) whose sum equals the same total, so the
  anti-ban pacing/budget is unchanged — only made visible; `-v` still adds the
  full DEBUG trace.
- **`--skip-auth-check` + deferred check.** The startup account-attribution
  session probe (`common.py`, `make_transport`) can be skipped to avoid a long
  startup wait on a poor network. As a safety net, `batch` runs a one-time
  `report_account_status` (`common.py`) once generic errors accumulate
  (`batch_cmd.py`), warning whether the cookie is expired, the account
  mismatches, or the account is fine (so errors are network / rate-limit).
