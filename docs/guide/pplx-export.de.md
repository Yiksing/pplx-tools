---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/pplx-export.md"
translation_source_sha256: "6ef4d5b78ce748c1fd97d6d1dfaea40f0bdfd427f23a089b6110c2fb0e4f9c53"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` ist die Archiver-CLI: Sie ruft Konversationsindizes von Perplexity ab, exportiert Threads in das lokale Archiv und pflegt die abgeleiteten Ansichten (Raumindex, Cron-Snippet). Diese Seite behandelt die Erfassungsseitigen Unterbefehle — `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule` — sowie den einmaligen Einrichtungsbefehl `init`. Die Backfill-/Reparatur-Befehle befinden sich in [maintenance-commands.md](maintenance-commands.md); die Abfrage-CLI wird in [pplx-ask.md](pplx-ask.md) behandelt.

<a id="common-options" data-pplx-source-anchor="true"></a>
## Gemeinsame Optionen

Jeder Unterbefehl akzeptiert diese Flags (einmalig definiert in `pplx_export/commands/common.py`):

| Flag | Bedeutung | Standard |
|---|---|---|
| `--account NAME` | Zielkonto. Wenn die E-Mail des Cookies nicht mit der registrierten E-Mail übereinstimmt, werden pro-Konto Browser-Sitzungstoken aufgezählt, um automatisch umzuschalten | `default_account` aus der Benutzerkonfiguration |
| `--config PATH` | Benutzerkonfigurationsdatei (Kontoregister). Priorität: `--config` > Umgebungsvariable `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | Standard-Suchkette |
| `--site NAME` | Site-Adapter | `perplexity` |
| `--out DIR` | Archiv-Ausgabeverzeichnis | `./web_archive` |
| `--cookies-from BROWSER` | Cookies aus einem Browser importieren (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | Netscape-Cookie-Datei oder JSON-Cookie-Datei | — |
| `--transport MODE` | `cookie` = Cookie-direkte Anfragen; `webbridge` = Abruf im Browser-Seitenkontext | `cookie` |
| `-v`, `--verbose` | DEBUG-Ausgabe (Anfrage-Traces, interne Entscheidungen); wiederholbar | aus |
| `--log-file [PATH]` | Vollständiges Log auf Festplatte schreiben; ohne Wert, automatischer Pfad `<out>/index/logs/<cmd>-<timestamp>.log` | aus |

- `--cookies-from` / `--cookies` schließen sich gegenseitig mit `--transport webbridge` aus — die Brücke läuft im Seitenkontext und trägt bereits die Browser-Cookies.
- `pplx-export --version` gibt die Paketversion aus und beendet das Programm (nur auf oberster Ebene, kein Unterbefehls-Flag).
- Kontoregistrierung, Cookie-Quellen und Multi-Konto-Umschaltung: [configuration.md](configuration.md). Wo alles auf der Festplatte landet: [archive-layout.md](archive-layout.md).

## init

Konten aus Browser-Cookies erkennen und die Benutzerkonfiguration schreiben — die automatische Alternative zum manuellen Kopieren von `config.example.toml` (siehe [configuration.md](configuration.md)).

| Flag | Bedeutung | Standard |
|---|---|---|
| `--force` | Vorhandene Konfigurationsdatei überschreiben | aus (weigert sich zu überschreiben) |
| `--create-bot-space [TITLE]` | Den BOT-Raum über die API erstellen, wenn kein Raumtitel übereinstimmt (ein Schreibvorgang auf dem Konto); ein expliziter TITLE steuert sowohl Abgleich als auch Erstellung, andernfalls stammt der Titel von `--bot-title`; ohne dieses Flag wird `[bot_space]` leer geschrieben | aus |
| `--bot-title TITLE` | Raumtitel, der sowohl zum Abgleichen eines vorhandenen Raums als auch zum Benennen eines erstellten verwendet wird | `BOT` |
| *(gemeinsame Optionen gelten)* | Cookie-Quellen-Flags bestimmen, wo Konten erkannt werden; nur für `init` ist `--config` der **Schreib**-Pfad (das strikte Konfigurationsladen wird übersprungen) | |

Wichtige Verhaltensweisen:

- Token-Enumeration: Pro-Konto Sitzungs-Cookies (`__Secure-pplx.session.<uid>`) werden aus den Browser-Speichern gesammelt — oder, mit `--cookies FILE`, aus der Cookie-Datei gescannt (ein vollständiger Export kann mehrere Konten enthalten). Ohne aufzählbare Token wird nur die aktuell aktive Sitzung geprüft.
- Sitzungsprüfung: Jedes Token wird gegen `GET /api/auth/session` versucht, um die E-Mail / den Anzeigenamen des Kontos zu erfahren; Token, die fehlschlagen oder keine E-Mail zurückgeben, werden mit einer Warnung übersprungen.
- Registerzusammenstellung: Jeder Kontoschlüssel wird aus dem lokalen Teil der E-Mail abgeleitet (Kollisionen erhalten `-2`/`-3`… Suffixe); `default_account` wird auf das aktuell aktive Konto gesetzt, andernfalls auf das zuerst erkannte.
- BOT-Raum: Ein Raum wird durch exakten Titel (Groß-/Kleinschreibung nicht beachtet) über `list_user_collections` abgeglichen; wenn nichts übereinstimmt, erstellt `--create-bot-space [TITLE]` ihn sofort (ein expliziter TITLE überschreibt `--bot-title` sowohl für Abgleich als auch Erstellung), andernfalls wird `[bot_space]` leer gelassen.
- Die TOML-Datei wird atomar geschrieben (temporäre Datei + Umbenennung) mit 0600-Berechtigungen, und eine vorhandene Datei wird ohne `--force` nie überschrieben. Der Befehl endet mit einer zusammenfassenden JSON-Zeile: Konfigurationspfad, Kontoschlüssel, Standardkonto, BOT-Raum-UUID/Slug.
- `--transport webbridge` wird abgelehnt — der Seitenkontext-Kanal kann keine Pro-Konto-Token aufzählen.

```bash
pplx-export init                          # write the default ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --config /path/to/config.toml --force   # custom path, overwrite allowed
```

## index

Die vollständige Konversationsliste des Kontos abrufen (GraphQL) und den Master-Index `index/library_<account>.json` schreiben — die Basis, gegen die jeder andere Befehl difft.

| Flag | Bedeutung | Standard |
|---|---|---|
| *(nur gemeinsame Optionen)* | | |

Wichtige Verhaltensweisen:

- Bewahrt die von `search-mode-backfill` geschriebene `search_mode`-Anreicherung: Indexzeilen tragen sie nativ nicht, daher wird sie bei Aktualisierung aus dem alten Index durch `entryUUID` zurückgemischt.
- Vor `batch`, `sync-space` und `sync-deleted` ausführen — deren Diffs sind nur so aktuell wie dieser Index.

```bash
pplx-export index --account alice
```

## space-index

Die „Alle"-Konversationsliste eines Raums extrahieren — einschließlich von anderen Mitgliedern geteilter Threads — in `index/space_<slug>.json`.

| Flag | Bedeutung | Standard |
|---|---|---|
| `SPACE_URL` (positionsabhängig) | Raum-Seiten-URL | erforderlich |
| `--transport webbridge` | Legacy-Browser-Rendering-Pfad anstelle von REST verwenden | `cookie` (REST direkt) |

Wichtige Verhaltensweisen:

- Standardpfad ist REST direkt: `list_collection_threads` über den Cookie-Transport mit Offset-Paginierung; Zeilen enthalten `context_uuid` und `answer_preview`.
- Mit `--transport webbridge` wird auf das Scrollen der gerenderten Raumseite und das Auslesen von Zeilen-Eigenschaften zurückgegriffen — eine Sicherung für den Fall, dass sich die REST-Struktur ändert.
- Zeilen werden neueste zuerst durch `lastUpdated` geschrieben.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

Einen einzelnen Thread (URL oder bare UUID) in sein Archivverzeichnis `<out>/<account-folder>/<mode>/<thread-dir>/` exportieren.

| Flag | Bedeutung | Standard |
|---|---|---|
| `THREAD` (positionsabhängig) | Thread-URL oder UUID | erforderlich |
| `--force` | Erneut exportieren, auch wenn `lastUpdated` unverändert ist | aus |

Wichtige Verhaltensweisen:

- Wenn die archivierte Kopie bereits aktuell ist, wird der Export ohne Schreibvorgänge übersprungen; `--force` überschreibt die Prüfung.
- `lastUpdated` wird aus dem lokalen Bibliotheksindex übernommen, wenn der Thread dort gelistet ist (gleiche Semantik und Format wie `batch`), andernfalls auf den Plattformwert zurückgegriffen.
- Terminalzustände werden ordentlich registriert, ohne Traceback: `ENTRY_DELETED` markiert `deleted` in `batch_state.json`, `ENTRY_EXPIRED` markiert `expired` — das vorhandene lokale Archiv wird in beiden Fällen unberührt gelassen.
- Ein erfolgreicher Export schreibt `ok` in `index/batch_state.json`, sodass der inkrementelle Plan den Thread als „exportiert und unverändert" zählt.
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
| `--limit N` | Nur die ersten N Zeilen der Liste verarbeiten (neueste zuerst) | alle |
| `--mode MODE` | Nur `search` / `deep-research` / `computer` / `council` / `study` Threads exportieren | alle Modi |
| `--delay-min SEC` | Untere Grenze des zufälligen Intervalls zwischen Threads | `10` |
| `--delay-max SEC` | Obere Grenze des zufälligen Intervalls zwischen Threads | `20` |

Wichtige Verhaltensweisen:

- Erfordert `index/library_<account>.json` — zuerst `index` ausführen.
- Standard **inkrementeller früher Stopp**: Die Liste wird neueste zuerst sortiert und der nachlaufende Block von „exportiert und unverändert"-Threads wird vollständig abgeschnitten; Lücken durch unterbrochene Läufe (Fehler/nie exportiert) liegen oberhalb dieses Suffixes und werden dennoch repariert. `--full` deaktiviert den frühen Stopp (periodische Absicherung oder wenn Archivlücken vermutet werden); `--force` exportiert alles außer Terminalzuständen erneut, die nie wiederholt werden. Vollständige Semantik: [incremental-sync.md](incremental-sync.md).
- `--mode`-Filterung: Zeilen mit `search_mode` (dem plattformautoritativen Feld, angereichert durch `search-mode-backfill`) stimmen exakt über `SEARCH_MODE_MAP` überein — auf diesem Pfad zieht `--mode search` keine Deep-Research/Council/Study-Threads mehr herein. Zeilen ohne `search_mode` fallen auf Index-Heuristiken zurück: `computer` = Modus `COMPUTER`; `deep-research` = displayModel `pplx_alpha`; `council` = `pplx_agentic_research`; `study` = `pplx_study`; `search` = die verbleibenden Modus-`SEARCH`-Zeilen (einschließlich dieser drei Arten — filtern Sie sie genau aus, indem Sie die spezifischen Modi separat exportieren).
- Der Zustand wird nach jedem Thread in `index/batch_state.json` gespeichert — unterbrechen und erneut ausführen nach Belieben.
- Auth-Fail-Fast: 3 aufeinanderfolgende 401/403-Antworten brechen den Lauf ab (ein abgelaufenes Cookie kann sich nicht selbst heilen, und das Durchlaufen würde Hunderte von Threads einzeln fehlschlagen lassen).
- Taktung: Eine zufällige Pause von `--delay-min`–`--delay-max` zwischen Threads; 429/5xx werden von der Transportschicht zurückgefahren. Details: [rate-limiting.md](rate-limiting.md).
- Threads, die auf umgeschriebene Antwortvarianten stoßen, werden in `index/answer_variants_log.jsonl` mit einer Warnung registriert, um sie so bald wie möglich manuell zu behandeln (siehe [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md)).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

Die Raumansichts-Indizes neu erstellen — eine Markdown-Seite pro Raum plus ein `spaces.json`-Register — aus den lokalen Bibliotheksindizes.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--fetch-meta` | Besitzer-/Mitglieds-Metadaten vor dem Neuerstellen aktualisieren | aus |

Wichtige Verhaltensweisen:

- Ohne `--fetch-meta` ist der Befehl rein lokal (kein Netzwerk): Er aggregiert Threads pro Raum-Slug über alle `library_*.json`-Dateien, mit Statistiken der teilnehmenden Konten und Backlinks zu den exportierten Thread-Verzeichnissen.
- Die Ausgabe erfolgt in `./spaces/` relativ zum aktuellen Arbeitsverzeichnis — führen Sie ihn aus dem Verzeichnis aus, das `web_archive/` enthält, damit die Backlinks in den Raumseiten aufgelöst werden.
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

- Voraussetzung: `index` zuerst ausführen — der aktualisierte `library_*.json` ist die Quelle der Wahrheit für die aktuelle Raumzugehörigkeit.
- Vergleicht Raum-Slugs pro Thread und patcht `thread.json` bei Abweichung direkt; die ersten 30 Änderungen werden protokolliert.
- Nach jeder Änderung wird der `spaces/`-Index automatisch neu erstellt.

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
- Schreibt `<out>/index/cron_snippet.txt` mit einer `17 3 * * *`-Zeile der Form `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'` — Pfade sind absolut und in Anführungszeichen, da cwd und PATH von Cron unvorhersehbar sind. Der ausführbare Pfad wird über `shutil.which` aufgelöst; wenn dies fehlschlägt, fällt das Snippet auf den bloßen `pplx-export`-Namen zurück.
- Geplante Läufe sind standardmäßig nur inkrementell; führen Sie `batch --full` manuell als periodische Absicherung aus.

```bash
pplx-export schedule --account alice
```
