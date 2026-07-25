---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "17a6ed1ea6a178fefb108fb05ebc93982f869568bba13654444489c41d36da34"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="configuration" data-pplx-source-anchor="true"></a>
# Konfiguration

pplx-export speichert Ihre Identitätsdaten – die Kontoregistrierung (Anzeigenamen, Login-E-Mails, Benutzer-IDs) und den BOT-Bereich – in einer benutzerspezifischen TOML-Datei, die sich außerhalb des Repositorys befindet. Diese Seite behandelt, wo diese Datei liegt, jedes Feld, das sie akzeptiert, was passiert, wenn sie fehlt, und wie die Registrierung die Multi-Account-Cookie-Verwaltung steuert.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## Warum die Konfiguration außerhalb des Repositorys liegt

Die Kontoregistrierung und der BOT-Bereich sind persönliche Daten und werden **niemals** in das Repository übertragen (`pplx_export/config.py:7-12`). Das Repository enthält nur eine Platzhaltervorlage, `config.example.toml`; Ihre tatsächlichen Werte gehen in eine private Kopie. Alles andere, was das Tool benötigt – die Site-Domain, API-URLs, das Standard-Archivverzeichnis – ist eine Code-Konstante (`pplx_export/config.py:50-58`), keine Benutzerkonfiguration.

Die TOML-Datei enthält nur Identitätsdaten. Die Cookie-Quelle und die Transportauswahl erfolgen über CLI-Flags pro Aufruf, nicht über Konfigurationsfelder – siehe [CLI-Flags, keine Konfigurationsfelder](#cli-flags-not-config-fields) unten.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## Speicherort und Ladepriorität

`configure()` (`pplx_export/config.py:113`) ermittelt den Konfigurationspfad mit folgender Priorität (`pplx_export/config.py:95-110`):

| Priorität | Quelle | Gilt als explizit |
|---|---|---|
| 1 | `--config PATH` CLI-Flag | ja |
| 2 | `PPLX_EXPORT_CONFIG` Umgebungsvariable | ja |
| 3 | `~/.config/pplx-export/config.toml` (Standardpfad) | nein |

„Explizit“ ist wichtig für das Fehlerverhalten, wenn die Datei fehlt – siehe [Degradierter Modus](#missing-config-degraded-mode). Beide CLI-Einträge laden die Konfiguration nach der Argumentanalyse im strikten Modus neu (`pplx_export/cli.py:223`, `pplx_export/ask_cli.py:278`); das Laden zum Importzeitpunkt (`pplx_export/config.py:174-179`) ist fehlertolerant, sodass das Importieren des Pakets niemals aufgrund einer fehlenden Datei fehlschlägt.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## Erstellen Ihrer Konfiguration

!!! tip "Automatische Alternative"
    `pplx-export init` kann diese Datei automatisch generieren – es erkennt die angemeldeten Konten aus Ihren Browser-Cookies und schreibt die TOML-Datei mit Berechtigungen 0600. Siehe [pplx-export → init](pplx-export.md#init).

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
    Die echte Konfiguration enthält persönliche Daten (E-Mails, Benutzer-IDs). Empfohlene Berechtigung ist `0o600`; übergeben Sie sie niemals an ein Git-Repository (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## Feldreferenz

<a id="top-level" data-pplx-source-anchor="true"></a>
### Oberste Ebene

| Feld | Typ | Bedeutung |
|---|---|---|
| `default_account` | string | Schlüssel einer `[accounts.<name>]`-Tabelle, verwendet wenn `--account` nicht angegeben ist (`pplx_export/commands/common.py:84-85`). Leer/fehlend = degradierter Modus. |

### `[accounts.<name>]`

Eine Tabelle pro Konto; `<name>` ist der Kontobenutzername. Die Registrierung lädt in drei Dicts, die nach Benutzername indiziert sind: `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Feld | Typ | Erforderlich | Bedeutung |
|---|---|---|---|
| `display_name` | string | nein | Vollständiger Anzeigename, verwendet für die Archivverzeichnisbenennung (`web_archive/<display name>/…`); fällt auf den Benutzernamen zurück, wenn nicht angegeben. Siehe [Archiv-Layout](archive-layout.md). |
| `email` | string | empfohlen | Login-E-Mail. Der Transport überprüft den Cookie-Besitz damit, um einen „Export für Konto B, der die Sitzung von Konto A trägt“ zu verhindern (`pplx_export/config.py:69-72`). Bei Nichtübereinstimmung zählt das Tool die Sitzungstoken pro Konto im Browser auf und wechselt automatisch – siehe [Multi-Account-Cookie-Modell](#multi-account-cookie-model). |
| `user_id` | string | für `pplx-ask`-Telemetrie | Konto-UID, erforderlich für die Telemetrie der Thread-Ansicht (`pplx_export/config.py:73-75`). Lesen Sie sie von `GET /api/auth/linked-accounts`, das für jedes angemeldete Konto `user_id` / `email` / `display_name` zurückgibt – siehe [API-Authentifizierung](../reference/api/api-authentication.md). |

### `[bot_space]`

Der BOT-Bereich ist der Sammelpunkt für Threads, die von `pplx-ask` erstellt wurden, nachdem sie abgeschlossen sind (`pplx_export/config.py:76-79`). Erstellen Sie den Bereich selbst mit `pplx-ask space-create` (siehe [pplx-ask](pplx-ask.md)), und registrieren Sie ihn dann hier.

| Feld | Typ | Bedeutung |
|---|---|---|
| `uuid` | string | Bereichs-UUID. `pplx-ask` verschiebt abgeschlossene Threads hierher (`pplx_export/ask_cli.py:156-158`); wenn leer, wird der Verschiebeschritt übersprungen. |
| `slug` | string | Der URL-Slug des Bereichs. Geladen in `BOT_SPACE_SLUG` (`pplx_export/config.py:79`); die Laufzeit-CLI liest es nicht – das Fixture-Wartungstool konsumiert es und erstellt daraus ein Identitätsersetzungspaar (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### CLI-Flags, keine Konfigurationsfelder

Die TOML-Datei enthält keine Transport- oder Cookie-Einstellungen. Diese werden pro Aufruf gewählt:

| Bereich | Wo es gesetzt wird |
|---|---|
| Konfigurationsdateipfad | `--config PATH` oder `PPLX_EXPORT_CONFIG` |
| Cookie-Quelle | `--cookies-from BROWSER` / `--cookies FILE` |
| Transport | `--transport cookie\|webbridge` (nur `pplx-export`; Standard `cookie`) |

Siehe [pplx-export](pplx-export.md) für die vollständige Flag-Referenz.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## Fehlende Konfiguration: Degradierter Modus

Wenn nichts geladen ist, bleiben die Registrierungen auf Modulebene leer und `LOADED_CONFIG_PATH` ist `None` (`pplx_export/config.py:83-85`). Verhalten nach Szenario (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`):

| Szenario | Verhalten |
|---|---|
| Keine Konfiguration am Standardpfad, `--account` nicht angegeben | Degradierter Modus: eine Warnung wird protokolliert und Befehle laufen mit einem Platzhalterkonto (`username='default'`); die E-Mail-Besitzprüfung wird übersprungen. Tägliche Offline-Befehle sind nicht betroffen (`pplx_export/commands/common.py:86-90`). |
| Keine Konfiguration, explizites `--account` | `SystemExit`, das die Suchreihenfolge nennt und auf `config.example.toml` verweist (`pplx_export/commands/common.py:67-74`). |
| Konfiguration geladen, `--account` nicht registriert | `SystemExit`, das die geladene Datei nennt und Sie auffordert, `[accounts.<name>]` hinzuzufügen (`pplx_export/commands/common.py:77-82`). |
| Expliziter Pfad (`--config` / Umgebungsvariable) existiert nicht | `ConfigError` im strikten Modus (`pplx_export/config.py:140-146`). |
| Datei existiert, kann aber nicht geparst werden | Immer `ConfigError` – eine beschädigte Konfiguration darf nicht stillschweigend degradieren (`pplx_export/config.py:147-150`). |
| `--account` ausgelassen, Konfiguration geladen | `default_account` wird verwendet (`pplx_export/commands/common.py:84-85`). |

Was „Offline-Befehle“ abdecken und wie degradierte Läufe mit dem Archiv interagieren, wird in [Offline-Operationen](../architecture/offline-operations.md) detailliert beschrieben.

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## Multi-Account-Cookie-Modell

Wenn mehrere Konten im selben Browser angemeldet sind, enthält der Speicher ein Sitzungs-Cookie **pro Konto**, und das `email`-Feld der Konfiguration teilt dem Tool mit, welches es benötigt:

- Jedes angemeldete Konto hat ein `__Secure-pplx.session.<uid>`-Cookie (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:104`); das `<uid>`-Suffix ist die `user_id` des Kontos.
- Das **aktive** Konto ist dasjenige, dessen Token sich derzeit in `__Secure-next-auth.session-token` befindet (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:105`). Kontenwechsel = Schreiben des pro-Konto-Cookie-Werts des Zielkontos in dieses Cookie – keine Browser-UI erforderlich (`pplx_export/core/cookies/loaders.py:113-120`).
- Beim Start prüft der Transport `GET https://www.perplexity.ai/api/auth/session` und vergleicht die zurückgegebene E-Mail mit `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- Bei Nichtübereinstimmung zählt `_try_switch_account` (`pplx_export/commands/common.py:190-215`) jedes Konto-Token im Browser über `list_account_tokens` auf (`pplx_export/core/cookies/loaders.py:108-139`, bevorzugt Einträge auf der `www.`-Subdomain), versucht jedes in `__Secure-next-auth.session-token` und baut den Transport beim ersten Treffer neu auf.
- Wenn kein Token übereinstimmt, beendet sich der Befehl, nennt beide E-Mails und fordert Sie auf, das Zielkonto zuerst im Browser anzumelden (`pplx_export/commands/common.py:142-145`) – siehe [Fehlerbehebung](troubleshooting.md).
- Ein Konto ohne registriertes `email` wird ungeprüft fortgesetzt, mit einer Warnung, die Sie auffordert, den Browser-Login selbst zu bestätigen (`pplx_export/commands/common.py:146-149`).

Für den vollständigen Wechselablauf und die Semantik des Sitzungsendpunkts siehe [Ask und Konten](../architecture/ask-and-accounts.md) und [API-Authentifizierung](../reference/api/api-authentication.md).

## Cookie-Cache

Nach erfolgreicher Validierung werden die aufgelösten Cookies zwischengespeichert, sodass spätere Läufe den Browser überspringen:

| Eigenschaft | Wert |
|---|---|
| Pfad | `<archive root>/index/.cookies.json` – folgt `--out` (`pplx_export/commands/common.py:111`) |
| Aktualität | 12 Stunden (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`); ein veralteter oder beschädigter Cache wird als nicht vorhanden behandelt |
| Inhalt | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Schreiben | Atomar: temporäre Datei mit Modus `0o600` erstellt, dann `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Abgedeckt durch `.gitignore` (`**/index/.cookies.json`) |

Cookie-Auflösungsreihenfolge (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:203-235`): explizites `--cookies-from` → explizite `--cookies`-Datei → frischer Cache → automatische Erkennung von Browsern (Edge → Chrome → Firefox → Safari). Der Cache wird nach jeder erfolgreichen Konto-Validierung aktualisiert (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## Schützen Ihrer Dateien

- `chmod 600` Ihre `config.toml` – sie enthält persönliche Daten (E-Mails, Benutzer-IDs).
- Der Cookie-Cache wird bereits mit Modus `0o600` vom Tool geschrieben; Sitzungs-Cookies sind anmeldeäquivalente Anmeldeinformationen.
- Wenn Sie eine Cookie-Datei manuell für `--cookies` erstellen, wenden Sie auch `chmod 600` darauf an.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## Wenn die Authentifizierung fehlschlägt

Abgelaufene Cookies, ein Konto, das die automatische Umschaltung nicht finden kann, Berechtigungsfehler der Browser-Tresor-App und andere Authentifizierungsfehler werden in [Fehlerbehebung](troubleshooting.md) behandelt.
