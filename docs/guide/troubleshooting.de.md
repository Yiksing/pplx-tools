---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/troubleshooting.md"
translation_source_sha256: "99dee1bd48f525fcf72fcfd09992043114e918fd4ce2870f0586fc2937c70d62"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="troubleshooting" data-pplx-source-anchor="true"></a>
# Fehlerbehebung

FAQ-Format: jeder Eintrag ist **Problem → Ursache → Lösung**. Die vollständige Referenz zur Fehlersemantik (Statuscodes, Endzustände, Wiederholungsdisziplin) finden Sie unter [Responses and errors](../reference/api/api-responses-errors.md) und [Rate limiting and errors](../architecture/rate-limiting-errors.md).

<a id="bare-requests-to-the-api-get-a-cloudflare-403" data-pplx-source-anchor="true"></a>
## Bare Anfragen an die API erhalten einen Cloudflare 403

**Problem**: Ein handgeschriebenes `curl` / Skript gegen `www.perplexity.ai` REST-Endpunkte gibt 403 mit einer Cloudflare-Challenge-Seite zurück – selbst mit aus dem Browser kopierten Cookies –, während dieselben Endpunkte über das Tool funktionieren.

**Ursache**: Cloudflare sitzt vor der Website, und `cf_clearance` / `__cf_bm` sind an den TLS-Fingerabdruck des Browsers gebunden. Der Fingerabdruck eines nackten Clients stimmt nicht überein, daher wird die Challenge ausgelöst. Das Tool funktioniert, weil es Python `urllib` mit aus dem Browser importierten Cookies und einem Desktop-Chrome `User-Agent` (`pplx_export/core/http/cookie_transport.py:29`) verwendet. Cloudflare kann auch unter Ratenkontrolle 403 zurückgeben – in diesem Fall trägt die Antwort dieselbe Challenge-Form.

**Lösung**:

- Umgehen Sie nicht den Transport des Tools; führen Sie Ihren Aufruf stattdessen über `pplx-export` / `pplx-ask` aus, anstatt Ad-hoc-Skripte zu verwenden.
- Innerhalb des Tools wird eine 200-Antwort mit einem Nicht-JSON-Textkörper (der Cloudflare-Interstitial) als Transportfehler klassifiziert, nicht als Daten (`pplx_export/core/http/cookie_transport.py:133`).
- Wenn 403s innerhalb des Tools auftreten, verlangsamen Sie (siehe [Rate limiting](rate-limiting.md)) und aktualisieren Sie die Cookies; eine anhaltende Challenge bedeutet erneutes Einloggen im Browser.
- Beachten Sie die zwei Gesichter von 403: eine Cloudflare-Risikokontroll-Challenge (verschwindet, wenn Sie langsamer machen) gegenüber einem API-Level 403 (totes Cookie – wird sofort ohne Backoff ausgelöst; siehe nächster Abschnitt). Die Designseite bildet letzteres ab ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

Hintergrund: [API authentication](../reference/api/api-authentication.md).

<a id="401-errors-expired-cookies" data-pplx-source-anchor="true"></a>
## 401-Fehler / abgelaufene Cookies

**Problem**: Befehle schlagen mit einem Authentifizierungsfehler fehl – `AuthTransportError: 鉴权失败 401` von `pplx-export`, oder `pplx-ask ask` beendet sich mit einem HTTP 401/403-Hinweis, das Cookie zu aktualisieren.

**Ursache**: Das Sitzungscookie ist abgelaufen oder wurde ungültig gemacht. `401`/`403` werden als Authentifizierungsfehler behandelt und sofort ausgelöst – kein Backoff, da Backoff eine tote Sitzung nicht selbst heilen kann (`pplx_export/core/http/cookie_transport.py:82`; `pplx_export/core/errors.py:68`). `batch` bricht zusätzlich nach 3 aufeinanderfolgenden Authentifizierungsfehlern schnell ab, damit ein totes Cookie nicht die Warteschlange durchbrennt.

**Lösung**:

1. Loggen Sie sich im Browser erneut ein (oder öffnen Sie die Website erneut), damit die Sitzungscookies erneuert werden.
2. Aktualisieren Sie den Cookie-Cache des Tools. Der Cache unter `<out>/index/.cookies.json` wird innerhalb eines 12-Stunden-Frischefensters wiederverwendet (`pplx_export/core/cookies/cache.py:22`). Führen Sie nach dem erneuten Einloggen entweder:
   - einmalig `--cookies-from <browser>` aus, um einen frischen Browser-Import zu erzwingen, oder
   - löschen Sie `<out>/index/.cookies.json` und lassen Sie den nächsten Lauf automatisch neu importieren.
3. Jeder erfolgreich validierte Lauf speichert den Cache erneut (`pplx_export/commands/common.py:150`), sodass alltägliche Läufe von selbst frisch bleiben.

Einrichtungsdetails: [Getting started](getting-started.md) · [Configuration](configuration.md).

<a id="linux-cookie-decryption" data-pplx-source-anchor="true"></a>
## Linux-Cookie-Entschlüsselung

**Problem**: Unter Linux kann die automatische Erkennung (oder `--cookies-from chrome` & Co.) den Cookie-Speicher des Browsers nicht lesen, obwohl der Browser eingeloggt ist.

**Mechanismus**: Chromium-Familien-Browser unter Linux verschlüsseln die Cookie-Datenbank mit einem Schlüssel, der im OS-Keyring gespeichert und zur Laufzeit über die Secret Service D-Bus-API gelesen wird. `browser_cookie3` kommuniziert mit D-Bus über reines Python `jeepney` – bereits mit dem Tool unter Linux installiert, nichts zusätzlich einzurichten – und fällt auf das Legacy-`peanuts`-Passwort zurück, wenn kein Keyring antwortet, was nur Cookies entschlüsselt, die Chrome auch ohne Keyring geschrieben hat. Firefox benötigt nichts davon: sein `cookies.sqlite` ist unverschlüsselt.

**Die Matrix**:

| Ebene | Fall | Was passiert |
|---|---|---|
| Browser | Firefox | Null Reibung – `cookies.sqlite` ist nicht verschlüsselt |
| Browser | Chromium + erreichbarer Keyring | Funktioniert – der Schlüssel wird über Secret Service abgerufen |
| Browser | Chromium + kein Keyring | `peanuts`-Pfad – funktioniert nur, wenn Chrome auch ohne Keyring geschrieben hat |
| Installationsmethode | Native Pakete | Automatisch erkannt (browser_cookie3's eingebaute Pfade) |
| Installationsmethode | snap / flatpak | Automatisch erkannt – die eingebaute Profilregistrierung deckt Profile unter `~/snap/<name>/...` bzw. `~/.var/app/<app-id>/...` ab (`pplx_export/core/cookies/profiles.py:37-67`) |
| Desktop-Umgebung | GNOME | Funktioniert normalerweise sofort (gnome-keyring) |
| Desktop-Umgebung | KDE | Aktivieren Sie **Use KWallet for the Secret Service interface** in den KWallet-Einstellungen |
| Desktop-Umgebung | Headless / Minimal | Kein D-Bus Session Bus → `peanuts`-Pfad |
| Distro-Familie | Debian / Ubuntu | Installieren Sie `libsecret-1-0` + `gnome-keyring` |
| Distro-Familie | Fedora / RHEL | Installieren Sie `libsecret` + `gnome-keyring`; minimale / Server-Installationen haben oft gar keinen Keyring – der häufigste Fehler |
| Distro-Familie | Arch | Gleicher Mechanismus, nur die Paketnamen unterscheiden sich |

Sandbox-Installationen benötigen keine zusätzlichen Flags: der native Pfad wird zuerst geprüft, dann die snap/flatpak-Cookie-Datenbanken der Registrierung über ein explizites `cookie_file=` (`pplx_export/core/cookies/loaders.py:89-101`).

**Szenario → empfohlener Kanal**:

| Szenario | Empfohlener Kanal |
|---|---|
| Firefox installiert | `--cookies-from firefox` – null Reibung |
| Desktop GNOME / KDE | Automatische Erkennung funktioniert einfach |
| snap / flatpak Browser | Automatische Erkennung – die Registrierung deckt es ab; andernfalls `--cookies FILE` über eine Browser-Erweiterung exportiert |
| Headless-Server | `--cookies FILE` – der universelle Fallback; `--transport webbridge` als letzte Möglichkeit |

<a id="an-export-ran-under-the-wrong-account-multi-account" data-pplx-source-anchor="true"></a>
## Ein Export lief unter dem falschen Konto (Multi-Konto)

**Problem**: Archivierte Threads wurden mit der Sitzung des falschen Kontos abgerufen – z. B. ein `--account alice`-Lauf zog Daten als `bob`, oder das Archiv zeigt Threads, die nicht zum beabsichtigten Konto gehören.

**Ursache**: Wenn mehrere Konten im selben Browser eingeloggt sind, kann das aktive Sitzungstoken (`__Secure-next-auth.session-token`) zu einem anderen Konto gehören als dem, das Sie anvisiert haben. Wenn das `email` des Zielkontos nicht in der Benutzerkonfiguration registriert ist, kann das Tool dies nicht erkennen und protokolliert nur eine Warnung.

**Wie das Tool es verhindert** (`pplx_export/commands/common.py:93`): Beim Start ruft der Transport `GET /api/auth/session` auf und vergleicht die Live-E-Mail mit der registrierten. Bei Nichtübereinstimmung zählt es automatisch die pro-Konto-Sitzungscookies des Browsers auf (`__Secure-pplx.session.<user_id>`), setzt jedes in das aktive Token ein und testet die Sitzung, bis die Ziel-E-Mail übereinstimmt (`pplx_export/commands/common.py:190`; `pplx_export/core/cookies/loaders.py:108`). Wenn kein Token übereinstimmt, bricht der Befehl mit einer klaren Fehlermeldung ab – er fährt niemals stillschweigend mit dem falschen Konto fort.

**Lösung**:

- Registrieren Sie jedes `email` des Kontos unter `[accounts.<name>]` (siehe [Configuration](configuration.md)) und übergeben Sie `--account` explizit.
- Überprüfen Sie die Startprotokollzeile `[auth] cookie 来源 …，当前账户: …` – sie nennt die Live-Sitzungs-E-Mail, bevor etwas abgerufen wird.
- Um ein vorhandenes Archiv zu prüfen, trägt jedes `thread.json` des Threads ein `export_via`-Feld, das aufzeichnet, welches Konto den Export durchgeführt hat (`pplx_export/sites/perplexity/fs_writer.py:229`). `pplx-export sync-deleted` verwendet dasselbe Feld, um das Konto für die Online-Überprüfung auszuwählen.

Mechanismus-Tiefe: [API authentication](../reference/api/api-authentication.md) · [Ask and accounts](../architecture/ask-and-accounts.md).

<a id="config-file-not-found-degraded-mode" data-pplx-source-anchor="true"></a>
## „Config file not found“ – abgesenkter Modus

**Problem**: Eine Startwarnung sagt, dass keine Benutzerkonfigurationsdatei gefunden wurde, und der Befehl läuft im abgesenkten Modus; oder ein explizites `--account alice` schlägt mit einem Fehler fehl, der auf `config.example.toml` verweist.

**Ursache**: Keine Konfigurationsdatei an einem der drei Suchorte – `--config PATH`, die Umgebungsvariable `PPLX_EXPORT_CONFIG` oder der Standardpfad `~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). Zwei verwandte, aber unterschiedliche Fälle: Ein **explizit angegebener** Konfigurationspfad, der nicht existiert, löst `ConfigError` aus; eine beschädigte (nicht parsbare) Konfiguration löst immer `ConfigError` aus – eine defekte Konfiguration führt niemals stillschweigend zu einer Degradierung.

**Auswirkungen des abgesenkten Modus**:

- Die Kontoregistrierung ist leer, daher wird die Cookie-Eigentumsüberprüfung mit einer Warnung übersprungen, und Befehle laufen als Platzhalterkonto `default` (`pplx_export/commands/common.py:51`). Ein explizites `--account` führt stattdessen zu einem Fehler.
- `pplx-ask ask` überspringt die automatische Verschiebung in den BOT-Bereich (`moved_to_bot` bleibt `false` im Ergebnis-JSON) und die Telemetrie trägt eine leere Benutzer-ID; Fragen und Archivieren funktionieren ansonsten.
- Archive landen im Fallback-Kontoordner, der aus dem Benutzernamen abgeleitet wird.

**Lösung**: Kopieren Sie `config.example.toml` nach `~/.config/pplx-export/config.toml`, füllen Sie `[accounts.<name>]` (`display_name` / `email` / `user_id`), `[bot_space]` und `default_account` aus – siehe [Configuration](configuration.md).

## ENTRY_EXPIRED vs ENTRY_DELETED

**Problem**: Beim Exportieren oder erneuten Synchronisieren eines Threads wird `ENTRY_EXPIRED` oder `ENTRY_DELETED` gemeldet, und der Thread kann nie wieder abgerufen werden.

**Ursache**: Beide kommen als HTTP 400 von `GET /rest/thread/<uuid>` mit unterschiedlichen Fehlercodes, und beide sind endgültig – der Thread existiert nicht mehr auf der Plattform:

| Code | Bedeutung | Tool-Zuordnung | Endzustand |
|---|---|---|---|
| `ENTRY_EXPIRED` | Die Plattform hat den Thread gelöscht (~3 Monate Aufbewahrung) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | Der Thread wurde aktiv vom Benutzer / der entfernten Seite gelöscht (der nachgelagerte Effekt von `DELETE /rest/thread/delete_thread_by_entry_uuid`) | `EntryDeletedError`, eine Unterklasse von `EntryExpiredError` (`pplx_export/core/errors.py:30`) | `deleted` |

**Was es für Ihr Archiv bedeutet**:

- Keiner der Zustände wird jemals wiederholt – nicht durch inkrementelle Synchronisation, nicht mit `--force`. Die Endmarkierung lebt in `<out>/index/batch_state.json`.
- Ihr **lokales Archiv wird vom Tool nie gelöscht oder verschoben** – die Repository-Kopie ist das Backup. Der Exportbefehl registriert den Endzustand und beendet sich ordnungsgemäß (`pplx_export/commands/export_cmd.py:51`).
- Da die Unterklassenbeziehung bewusst ist, behandeln Codepfade, die nur `EntryExpiredError` kennen, `ENTRY_DELETED` dennoch als endgültig; bewusste Pfade (Batch / Export / Sync-deleted / Search-mode-backfill) klassifizieren es präzise als `deleted`.
- Praktische Konsequenz: Exportieren Sie rechtzeitig. Nach der ~3-Monats-Löschung verfallen auch Artefakt-/Berichtsquelllinks unwiederbringlich.

Verwandt: [Incremental sync](incremental-sync.md) · [Responses and errors](../reference/api/api-responses-errors.md).

<a id="assets-that-cannot-be-downloaded-toolu_-handles" data-pplx-source-anchor="true"></a>
## Assets, die nicht heruntergeladen werden können (`toolu_`-Handles)

**Problem**: Einige Einträge in `assets/assets_manifest.json` haben Versionen, die als `"no_download_channel": true` gekennzeichnet sind, und es existiert keine entsprechende Datei unter `assets/files/`.

**Ursache**: `toolu_`-präfixierte Cloud-Workspace-Handles (DOC_FILE / CODE_FILE / UNKNOWN ohne URL-Form) haben keinen API-Download-Kanal: `GET /rest/assets/<asset_uuid>/data` gibt 404 `ASSET_NOT_FOUND` für sie zurück, und `file-repository/download` lehnt `file:repo/...`-Handles ab (400). Dies ist eine **bekannte Archiv-Vollständigkeitsgrenze**, kein Fehler im Export. `pplx-export assets-backfill` markiert diese Versionen als `no_download_channel` und überspringt sie (`pplx_export/commands/assets_backfill_cmd.py:356`).

**Lösung**:

- Heute gibt es nichts herunterzuladen – das Flag ist der bewusste Nachweis der Grenze.
- Der Inhalt überlebt oft inline: Subagent-Seitenextraktionstexte und Schritt-Payloads sind im rohen JSON des Threads (`raw_entries.json` / `raw_blocks.json`) und im gerenderten `turns/` erhalten – prüfen Sie dort zuerst.
- `file-repository/list-files` wird als potenzieller zukünftiger Rettungspfad verfolgt; siehe [API discovery roadmap](../reference/api/api-discovery-roadmap.md).

Manifest-Layout: [Archive layout](archive-layout.md).

<a id="where-are-the-logs" data-pplx-source-anchor="true"></a>
## Wo sind die Protokolle?

**Konsole**: INFO-Level-Fortschritt standardmäßig; `-v` / `--verbose` wechselt zu DEBUG (Anfrageverfolgung, interne Entscheidungen); Warnungen und Fehler werden immer angezeigt.

**Datei**: Übergeben Sie `--log-file`, um den vollständigen DEBUG-Stream zu erfassen (`pplx_export/core/logging.py:45`):

- `--log-file` ohne Wert landet unter `<out>/index/logs/<cmd>-<timestamp>.log` (`pplx_export/commands/common.py:218`) – z. B. `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH` schreibt in den angegebenen Pfad.

**Andere Zustandsdateien, die für die Diagnose nützlich sind** (unter `<out>/index/`):

| Datei | Inhalt |
|---|---|
| `.cookies.json` | Cookie-Cache (12 h Frische; atomar mit 0o600 geschrieben – es ist eine anmeldeäquivalente Anmeldeinformation, halten Sie sie privat) |
| `batch_state.json` | Pro-Thread-Exportzustand, einschließlich der Endmarkierungen `expired` / `deleted` |
| `answer_variants_log.jsonl` | Antwort-Umschreibungs-Varianten-Registrierung |
| `library_*.json` | Pro-Konto-Bibliotheksindex-Snapshots |

<a id="see-also" data-pplx-source-anchor="true"></a>
## Siehe auch

- [Getting started](getting-started.md) – Ersteinrichtung und Cookie-Import
- [Configuration](configuration.md) – Konten, BOT-Bereich, abgesenkter Modus
- [pplx-ask](pplx-ask.md) – die interaktive Abfrage-CLI
- [pplx-export](pplx-export.md) – die Archivierungs-CLI
- [Rate limiting](rate-limiting.md) – Taktung und Backoff-Disziplin
