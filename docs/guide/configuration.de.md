---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "0c5f1be9b103913deee332caa4397a3dc356027148beac491834f6791f3b73db"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="configuration" data-pplx-source-anchor="true"></a>
# Konfiguration

pplx-export speichert Ihre Identitätsdaten – das Kontoregister (Anzeigenamen, Login-E-Mails, Benutzer-IDs) und den BOT-Space – in einer benutzerspezifischen TOML-Datei, die sich außerhalb des Repositorys befindet. Diese Seite behandelt, wo diese Datei liegt, jedes Feld, das sie akzeptiert, was passiert, wenn sie fehlt, und wie das Register die Multi-Account-Cookie-Verwaltung steuert.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## Warum die Konfiguration außerhalb des Repositorys liegt

Das Kontoregister und der BOT-Space sind persönliche Daten und werden **niemals** in das Repository übertragen (`pplx_export/config.py:7-12`). Das Repository enthält nur eine Platzhaltervorlage, `config.example.toml`; Ihre tatsächlichen Werte gehen in eine private Kopie. Alles andere, was das Tool benötigt – die Site-Domain, API-URLs, das Standard-Archiv-Root – ist eine Code-Konstante (`pplx_export/config.py:50-58`), keine Benutzerkonfiguration.

Die TOML enthält nur Identitätsdaten. Die Cookie-Quelle und die Transportauswahl sind pro Aufruf über CLI-Flags festgelegt, keine Konfigurationsfelder – siehe [CLI-Flags, keine Konfigurationsfelder](#cli-flags-not-config-fields) unten.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## Speicherort und Ladepriorität

`configure()` (`pplx_export/config.py:113`) ermittelt den Konfigurationspfad mit dieser Priorität (`pplx_export/config.py:95-110`):

| Priorität | Quelle | Zählt als explizit |
|---|---|---|
| 1 | `--config PATH` CLI-Flag | ja |
| 2 | `PPLX_EXPORT_CONFIG` Umgebungsvariable | ja |
| 3 | `~/.config/pplx-export/config.toml` (Standardpfad) | nein |

„Explizit“ ist wichtig für das Fehlerverhalten, wenn die Datei fehlt – siehe [Degradierter Modus](#missing-config-degraded-mode). Beide CLI-Einträge laden die Konfiguration nach der Argumentanalyse im strikten Modus neu (`pplx_export/cli.py:223`, `pplx_export/ask_cli.py:278`); das Laden zum Importzeitpunkt (`pplx_export/config.py:174-179`) ist fehlertolerant, sodass das Importieren des Pakets niemals aufgrund einer fehlenden Datei fehlschlägt.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## Erstellen Ihrer Konfiguration

!!! tip "Automatische Alternative"
    `pplx-export init` kann diese Datei automatisch generieren – es erkennt die angemeldeten Konten aus Ihren Browser-Cookies und schreibt die TOML mit Berechtigungen 0600. Siehe [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

Bearbeiten Sie dann die Kopie. Die Vorlage verwendet reine Platzhalter – kopieren Sie die Struktur, ersetzen Sie jeden Wert:

```toml
# Default account used when --account is not given (a key of [accounts.<name>] below)
default_account = "alice"

# Account registry: key = account username (the username in thread URLs / library)
[accounts.alice]
# Full display name: used for archive directory naming (web_archive/<display name>/…)
display_name = "Alice Example"
# Login email: verifies cookie ownership
email = "alice@example.com"
# Account uid (required for thread-viewed telemetry)
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT space: where threads created by pplx-ask are collected after completion
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

Platzhalter-Stil: `alice`/`bob` sind erfundene Kontobenutzernamen, E-Mails verwenden `example.com` und UUIDs verwenden die Nullform `00000000-0000-4000-8000-…`. In Ihrer echten Datei **muss** der Tabellenschlüssel der tatsächliche Kontobenutzername sein, wie er in Thread-URLs und Ihrer Bibliothek erscheint.

!!! warning "Privat halten"
    Die echte Konfiguration enthält persönliche Daten (E-Mails, Benutzer-IDs). Empfohlene Berechtigung ist `0o600`; übertragen Sie sie niemals in ein Git-Repository (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## Feldreferenz

<a id="top-level" data-pplx-source-anchor="true"></a>
### Oberste Ebene

| Feld | Typ | Bedeutung |
|---|---|---|
| `default_account` | string | Schlüssel einer `[accounts.<name>]`-Tabelle, verwendet wenn `--account` nicht angegeben ist (`pplx_export/commands/common.py:84-85`). Leer/fehlend = degradierter Modus. |
| `archive_root` | string | Optional. Ausgabe-Root des Archivs, das als `--out`-Fallback verwendet wird, sodass tägliche Befehle `--out` weglassen können. Priorität: `--out` > `archive_root` > `./web_archive` (`pplx_export/config.py`, geladen in `ARCHIVE_ROOT`; aufgelöst in `cli.py` / `ask_cli.py`). `~` wird expandiert. |
| `[models]` (Tabelle) | table | **Automatisch verwaltet, nicht manuell erstellt.** Aktualisierbarer Modellkatalog, geschrieben von `pplx-ask models --refresh` und initialisiert von `pplx-export init`; überschreibt die festgelegte Basislinie in `pplx_export/sites/perplexity/platform.py`. Schlüssel: `last_refreshed` (UTC), `source_version`, `auto_refresh` (bool), `mode_defaults`, `council_defaults`, `search_models` und eine vollständige `[models.catalog]` (`id → {label, provider, mode}`). Anfragen lesen daraus (mit der `platform.py`-Basislinie als Fallback); eine TTL von 7 Tagen gibt eine Aktualisierungserinnerung aus oder aktualisiert automatisch, wenn `auto_refresh = true`. Der Round-Trip-Schreibvorgang bewahrt Ihre anderen Tabellen und Kommentare (über die `tomlkit`-Laufzeitabhängigkeit) und bleibt `0600`. |

### `[accounts.<name>]`

Eine Tabelle pro Konto; `<name>` ist der Kontobenutzername. Das Register lädt in drei Dicts, die nach Benutzername indiziert sind: `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Feld | Typ | Erforderlich | Bedeutung |
|---|---|---|---|
| `display_name` | string | nein | Vollständiger Anzeigename, verwendet für die Archivverzeichnisbenennung (`web_archive/<display name>/…`); fällt auf den Benutzernamen zurück, wenn nicht angegeben. Siehe [Archiv-Layout](archive-layout.md). |
| `email` | string | empfohlen | Login-E-Mail. Der Transport überprüft den Cookie-Besitz damit, um „einen Export für Konto B, der die Sitzung von Konto A trägt“ zu verhindern (`pplx_export/config.py:69-72`). Bei Nichtübereinstimmung zählt das Tool die Sitzungstoken pro Konto im Browser auf und wechselt automatisch – siehe [Multi-Account-Cookie-Modell](#multi-account-cookie-model). |
| `user_id` | string | für `pplx-ask`-Telemetrie | Konto-UID, erforderlich für die Thread-Ansichts-Telemetrie (`pplx_export/config.py:73-75`). Lesen Sie sie von `GET /api/auth/linked-accounts`, das für jedes angemeldete Konto `user_id` / `email` / `display_name` zurückgibt – siehe [API-Authentifizierung](../reference/api/api-authentication.md). |

### `[bot_space]`

Der BOT-Space ist der Sammelpunkt für Threads, die von `pplx-ask` nach deren Abschluss erstellt wurden (`pplx_export/config.py:76-79`). Erstellen Sie den Space selbst mit `pplx-ask space-create` (siehe [pplx-ask](pplx-ask.md)), und registrieren Sie ihn dann hier.

| Feld | Typ | Bedeutung |
|---|---|---|
| `uuid` | string | Space-UUID. `pplx-ask` verschiebt abgeschlossene Threads hierher (`pplx_export/ask_cli.py:156-158`); wenn leer, wird der Schritt übersprungen. |
| `slug` | string | Der URL-Slug des Spaces. Geladen in `BOT_SPACE_SLUG` (`pplx_export/config.py:79`); die Laufzeit-CLI liest ihn nicht – das Fixture-Wartungstool konsumiert ihn und erstellt daraus ein Identitätsersatzpaar (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### CLI-Flags, keine Konfigurationsfelder

Die TOML enthält keine Transport- oder Cookie-Einstellungen. Diese werden pro Aufruf gewählt:

| Bereich | Wo festgelegt |
|---|---|
| Konfigurationsdateipfad | `--config PATH` oder `PPLX_EXPORT_CONFIG` |
| Cookie-Quelle | `--cookies-from BROWSER` / `--cookies FILE` |
| Transport | `--transport cookie\|webbridge` (nur `pplx-export`; Standard `cookie`) |
| Start-Kontoprüfung überspringen | `--skip-auth-check` (beide Einträge) – siehe [Multi-Account-Cookie-Modell](#multi-account-cookie-model) |

Siehe [pplx-export](pplx-export.md) für die vollständige Flag-Referenz.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## Fehlende Konfiguration: Degradierter Modus

Wenn nichts geladen ist, bleiben die Modulebene-Register leer und `LOADED_CONFIG_PATH` ist `None` (`pplx_export/config.py:83-85`). Verhalten nach Szenario (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`):

| Szenario | Verhalten |
|---|---|
| Keine Konfiguration am Standardpfad, `--account` nicht angegeben | Degradierter Modus: eine Warnung wird protokolliert und Befehle laufen mit einem Platzhalterkonto (`username='default'`); die E-Mail-Besitzprüfung wird übersprungen. Tägliche Offline-Befehle sind nicht betroffen (`pplx_export/commands/common.py:86-90`). |
| Keine Konfiguration, explizites `--account` | `SystemExit` nennt die Suchreihenfolge und verweist auf `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| Konfiguration geladen, `--account` nicht registriert | `SystemExit` nennt die geladene Datei und bittet Sie, `[accounts.<name>]` hinzuzufügen (`pplx_export/commands/common.py:77-82`). |
| Expliziter Pfad (`--config` / Umgebungsvariable) existiert nicht | `ConfigError` im strikten Modus (`pplx_export/config.py:140-146`). |
| Datei existiert, kann aber nicht geparst werden | Immer `ConfigError` – eine beschädigte Konfiguration darf nicht stillschweigend degradieren (`pplx_export/config.py:147-150`). |
| `--account` ausgelassen, Konfiguration geladen | `default_account` wird verwendet (`pplx_export/commands/common.py:84-85`). |

Was „Offline-Befehle“ abdecken und wie degradierte Läufe mit dem Archiv interagieren, wird in [Offline-Operationen](../architecture/offline-operations.md) detailliert beschrieben.

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## Multi-Account-Cookie-Modell

Wenn mehrere Konten im selben Browser angemeldet sind, enthält der Speicher ein Sitzungscookie **pro Konto**, und das `email`-Feld der Konfiguration teilt dem Tool mit, welches es benötigt:

- Jedes angemeldete Konto hat ein `__Secure-pplx.session.<uid>`-Cookie (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`); das Suffix `<uid>` ist die `user_id` des Kontos.
- Das **aktive** Konto ist dasjenige, dessen Token sich derzeit in `__Secure-next-auth.session-token` befindet (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). Konten wechseln = den Wert des konto-spezifischen Cookies des Zielkontos in dieses Cookie schreiben – keine Browser-UI erforderlich (`pplx_export/core/cookies/loaders.py:180-187`).
- Beim Start prüft der Transport `GET https://www.perplexity.ai/api/auth/session` und vergleicht die zurückgegebene E-Mail mit `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- Bei Nichtübereinstimmung zählt `_try_switch_account` (`pplx_export/commands/common.py:190-215`) jedes Konto-Token im Browser über `list_account_tokens` auf (`pplx_export/core/cookies/loaders.py:175-206`, bevorzugt Einträge auf der Subdomain `www.`), probiert jedes in `__Secure-next-auth.session-token` aus und baut den Transport bei der ersten Übereinstimmung neu auf.
- Wenn kein Token übereinstimmt, beendet sich der Befehl mit Nennung beider E-Mails und der Aufforderung, das Zielkonto zuerst im Browser anzumelden (`pplx_export/commands/common.py:142-145`) – siehe [Fehlerbehebung](troubleshooting.md).
- Ein Konto ohne registriertes `email` wird ungeprüft durchgeführt, mit einer Warnung, die Sie bittet, den Browser-Login selbst zu bestätigen (`pplx_export/commands/common.py:146-149`).

Für den vollständigen Wechselablauf und die Semantik der Sitzungsendpunkte siehe [Ask und Konten](../architecture/ask-and-accounts.md) und [API-Authentifizierung](../reference/api/api-authentication.md).

**Prüfung überspringen (`--skip-auth-check`).** Die obige Start-Sitzungsprüfung
tauscht ein paar Sekunden – manchmal Minuten bei schlechtem Netzwerk – gegen die
Besitzsicherung „Konto B als Konto A verwendet“. Wenn Sie wissen, dass der
Browser im richtigen Konto angemeldet ist, überspringt `--skip-auth-check` (geteilt
von `pplx-export` und `pplx-ask`) diese Prüfung vollständig und geht
direkt zur Arbeit (`pplx_export/commands/common.py`,
`make_transport`):

- Kein `GET /api/auth/session` beim Start, sodass ein unzuverlässiges Netzwerk nicht
  mehr eine lange stille Wartezeit (jetzt mit Heartbeat) vor der ersten echten
  Anfrage erzeugt.
- Das Tool vertraut dem aktuell angemeldeten Konto; die vorgelagerte
  E-Mail-Besitzprüfung und der automatische Multi-Account-Wechsel oben werden
  nicht ausgeführt.
- **Aufgeschobenes Sicherheitsnetz**: in `batch`, sobald generische
  Exportfehler akkumuliert sind (drei Fehlschläge), wird eine einmalige
  Kontoprüfung durchgeführt und warnt Sie, was gefunden wurde – das Cookie ist
  abgelaufen, das Konto stimmt nicht mit dem Ziel überein oder das Konto ist in
  Ordnung (die Fehler sind also Netzwerk-/Ratenbegrenzungs-, nicht
  Authentifizierungsfehler)
  (`pplx_export/commands/common.py`, `report_account_status`;
  `pplx_export/commands/batch_cmd.py`).
- **Kompromiss**: Die aufgeschobene Prüfung fängt ein abgelaufenes Cookie,
  kann aber kein *falsches, aber gültiges* Konto erkennen, das ohne Fehler
  exportiert – mit `--skip-auth-check` übernehmen Sie die Verantwortung, dass das
  angemeldete Konto das beabsichtigte ist.

Verwenden Sie es für schnelle, unbeaufsichtigte Läufe mit einem bekanntermaßen guten Login; lassen Sie es weg, wenn Sie auf die vorgelagerte Besitzsicherung oder den automatischen Kontowechsel angewiesen sind.

## Cookie-Cache

Nach erfolgreicher Validierung werden die aufgelösten Cookies zwischengespeichert, sodass spätere Läufe den Browser überspringen:

| Eigenschaft | Wert |
|---|---|
| Pfad | `<archive root>/index/.cookies.json` – folgt `--out` (`pplx_export/commands/common.py:111`) |
| Aktualität | 12 Stunden (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`); ein veralteter oder beschädigter Cache wird als nicht vorhanden behandelt |
| Inhalt | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Schreiben | Atomar: temporäre Datei mit Modus `0o600` erstellt, dann `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Abgedeckt von `.gitignore` (`**/index/.cookies.json`) |

Cookie-Auflösungsreihenfolge (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`): explizites `--cookies-from` → explizite `--cookies`-Datei → frischer Cache → automatische Browsererkennung (Edge → Chrome → Firefox → Safari). Der Cache wird nach jeder erfolgreichen Konto-Validierung aktualisiert (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## Schützen Ihrer Dateien

- `chmod 600` Ihre `config.toml` – sie enthält persönliche Daten (E-Mails, Benutzer-IDs).
- Der Cookie-Cache wird bereits mit Modus `0o600` vom Tool geschrieben; Sitzungscookies sind anmeldeäquivalente Anmeldeinformationen.
- Wenn Sie manuell eine Cookie-Datei für `--cookies` erstellen, wenden Sie auch `chmod 600` darauf an.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## Wenn die Authentifizierung fehlschlägt

Abgelaufene Cookies, ein Konto, das die automatische Umschaltung nicht finden kann, Berechtigungsfehler des Browser-Schlüsselbunds und andere Authentifizierungsfehler werden in [Fehlerbehebung](troubleshooting.md) behandelt.
