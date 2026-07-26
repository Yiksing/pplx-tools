---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/ask-and-accounts.md"
translation_source_sha256: "fecfe8824ffed615a6fcc43ff90af9f59c12dfb4c8173aab0b0a075e72416116"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="pplx-ask-and-accounts" data-pplx-source-anchor="true"></a>
# pplx-ask und Konten

---

<a id="pplx-ask-sequence-in-detail" data-pplx-source-anchor="true"></a>
## pplx-ask-Sequenz im Detail

Die vollständige Sequenz von `cmd_ask` (ask_cli.py:86-198): Envelope-Konstruktion → SSE-Stream → Endstatus-Prüfung →
BOT-Space → Lesebestätigung → humanisierte Telemetrie → Archivierung über die Export-Pipeline.

```mermaid
sequenceDiagram
    participant U as agent / user
    participant A as ask_cli.cmd_ask
    participant AK as ask_api
    participant P as Perplexity
    participant EX as cmd_export (export pipeline reused)

    U->>A: pplx-ask ask "prompt" --mode M [--models ...] [--space S]
    A->>A: when --space is not home, resolve the space uuid first<br/>_resolve_space_uuid (ask_cli.py:74-83)
    A->>AK: build_envelope(prompt, mode, models, target_uuid) (ask_api.py:71)
    Note over AK: mode → model_preference mapping (MODE_MODEL, ask_api.py:36-41):<br/>search→pplx_pro / deep-research→pplx_alpha /<br/>council→pplx_agentic_research / study→pplx_study;<br/>mode always "copilot"; council slot validation 2–3 models<br/>(ask_api.py:85-90), default COUNCIL_DEFAULT_MODELS
    AK-->>A: {"params": {template params}, "query_str": prompt}
    A->>AK: sse_ask(transport, envelope, on_event) (ask_api.py:153)
    AK->>P: POST /rest/sse/perplexity_ask (ASK_URL, ask_api.py:28)<br/>Accept: text/event-stream; reuses CookieTransport's internal opener/cookie (ask_api.py:114-130)
    loop SSE event stream (blank-line delimited, _parse_sse, ask_api.py:101-111)
        P-->>AK: data: {...backend_uuid / status / text deltas...}
        AK-->>A: on_event: first backend_uuid records thread creation<br/>status changes printed; progress every +200 text chars (ask_cli.py:106-119)
    end
    AK-->>A: final_sse_message terminates; return the final event (ask_api.py:164-165)
    A->>A: final-status check: final_status != COMPLETED → SystemExit<br/>no space move / no telemetry / no export (ask_cli.py:134-140)
    A->>AK: move_threads([context_uuid], BOT_SPACE_UUID) (ask_api.py:169)
    AK->>P: POST /rest/collections/batch_move_threads<br/>(use context_uuid, not entryUUID; BOT space from user-level config bot_space.uuid)
    opt --mark-read
        A->>AK: mark_read(context_uuid) (ask_api.py:190)
        AK->>P: POST /rest/thread/mark_viewed (unread flips immediately)
    end
    opt on by default (disabled by --no-telemetry)
        A->>AK: send_view_telemetry (ask_api.py:234)
        AK->>P: POST /rest/event/analytics ×4:<br/>ask context pane viewed → thread viewed<br/>→ ask context pane viewed → thread entry exited<br/>(random device pool + random 0.6–2.4s pauses between events<br/>+ timeOnEntryMs 12–45s, ask_api.py:266-278)
    end
    opt on by default (disabled by --no-export)
        A->>EX: cmd_export(adapter, writer, backend_uuid, force=True) (ask_cli.py:192)
        EX->>P: runs the full export pipeline (export-pipeline.md §3)
        EX-->>A: web_archive persisted
    end
    A-->>U: machine-readable JSON: thread_uuid / thread_url /<br/>context_uuid / moved_to_bot / mark_read / telemetry (booleans)<br/>/ step_errors (failed steps only) / exported (end of ask_cli.py)
```

Wesentliche Designaspekte:

- **Der Envelope ist eine feldgeprüfte Parametervorlage**: `_BASE_PARAMS` (ask_api.py:44-68) hat 25 feste Schlüssel
  (inkl. 32 `supported_block_use_cases`, Sprache/Zeitzone/Suchfokus usw.); `build_envelope`
  injiziert Mode/Model/Frontend_uuid-Felder, die echten Browser-Übermittlungen entsprechen (vergleiche
  [../reference/api/api-rest-endpoints.md](../reference/api/api-rest-endpoints.md) §3.9 und die 39-Parameter-Beispiele in `docs/perplexity-api-samples/`).
- **SSE-Konsum umgeht das Transport-ABC**: Streaming liegt außerhalb der `get_json/post_json/download`-
  Abstraktion; `post_stream` verwendet direkt `CookieTransport`s `_cookie_header`/`_opener`
  (ask_api.py:126-130) – die bewusste Kopplung, die in [§1](overview.md) erwähnt wird.
- **Telemetrie-Humanisierung**: `_DEVICE_POOL` randomisiert über drei Geräte (ask_api.py:210-214), zufällige Pausen,
  zufällige Lesedauern; Ereignisschemata stimmen Punkt für Punkt mit Browser-Beobachtungen überein (`_telemetry_event`,
  ask_api.py:217-231); die Lesebestätigung ist getrennt von der Telemetrie – Analytics „Thread angesehen“ setzt nicht
  ungelesen zurück; die echte Bestätigung ist `mark_viewed` (ask_api.py:194-201 Kommentar).

---

<a id="multi-account-cookie-switching-flow" data-pplx-source-anchor="true"></a>
## Multi-Account-Cookie-Wechselablauf

Cookie-Auflösung und Kontovalidierung befinden sich in `commands/common.py:make_transport` (common.py:93-155);
Quellenaufzählung in `core/cookies/loaders.py`; Webbridge-Pfadvalidierung in `_validate_bridge_account`
(common.py:158-187).

```mermaid
flowchart TD
    START(["make_transport(account, ...)"]) --> MODE{"transport_mode?"}
    MODE -->|"webbridge (explicitly chosen)"| WB1["WebBridgeTransport (bridge_transport.py:22)"]
    WB1 --> WB2{"_validate_bridge_account<br/>GET /api/auth/session (common.py:173)"}
    WB2 -->|"email matches or unregistered"| WBOK(("return bridge"))
    WB2 -->|"email mismatch"| WBERR["SystemExit: switch the browser account first (common.py:177-179)"]
    WB2 -->|"bridge unreachable"| WBWARN["log.warning only, proceed<br/>(fallback path doesn't hard-fail, common.py:186-187)"]
    WBWARN --> WBOK

    MODE -->|"cookie (default)"| SRC{"cookie source priority<br/>cookies.resolve (cookies/loaders.py:270-302)"}
    SRC -->|"1. --cookies-from specifies browser"| F1["from_browser (cookies/loaders.py:107)"]
    SRC -->|"2. --cookies file"| F2["from_file: Netscape / JSON formats<br/>#HttpOnly_ prefix restored (cookies/loaders.py:209-249)"]
    SRC -->|"3. fresh cache"| F3["CookieCache.load<br/>&lt;out&gt;/index/.cookies.json, 12h freshness<br/>(cookies/cache.py:33-47)"]
    SRC -->|"4. auto-detect"| F4["edge → chrome → firefox → safari<br/>(AUTO_DETECT_ORDER, cookies/loaders.py:39)<br/>browser_cookie3 decryption"]
    F1 --> SESS
    F2 --> SESS
    F3 --> SESS
    F4 --> SESS
    SESS{"GET /api/auth/session<br/>read current email (common.py:126-128)"}
    SESS -->|"email == ACCOUNT_EMAIL[account]<br/>(user-level config accounts.&lt;name&gt;.email)"| OK(("CookieTransport ready<br/>+ CookieCache.save refreshes cache (common.py:150)"))
    SESS -->|"unregistered email"| WARN2["log.warning suggests registering, proceed (common.py:146-149)"] --> OK
    SESS -->|"email mismatch"| SW["_try_switch_account (common.py:190-215)"]
    SW --> ENUM["list_account_tokens (cookies/loaders.py:175-206)<br/>enumerate browser __Secure-pplx.session.&lt;uid&gt;<br/>(www-subdomain entries preferred)"]
    ENUM --> LOOP{"per token: replace<br/>__Secure-next-auth.session-token<br/>(ACTIVE_SESSION_COOKIE, cookies/loaders.py:172)"}
    LOOP --> PROBE["probe with new CookieTransport<br/>GET /api/auth/session (common.py:207-208)"]
    PROBE -->|"email matches"| SWOK(("switch succeeded: rebuild CookieTransport<br/>with the new cookie jar (common.py:136-140)"))
    PROBE -->|"no match"| LOOP
    LOOP -->|"all failed"| ERR["SystemExit: list target email and current email<br/>prompt to log in in the browser first (common.py:142-145)"]
```

Wesentliches:

- **Multi-Account-Modell**: ein `__Secure-pplx.session.<uid>`-Cookie pro Konto im selben Browser;
  Wechsel = Schreiben des Werts des Zielkontos in `__Secure-next-auth.session-token` (cookies/loaders.py:180-187
  Kommentar; Mechanismus getestet in [../reference/api/api-authentication.md](../reference/api/api-authentication.md) §1.2). Keine Browser-UI erforderlich.
- **Cache folgt `--out`**: `<out_root>/index/.cookies.json` (common.py:111),
  mit fetched_at/source/account_email; immer nach erfolgreicher Validierung aktualisiert (common.py:150).
- **Webbridge und Cookie schließen sich gegenseitig aus**: Übergabe von `--cookies/--cookies-from` zusammen mit `--transport webbridge`
  führt zu einem Fehler (cli.py:229-233; common.py:112-116).
- `core/auth.py:CredentialProvider` (Cookie-Extraktion über WebBridge: CDP Storage.getCookies
  bevorzugt, document.cookie-Fallback, auth.py:41-67) gehört zur **reservierten Fallback-Kette**; sein einziger Aufrufer heute ist
  `cookies.from_webbridge` (cookies/loaders.py:252-267).
