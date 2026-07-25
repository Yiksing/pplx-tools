---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/archive-layout.md"
translation_source_sha256: "6302a47c60b6c8703d36f420cee6c18017110fcbb6127926eedb5c77e3e1f8e2"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="archive-layout" data-pplx-source-anchor="true"></a>
# Archiv-Layout

Alles, was `pplx-export` herunterlädt, landet in einem einzigen Ausgabebaum – standardmäßig `./web_archive/`
(überschreibbar mit `--out`). Diese Seite ist ein Leitfaden zu diesem Baum: was jedes Verzeichnis und jede Datei
ist, welche Schlüssel `thread.json` trägt und wie das Tool ein Verzeichnis pro Thread beibehält, wenn eine
Unterhaltung über mehrere Tage fortgesetzt wird. Alles wird vom Tool generiert; die Mechanismen im Detail finden sich in
[Datenmodell & Verzeichnisvertrag](../architecture/data-model.md) und
[Export-Pipeline](../architecture/export-pipeline.md).

<a id="the-output-tree" data-pplx-source-anchor="true"></a>
## Der Ausgabebaum

```
web_archive/
├── alice/                                # one folder per account (author display name)
│   ├── search/                           # mode: search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # one directory per thread
│   │       ├── thread.json               # metadata + optional registries
│   │       ├── conversation.md           # compact read: per-turn Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # full read: complete work-process detail
│   │       │   └── ...
│   │       ├── sources.json              # thread-wide citations (deduped by url)
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research report (only when one exists)
│   │       ├── raw_entries.json          # plain API response, verbatim (always present)
│   │       ├── raw_blocks.json           # schematized API response (absent for search)
│   │       └── assets/
│   │           ├── assets_manifest.json  # versioned manifest
│   │           └── files/                # downloaded asset bodies
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # state files and indexes (see below)
├── relations/                            # edges.jsonl + graph.md (rebuilt by `pplx-export relations`)
├── crosscheck/                           # cross-validation reports (manual/review artifacts)
└── bob/ ...
```

<a id="the-thread-directory" data-pplx-source-anchor="true"></a>
## Das Thread-Verzeichnis

Jeder Thread erhält genau ein Verzeichnis, berechnet von `thread_dir_for` (`fs_writer.py:58-72`):

```
<account display name>/<mode>/<YYYY-MM-DD>_<title-slug>_<uuid8>/
```

| Komponente | Quelle | Hinweise |
|---|---|---|
| `<account display name>` | Thread-Autor, via `author_folder` → `_safe_folder` (`fs_writer.py:40-51`) | Pfadtrennzeichen und unter Windows ungültige Zeichen (`:*?"<>\|`) werden zu `_`; `.`/`..` abgelehnt (Pfad-Traversal-Schutz für gemeinsame Bereiche); alles andere – einschließlich Leerzeichen – wird beibehalten |
| `<mode>` | `detect_mode` | einer der fünf Modi; siehe [Gesprächsmodi](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` `lastUpdated` Datumspräfix | das Datum der letzten Aktualisierung auf der Plattform, **nicht** das Exportdatum – es verschiebt sich, wenn ein fortgesetzter Thread aktualisiert wird (siehe Migration unten) |
| `<title-slug>` | `slugify(title)` (`normalize.py:261-263`) | max. 40 Zeichen, Nicht-Wort-Zeichen → `-`, leer → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | die ersten 8 Zeichen der Thread-UUID – der Identitätsanker des Verzeichnisses |

<a id="files-in-a-thread-directory" data-pplx-source-anchor="true"></a>
## Dateien in einem Thread-Verzeichnis

<a id="threadjson-metadata-and-registries" data-pplx-source-anchor="true"></a>
### thread.json – Metadaten und Register

Geschrieben von `write_thread` (`fs_writer.py:224-253`). Immer vorhandene Schlüssel:

| Schlüssel | Inhalt |
|---|---|
| `web_uuid` | Web-Eintrags-UUID – die UUID in der Thread-URL; die Identität des Threads |
| `psc_uuid` | Plattform-`context_uuid` (nullable; vom ersten nicht-leeren Turn) – die duale ID, die von Bereichsindizes verwendet wird |
| `url` | Kanonische Thread-URL |
| `title` | Thread-Titel |
| `mode` | Erkannter Modus (`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | Anzeigename des Autors |
| `export_via` | Benutzername des Kontos, das den Export durchgeführt hat – wichtig für Threads in gemeinsamen Bereichen, die über ein anderes Konto exportiert wurden |
| `space` | `{"uuid", "title", "slug"}` oder `null` |
| `lastUpdated` | Zeitstempel der letzten Aktualisierung auf der Plattform (Maschinenvergleichsvertrag für inkrementelle Synchronisation) |
| `threadAccess` | Zugriffsflag der Plattform |
| `n_turns` | Anzahl der Turns |
| `n_sources` | Thread-weite Zitatanzahl |
| `metadata` | `thread_metadata` aus der API-Antwort, wörtlich |
| `report_info` | `{"title", "file_name", "url"}` oder `null` |
| `exported_at` | Exportzeit (UTC ISO 8601) |

Optionale Schlüssel – fehlen, wenn es nichts aufzuzeichnen gibt:

| Schlüssel | Hinzugefügt wenn | Inhalt |
|---|---|---|
| `interruptions` | ein nicht abgeschlossener Workflow (`fs_writer.py:242-244`) | Liste von `{location, kind, headline, status}`; siehe [Gesprächsmodi – Unterbrechungen](modes.md#interruptions-non-completed-workflows) |
| `answer_variants` | eine Antwort-Umschreibungsvariante wird erkannt (`fs_writer.py:247-252`) | eingegrenzte `side_by_side_metadata`-Felder; siehe [Gesprächsmodi – Antwort-Umschreibungsvarianten](modes.md#answer-rewrite-variants-answer_variants) |
| `remote_deleted` | `pplx-export sync-deleted --online` bestätigt entfernte Löschung | Tombstone-Zeitstempel, an Ort und Stelle geschrieben, idempotent (vorhandener Wert wird nie überschrieben; `sync_deleted_cmd.py:215-244`) – das lokale Archiv selbst wird behalten |

<a id="conversationmd-the-compact-read" data-pplx-source-anchor="true"></a>
### conversation.md – die kompakte Ansicht

`render_conversation` (`render.py:641`): Titel-Header (Modus / Autor / Turns / Zitatanzahl),
dann pro Turn ein `### Query` + `### Answer`-Paar mit vollständigen Antworten und – falls vorhanden – dem
Thread-weiten Hintergrundaufgaben-Anhang am Ende. Dies ist die zuerst zu öffnende Datei; die Arbeitsprozesse pro Turn
befinden sich in `turns/`.

<a id="turnsturn_nnnnmd-the-full-read" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md – die vollständige Ansicht

`render_turn` (`render.py:596`): eine Datei pro Turn (`turn_0001.md` …), jede mit dem vollständigen
Arbeitsprozess – Schritte, Tool-Aufrufe, Sub-Agent-Läufe, Tabellen, Zitate pro Turn. Wenn die Turn-Anzahl eines Threads
schrumpft, werden veraltete hochnummerierte `turn_*.md`-Dateien gelöscht, aber unberührte Dateien behalten
ihre mtime (`fs_writer.py:287-301`).

### sources.json / sources.md

Thread-weite Zitate, dedupliziert nach URL (`fs_writer.py:270-278`). `sources.json` ist
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`; `sources.md` ist dieselbe
Liste als nummerierte Markdown-Liste.

### report.md

Das Deep-Research-Berichtsprodukt, nur geschrieben, wenn der Thread eines enthält
(`fs_writer.py:308-316`): Berichtstitel, der ursprüngliche Produktdateiname, dann der vollständige Bericht
in Markdown.

<a id="raw_entriesjson-raw_blocksjson-raw-fidelity" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json – Rohdaten-Treue

Die API-Antworten, unverändert **vor** jeglicher Analyse gespeichert (`fs_writer.py:257-266`):

- `raw_entries.json` – die einfache Antwort: `{"thread_metadata", "entries", "background_entries"}`.
  Immer vorhanden.
- `raw_blocks.json` – die schematisierte Antwort, gleiche Form. Fehlt bei `search`-Threads
  (kein Blocks-Abruf); wird für die anderen vier Modi abgerufen, und auch als Fallback, wenn jedes
  Moduserkennungssignal fehlt.

Diese beiden Dateien sind der Treueanker des Archivs: Analyse, Darstellung und Register können
alle offline daraus neu erstellt werden, ohne Netzwerk. Siehe
[Offline-Operationen](../architecture/offline-operations.md).

<a id="assets-products-and-their-manifest" data-pplx-source-anchor="true"></a>
### assets/ – Produkte und ihr Manifest

Herunterladbare Produkte (Computer-Modus-Dateien und andere vom API gelistete Assets) werden
von CloudFront-signierten URLs in `assets/files/` abgerufen; die Erweiterung wird zum Download-Zeitpunkt
aus URL-Pfad, Content-Magic-Bytes oder Asset-Typ bestimmt. `assets/assets_manifest.json`
(`fs_writer.py:320-330`) zeichnet jede Version auf:

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` ist immer die **Gesamtzahl der Versionen** (Σ `len(versions)`), nicht die Anzahl der Dateigruppen – verwenden Sie `len(files)` dafür.

<a id="the-index-layer" data-pplx-source-anchor="true"></a>
## Die index/-Ebene

`web_archive/index/` enthält vom Tool verwalteten Zustand und Indizes – nicht manuell bearbeiten:

| Datei | Geschrieben von | Semantik |
|---|---|---|
| `library_<account>.json` | `pplx-export index` (`index_cmd.py:17-43`) | vollständiger Konto-Thread-Index (GraphQL); Eingabe für Batch-/Zeitplan-/Bereichsindizes |
| `batch_state.json` | `BatchState` (`state.py`) | fortsetzbarer Prüfpunkt: uuid → Status (ok/error/expired/deleted) + lastUpdated; atomare Schreibvorgänge; beschädigte Dateien automatisch als `.corrupt-<ts>` gesichert |
| `.cookies.json` | Cookie-Cache (`common.py:111`, `common.py:150`) | 12h-frischer Cookie-Cache mit Quelle und Konto-E-Mail; geschrieben `0o600` dann atomar ersetzt (Sitzungsanmeldeinformationen, nur für Besitzer lesbar) |
| `space_<slug>.json` | `pplx-export space-index` (`spaces_cmd.py:106-167`) | Bereichs-Thread-Liste, inkl. der `context_uuid`-Dual-ID-Zuordnung |
| `space_meta.json` | `pplx-export spaces --fetch-meta` (`spaces_cmd.py:299-330`) | Bereichsbesitzer-/Mitglieder-Cache, bei Neuerstellungen wiederverwendet |
| `credit_usage_<account>.json` | `pplx-export usage-backfill` (`usage_backfill_cmd.py:17`) | Thread-bezogene Guthabennutzung (idempotent, fortsetzbar, alle 25 Einträge geleert) |
| `cron_snippet.txt` | `pplx-export schedule` (`scheduler.py:48-78`) | Cron-Aufruf-Snippet (absolute Pfade) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (`variant_log.py:76`) | zentrales Register für Antwort-Umschreibungsvarianten, dedupliziert nach (Thread, Eintrag), idempotent |
| `logs/` | `--log-file` (`common.py:218-229`) | vollständige DEBUG-Protokolle |

<a id="the-spaces-layer" data-pplx-source-anchor="true"></a>
## Die spaces/-Ebene

`pplx-export spaces` aggregiert `index/library_*.json` zu einem Bereichsindex (`spaces_cmd.py:259-389`):
ein `<slug>.md` pro Bereich (teilnehmende Konten, Besitzer/Mitglieder-Header, Thread-Tabelle,
Exportort-Rückverweise) plus ein `spaces.json`-Register.

!!! note "Ausgabeort"
    `spaces/` wird relativ zum aktuellen Arbeitsverzeichnis (`spaces_cmd.py:332`) geschrieben – es
    folgt **nicht** `--out`. Nicht manuell bearbeiten: Der nächste Neubau überschreibt.

<a id="cross-day-continuation-directory-migration-by-uuid-identity" data-pplx-source-anchor="true"></a>
## Tagesübergreifende Fortsetzung: Verzeichnismigration per UUID-Identität

Der Verzeichnisname enthält das `lastUpdated`-Datum. Wenn Sie einen Thread an einem späteren Tag
fortsetzen, ergibt die naive Berechnung ein *neues* Verzeichnis. Der Schreiber verhindert Duplikate durch UUID-Identität
(`thread_dir_for`, `fs_writer.py:58-72`):

1. **Finden**: `find_thread_dirs` (`fs_writer.py:74-105`) durchsucht das gesamte Archiv nach
   Verzeichnissen, die auf `_<uuid8>` enden – konten- und modusübergreifend. Ein Kandidat wird nur akzeptiert,
   wenn seine `thread.json` existiert, geparst werden kann und sein `web_uuid` exakt übereinstimmt; fehlende, beschädigte oder
   nicht übereinstimmende Verzeichnisse werden nie berührt (besser eine Migration auslassen als falsch zusammenzuführen).
2. **Zusammenführen**: `_merge_into` (`fs_writer.py:107-178`) führt das alte Verzeichnis in das neue zusammen –
   Vereinigung der Dateien (nichts Einzigartiges im alten Verzeichnis geht verloren); gleicher Name + gleicher Inhalt → überspringen;
   Namenskonflikte **behalten immer die Zielseite** (die semantisch neuere), jeder Konflikt wird protokolliert. Jede kopierte Datei wird sha256-verifiziert, bevor das alte Verzeichnis gelöscht wird; jeder
   Fehler lässt das alte Verzeichnis intakt und Wiederholungen sind idempotent.
3. **Historische Duplikate bereinigen**: `consolidate_uuid` (`fs_writer.py:180-209`) führt
   doppelte Datumsverzeichnisse einer UUID archivweit zusammen und behält das mit dem maximalen
   `lastUpdated` – die Absicherung für Duplikate, die von älteren Versionen hinterlassen wurden.

Dieselbe UUID-Strenge schützt die Bereichsindex-Rückverweise: Kandidatenverzeichnisse mit einer
fehlenden/beschädigten/nicht übereinstimmenden `thread.json` werden nie verlinkt.

<a id="hand-editable-vs-tool-managed" data-pplx-source-anchor="true"></a>
## Manuell bearbeitbar vs. tool-verwaltet

- **Tool-verwaltet (nicht manuell bearbeiten)**: alles in Thread-Verzeichnissen, plus `index/`,
  `spaces/` und `relations/`. Wenn der Inhalt falsch ist, reparieren Sie das Tool und generieren Sie neu – Darstellungskorrekturen
  erfolgen über `pplx-export re-render`, Datenkorrekturen über den passenden Backfill-Befehl
  (siehe [Wartungsbefehle](maintenance-commands.md)) – sodass jedes Artefakt aus Rohdaten reproduzierbar bleibt.
- **Manuell bearbeitbar**: die Dokumentation und die `web_archive/crosscheck/`-Überprüfungsberichte.
  Eine Ausnahme auf Benutzerebene: Eine manuell gerettete alternative Antwort kann als
  `rewritten_answer_variant.md` im Thread-Verzeichnis aufgezeichnet werden – siehe
  [Gesprächsmodi – Antwort-Umschreibungsvarianten](modes.md#answer-rewrite-variants-answer_variants).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Siehe auch

- [Gesprächsmodi](modes.md) – die fünf Modi und was jeder produziert
- [Inkrementelle Synchronisation](incremental-sync.md) – wie `lastUpdated` Re-Exporte steuert
- [Wartungsbefehle](maintenance-commands.md) – Neu-Darstellung, Backfills, sync-deleted
- [Datenmodell & Verzeichnisvertrag](../architecture/data-model.md) – die zugrundeliegenden Datenklassen
- [Export-Pipeline](../architecture/export-pipeline.md) – wie diese Dateien geschrieben werden
- [Offline-Operationen](../architecture/offline-operations.md) – alles aus `raw_*.json` neu erstellen
