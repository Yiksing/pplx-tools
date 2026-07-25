---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/incremental-sync.md"
translation_source_sha256: "35868edfb3e8e914afd9afa1b00370bffb9f8a50ca374691229f41d51ffa9b64"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="incremental-sync" data-pplx-source-anchor="true"></a>
# Inkrementelle Synchronisation

`pplx-export batch` ist dafür ausgelegt, häufig ausgeführt zu werden: Jeder Lauf exportiert nur das, was neu oder geändert ist, schließt Lücken, die durch unterbrochene Läufe entstanden sind, und berührt niemals Threads, die die Plattform bereits als abgeschlossen betrachtet. Die einzige Quelle der Wahrheit für „was exportiert wurde“ ist `index/batch_state.json` (`BatchState`, `pplx_export/core/state.py:63`), die nach jedem Thread aktualisiert wird – es gibt keine separate Schattenkopie.

<a id="prerequisites-and-basic-usage" data-pplx-source-anchor="true"></a>
## Voraussetzungen und grundlegende Verwendung

```bash
pplx-export index --account alice   # refresh index/library_alice.json first
pplx-export batch --account alice   # incremental export (early stop, resumable)
```

`batch` weigert sich, ohne den Index ausgeführt zu werden (`pplx_export/commands/batch_cmd.py:79-81`). `--limit N` und `--mode <mode>` filtern die Indexzeilen vor der Planung; Zeilen ohne `entryUUID` werden mit einer Warnung übersprungen, anstatt den Lauf zum Absturz zu bringen (`batch_cmd.py:95-100`).

<a id="how-the-incremental-plan-works" data-pplx-source-anchor="true"></a>
## Wie der inkrementelle Plan funktioniert

1. **Sortieren.** Indexzeilen werden nach `lastUpdated` sortiert, die neuesten zuerst (`batch_cmd.py:89`). Brandneue Konversationen und wiederaufgenommene alte (deren `lastUpdated` sie gerade nach oben verschoben hat) befinden sich beide oben – diese Reihenfolge macht den frühen Stopp sicher.
2. **Klassifizieren.** `plan_incremental` (`pplx_export/hooks/incremental.py:36-87`) – eine reine Funktion, die von `batch` und `schedule` gemeinsam genutzt wird – weist jeder Zeile genau eine Aktion zu:

   | Aktion | Bedingung | Was der Batch tut |
   |---|---|---|
   | `new` | UUID noch nie in `batch_state` gesehen | exportieren |
   | `updated` | `lastUpdated` unterscheidet sich vom aufgezeichneten Wert, oder `--force` | erneut exportieren |
   | `done` | Status `ok` und `lastUpdated` unverändert | überspringen |
   | `expired` | die Plattform hat bei einem früheren Versuch `ENTRY_EXPIRED` zurückgegeben | überspringen – endgültig, nie wiederholt |
   | `deleted` | `sync-deleted` hat eine entfernte Löschung bestätigt | überspringen – endgültig, nie wiederholt |

3. **Früher Stopp.** Standardmäßig (weder `--full` noch `--force`) wird der längste nachfolgende Lauf von terminalen Einträgen (`done` / `expired` / `deleted`) vollständig abgeschnitten und als `n_stopped` gezählt (`incremental.py:83-87`). Da die Liste die neuesten zuerst enthält, ist alles unterhalb eines unveränderten Eintrags zwangsläufig älter und ebenfalls unverändert – weiter zu scannen würde nur Zeit verschwenden.

   ```mermaid
   flowchart TD
       IDX["library index rows<br/>sorted by lastUpdated, newest first"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → export"]
       PLAN --> UPD["updated → re-export"]
       PLAN --> DONE["done → skip"]
       PLAN --> TERM["expired / deleted → skip (terminal)"]
       DONE --> STOP["early stop:<br/>trailing terminal run trimmed"]
       TERM --> STOP
   ```

4. **Ausführen.** Jeder exportierte Thread wird sofort markiert (`mark_ok` / `mark_error` / `mark_expired` / `mark_deleted`) und die Zustandsdatei wird nach jedem Element gespeichert (`batch_cmd.py:154-201`); ein `KeyboardInterrupt` speichert auch vor der Weitergabe (`batch_cmd.py:158-161`). Schreibvorgänge sind atomar – temporäre Datei plus `os.replace` (`state.py:145-152`) – sodass ein unterbrochener Lauf niemals abgeschnittenes JSON hinterlässt.

<a id="gap-healing-after-interrupted-runs" data-pplx-source-anchor="true"></a>
## Lückenheilung nach unterbrochenen Läufen

Der frühe Stopp vergräbt niemals eine Lücke. Threads, die fehlgeschlagen sind (Status `error`) oder nie erreicht wurden, befinden sich **oberhalb** des terminalen Suffixes, sodass der nächste Lauf sie als `updated` / `new` neu plant und exportiert, bevor der Punkt des frühen Stopps erreicht wird (`incremental.py:12-14`, `batch_cmd.py:206-208`). In Kombination mit pro-Element-Zustandsspeicherungen kann ein Batch-Lauf an jeder Stelle unterbrochen und einfach erneut ausgeführt werden.

Wenn `batch_state.json` selbst beschädigt ist, wird es nicht stillschweigend geleert: Das Original wird in `batch_state.json.corrupt-<timestamp>` umbenannt, sodass aufgezeichnete terminale Zustände nicht verloren gehen und unnötig wiederholt werden (`state.py:68-81`).

<a id="-full-and-force" data-pplx-source-anchor="true"></a>
## `--full` und `--force`

| Flag | Effekt | Terminale Zustände | Wann verwenden |
|---|---|---|---|
| *(Standard)* | Früher Stopp über den nachfolgenden terminalen Lauf | übersprungen | Jeder reguläre / geplante Lauf |
| `--full` | Vollständiger Scan, kein früher Stopp; unveränderte Threads werden dennoch als `done` übersprungen | übersprungen | Periodische Absicherung oder wenn Archivlücken vermutet werden |
| `--force` | Alles erneut exportieren, auch unveränderte Threads | weiterhin ausgeschlossen – nie wiederholt | Nach Pipeline-Fixes, die Rohdaten erneut abrufen müssen |

Terminale Zustände werden standardmäßig von `--force` ausgeschlossen: Die Wiederholung eines abgelaufenen oder entfernt gelöschten Threads verschwendet nur Anfragen und Backoff-Budget (`batch_cmd.py:120-127`).

Siehe auch [`status`](maintenance-commands.md#status): Ein netzwerkfreier Bericht des Zustandskontos und des Änderungsplans, berechnet mit derselben `plan_incremental`-Semantik (`new`/`updated`/Anzahl früher Stopps).

Der `lastUpdated`-Vergleich normalisiert nachfolgende Nullen im Bruchteil-Sekunden-Teil (`.18033Z` ist gleich `.180330Z`; `state.py:23-55`), da die Plattform diese gelegentlich weglässt – ein exakter String-Vergleich würde fälschlicherweise „geändert“ urteilen und doppelte Exporte verursachen.

<a id="terminal-states-expired-and-deleted" data-pplx-source-anchor="true"></a>
## Terminale Zustände: `expired` und `deleted`

| | `expired` | `deleted` |
|---|---|---|
| Bedeutung | Die Plattform hat den Thread gelöscht (~3-Monats-Aufbewahrungsfenster); der Exportversuch gab `ENTRY_EXPIRED` zurück | Benutzer-/entfernte Löschung, bestätigt durch `sync-deleted` |
| Aufgezeichnet von | `batch` selbst (`mark_expired`, `state.py:131-134`) | `pplx-export sync-deleted --online` (`mark_deleted`, `state.py:136-143`) |
| Wiederholt? | Niemals – nicht einmal mit `--force` | Niemals – nicht einmal mit `--force` |
| Nachweis | Die `ENTRY_EXPIRED`-Antwort | `note`-Feld: Indexabwesenheit + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted-confirming-remote-deletions" data-pplx-source-anchor="true"></a>
### sync-deleted: Bestätigen entfernter Löschungen

```bash
pplx-export sync-deleted --account alice            # offline dry-run: list candidates only
pplx-export sync-deleted --account alice --online   # confirm each candidate online
```

1. **Kandidaten (offline, kein Netzwerk).** Jeder Thread mit Status `ok` in `batch_state`, der in der `entryUUID`-Vereinigung **aller** `index/library_*.json`-Kontoindizes fehlt, ist ein mutmaßlicher Kandidat für entfernte Löschung (`pplx_export/commands/sync_deleted_cmd.py:148-212`). Die Vereinigungsmenge über alle Konten ist erforderlich: Ein Thread, der `bob` gehört, aber von `alice` über einen gemeinsamen Bereich exportiert wurde, erscheint nie in `alice`s eigenem Index – ein Einzelkonto-Diff würde diese gesamte Menge fälschlicherweise als positiv melden. Wenn überhaupt kein brauchbarer Index existiert, wird jeder Kandidat sicher mit dem aufgezeichneten Grund übersprungen.
2. **Standardmäßig Probelauf.** Ohne `--online` listet der Befehl nur Kandidaten auf – kein Netzwerk, keine Dateiänderungen.
3. **`--online`-Bestätigung.** Jeder Kandidat wird mit `GET /rest/thread/<uuid>` verifiziert, wobei das Konto des Kandidaten aus `export_via` von `thread.json` verwendet wird (das Cookie wechselt automatisch):

   | Ergebnis | Ausgang |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | Bestätigt: `batch_state` markiert terminal `deleted` (der `note` zeichnet den Grund auf), und jeder `thread.json` dieses Threads erhält einen `remote_deleted`-Zeitstempel an Ort und Stelle |
   | Thread existiert noch | Falsch positiv: wird wie vorgefunden gemeldet (der Index ist möglicherweise nicht vollständig aktualisiert – führen Sie `index` erneut aus und überprüfen Sie es noch einmal), nichts geändert |
   | 5xx / Netzwerkfehler | Keine Zustandsänderung; der Kandidat wird für die nächste Runde belassen |
   | 3 aufeinanderfolgende 401/403 | Fail-Fast-Abbruch – ein abgelaufenes Cookie kann sich nicht selbst heilen, und das Weiterspinnen würde Live-Threads falsch markieren (`sync_deleted_cmd.py:333-337`) |

   Bestätigte Markierungen werden pro Element gespeichert, sodass ein unterbrochener `--online`-Lauf nichts verliert und Wiederholungen idempotent sind (`sync_deleted_cmd.py:254-256`).

<a id="the-tombstone-principle" data-pplx-source-anchor="true"></a>
## Das Grabstein-Prinzip

!!! warning "Lokale Archive werden niemals gelöscht"
    Dieses Archiv ist die Sicherungskopie der exportierten Konversationen.
    `sync-deleted` *identifiziert und markiert* nur (Grabstein): Es **löscht oder verschiebt niemals eine Archivdatei**. Die Bestätigung ändert genau zwei Dinge – den `batch_state`-Status und einen Markierungsschlüssel in `thread.json`:

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    Der Stempel ist idempotent: Ein vorhandener `remote_deleted`-Schlüssel wird weder neu geschrieben noch überschrieben (`sync_deleted_cmd.py:215-244`).

<a id="idempotence-and-offline-re-render" data-pplx-source-anchor="true"></a>
## Idempotenz und Offline-Neuberechnung

- Die erneute Ausführung von `batch` gegen einen unveränderten Index exportiert nichts: Jede Zeile wird als `done` klassifiziert und der Lauf stoppt am Punkt des frühen Stopps. Zustandsschreibvorgänge sind atomar, Markierungen erfolgen pro Thread, und erneut bestätigte Löschungen duplizieren niemals den `remote_deleted`-Stempel.
- Das Archiv behält die rohen API-Nutzlasten (`raw_entries.json` / `raw_blocks.json`), sodass die gerenderten Dateien jederzeit ohne Netzwerkzugriff neu generiert werden können:

  ```bash
  pplx-export re-render                 # rebuild conversation.md + turns/ everywhere
  pplx-export re-render --dry-run       # only list the thread directories
  pplx-export re-render --thread-json   # also sync interruptions / answer_variants keys
  ```

  `re-render` parst das rohe JSON mit dem aktuellen Renderer neu (`pplx_export/commands/rerender_cmd.py:105-190`): `conversation.md` und `turns/turn_*.md` werden neu geschrieben, veraltete Turn-Dateien, die über der aktuellen Turn-Anzahl nummeriert sind, werden entfernt, und Quellen, Assets, `report.md` und `thread.json` bleiben unberührt. So werden Renderer-Fixes ohne eine einzige Anfrage über das gesamte Archiv ausgerollt.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Siehe auch

- [pplx-export.md](pplx-export.md) – vollständige `batch`-Befehlsreferenz (`--mode`, `--limit`, Verzögerungen)
- [maintenance-commands.md](maintenance-commands.md) – `sync-deleted`, `re-render` und die Backfill-Befehle
- [archive-layout.md](archive-layout.md) – wo `batch_state.json` und `thread.json` leben
- [rate-limiting.md](rate-limiting.md) – Taktung zwischen Threads, Backoff, Auth-Fail-Fast
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) – die vollständige Export-Pipeline
- [../architecture/offline-operations.md](../architecture/offline-operations.md) – die Offline-Neuerstellungspipeline im Detail
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) – Fehlertaxonomie und Behandlung terminaler Zustände
