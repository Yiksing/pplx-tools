---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/pplx-export.md"
translation_source_sha256: "09f79a39d95641d1816d529b4471c245bb60e11c49266417504b27a495c90231"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` ist die Archiver-CLI: Sie ruft Konversationsindizes von Perplexity ab, exportiert Threads in das lokale Archiv und pflegt die abgeleiteten Ansichten (Space-Index, Cron-Snippet). Diese Seite behandelt die Erfassungsseitigen Unterbefehle — `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule` — sowie den einmaligen Einrichtungsbefehl `init`. Die Unterbefehle für Backfill/Reparatur befinden sich in [maintenance-commands.md](maintenance-commands.md); die Abfrage-CLI wird in [pplx-ask.md](pplx-ask.md) behandelt.

<a id="common-options" data-pplx-source-anchor="true"></a>
## Gemeinsame Optionen

Jeder Unterbefehl akzeptiert diese Flags (einmalig in `pplx_export/commands/common.py` definiert):

| Flag | Bedeutung | Standard |
|---|---|---|
| `--account NAME` | Zielkonto. Wenn die E-Mail des Cookies nicht mit der registrierten E-Mail übereinstimmt, werden pro-Konto Browser-Sitzungstoken aufgezählt, um automatisch zu wechseln | `default_account` aus der Benutzerkonfiguration |
| `--config PATH` | Benutzerkonfigurationsdatei (Kontoregister). Priorität: `--config` > Umgebungsvariable `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | Standard-Suchkette |
| `--skip-auth-check` | Überspringe die Start-Kontozuordnungs-Sitzungsprüfung und vertraue dem aktuellen Login, um eine lange Startwartezeit bei schlechtem Netzwerk zu vermeiden; `batch` führt eine verzögerte Kontoprüfung durch, wenn sich Fehler ansammeln — siehe [Konfiguration](configuration.md) | aus |
| `--site NAME` | Site-Adapter | `perplexity` |
| `--out DIR` | Archiv-Ausgabeverzeichnis | `--out` > Konfiguration `archive_root` > `./web_archive` |
| `--cookies-from BROWSER` | Cookies aus einem Browser importieren (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | Netscape-Cookie-Datei oder JSON-Cookie-Datei | — |
| `--transport MODE` | `cookie` = Cookie-direkte Anfragen; `webbridge` = Abruf im Browser-Seitenkontext | `cookie` |
| `-v`, `--verbose` | DEBUG-Ausgabe (Anforderungsspuren, interne Entscheidungen); wiederholbar | aus |
| `--log-file [PATH]` | Schreibe das vollständige Log auf die Festplatte; ohne Wert, automatischer Pfad `<out>/index/logs/<cmd>-<timestamp>.log` | aus |

- `--cookies-from` / `--cookies` schließen sich gegenseitig mit `--transport webbridge` aus — die Brücke läuft im Seitenkontext und trägt bereits die Browser-Cookies.
- `pplx-export --version` gibt die Paketversion aus und beendet sich (nur auf oberster Ebene, kein Unterbefehls-Flag).
- Kontoregistrierung, Cookie-Quellen und Multi-Konto-Wechsel: [configuration.md](configuration.md). Wo alles auf der Festplatte landet: [archive-layout.md](archive-layout.md).

## init

Konten aus Browser-Cookies erkennen und die Benutzerkonfiguration schreiben — die automatische Alternative zum manuellen Kopieren von `config.example.toml` (siehe [configuration.md](configuration.md)).

| Flag | Bedeutung | Standard |
|---|---|---|
| `--force` | Vorhandene Konfigurationsdatei überschreiben | aus (weigert sich zu überschreiben) |
| `--create-bot-space [TITLE]` | Erstelle den BOT-Space über die API, wenn kein Space-Titel übereinstimmt (ein Schreibvorgang auf dem Konto); ein expliziter TITLE steuert sowohl das Matching als auch die Erstellung, andernfalls stammt der Titel von `--bot-title`; ohne dieses Flag wird `[bot_space]` leer geschrieben | aus |
| `--bot-title TITLE` | Space-Titel, der sowohl zum Abgleichen eines vorhandenen Spaces als auch zur Benennung eines erstellten verwendet wird | `BOT` |
| *(Gemeinsame Optionen gelten)* | Cookie-Quellen-Flags bestimmen, wo Konten erkannt werden; nur für `init` ist `--config` der **Schreib**-Pfad (das strenge Konfigurationsladen wird übersprungen) | |

Wichtige Verhaltensweisen:

- Token-Aufzählung: Pro-Konto Sitzungs-Cookies (`__Secure-pplx.session.<uid>`) werden aus den Browser-Speichern gesammelt — oder, mit `--cookies FILE`, aus der Cookie-Datei gescannt (ein vollständiger Export kann mehrere Konten enthalten). Ohne aufzählbare Token wird nur die aktuell aktive Sitzung geprüft.
- Sitzungsprüfung: Jeder Token wird gegen `GET /api/auth/session` versucht, um die E-Mail / den Anzeigenamen des Kontos zu erfahren; Token, die fehlschlagen oder keine E-Mail zurückgeben, werden mit einer Warnung übersprungen.
- Registerzusammenstellung: Jeder Kontoschlüssel wird aus dem lokalen Teil der E-Mail abgeleitet (Kollisionen erhalten `-2`/`-3`… Suffixe); `default_account` wird auf das aktuell aktive Konto gesetzt, andernfalls auf das zuerst entdeckte.
- BOT-Space: Ein Space wird durch exakten Titel (Groß-/Kleinschreibung nicht beachtet) über `list_user_collections` abgeglichen; wenn nichts übereinstimmt, erstellt `--create-bot-space [TITLE]` ihn sofort (ein expliziter TITLE überschreibt `--bot-title` sowohl für das Matching als auch für die Erstellung), andernfalls wird `[bot_space]` leer gelassen.
- Das TOML wird atomar geschrieben (temporäre Datei + Umbenennung) mit 0600-Berechtigungen, und eine vorhandene Datei wird niemals ohne `--force` überschrieben. Der Befehl endet mit einer zusammenfassenden JSON-Zeile: Konfigurationspfad, Kontoschlüssel, Standardkonto, BOT-Space-UUID/Slug.
- Modell-Seeding (bestmöglich): Nach dem Schreiben der Konfiguration ruft `init` `models/config/v2` ab und befüllt die maschinenverwaltete `[models]`-Tabelle, sodass eine frische Konfiguration bereits die aktuellen Modellvorgaben/Katalog enthält; bei Fehlschlag wird es mit einer Warnung übersprungen (später mit `pplx-ask models --refresh` aktualisieren). Siehe [Konfiguration](configuration.md).
- `--transport webbridge` wird abgelehnt — der Seitenkontext-Kanal kann keine Pro-Konto-Token aufzählen.

```bash
pplx-export init                          # write the default ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --config /path/to/config.toml --force   # custom path, overwrite allowed
```

## index

Aktualisiere den Konversationslistenindex des Kontos `index/library_<account>.json` — die Basis, gegen die jeder andere Befehl abgleicht.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--full` | Durchblättere die gesamte Bibliothek und überschreibe den Index; setzt den inkrementellen Zähler zurück | inkrementell |

Wichtige Verhaltensweisen:

- **Standardmäßig inkrementell.** Es blättert neueste zuerst und stoppt, sobald eine vollständige Seite (`_STOP_RUN`) aufeinanderfolgender Zeilen bereits bekannt und unverändert ist, dann führt es den abgerufenen Kopf mit dem vorhandenen Index zusammen — ältere Zeilen werden wörtlich übernommen (kein Verlust). Der erste Durchlauf oder jeder Durchlauf ohne vorhandenen Index ist ein vollständiger Durchlauf.
- **`--full`** blättert alles durch und überschreibt den Index; verwenden Sie es als periodisches Frontend für die Abgleichung.
- **Blinder Fleck des inkrementellen Pfads:** Remote *Löschungen* und *Space-Änderungen* älterer Threads erscheinen nie im abgerufenen Kopf und werden daher nicht beobachtet. Die Löschautorität bleibt bei `sync-deleted --online`. Das Indexdokument verfolgt `incremental_runs_since_full`; nach genügend inkrementellen Durchläufen warnt es Sie, `--full` (und `sync-deleted --online`) auszuführen.
- Bewahrt die von `search_mode` geschriebene `search-mode-backfill`-Anreicherung, die von `entryUUID` zurückgeführt wird.
- Führen Sie es vor `batch`, `sync-space` und `sync-deleted` aus — ihre Abgleiche sind nur so aktuell wie dieser Index.

```bash
pplx-export index --account alice          # incremental refresh
pplx-export index --account alice --full   # full sweep + reconciliation front-end
```

## sync

Hochfrequenter Komforteinstieg: **inkrementelles `index` + inkrementelles `batch`**, nur auf Konversationen fokussiert.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--full` | Vollständige Abgleichung: vollständiger `index` + vollständiger `batch`-Durchlauf (und führt die Lösch-/Space-Schritte unten aus) | aus |
| `--check-deleted` | Führe auch `sync-deleted --online` aus, um remote gelöschte Threads zu überprüfen und zu markieren | aus |
| `--refresh-spaces` | Baue auch `spaces --fetch-meta` neu auf und führe `sync-space` aus | aus |
| `--limit N` / `--mode X` / `--delay-min` / `--delay-max` | Werden an die `batch`-Phase durchgereicht | — |

Wichtige Verhaltensweisen:

- Standardlauf ruft nur neue/aktualisierte Konversationen ab und **überspringt Löscherkennung und Space-Aktualisierung** — die günstigste Form für häufige Synchronisation.
- Lösch-/Space-Abgleichung ist optional (`--check-deleted` / `--refresh-spaces`) oder wird durch `--full` gebündelt. Der `index`-Zähler (`incremental_runs_since_full`) ist die Absicherung: Er erinnert Sie, wenn eine `--full`-Abgleichung überfällig ist.

```bash
pplx-export sync --account alice                     # conversations only (fast)
pplx-export sync --account alice --full              # periodic full reconciliation
pplx-export sync --account alice --check-deleted     # also mark remote deletions
```

## space-index

Extrahiere die "Alle"-Konversationsliste eines Spaces — einschließlich von anderen Mitgliedern geteilter Threads — in `index/space_<slug>.json`.

| Flag | Bedeutung | Standard |
|---|---|---|
| `SPACE_URL` (positionsabhängig) | Space-Seiten-URL | erforderlich |
| `--transport webbridge` | Verwende den Legacy-Browser-Rendering-Pfad anstelle von REST | `cookie` (REST direkt) |

Wichtige Verhaltensweisen:

- Standardpfad ist REST direkt: `list_collection_threads` über den Cookie-Transport mit Offset-Paginierung; Zeilen enthalten `context_uuid` und `answer_preview`.
- Mit `--transport webbridge` fällt es zurück auf das Scrollen der gerenderten Space-Seite und das Auslesen von Zeilen-Eigenschaften — eine Sicherung für den Fall, dass sich die REST-Struktur ändert.
- Zeilen werden neueste zuerst von `lastUpdated` geschrieben.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

Exportiere einen einzelnen Thread (URL oder bare UUID) in sein Archivverzeichnis `<out>/<account-folder>/<mode>/<thread-dir>/`.

| Flag | Bedeutung | Standard |
|---|---|---|
| `THREAD` (positionsabhängig) | Thread-URL oder UUID | erforderlich |
| `--force` | Erneut exportieren, auch wenn `lastUpdated` unverändert ist | aus |

Wichtige Verhaltensweisen:

- Wenn die archivierte Kopie bereits aktuell ist, wird der Export ohne Schreibvorgänge übersprungen; `--force` überschreibt die Prüfung.
- `lastUpdated` wird aus dem lokalen Bibliotheksindex entnommen, wenn der Thread dort aufgeführt ist (gleiche Semantik und Format wie `batch`), andernfalls auf den Plattformwert zurückgegriffen.
- Terminalzustände werden ordentlich registriert, ohne Traceback: `ENTRY_DELETED` markiert `deleted` in `batch_state.json`, `ENTRY_EXPIRED` markiert `expired` — das vorhandene lokale Archiv wird in beiden Fällen unberührt gelassen.
- Ein erfolgreicher Export schreibt `ok` in `index/batch_state.json`, sodass der inkrementelle Plan den Thread als "exportiert und unverändert" zählt.
- Was im Thread-Verzeichnis landet: [archive-layout.md](archive-layout.md); die Export-Pipeline selbst: [../architecture/export-pipeline.md](../architecture/export-pipeline.md).

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

Massenexport der Threads eines Kontos — der tägliche Treiber, mit inkrementellem frühen Stopp und fortsetzbaren Prüfpunkten.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--force` | Alle Threads erneut exportieren (Terminalzustände ausgeschlossen) | aus |
| `--full` | Vollständiger Scan: unveränderte Threads werden dennoch übersprungen, aber kein früher Stopp | aus |
| `--limit N` | Verarbeite nur die ersten N Zeilen der Liste (neueste zuerst) | alle |
| `--mode MODE` | Exportiere nur `search` / `deep-research` / `computer` / `council` / `study`-Threads | alle Modi |
| `--delay-min SEC` | Untere Grenze des zufälligen Intervalls zwischen Threads | `10` |
| `--delay-max SEC` | Obere Grenze des zufälligen Intervalls zwischen Threads | `20` |

Wichtige Verhaltensweisen:

- Erfordert `index/library_<account>.json` — führen Sie zuerst `index` aus.
- Standard **inkrementeller früher Stopp**: Die Liste wird neueste zuerst sortiert und der nachlaufende Block von "exportiert und unverändert"-Threads wird vollständig abgeschnitten; Lücken, die durch unterbrochene Läufe (Fehler/nie exportiert) entstanden sind, liegen oberhalb dieses Suffixes und werden dennoch repariert. `--full` deaktiviert den frühen Stopp (periodische Absicherung oder wenn Archivlücken vermutet werden); `--force` exportiert alles außer Terminalzuständen erneut, die nie wiederholt werden. Vollständige Semantik: [incremental-sync.md](incremental-sync.md).
- `--mode`-Filterung: Zeilen, die `search_mode` tragen (das plattformautoritative Feld, angereichert durch `search-mode-backfill`), stimmen exakt über `SEARCH_MODE_MAP` überein — auf diesem Pfad zieht `--mode search` keine Deep-Research/Council/Study-Threads mehr herein. Zeilen ohne `search_mode` fallen auf Index-Heuristiken zurück: `computer` = Modus `COMPUTER`; `deep-research` = displayModel `pplx_alpha`; `council` = `pplx_agentic_research`; `study` = `pplx_study`; `search` = die verbleibenden Modus-`SEARCH`-Zeilen (einschließlich dieser drei Arten — filtern Sie sie genau aus, indem Sie die spezifischen Modi separat exportieren).
- Der Zustand wird nach jedem Thread in `index/batch_state.json` gespeichert — unterbrechen und erneut ausführen nach Belieben.
- Auth-Fail-Fast: 3 aufeinanderfolgende 401/403-Antworten brechen den Lauf ab (ein abgelaufenes Cookie kann sich nicht selbst heilen, und das Durchlaufen würde Hunderte von Threads einzeln zum Scheitern bringen).
- Taktung: Eine zufällige `--delay-min`–`--delay-max`-Pause zwischen Threads; 429/5xx werden von der Transportschicht zurückgefahren. Details: [rate-limiting.md](rate-limiting.md).
- Threads, die auf umgeschriebene Antwortvarianten stoßen, werden in `index/answer_variants_log.jsonl` mit einer Warnung registriert, sie so bald wie möglich manuell zu behandeln (siehe [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md)).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

Baue den Space-Ansichtsindex neu auf — eine Markdown-Seite pro Space plus ein `spaces.json`-Register — aus den lokalen Bibliotheksindizes.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--fetch-meta` | Aktualisiere Besitzer/Mitglieder-Metadaten vor dem Neubau | aus |

Wichtige Verhaltensweisen:

- Ohne `--fetch-meta` ist der Befehl rein lokal (kein Netzwerk): Er aggregiert Threads pro Space-Slug über alle `library_*.json`-Dateien, mit Statistiken der teilnehmenden Konten und Backlinks zu den exportierten Thread-Verzeichnissen.
- Die Ausgabe erfolgt in `./spaces/` relativ zum aktuellen Arbeitsverzeichnis — führen Sie es aus dem Verzeichnis aus, das `web_archive/` enthält, damit die Backlinks in den Space-Seiten aufgelöst werden.
- `--fetch-meta` aktualisiert zuerst den Besitzer/Mitglieder-Cache jedes Spaces über `get_collection` (1 Anfrage pro Space, 3s Intervall) in `index/space_meta.json`; wenn das aktuelle Konto einen Space nicht sehen kann, wird automatisch ein Konto, das dies kann, erneut versucht (Cookies wechseln von selbst).

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

Synchronisiere das `space`-Feld bereits archivierter `thread.json`-Dateien mit dem aktuellen Index — rein lokal, kein Netzwerk.

| Flag | Bedeutung | Standard |
|---|---|---|
| *(nur gemeinsame Optionen; nur `--out` ist relevant)* | | |

Wichtige Verhaltensweisen:

- Voraussetzung: Führen Sie zuerst `index` aus — der aktualisierte `library_*.json` ist die Quelle der Wahrheit für die aktuelle Space-Zugehörigkeit.
- Vergleicht Space-Slugs pro Thread und patcht `thread.json` bei Abweichungen direkt; die ersten 30 Änderungen werden protokolliert.
- Nach jeder Änderung wird der `spaces/`-Index automatisch neu aufgebaut.

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

Berechne den inkrementellen Exportplan für diese Runde und schreibe ein Cron-Snippet, das der System-Cron direkt aufrufen kann.

| Flag | Bedeutung | Standard |
|---|---|---|
| *(nur gemeinsame Optionen)* | | |

Wichtige Verhaltensweisen:

- Ruft einen Live-Index ab und meldet den Plan als Gesamt-/Neu-/Aktualisiert-Zahlen, unter Verwendung derselben Early-Stop-Reinfunktion (`plan_incremental`) wie `batch` — siehe [incremental-sync.md](incremental-sync.md).
- Schreibt `<out>/index/cron_snippet.txt`, das eine `17 3 * * *`-Zeile der Form `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'` enthält — Pfade sind absolut und in Anführungszeichen, da cwd und PATH von cron unvorhersehbar sind. Der ausführbare Pfad wird über `shutil.which` aufgelöst; wenn dies fehlschlägt, fällt das Snippet auf den bloßen `pplx-export`-Namen zurück.
- Geplante Läufe sind standardmäßig nur inkrementell; führen Sie `batch --full` manuell als periodische Absicherung aus.

```bash
pplx-export schedule --account alice
```
