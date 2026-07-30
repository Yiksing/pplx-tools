---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/troubleshooting.md"
translation_source_sha256: "97f7bccfca0aa4546418bd68903cbd5b905aa5658d496da6ea06413b246bfd88"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="troubleshooting" data-pplx-source-anchor="true"></a>
# Fehlerbehebung

FAQ-Format: jeder Eintrag ist **Problem → Ursache → Lösung**. Die vollständige Referenz zur Fehlersemantik (Statuscodes, Endzustände, Wiederholungsdisziplin) finden Sie unter
[Antworten und Fehler](../reference/api/api-responses-errors.md) und
[Ratenbegrenzung und Fehler](../architecture/rate-limiting-errors.md).

<a id="bare-requests-to-the-api-get-a-cloudflare-403" data-pplx-source-anchor="true"></a>
## Bare Anfragen an die API erhalten einen Cloudflare 403

**Problem**: Ein handgeschriebenes `curl` / Skript gegen `www.perplexity.ai` REST-Endpunkte
liefert 403 mit einer Cloudflare-Challenge-Seite zurück – selbst mit aus dem Browser kopierten Cookies – während dieselben Endpunkte über das Tool funktionieren.

**Ursache**: Cloudflare sitzt vor der Website, und `cf_clearance` / `__cf_bm` sind an den TLS-Fingerabdruck des Browsers gebunden. Der Fingerabdruck eines nackten Clients stimmt nicht überein, daher wird die Challenge ausgelöst. Das Tool besteht, weil es Python `urllib` mit aus dem Browser importierten Cookies und einem Desktop-Chrome `User-Agent` (`pplx_export/core/http/cookie_transport.py:29`) verwendet. Cloudflare kann auch unter Ratenkontrolle 403 liefern – in diesem Fall trägt die Antwort dieselbe Challenge-Form.

**Lösung**:

- Umgehen Sie den Transport des Tools nicht; führen Sie Ihren Aufruf über `pplx-export` / `pplx-ask` aus, anstatt Ad-hoc-Skripte zu verwenden.
- Innerhalb des Tools wird eine 200-Antwort mit einem Nicht-JSON-Textkörper (der Cloudflare-Interstitial) als Transportfehler klassifiziert, nicht als Daten (`pplx_export/core/http/cookie_transport.py:133`).
- Wenn 403s innerhalb des Tools auftauchen, verlangsamen Sie (siehe [Ratenbegrenzung](rate-limiting.md)) und aktualisieren Sie die Cookies; eine anhaltende Challenge bedeutet erneutes Einloggen im Browser.
- Beachten Sie die zwei Gesichter von 403: eine Cloudflare-Risikokontroll-Challenge (verschwindet, wenn Sie langsamer werden) versus einen API-Level-403 (totes Cookie – wird sofort ohne Backoff ausgelöst; siehe nächster Abschnitt). Die Designseite bildet letzteres ab ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

Hintergrund: [API-Authentifizierung](../reference/api/api-authentication.md).

<a id="401-errors-expired-cookies" data-pplx-source-anchor="true"></a>
## 401-Fehler / abgelaufene Cookies

**Problem**: Befehle schlagen mit einem Authentifizierungsfehler fehl – `AuthTransportError: 鉴权失败 401` von `pplx-export`, oder `pplx-ask ask` beendet sich mit einem HTTP-401/403-Hinweis, das Cookie zu aktualisieren.

**Ursache**: Das Sitzungscookie ist abgelaufen oder wurde ungültig gemacht. `401`/`403` werden als Authentifizierungsfehler behandelt und sofort ausgelöst – kein Backoff, weil Backoff eine tote Sitzung nicht selbst heilen kann (`pplx_export/core/http/cookie_transport.py:82`; `pplx_export/core/errors.py:68`). `batch` bricht zusätzlich nach 3 aufeinanderfolgenden Authentifizierungsfehlern schnell ab, damit ein totes Cookie nicht die gesamte Warteschlange verbraucht.

**Lösung**:

1. Loggen Sie sich im Browser erneut ein (oder öffnen Sie die Website erneu), damit die Sitzungscookies erneuert werden.
2. Aktualisieren Sie den Cookie-Cache des Tools. Der Cache unter `<out>/index/.cookies.json` wird innerhalb eines 12-Stunden-Frischefensters wiederverwendet (`pplx_export/core/cookies/cache.py:22`). Führen Sie daher nach dem erneuten Einloggen entweder:
   - einmal mit `--cookies-from <browser>` aus, um einen frischen Browser-Import zu erzwingen, oder
   - löschen Sie `<out>/index/.cookies.json` und lassen Sie den nächsten Lauf automatisch neu importieren.
3. Jeder erfolgreich validierte Lauf speichert den Cache erneut (`pplx_export/commands/common.py:150`), sodass tägliche Läufe von selbst frisch bleiben.

Einrichtungsdetails: [Erste Schritte](getting-started.md) · [Konfiguration](configuration.md).

<a id="linux-cookie-decryption" data-pplx-source-anchor="true"></a>
## Linux-Cookie-Entschlüsselung

**Problem**: Unter Linux kann die automatische Erkennung (oder `--cookies-from chrome` & Co.) den Cookie-Speicher des Browsers nicht lesen, obwohl der Browser eingeloggt ist.

**Mechanismus**: Chromium-Familien-Browser unter Linux verschlüsseln die Cookie-Datenbank mit einem Schlüssel, der im OS-Keyring gespeichert und zur Laufzeit über die Secret Service D-Bus-API gelesen wird. `browser_cookie3` spricht D-Bus über reines Python `jeepney` – bereits mit dem Tool unter Linux installiert, nichts zusätzlich einzurichten – und fällt auf das Legacy-`peanuts`-Passwort zurück, wenn kein Keyring antwortet, was nur Cookies entschlüsselt, die Chrome auch ohne Keyring geschrieben hat. Wenn der Keyring existiert, aber die D-Bus-Suche selbst auf Transportebene fehlschlägt (z. B. eine Sitzungsbus, die anonyme Authentifizierung ablehnt), greift die eigene Fallback-Kette von `browser_cookie3` nie; das Tool erkennt diesen Fall und wiederholt einmal unter Umgehung des Keyrings, wobei es Chromiums Standardpasswort verwendet – denselben Schlüssel, den Chromium selbst verwendet, wenn kein Keyring verfügbar ist (`pplx_export/core/cookies/loaders.py:62-104`, eingebunden in den Ladepfad bei `loaders.py:136-153`). Firefox benötigt nichts davon: seine `cookies.sqlite` ist unverschlüsselt.

**Die Matrix**:

| Ebene | Fall | Was passiert |
|---|---|---|
| Browser | Firefox | Null Reibung – `cookies.sqlite` ist nicht verschlüsselt |
| Browser | Chromium + erreichbarer Keyring | Funktioniert – der Schlüssel wird über Secret Service abgerufen |
| Browser | Chromium + kein Keyring | `peanuts`-Pfad – funktioniert nur, wenn Chrome auch ohne Keyring geschrieben hat |
| Browser | Chromium + Keyring unerreichbar (D-Bus-Ebene-Fehler) | Das Tool wiederholt automatisch mit Chromiums Standardpasswort – gleiche Reichweite wie der `peanuts`-Pfad |
| Installationsmethode | Native Pakete | Automatisch erkannt (browser_cookie3's eingebaute Pfade) |
| Installationsmethode | snap / flatpak | Automatisch erkannt – die eingebaute Profilregistrierung deckt Profile unter `~/snap/<name>/...` bzw. `~/.var/app/<app-id>/...` ab (`pplx_export/core/cookies/profiles.py:37-67`) |
| Desktop-Umgebung | GNOME | Funktioniert normalerweise sofort (gnome-keyring) |
| Desktop-Umgebung | KDE | Aktivieren Sie **Use KWallet for the Secret Service interface** in den KWallet-Einstellungen |
| Desktop-Umgebung | Headless / Minimal | Kein D-Bus-Sitzungsbus → `peanuts`-Pfad |
| Distributionsfamilie | Debian / Ubuntu | Installieren Sie `libsecret-1-0` + `gnome-keyring` |
| Distributionsfamilie | Fedora / RHEL | Installieren Sie `libsecret` + `gnome-keyring`; minimale / Server-Installationen haben oft gar keinen Keyring – der häufigste Fehler |
| Distributionsfamilie | Arch | Gleicher Mechanismus, nur die Paketnamen unterscheiden sich |

Sandbox-Installationen benötigen keine zusätzlichen Flags: der native Pfad wird zuerst geprüft, dann die Snap/Flatpak-Cookie-Datenbanken der Registrierung über ein explizites `cookie_file=` (`pplx_export/core/cookies/loaders.py:155-168`).

**Szenario → empfohlener Kanal**:

| Szenario | Empfohlener Kanal |
|---|---|
| Firefox installiert | `--cookies-from firefox` – null Reibung |
| Desktop GNOME / KDE | Automatische Erkennung funktioniert einfach |
| snap / flatpak Browser | Automatische Erkennung – die Registrierung deckt es ab; andernfalls `--cookies FILE` über eine Browser-Erweiterung exportiert |
| Headless-Server | `--cookies FILE` – der universelle Fallback; `--transport webbridge` als letzte Option |

<a id="an-export-ran-under-the-wrong-account-multi-account" data-pplx-source-anchor="true"></a>
## Ein Export lief unter dem falschen Konto (Multi-Konto)

**Problem**: Archivierte Threads wurden mit der Sitzung des falschen Kontos abgerufen – z. B. ein `--account alice`-Lauf zog Daten als `bob`, oder das Archiv zeigt Threads, die nicht zum beabsichtigten Konto gehören.

**Ursache**: Wenn mehrere Konten im selben Browser eingeloggt sind, kann das aktive Sitzungstoken (`__Secure-next-auth.session-token`) zu einem anderen Konto gehören als dem, das Sie anvisiert haben. Wenn die `email` des Zielkontos nicht in der Benutzerkonfiguration registriert ist, kann das Tool dies nicht erkennen und protokolliert nur eine Warnung.

**Wie das Tool es verhindert** (`pplx_export/commands/common.py:93`): Beim Start ruft der Transport `GET /api/auth/session` auf und vergleicht die Live-E-Mail mit der registrierten. Bei Nichtübereinstimmung zählt es automatisch die pro-Konto-Sitzungscookies des Browsers auf (`__Secure-pplx.session.<user_id>`), setzt jedes in das aktive Token ein und prüft die Sitzung, bis die Ziel-E-Mail übereinstimmt (`pplx_export/commands/common.py:190`; `pplx_export/core/cookies/loaders.py:175`). Wenn kein Token übereinstimmt, bricht der Befehl mit einem klaren Fehler ab – er fährt nie stillschweigend mit dem falschen Konto fort.

**Lösung**:

- Registrieren Sie die `email` jedes Kontos unter `[accounts.<name>]` (siehe [Konfiguration](configuration.md)) und übergeben Sie `--account` explizit.
- Überprüfen Sie die Startprotokollzeile `[auth] cookie 来源 …，当前账户: …` – sie nennt die Live-Sitzungs-E-Mail, bevor etwas abgerufen wird.
- Um ein vorhandenes Archiv zu prüfen, trägt die `thread.json` jedes Threads ein `export_via`-Feld, das aufzeichnet, welches Konto den Export durchgeführt hat (`pplx_export/sites/perplexity/fs_writer.py:229`). `pplx-export sync-deleted` verwendet dasselbe Feld, um das Konto für die Online-Überprüfung auszuwählen.

Mechanismus-Tiefe: [API-Authentifizierung](../reference/api/api-authentication.md) · [Fragen und Konten](../architecture/ask-and-accounts.md).

<a id="config-file-not-found-degraded-mode" data-pplx-source-anchor="true"></a>
## "Config file not found" – abgesenkter Modus

**Problem**: Eine Startwarnung sagt, dass keine Benutzerkonfigurationsdatei gefunden wurde, und der Befehl läuft im abgesenkten Modus; oder ein explizites `--account alice` schlägt mit einem Fehler fehl, der auf `config.example.toml` verweist.

**Ursache**: Keine Konfigurationsdatei an einem der drei Suchorte – `--config PATH`, die Umgebungsvariable `PPLX_EXPORT_CONFIG` oder der Standardpfad `~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). Zwei verwandte, aber unterschiedliche Fälle: Ein **explizit angegebener** Konfigurationspfad, der nicht existiert, löst `ConfigError` aus; eine beschädigte (nicht parsbare) Konfiguration löst immer `ConfigError` aus – eine defekte Konfiguration führt nie stillschweigend zu einer Degradierung.

**Auswirkungen des abgesenkten Modus**:

- Die Kontoregistrierung ist leer, daher wird die Cookie-Besitzüberprüfung mit einer Warnung übersprungen, und Befehle laufen als Platzhalterkonto `default` (`pplx_export/commands/common.py:51`). Ein explizites `--account` führt stattdessen zu einem Fehler.
- `pplx-ask ask` überspringt die automatische Verschiebung in den BOT-Bereich (`moved_to_bot` bleibt `false` im Ergebnis-JSON) und die Telemetrie trägt eine leere Benutzer-ID; Fragen und Archivieren funktionieren ansonsten.
- Archive landen im Fallback-Kontoordner, der aus dem Benutzernamen abgeleitet wird.

**Lösung**: Kopieren Sie `config.example.toml` nach `~/.config/pplx-export/config.toml`, füllen Sie `[accounts.<name>]` (`display_name` / `email` / `user_id`), `[bot_space]` und `default_account` aus – siehe [Konfiguration](configuration.md).

## ENTRY_EXPIRED vs ENTRY_DELETED

**Problem**: Beim Exportieren oder erneuten Synchronisieren eines Threads wird `ENTRY_EXPIRED` oder `ENTRY_DELETED` gemeldet, und der Thread kann nie wieder abgerufen werden.

**Ursache**: Beide treten als HTTP 400 von `GET /rest/thread/<uuid>` mit unterschiedlichen Fehlercodes auf, und beide sind endgültig – der Thread existiert nicht mehr auf der Plattform:

| Code | Bedeutung | Tool-Zuordnung | Endzustand |
|---|---|---|---|
| `ENTRY_EXPIRED` | Die Plattform hat den Thread gelöscht (~3 Monate Aufbewahrung) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | Der Thread wurde aktiv vom Benutzer / der entfernten Seite gelöscht (der nachgelagerte Effekt von `DELETE /rest/thread/delete_thread_by_entry_uuid`) | `EntryDeletedError`, eine Unterklasse von `EntryExpiredError` (`pplx_export/core/errors.py:30`) | `deleted` |

**Was es für Ihr Archiv bedeutet**:

- Keiner der Zustände wird jemals wiederholt – nicht durch inkrementelle Synchronisation, nicht mit `--force`. Die Endmarkierung lebt in `<out>/index/batch_state.json`.
- Ihr **lokales Archiv wird vom Tool nie gelöscht oder verschoben** – die Repository-Kopie ist das Backup. Der Exportbefehl registriert den Endzustand und beendet sich ordnungsgemäß (`pplx_export/commands/export_cmd.py:51`).
- Da die Unterklassenbeziehung beabsichtigt ist, behandeln Codepfade, die nur `EntryExpiredError` kennen, `ENTRY_DELETED` immer noch als endgültig; bewusste Pfade (Batch / Export / Sync-Gelöscht / Suchmodus-Backfill) klassifizieren es präzise als `deleted`.
- Praktische Konsequenz: Exportieren Sie rechtzeitig. Nach der ~3-Monats-Bereinigung verfallen auch Quelllinks von Artefakten/Berichten unwiederbringlich.

Verwandt: [Inkrementelle Synchronisation](incremental-sync.md) · [Antworten und Fehler](../reference/api/api-responses-errors.md).

<a id="assets-that-cannot-be-downloaded-toolu_-handles" data-pplx-source-anchor="true"></a>
## Assets, die nicht heruntergeladen werden können (`toolu_`-Handles)

**Problem**: Einige Einträge in `assets/assets_manifest.json` haben Versionen, die als `"no_download_channel": true` gekennzeichnet sind, und es existiert keine entsprechende Datei unter `assets/files/`.

**Ursache**: `toolu_`-präfixierte Cloud-Workspace-Handles (DOC_FILE / CODE_FILE / UNKNOWN ohne URL-Form) haben keinen API-Download-Kanal: `GET /rest/assets/<asset_uuid>/data` gibt 404 `ASSET_NOT_FOUND` für sie zurück, und `file-repository/download` lehnt `file:repo/...`-Handles ab (400). Dies ist eine **bekannte Archiv-Vollständigkeitsgrenze**, kein Fehler im Export. `pplx-export assets-backfill` markiert diese Versionen als `no_download_channel` und überspringt sie (`pplx_export/commands/assets_backfill_cmd.py:356`).

**Lösung**:

- Heute gibt es nichts herunterzuladen – die Markierung ist der bewusste Nachweis der Grenze.
- Der Inhalt bleibt oft inline erhalten: Subagent-Seitenextraktionstext und Schritt-Nutzlasten sind im rohen JSON des Threads (`raw_entries.json` / `raw_blocks.json`) und im gerenderten `turns/` erhalten – prüfen Sie dort zuerst.
- `file-repository/list-files` wird als potenzieller zukünftiger Rettungspfad verfolgt; siehe [API-Entdeckungs-Roadmap](../reference/api/api-discovery-roadmap.md).

Manifest-Layout: [Archiv-Layout](archive-layout.md).

<a id="command-seems-hung-long-silences" data-pplx-source-anchor="true"></a>
## Befehl scheint hängen geblieben / lange Stille

**Symptom**: `index` / `batch` / `export` scheint zu stocken; ein externer Task-Manager könnte es als "zeitüberschritten" beenden.

**Ursache**: Fast immer ein Backoff oder eine Wartezeit auf eine laufende Anfrage, kein Hängen. Bei 429 / 5xx / Netzwerkfehlern schläft der Transport zwischen den Versuchen – bis zu 300 s pro Wartezeit (`pplx_export/core/throttle.py`, `Throttle.backoff`).

**Was Sie jetzt sehen (Standard-Ausführlichkeit, kein `-v` erforderlich)**: Die Wartezeit wird durch INFO-Herzschläge sichtbar gemacht. Ein Backoff gibt eine vorausgehende Zeile und dann alle ~10 s einen Countdown-Tick aus (`Throttle.heartbeat_interval`); eine einzelne Anfrage, die vor der Antwort ins Stocken gerät, gibt einen "still waiting for response"-Tick aus; und `pplx-ask`-Streams geben einen "still waiting for the response stream"-Tick aus, während eine Deep-Research / Council-Ausführung still ist:

```
22:27:24 [auth] 正在校验账户 cookie（来源 cache）…
22:27:40 退避 ~51s（连续失败 1 次，网络异常重试中）
22:27:50 仍在等待重试，剩余 ~41s
22:28:00 仍在等待重试，剩余 ~31s
```

Die Gesamtwartezeit bleibt unverändert – Herzschläge machen sie nur sichtbar; ein Unterbrechen ist jederzeit sicher (der Zustand wird atomar geschrieben und der nächste Lauf repariert die Lücke). `-v` / `--log-file` fügen weiterhin die vollständige DEBUG-Anfrageverfolgung hinzu.

**Startprobe überspringen**: `index` / `batch` beginnen mit einer Sitzungsprobe, die denselben Backoff-Regeln folgt, sodass bei einem schlechten Netzwerk die allererste Wartezeit dieser Kontovalidierungsschritt sein kann. Übergeben Sie `--skip-auth-check`, um ihn zu überspringen und direkt zur Arbeit zu gehen, wobei Sie dem aktuell eingeloggten Konto vertrauen – siehe [Konfiguration](configuration.md).

**Anti-Pattern**: Das CLI in einen Task-Manager mit kurzem hartem Timeout einwickeln (Agent-Hintergrundaufgaben, `timeout(1)`-artige Cron-Wrapper) *während* Konten mit `&&` verkettet werden – die Backoff-Kaskade des ersten Kontos verbraucht das gesamte Timeout und das verkettete Konto wird nie ausgeführt. Ein Konto pro Aufruf, großzügiges Budget: siehe [Laufzeitbudget für Aufrufer](rate-limiting.md#runtime-budget-for-callers).

<a id="where-are-the-logs" data-pplx-source-anchor="true"></a>
## Wo sind die Protokolle?

**Konsole**: Standardmäßig INFO-Level-Fortschritt; `-v` / `--verbose` wechselt zu DEBUG (Anfrageverfolgung, interne Entscheidungen); Warnungen und Fehler werden immer angezeigt.

**Datei**: Übergeben Sie `--log-file`, um den vollständigen DEBUG-Stream zu erfassen (`pplx_export/core/logging.py:45`):

- `--log-file` ohne Wert landet unter `<out>/index/logs/<cmd>-<timestamp>.log` (`pplx_export/commands/common.py:218`) – z. B. `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH` schreibt in den angegebenen Pfad.

**Andere Zustandsdateien, die für die Diagnose nützlich sind** (unter `<out>/index/`):

| Datei | Inhalt |
|---|---|
| `.cookies.json` | Cookie-Cache (12 h Frische; atomar mit 0o600 geschrieben – es ist ein login-äquivalentes Credential, halten Sie es privat) |
| `batch_state.json` | Pro-Thread-Exportzustand, einschließlich der Endmarkierungen `expired` / `deleted` |
| `answer_variants_log.jsonl` | Antwort-Umschreibungs-Varianten-Registrierung |
| `library_*.json` | Pro-Konto-Bibliotheksindex-Snapshots |

<a id="see-also" data-pplx-source-anchor="true"></a>
## Siehe auch

- [Erste Schritte](getting-started.md) – Ersteinrichtung und Cookie-Import
- [Konfiguration](configuration.md) – Konten, BOT-Bereich, abgesenkter Modus
- [pplx-ask](pplx-ask.md) – das interaktive Abfrage-CLI
- [pplx-export](pplx-export.md) – das Archivierungs-CLI
- [Ratenbegrenzung](rate-limiting.md) – Taktung und Backoff-Disziplin
