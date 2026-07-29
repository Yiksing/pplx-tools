---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/rate-limiting.md"
translation_source_sha256: "5d2c127866c97b95edeb2938dabbcb2ce485b15f3d316a61c6057f7653a571d5"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="rate-limiting" data-pplx-source-anchor="true"></a>
# Ratenbegrenzung

Jede Zahl in der Taktungsrichtlinie dient einem Ziel: Archiv-Traffic muss wie normales Surfen aussehen. Ein einzelner Thread-Export kostet 1–2 Anfragen – ungefähr ein Seitenaufruf – und Batch-Läufe verteilen diese Anfragen über randomisierte Intervalle ohne Parallelität. Dies ist eine explizite Anti-Risiko-Kontrollanforderung (`pplx_export/core/throttle.py:1-2`), kein einstellbarer Leistungsregler.

<a id="the-numbers" data-pplx-source-anchor="true"></a>
## Die Zahlen

| wo | Taktung | Code |
|---|---|---|
| `batch`: zwischen Threads | zufällig gleichverteilt 10–20 s (`--delay-min` / `--delay-max`) | `pplx_export/cli.py:126-129`, `pplx_export/core/throttle.py:33-36` |
| `sync-deleted --online`: zwischen Kandidaten | zufällig gleichverteilt 10–20 s | `pplx_export/cli.py:164-167`, `pplx_export/commands/sync_deleted_cmd.py:368-369` |
| `search-mode-backfill`: Online-Fallback | zufällig gleichverteilt 10–20 s | `pplx_export/cli.py:144-147` |
| Paginierung innerhalb eines Threads / Space-Listings | ≥3 s zwischen Seiten | `pplx_export/sites/perplexity/rest.py:39,56`, `pplx_export/sites/perplexity/adapter.py:285-309` |
| Schematisierter-Block-Nachladevorgang (Computer / Deep Research / Council / Study) | ≥4 s Wartezeit vor dem zweiten Abruf | `pplx_export/sites/perplexity/adapter.py:27-32,88` |
| `spaces --fetch-meta` | 3 s pro Space | `pplx_export/commands/spaces_cmd.py:328` |
| `usage-backfill` | 3 s pro Thread | `pplx_export/commands/usage_backfill_cmd.py:77` |
| `assets-backfill` Online-Phasen | 3 s pro Thread | `pplx_export/commands/assets_backfill_cmd.py:215,456` |
| Asset-Downloads innerhalb eines Threads | 0,5 s | `pplx_export/sites/perplexity/assets.py:28,103` |
| `assets-backfill` CDN-Phase | 6 parallele Downloads, keine Verzögerung | `pplx_export/commands/assets_backfill_cmd.py:460-475` |
| API-Parallelität | keine – niemals | — |

<a id="why-these-numbers" data-pplx-source-anchor="true"></a>
## Warum diese Zahlen

- **Einzelner Export = 1–2 Anfragen ≈ ein Seitenaufruf.** Ein Such-Thread kostet einen `GET /rest/thread/<uuid>`; Computer / Deep Research / Council / Study fügen genau einen Abruf der schematisierten Blöcke hinzu (`pplx_export/sites/perplexity/adapter.py:87-89`). Das entspricht in etwa dem, was ein Browser tut, wenn Sie die Seite einmal öffnen – das Archiv fügt keine nennenswerte Last zusätzlich zur normalen Nutzung hinzu.
- **10–20 s zufälliges Intervall, keine Parallelität.** Menschlicher Leserhythmus, und die Randomisierung vermeidet metronomgenaues Timing. Serielle Anfragen halten die Rate unter dem, was normales Surfen bereits produziert.
- **≥3 s Seitenwechsel.** Paginierung innerhalb eines langen Threads imitiert Scroll- und Lesezeit.
- **≥4 s vor dem Blockabruf.** Der schematisierte Neuladevorgang würde sonst die API direkt nach dem einfachen Abruf treffen; die Pause imitiert die Verzögerung, bevor eine schwere Seite ihre vollständige Nutzlast lädt.
- **0,5 s Asset-Downloads.** Kleine statische Dateien, weitaus günstiger als API-Aufrufe – aber dennoch getaktet.
- **Die CDN-Phase ist die einzige Lockerung.** Downloads mit signierten URLs treffen das Content Delivery Network, nicht die Perplexity-API, daher sind 6 parallele Verbindungen dort und nur dort akzeptabel.

<a id="error-handling-and-backoff" data-pplx-source-anchor="true"></a>
## Fehlerbehandlung und Backoff

Die gesamte Klassifizierung erfolgt in `CookieTransport._request` (`pplx_export/core/http/cookie_transport.py:63-126`); jede Anfrage erhält bis zu `max_retries=3` Versuche (`cookie_transport.py:48`).

```mermaid
flowchart TD
    R{response} -->|"2xx"| OK["reset backoff counter"]
    R -->|"429"| BO["backoff + retry (≤3 attempts)"]
    R -->|"5xx / network error"| BO
    R -->|"401 / 403"| AF["raise immediately →<br/>abort after 3 consecutive"]
    R -->|"ENTRY_EXPIRED / ENTRY_DELETED"| TERM["terminal mark<br/>never retried"]
```

| Antwort | Klassifizierung | Behandlung |
|---|---|---|
| 2xx | Erfolg | Backoff-Zähler zurücksetzen (`cookie_transport.py:77`) – Zähler akkumulieren nie über Anfragen hinweg |
| 429 | Ratenbegrenzung | Backoff und Wiederholung (`cookie_transport.py:86-92`) |
| 500 / 502 / 503 / 504 | Transienter Serverfehler (504 ist häufig ein Cloudflare-Aussetzer) | Backoff und mindestens einmal wiederholen, bevor aufgegeben wird (`cookie_transport.py:99-107`) |
| Netzwerkfehler | Transient | Backoff und Wiederholung (`cookie_transport.py:117-125`) |
| 401 / 403 | Authentifizierungsfehler | `AuthTransportError` sofort ausgelöst – kein Backoff (`cookie_transport.py:82-85`) |
| 400 + `ENTRY_EXPIRED` | Plattform-Bereinigung | `EntryExpiredError` – endgültig, nie wiederholt (`cookie_transport.py:96-98`) |
| 400 + `ENTRY_DELETED` | Benutzer-/Remote-Löschung | `EntryDeletedError` – endgültig, nie wiederholt (`cookie_transport.py:93-95`) |
| 404 / andere Codes | Gewöhnlicher Fehler | kein Transport-Level-Retry; **nie** auf einen Endzustand abgebildet (`cookie_transport.py:108-116`) |

**Backoff-Formel** (`pplx_export/core/throttle.py:38-50`):
`delay_max × 3^N`, wobei `N` die Anzahl aufeinanderfolgender Fehler ist (Exponent bei 8 begrenzt), mit ±20 % Jitter gegen Synchronisation, gedeckelt bei 300 s. Es gibt keinen sinnlosen Schlaf nach dem letzten fehlgeschlagenen Versuch, und `throttle.reset()` setzt den Zähler beim ersten Erfolg zurück (`throttle.py:52`).

Warum jede Regel existiert:

- **429 Backoff** – der Server hat explizit um Verlangsamung gebeten; ehren Sie dies exponentiell.
- **5xx Wiederholung** – ein einzelner Gateway-Aussetzer darf keinen Thread zum Scheitern bringen.
- **401/403 ohne Backoff** – Warten kann ein totes Cookie nicht heilen.
- **`ENTRY_EXPIRED` ohne Wiederholung** – die Plattform-Bereinigung (~3-Monats-Fenster) ist permanent; Wiederholung verbrennt nur Anfragen und Backoff-Budget.
- **404 nie endgültig** – ein von `pplx-ask` erstellter Thread kann direkt nach der Erstellung kurzzeitig 404 liefern (Ausbreitungsverzögerung); eine endgültige Markierung würde einen lebendigen Thread begraben, der nur kurz unsichtbar ist.

<a id="runtime-budget-for-callers" data-pplx-source-anchor="true"></a>
## Laufzeitbudget für Aufrufer

Die obige Backoff-Disziplin tauscht Wanduhrzeit gegen Kontosicherheit, und Aufrufer müssen für diese Zeit budgetieren: Eine einzelne Anfrage macht bis zu 3 Versuche mit einem Backoff-Schlaf dazwischen – bis zu 300 s jeder (`pplx_export/core/throttle.py:38-50`) –, sodass eine Anfrage bei Netzwerkflackern legitimerweise in der Größenordnung von 10 Minuten beanspruchen kann. `index` / `batch` beginnen ebenfalls mit einem Session-Probe, der denselben Regeln folgt (`pplx_export/commands/common.py:126`). Eine lange Stille bedeutet, dass ein Backoff-Wartevorgang läuft, kein Hängen.

Drei Regeln für Agenten, Cron-Jobs und CI-Wrapper:

1. **Ein Konto pro Aufruf.** Führen Sie Konten seriell als separate Prozesse aus; verketten Sie sie niemals mit `&&` innerhalb einer äußeren Aufgabe, die ein hartes Timeout erzwingt – die Backoff-Kaskade des ersten Kontos frisst das gesamte Budget und das verkettete Konto wird nie ausgeführt.
2. **Budget ≥ 15 Minuten, oder trennen.** Geben Sie Wrappern ein großzügiges Timeout, oder führen Sie sie im Hintergrund aus und beobachten Sie das Log (`-v` / `--log-file`), um Backoff-Wartezeiten von echten Hängern zu unterscheiden.
3. **Unterbrechen ist immer sicher.** Der Zustand wird atomar geschrieben; ein erneuter Lauf ist idempotent und repariert jede Lücke, die die Unterbrechung hinterlassen hat (Early-Stop- und Resume-Semantik: [Inkrementelle Synchronisation](incremental-sync.md)).

## Auth-Fail-Fast

Die Batch-Ebene zählt aufeinanderfolgende Authentifizierungsfehler (`_AUTH_FAIL_FAST = 3`, `pplx_export/commands/batch_cmd.py:43`). Jede Antwort, die den Server erreicht hat – einschließlich `ENTRY_DELETED` / `ENTRY_EXPIRED` – beweist, dass das Cookie funktioniert, und setzt den Zähler zurück (`batch_cmd.py:170-182`). Drei aufeinanderfolgende 401/403 und der Lauf speichert seine Zustandsdatei und bricht dann ab (`batch_cmd.py:190-194`): Mit einem toten Cookie weiterzumachen, würde Hunderte von Threads jeweils einmal scheitern lassen – Stunden verschwendet. `sync-deleted` wendet dieselbe Disziplin an (`pplx_export/commands/sync_deleted_cmd.py:111,333-337`). Die Lösung ist, das Cookie zu erneuern und erneut auszuführen; alles bereits Exportierte wird übersprungen.

`batch` und der Transport teilen sich eine `Throttle`-Instanz (`pplx_export/cli.py:280-282`, `batch_cmd.py:101-105`), sodass die Backoff-Zählung niemals zwischen Ebenen aufgeteilt wird – und die gemeinsame Instanz überlebt automatischen Kontowechsel.

<a id="scheduling-periodic-sync" data-pplx-source-anchor="true"></a>
## Planung der periodischen Synchronisation

`pplx-export schedule` berechnet den aktuellen inkrementellen Plan (neue/aktualisierte Zählungen) und schreibt einen Cron-Ausschnitt nach `<out>/index/cron_snippet.txt` (`pplx_export/commands/misc_cmd.py:86-96`, `pplx_export/hooks/scheduler.py:48-77`):

```bash
pplx-export schedule --account alice
```

```cron
17 3 * * * cd '<out-parent>' && '/abs/path/to/pplx-export' batch --account 'alice' --out '<out>'
```

- Periodische Läufe sind **nur inkrementell** (Early Stop) – keine vollständigen Neuladevorgänge (`scheduler.py:4-9`).
- Der Ausschnitt verwendet absolute, in Anführungszeichen gesetzte Pfade, da das Arbeitsverzeichnis von Cron und `PATH` unvorhersehbar sind (`scheduler.py:63-75`).
- Installieren Sie es mit `crontab -e` und passen Sie die Zeit nach Geschmack an; staffeln Sie mehrere Konten auf verschiedene Slots.
- Optionaler Backstop: Fügen Sie einen wöchentlichen oder monatlichen manuellen Durchlauf mit `pplx-export batch --account alice --full` hinzu (siehe [incremental-sync.md](incremental-sync.md)).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Siehe auch

- [incremental-sync.md](incremental-sync.md) – was jeder geplante Lauf tatsächlich exportiert
- [pplx-export.md](pplx-export.md) – `--delay-min` / `--delay-max` und die anderen Befehlsoptionen
- [troubleshooting.md](troubleshooting.md) – was nach einem Auth-Fail-Fast-Abbruch zu tun ist
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) – die vollständige Fehlertaxonomie
- [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) – plattformseitige Fehlersemantik (`ENTRY_EXPIRED`, `ENTRY_DELETED`, Cloudflare)
- [../reference/api/api-authentication.md](../reference/api/api-authentication.md) – Cookies und Multi-Konto-Wechsel
