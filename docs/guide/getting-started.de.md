---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/getting-started.md"
translation_source_sha256: "d98ba1f32b1e75bff7b3d51ef17e833417ecaf283996152cfa3342455b6eca7a"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="getting-started" data-pplx-source-anchor="true"></a>
# Erste Schritte

Von einem frischen Checkout zum ersten lokalen Archiv: Installieren Sie die beiden Befehle, erstellen Sie die
benutzerspezifische Konfiguration, wählen Sie einen Cookie-Kanal und führen Sie einen ersten Export durch.

<a id="requirements" data-pplx-source-anchor="true"></a>
## Voraussetzungen

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — wird verwendet, um die Tools zu installieren und die Testsuite auszuführen
- **Ein Desktop-Browser, der bei Perplexity angemeldet ist** — die Tools verwenden dessen Session-Cookies wieder;
  es wird niemals ein Token in der Konfiguration gespeichert

Die Cookie-Entschlüsselung verwendet `browser_cookie3`. Die automatische Erkennung umfasst Edge, Chrome, Firefox und
Safari; Brave, Chromium, Opera und Vivaldi funktionieren über `--cookies-from`.

<a id="install" data-pplx-source-anchor="true"></a>
## Installation

Kein Klon erforderlich — Installation direkt von der Git-URL:

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

Von einem lokalen Klon (Repository-Stammverzeichnis):

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

Dies installiert zwei Befehle: `pplx-export` (Archivierung) und `pplx-ask` (interaktive
Abfragen). Überprüfung:

```bash
pplx-export --version
pplx-export --help           # overview with examples; each subcommand has its own --help
pplx-ask --help
```

`uvx --from . pplx-export` führt einen einmaligen Befehl ohne Installation aus.

<a id="create-the-user-level-config" data-pplx-source-anchor="true"></a>
## Erstellen der benutzerspezifischen Konfiguration

Das Kontoregister (Anzeigename / E-Mail / user_id) und der BOT-Bereich sind persönliche
Daten und werden **nicht in das Repository übertragen**; sie befinden sich in einer externen TOML-Datei.
Vorlage: `config.example.toml` im Repository-Stammverzeichnis.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

1. Erstellen Sie das Konfigurationsverzeichnis.
2. Kopieren Sie die Vorlage in den Standardpfad.
3. `chmod 600` — die Datei enthält persönliche Daten; behalten Sie sie als nur für den Besitzer zugänglich.
4. Füllen Sie `[accounts.<name>]` aus — der Schlüssel ist der Kontobenutzername (wie er in
   Thread-URLs / der Bibliothek erscheint); setzen Sie `display_name`, `email`, `user_id` und wählen Sie einen
   `default_account`.
5. Füllen Sie `[bot_space]` aus — wo Threads, die von `pplx-ask` erstellt wurden, nach
   Abschluss gesammelt werden (ein echter Bereich kann mit `pplx-ask space-create` erstellt werden).

**Automatische Alternative:** `pplx-export init` leitet diese Datei für Sie ab — es
zählt die pro-Konto Session-Cookies in Ihrem Browser auf, durchsucht
`/api/auth/session` nach der E-Mail / dem Anzeigenamen jedes Tokens, setzt
`default_account` auf das aktuell aktive Konto, findet den BOT-Bereich anhand des
Titels und schreibt das TOML atomar mit 0600-Berechtigungen (eine vorhandene Datei
wird nur mit `--force` überschrieben).

```bash
pplx-export init                     # discover accounts, write the default config path
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --bot-title TITLE   # match/create a different space title (default BOT)
pplx-export init --config /path/to/config.toml   # write to a custom path
```

Flags: `--force` überschreibt eine vorhandene Konfiguration; `--create-bot-space [TITLE]`
erstellt den Bereich über die API, wenn kein Titel übereinstimmt (ein Schreibvorgang auf dem
Konto; ein expliziter TITLE steuert sowohl die Übereinstimmung als auch die Erstellung); `--bot-title TITLE`
wird sowohl für die Übereinstimmung als auch für die Erstellung verwendet. Beachten Sie, dass für
`init` — anders als bei jedem anderen Befehl — `--config` der **Schreib**-Pfad ist, nicht
der Ladepfad. Vollständige Details: [pplx-export → init](pplx-export.md#init).

Die vollständige Feldreferenz finden Sie unter [Konfiguration](configuration.md).

**Ladepriorität** (höchste zuerst):

| # | Quelle |
|---|--------|
| 1 | `--config PATH` |
| 2 | `PPLX_EXPORT_CONFIG` Umgebungsvariable |
| 3 | `~/.config/pplx-export/config.toml` (Standard) |

!!! note "Wenn die Konfiguration fehlt"
    Befehle ohne `--account` laufen in einem eingeschränkten Modus — die E-Mail-Besitzprüfung wird
    mit einer Warnung übersprungen (Offline-Befehle sind nicht betroffen); ein explizites `--account`
    löst einen Fehler aus, der auf `config.example.toml` verweist. Wenn `--account` weggelassen wird,
    wird `default_account` aus der Konfiguration verwendet.

<a id="choose-a-cookie-channel" data-pplx-source-anchor="true"></a>
## Auswählen eines Cookie-Kanals

Anmeldeinformationen stammen aus den angemeldeten Perplexity Session-Cookies Ihres lokalen Browsers, die über
`browser_cookie3` gelesen werden — einschließlich der Aufzählung von Multi-Konto-Token und automatischem
Umschalten. Vier Kanäle:

| Kanal | Wie | Hinweise |
|---------|-----|-------|
| Automatische Erkennung (Standard) | kein Flag | frischer 12-Stunden-Cache zuerst, dann Browser-Speicher in der Reihenfolge edge→chrome→firefox→safari |
| Benannter Browser | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| Cookie-Datei | `--cookies /path/to/cookies.txt` | Netscape-Cookie-Datei oder exportiertes JSON |
| WebBridge | `--transport webbridge` | Seitenkontext-Abruf — der Fallback-Kanal, nur verwendet, wenn explizit angefordert |

Unter Linux werden auch Snap- und Flatpak-Browserinstallationen automatisch erkannt — ihre Profilpfade
sind durch die integrierte Registrierung abgedeckt. Die vollständige Linux-Matrix (Keyring, Desktop-Umgebungen,
Distro-Pakete):
[Fehlerbehebung → Linux-Cookie-Entschlüsselung](troubleshooting.md#linux-cookie-decryption).

```bash
pplx-export export <thread_url>                                 # default: auto-detect browser store
pplx-export export <thread_url> --cookies-from edge             # import from a specific browser
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # use a cookie file
pplx-export export <thread_url> --transport webbridge           # WebBridge page context (explicit fallback)
```

Nachdem Cookies abgerufen wurden, ruft das Tool `/api/auth/session` auf und gibt die aktuelle
Konto-E-Mail aus, damit Sie bestätigen können, dass das richtige Konto verwendet wird — achten Sie darauf, wenn `--account`
mit dem Cookie-Konto nicht übereinstimmt. Das Transport-/Anmeldeinformationsdesign wird in
[Ask & Konten](../architecture/ask-and-accounts.md) behandelt.

<a id="first-run" data-pplx-source-anchor="true"></a>
## Erster Durchlauf

```bash
pplx-export index --account alice     # fetch the library index
pplx-export export <thread_url>       # export a single thread
pplx-export batch --account alice     # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run       # offline re-render, zero network
```

1. **`index`** ruft den Bibliotheksindex des Kontos ab — der Einstiegspunkt, auf dem `batch` und
   die anderen kontoübergreifenden Befehle aufbauen.
2. **`export`** archiviert einen Thread vollständig: Es behält die rohen API-Antworten
   (`raw_*.json`) zusammen mit Markdown, sodass die Darstellung offline wiederholt werden kann.
3. **`batch`** durchläuft die gesamte Bibliothek. Es stoppt frühzeitig, sobald alles Verbleibende bereits
   archiviert ist (inkrementeller Frühstopp), schreibt fortsetzbare Prüfpunkte und akzeptiert
   `--full` für einen vollständigen Durchlauf. Details: [Inkrementelle Synchronisation](incremental-sync.md).
4. **`re-render --dry-run`** beweist den Offline-Pfad: Es regeneriert `conversation.md`
   + `turns/` aus lokalen Rohdateien ohne Netzwerk. Verwenden Sie `--dry-run`, um die
   Ergebnisse zu schreiben. Siehe [Offline-Operationen](../architecture/offline-operations.md).

Sobald das funktioniert, führt `pplx-ask ask "<prompt>"` eine Streaming-Abfrage aus und archiviert den
resultierenden Thread automatisch — siehe [pplx-ask](pplx-ask.md).

<a id="where-archives-land" data-pplx-source-anchor="true"></a>
## Wo Archive landen

Archive werden standardmäßig in `./web_archive/` geschrieben (Überschreibung mit `--out`): ein
Verzeichnis pro Thread.

| Pfad | Inhalt |
|------|---------|
| `conversation.md`, `turns/` | dargestellte Konversation |
| `thread.json` | Thread-Metadaten + Unterbrechungsregister |
| `sources.md` / `sources.json` | Zitate |
| `report.md` | Deep-Research / Council / Study-Bericht |
| `assets/` | heruntergeladene Assets (Computermodus) |
| `raw_*.json` | aufbewahrte rohe API-Antworten — erfolgreiche Archive können offline ohne erneuten Abruf neu dargestellt werden |

Der vollständige Verzeichnisvertrag: [Archiv-Layout](archive-layout.md).

<a id="next-steps" data-pplx-source-anchor="true"></a>
## Nächste Schritte

- Ist etwas schiefgelaufen? → [Fehlerbehebung](troubleshooting.md)
- Befehl-für-Befehl-Referenz → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [Wartungsbefehle](maintenance-commands.md)
- Die fünf Konversationsmodi → [Modi](modes.md)
