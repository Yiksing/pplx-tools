---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/pplx-export.md"
translation_source_sha256: "1eca86e36ffab4e4b66fcc9b085d4214dd72d8e796a90827c2589178f0197f4b"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` ist die Archiver-CLI: Sie ruft Konversationsindizes von Perplexity ab, exportiert Threads in das lokale Archiv und pflegt die abgeleiteten Ansichten (Raumindex, Cron-Snippet). Diese Seite behandelt die Erfassungsseiten-Unterbefehle — `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule` — plus den einmaligen Einrichtungsbefehl `init`. Die Backfill/Repair-Unterbefehle befinden sich in [maintenance-commands.md](maintenance-commands.md); die Query-CLI wird in [pplx-ask.md](pplx-ask.md) behandelt.

<a id="common-options" data-pplx-source-anchor="true"></a>
## Gemeinsame Optionen

Jeder Unterbefehl akzeptiert diese Flags (einmalig in `pplx_export/commands/common.py` definiert):

| Flag | Bedeutung | Standard |
|---|---|---|
| `--account NAME` | Zielkonto. Wenn die E-Mail des Cookies nicht mit der registrierten E-Mail übereinstimmt, werden pro-Konto Browser-Sitzungstoken aufgezählt, um automatisch zu wechseln | `default_account` aus der Benutzerkonfiguration |
| `--config PATH` | Benutzerkonfigurationsdatei (Kontoregister). Priorität: `--config` > Umgebungsvariable `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | Standard-Suchkette |
| `--skip-auth-check` | Überspringe die Start-Kontozuordnungs-Sitzungssondierung und vertraue dem aktuellen Login, vermeidet lange Startwartezeit bei schlechtem Netzwerk; `batch` führt eine verzögerte Kontoprüfung durch, wenn Fehler akkumuliert werden — siehe [Konfiguration](configuration.md) | aus |
| `--site NAME` | Site-Adapter | `perplexity` |
| `--out DIR` | Archiv-Ausgabeverzeichnis | `--out` > Konfiguration `archive_root` > `./web_archive` |
| `--cookies-from BROWSER` | Cookies aus einem Browser importieren (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | Netscape-Cookie-Datei oder JSON-Cookie-Datei | — |
| `--transport MODE` | `cookie` = Cookie-direkte Anfragen; `webbridge` = Abruf im Browser-Seitenkontext | `cookie` |
| `-v`, `--verbose` | DEBUG-Ausgabe (Anfrage-Traces, interne Entscheidungen); wiederholbar | aus |
| `--log-file [PATH]` | Vollständiges Log auf Festplatte schreiben; ohne Wert, automatischer Pfad `<out>/index/logs/<cmd>-<timestamp>.log` | aus |

- `--cookies-from` / `--cookies` schließen sich gegenseitig mit `--transport webbridge` aus — die Brücke läuft im Seitenkontext und trägt bereits die Browser-Cookies.
- `pplx-export --version` gibt die Paketversion aus und beendet (nur auf oberster Ebene, kein Unterbefehls-Flag).
- Kontoregistrierung, Cookie-Quellen und Multi-Konto-Wechsel: [configuration.md](configuration.md). Wo alles auf der Festplatte landet: [archive-layout.md](archive-layout.md).

## init

Konten aus Browser-Cookies erkennen und die Benutzerkonfiguration schreiben — die automatische Alternative zum manuellen Kopieren von `config.example.toml` (siehe [configuration.md](configuration.md)).

| Flag | Bedeutung | Standard |
|---|---|---|
| `--force` | Vorhandene Konfigurationsdatei überschreiben | aus (weigert sich zu überschreiben) |
| `--create-bot-space [TITLE]` | Den BOT-Raum über die API erstellen, wenn kein Raumtitel übereinstimmt (ein Schreibvorgang auf dem Konto); ein expliziter TITLE steuert sowohl Abgleich als auch Erstellung, andernfalls stammt der Titel von `--bot-title`; ohne dieses Flag wird `[bot_space]` leer geschrieben | aus |
| `--bot-title TITLE` | Raumtitel, der sowohl zum Abgleichen eines vorhandenen Raums als auch zum Benennen eines erstellten verwendet wird | `BOT` |
| *(gemeinsame Optionen gelten)* | Cookie-Quellen-Flags bestimmen, wo Konten erkannt werden; für `init` nur, `--config` ist der **Schreib**-Pfad (das strikte Konfigurationsladen wird übersprungen) | |

Wichtige Verhaltensweisen:

- Token-Aufzählung: Pro-Konto Sitzungs-Cookies (`__Secure-pplx.session.<uid>`) werden aus den Browser-Speichern gesammelt — oder, mit `--cookies FILE`, aus der Cookie-Datei gescannt (ein vollständiger Export kann mehrere Konten enthalten). Ohne aufzählbare Token wird nur die aktuell aktive Sitzung sondiert.
- Sitzungssondierung: Jedes Token wird gegen `GET /api/auth/session` versucht, um die E-Mail / den Anzeigenamen des Kontos zu erfahren; Token, die fehlschlagen oder keine E-Mail zurückgeben, werden mit einer Warnung übersprungen.
- Registerzusammenstellung: Jeder Kontoschlüssel wird aus dem lokalen Teil der E-Mail abgeleitet (Kollisionen erhalten `-2`/`-3`… Suffixe); `default_account` wird auf das aktuell aktive Konto gesetzt, andernfalls auf das zuerst entdeckte.
- BOT-Raum: Ein Raum wird durch exakten Titel (Groß-/Kleinschreibung nicht beachtet) über `list_user_collections` abgeglichen; wenn nichts übereinstimmt, erstellt `--create-bot-space [TITLE]` ihn sofort (ein expliziter TITLE überschreibt `--bot-title` sowohl für Abgleich als auch Erstellung), andernfalls wird `[bot_space]` leer gelassen.
- Das TOML wird atomar geschrieben (temporäre Datei + Umbenennung) mit 0600-Berechtigungen, und eine vorhandene Datei wird niemals ohne `--force` überschrieben. Der Befehl endet mit einer zusammenfassenden JSON-Zeile: Konfigurationspfad, Kontoschlüssel, Standardkonto, BOT-Raum-UUID/Slug.
- `--transport webbridge` wird abgelehnt — der Seitenkontext-Kanal kann keine Pro-Konto-Token aufzählen.

```bash
pplx-export init                          # write the default ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --config /path/to/config.toml --force   # custom path, overwrite allowed
```

## index

Die Konversationsliste des Kontos aktualisieren `index/library_<account>.json` — die Basis, gegen die jeder andere Befehl differenziert.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--full` | Die gesamte Bibliothek seitenweise durchgehen und den Index neu schreiben; setzt den inkrementellen Zähler zurück | inkrementell |

Wichtige Verhaltensweisen:

- **Standardmäßig inkrementell.** Es seitenweise von neuesten zuerst und stoppt, sobald eine vollständige Seite (`_STOP_RUN`) aufeinanderfolgender Zeilen bereits bekannt und unverändert ist, dann führt es den abgerufenen Kopf mit dem vorhandenen Index zusammen — ältere Zeilen werden wörtlich übernommen (kein Verlust). Der erste Durchlauf oder jeder Durchlauf ohne vorhandenen Index ist ein vollständiger Durchlauf.
- **`--full`** seitenweise alles durchgehen und den Index neu schreiben; verwenden Sie es als periodisches Abgleichs-Frontend.
- **Blinder Fleck des inkrementellen Pfads:** Remote *Löschungen* und *Raumänderungen* älterer Threads erscheinen nie im abgerufenen Kopf, werden also nicht beobachtet. Löschungsautorität bleibt bei `sync-deleted --online`. Das Indexdokument verfolgt `incremental_runs_since_full`; nach genügend inkrementellen Durchläufen warnt es Sie, `--full` (und `sync-deleted --online`) auszuführen.
- Bewahrt die `search_mode`-Anreicherung, die von `search-mode-backfill` geschrieben und von `entryUUID` zurückgeführt wird.
- Führen Sie es vor `batch`, `sync-space` und `sync-deleted` aus — ihre Differenzen sind nur so aktuell wie dieser Index.

```bash
pplx-export index --account alice          # incremental refresh
pplx-export index --account alice --full   # full sweep + reconciliation front-end
```

## sync

Hochfrequenz-Komforteinstieg: **inkrementelles `index` + inkrementelles `batch`**, nur auf Konversationen fokussiert.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--full` | Vollständiger Abgleich: vollständiger `index` + vollständiger `batch`-Durchlauf (und führt die Löschungs-/Raumschritte unten aus) | aus |
| `--check-deleted` | Auch `sync-deleted --online` ausführen, um remote gelöschte Threads zu überprüfen und zu markieren | aus |
| `--refresh-spaces` | Auch `spaces --fetch-meta` neu aufbauen und `sync-space` ausführen | aus |
| `--limit N` / `--mode X` / `--delay-min` / `--delay-max` | An die `batch`-Phase durchgereicht | — |

Wichtige Verhaltensweisen:

- Standardlauf ruft nur neue/aktualisierte Konversationen ab und **überspringt Löschungserkennung und Raumaktualisierung** — die günstigste Form für häufige Synchronisation.
- Löschungs-/Raumabgleich ist optional (`--check-deleted` / `--refresh-spaces`) oder durch `--full` gebündelt. Der `index`-Zähler (`incremental_runs_since_full`) ist die Absicherung: Er erinnert Sie, wenn ein `--full`-Abgleich überfällig ist.

```bash
pplx-export sync --account alice                     # conversations only (fast)
pplx-export sync --account alice --full              # periodic full reconciliation
pplx-export sync --account alice --check-deleted     # also mark remote deletions
```

## space-index

Die „Alle"-Konversationsliste eines Raums extrahieren — einschließlich Threads, die von anderen Mitgliedern geteilt wurden — in `index/space_<slug>.json`.

| Flag | Bedeutung | Standard |
|---|---|---|
| `SPACE_URL` (positional) | Raum-Seiten-URL | erforderlich |
| `--transport webbridge` | Legacy-Browser-Rendering-Pfad anstelle von REST verwenden | `cookie` (REST direkt) |

Wichtige Verhaltensweisen:

- Standardpfad ist REST direkt: `list_collection_threads` über den Cookie-Transport mit Offset-Paginierung; Zeilen enthalten `context_uuid` und `answer_preview`.
- Mit `--transport webbridge` fällt es zurück auf Scrollen der gerenderten Raumseite und Herauslesen von Zeilen-Eigenschaften — eine Sicherung für den Fall, dass sich die REST-Struktur ändert.
- Zeilen werden von `lastUpdated` zuerst die neuesten geschrieben.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

Einen einzelnen Thread (URL oder bare UUID) in sein Archivverzeichnis `<out>/<account-folder>/<mode>/<thread-dir>/` exportieren.

| Flag | Bedeutung | Standard |
|---|---|---|
| `THREAD` (positional) | Thread-URL oder UUID | erforderlich |
| `--force` | Erneut exportieren, auch wenn `lastUpdated` unverändert ist | aus |

Wichtige Verhaltensweisen:

- Wenn die archivierte Kopie bereits aktuell ist, wird der Export ohne Schreibvorgänge übersprungen; `--force` überschreibt die Prüfung.
- `lastUpdated` wird aus dem lokalen Bibliotheksindex entnommen, wenn der Thread dort aufgeführt ist (gleiche Semantik und Format wie `batch`), andernfalls auf den Plattformwert zurückgegriffen.
- Endzustände werden ordentlich registriert, ohne Traceback: `ENTRY_DELETED` markiert `deleted` in `batch_state.json`, `ENTRY_EXPIRED` markiert `expired` — das vorhandene lokale Archiv bleibt in beiden Fällen unberührt.
- Ein erfolgreicher Export schreibt `ok` in `index/batch_state.json`, sodass der inkrementelle Plan den Thread als „exportiert und unverändert" zählt.
- Was im Thread-Verzeichnis landet: [archive-layout.md](archive-layout.md); die Export-Pipeline selbst: [../architecture/export-pipeline.md](../architecture/export-pipeline.md).

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

Massenexport der Threads eines Kontos — der tägliche Treiber, mit inkrementellem frühen Stopp und fortsetzbaren Prüfpunkten.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--force` | Alle Threads erneut exportieren (Endzustände ausgeschlossen) | aus |
| `--full` | Vollständiger Scan: unveränderte Threads werden dennoch übersprungen, aber kein früher Stopp | aus |
| `--limit N` | Nur die ersten N Zeilen der Liste verarbeiten (neueste zuerst) | alle |
| `--mode MODE` | Nur `search` / `deep-research` / `computer` / `council` / `study` Threads exportieren | alle Modi |
| `--delay-min SEC` | Untere Grenze des zufälligen Intervalls zwischen Threads | `10` |
| `--delay-max SEC` | Obere Grenze des zufälligen Intervalls zwischen Threads | `20` |

Wichtige Verhaltensweisen:

- Erfordert `index/library_<account>.json` — führen Sie zuerst `index` aus.
- Standard **inkrementeller früher Stopp**: Die Liste wird neueste zuerst sortiert und der nachlaufende Block von „exportiert und unverändert" Threads wird vollständig abgeschnitten; Lücken, die durch unterbrochene Läufe (Fehler/nie exportiert) entstanden sind, liegen oberhalb dieses Suffixes und werden dennoch repariert. `--full` deaktiviert den frühen Stopp (periodische Absicherung oder wenn Archivlücken vermutet werden); `--force` exportiert alles außer Endzuständen erneut, die nie wiederholt werden. Vollständige Semantik: [incremental-sync.md](incremental-sync.md).
- `--mode`-Filterung: Zeilen, die `search_mode` tragen (das plattformautoritative Feld, angereichert durch `search-mode-backfill`), stimmen exakt über `SEARCH_MODE_MAP` überein — auf diesem Pfad zieht `--mode search` keine Deep-Research/Council/Study-Threads mehr herein. Zeilen ohne `search_mode` fallen auf Index-Heuristiken zurück: `computer` = Modus `COMPUTER`; `deep-research` = displayModel `pplx_alpha`; `council` = `pplx_agentic_research`; `study` = `pplx_study`; `search` = die verbleibenden Modus-`SEARCH` Zeilen (einschließlich dieser drei Arten — filtern Sie sie präzise heraus, indem Sie die spezifischen Modi separat exportieren).
- Der Zustand wird nach jedem Thread in `index/batch_state.json` gespeichert — unterbrechen und erneut ausführen nach Belieben.
- Auth-Fail-Fast: 3 aufeinanderfolgende 401/403-Antworten brechen den Lauf ab (ein abgelaufenes Cookie kann sich nicht selbst heilen, und das Durchlaufen würde Hunderte von Threads einzeln fehlschlagen lassen).
- Taktung: Eine zufällige `--delay-min`–`--delay-max` Pause zwischen Threads; 429/5xx werden von der Transportschicht zurückgefahren. Details: [rate-limiting.md](rate-limiting.md).
- Threads, die auf umgeschriebene Antwortvarianten stoßen, werden in `index/answer_variants_log.jsonl` mit einer Warnung registriert, sie so bald wie möglich manuell zu behandeln (siehe [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md)).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

Den Raumansichtsindex neu aufbauen — eine Markdown-Seite pro Raum plus ein `spaces.json`-Register — aus den lokalen Bibliotheksindizes.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--fetch-meta` | Besitzer-/Mitgliedsmetadaten vor dem Neubau aktualisieren | aus |

Wichtige Verhaltensweisen:

- Ohne `--fetch-meta` ist der Befehl rein lokal (kein Netzwerk): Er aggregiert Threads pro Raum-Slug über alle `library_*.json`-Dateien, mit teilnehmenden Kontostatistiken und Backlinks zu den exportierten Thread-Verzeichnissen.
- Die Ausgabe geht nach `./spaces/` relativ zum aktuellen Arbeitsverzeichnis — führen Sie es aus dem Verzeichnis aus, das `web_archive/` enthält, damit die Backlinks in den Raumseiten aufgelöst werden.
- `--fetch-meta` aktualisiert zuerst den Besitzer-/Mitglieds-Cache jedes Raums über `get_collection` (1 Anfrage pro Raum, 3s Intervall) in `index/space_meta.json`; wenn das aktuelle Konto einen Raum nicht sehen kann, wird automatisch ein Konto, das dies kann, erneut versucht (Cookies wechseln von selbst).

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

Das `space`-Feld bereits archivierter `thread.json`-Dateien mit dem aktuellen Index synchronisieren — rein lokal, kein Netzwerk.

| Flag | Bedeutung | Standard |
|---|---|---|
| *(nur gemeinsame Optionen; nur `--out` ist relevant)* | | |

Wichtige Verhaltensweisen:

- Voraussetzung: Führen Sie zuerst `index` aus — der aktualisierte `library_*.json` ist die Quelle der Wahrheit für die aktuelle Rauminhaberschaft.
- Vergleicht Raum-Slugs pro Thread und patcht `thread.json` bei Abweichungen direkt; die ersten 30 Änderungen werden protokolliert.
- Nach jeder Änderung wird der `spaces/`-Index automatisch neu aufgebaut.

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

Den inkrementellen Exportplan für diese Runde berechnen und ein Cron-Snippet schreiben, das der System-Cron direkt aufrufen kann.

| Flag | Bedeutung | Standard |
|---|---|---|
| *(nur gemeinsame Optionen)* | | |

Wichtige Verhaltensweisen:

- Ruft einen Live-Index ab und meldet den Plan als Gesamt-/Neu-/Aktualisiert-Zahlen, unter Verwendung derselben Early-Stop-Reinfunktion (`plan_incremental`) wie `batch` — siehe [incremental-sync.md](incremental-sync.md).
- Schreibt `<out>/index/cron_snippet.txt` mit einer `17 3 * * *`-Zeile der Form `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'` — Pfade sind absolut und in Anführungszeichen, da cwd und PATH von cron unvorhersehbar sind. Der ausführbare Pfad wird über `shutil.which` aufgelöst; wenn dies fehlschlägt, fällt das Snippet auf den bloßen `pplx-export`-Namen zurück.
- Geplante Läufe sind standardmäßig nur inkrementell; führen Sie `batch --full` manuell als periodische Absicherung aus.

```bash
pplx-export schedule --account alice
```
