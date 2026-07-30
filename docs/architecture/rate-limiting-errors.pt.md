---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/rate-limiting-errors.md"
translation_source_sha256: "91252ba3add326958d39759900774a7a4268b67820c65a36a4ae9e9b8eaa2ec3"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="rate-limiting-and-error-handling" data-pplx-source-anchor="true"></a>
# Limitação de taxa e tratamento de erros

<a id="rate-limiting-and-error-handling_1" data-pplx-source-anchor="true"></a>
## Limitação de taxa e tratamento de erros

Duas camadas: `Throttle` (core/throttle.py:15) + roteamento de erros em `CookieTransport._request`
(core/http/cookie_transport.py:63-126); além de falha rápida na camada de lote.

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
        D1["delay: uniform(delay_min, delay_max)<br/>batch default 10–20s (cli.py:126-129)"]
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
        L2["pagination ≥3s (rest.py:39)<br/>≥4s before blocks re-fetch (adapter.py:28,88)<br/>space metadata ≥3s (spaces_cmd.py:328)<br/>usage / backfill metadata ≥3s"]
        L3["0.5s between asset downloads (assets.py:28,103)<br/>backfill online phase: CDN downloads at 6 threads<br/>(CDN is not the API, assets_backfill_cmd.py:460-475)"]
    end
```

- **WebBridgeTransport** alinha backoff 429 e `throttle.reset()` em caso de sucesso
  (bridge_transport.py); classificação de erros alinhada com CookieTransport — 401/403 →
  `AuthTransportError`, 400 com corpo contendo ENTRY_EXPIRED → `EntryExpiredError`,
  5xx backoff-retry; os estados terminais de falha rápida de autenticação e expirado do lote também se aplicam sob
  `--transport webbridge`; respostas não JSON do daemon colapsam em
  TransportError (URLError/JSONDecodeError/OSError capturados uniformemente); outros não-200 vão diretamente para
  TransportError.
- **Throttle Compartilhado**: o lote passa a mesma instância para CookieTransport (cli.py:280-282),
  unificando as contagens de backoff entre as camadas de transporte e lote; **reconstruções após troca automática de conta também não o perdem**
  (common.py:139 também o passa); comandos únicos que não passam um recebem uma instância padrão construída por CookieTransport
  (cookie_transport.py:49).
- **Heartbeats (verbosidade padrão).** As três longas esperas — um sono de `Throttle.backoff`,
  uma requisição em andamento travada (`CookieTransport._open_read`) e um stream SSE
  `pplx-ask` ocioso (`ask_api.post_stream`) — agora emitem heartbeats INFO "still waiting"
  para que uma espera nunca seja confundida com um travamento. Os sonos de backoff em partes
  (`Throttle._sleep_with_heartbeat`) cuja soma é igual ao mesmo total, então o
  ritmo/orçamento anti-ban não é alterado — apenas tornado visível; `-v` ainda adiciona o
  trace completo de DEBUG.
- **`--skip-auth-check` + verificação adiada.** A sonda de sessão de atribuição de conta na inicialização
  (`common.py`, `make_transport`) pode ser pulada para evitar uma longa espera
  de inicialização em uma rede ruim. Como rede de segurança, `batch` executa um
  `report_account_status` único (`common.py`) uma vez que erros genéricos se acumulam
  (`batch_cmd.py`), avisando se o cookie expirou, a conta não corresponde,
  ou a conta está ok (então os erros são de rede / limite de taxa).
