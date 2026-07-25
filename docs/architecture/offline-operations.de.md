---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/offline-operations.md"
translation_source_sha256: "c813dedc53caddaa170728bac2152dadca3175bb204ddb9e0cdbca72d7907763"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="offline-operations" data-pplx-source-anchor="true"></a>
# Offline-Operationen

Die netzwerkfreie Seite von `pplx_export`: Offline-Regenerierung aus rohem JSON, die Relations-Neuerstellungspipeline, Index-Anreicherungs-Backfills, die Zustandsmaschine für Remote-Löschungen und die answer_variants-Erkennungskette. Die Abschnitte behalten ihre ursprüngliche Nummerierung aus der [Architekturübersicht](overview.md).

---

<a id="offline-regeneration-re-render" data-pplx-source-anchor="true"></a>
## Offline-Regenerierung (Neu-Rendering)

Nach Render-Ebene-Korrekturen alle Artefakte aus rohem JSON **ohne Netzwerk** idempotent regenerieren.
Implementierung: `commands/rerender_cmd.py` (Einzelthread `rerender` rerender_cmd.py:105-190;
Batch `cmd_rerender` rerender_cmd.py:193-212).

```mermaid
flowchart TD
    IN[("&lt;out&gt;/*/*/*/raw_entries.json<br/>glob all thread directories (rerender_cmd.py:199)")] --> CHK{"raw_entries.json exists?"}
    CHK -->|"no"| SKIP["skip (counted as skipped)"]
    CHK -->|"yes"| P1["parse_turn per entry (parsers.py:173)<br/>sort by created_us, re-number index<br/>(rerender_cmd.py:57-60)"]
    P1 --> P2["Conversation rebuilt<br/>metadata = thread_metadata (rerender_cmd.py:65-70)<br/>conv._plain = doc"]
    P2 --> P3{"raw_blocks.json exists?"}
    P3 -->|"yes"| P4["conv._blocks loaded (rerender_cmd.py:91)<br/>PerplexityAdapter(None).sub_agents builds sub_map<br/>(None-transport pure data assembly, rerender_cmd.py:84-88, 138)"]
    P3 -->|"no"| P5["sub_map = {}"]
    P4 --> P6{"mode in computer/council?"}
    P6 -->|"yes"| P7["attach_workflow_blocks (rerender_cmd.py:93)<br/>attach_stub_workflows (rerender_cmd.py:97)<br/>collect_unconsumed_background (rerender_cmd.py:101)"]
    P6 -->|"no"| P8
    P5 --> P8["render_conversation → conversation.md<br/>render_turn × N → turns/turn_NNNN.md<br/>(rerender_cmd.py:170, 189)"]
    P7 --> P8
    P8 --> TJ{"--thread-json?"}
    TJ -->|"no"| OUT(("done: other files untouched"))
    TJ -->|"yes"| TJ1["collect_interruptions(conv, sub_map) (rerender_cmd.py:150)<br/>answer_variants rebuilt with load_archived's same implementation (rerender_cmd.py:83)"]
    TJ1 --> TJ2{"compare the two keys<br/>interruptions / answer_variants<br/>against existing thread.json"}
    TJ2 -->|"content changed"| TJ3["add/remove the two keys in place, then write; all other fields kept as-is (round-trip indent=1)<br/>(rerender_cmd.py:141-169)<br/>warn + append jsonl registration when variants are added/changed<br/>(rerender_cmd.py:163-166, see §18)"]
    TJ2 -->|"no change"| TJ4["no write — avoids library-wide mtime/diff noise"]
```

Disziplin:

- **Kein Netzwerk**: `PerplexityAdapter(None)` verwendet nur reine Daten-Assembly-Methoden; keine Online-Methode (get_thread usw.) wird jemals aufgerufen.
- **Idempotent**: Artefakte hängen nur von Rohdaten + Renderer ab; Wiederholungsläufe sind byte-identisch (garantiert durch die Snapshot-Regressionstests, [§13](../development/testing-architecture.md)).
- **Andere Dateien unberührt**: Quellen, report.md, Assets bleiben unverändert; thread.json wird standardmäßig nicht berührt – mit `--thread-json` werden nur die beiden Schlüssel interruptions / answer_variants hinzugefügt oder entfernt.
- `--dry-run` listet nur Verzeichnisse auf, ohne Dateien zu schreiben (rerender_cmd.py:204-206); `--limit N` nimmt die ersten N.

---

<a id="relations-offline-rebuild-pipeline" data-pplx-source-anchor="true"></a>
## Relations-Offline-Neuerstellungspipeline

`cmd_relations` (misc_cmd.py:16) erstellt den bibliotheksweiten Konversationsbeziehungsgraphen aus archivierten Rohdaten **ohne Netzwerk** neu: Es verwendet die Offline-Neuerstellungspipeline von Re-Render `load_archived_conversation` (rerender_cmd.py:34), um jede Konversation wiederherzustellen (Zug-Parsing/Sortierung/Nummerierung, _plain/_blocks-Anhängung), füllt konversationsebene `conv.sub_agents` über `adapter.sub_agents` Thread für Thread (misc_cmd.py:70-73; die Export-Pipeline füllt dieses Feld nicht nach, models.py:178-182); der Computer-Antwort-Fallback (`wf_block_answer`) füllt `turn.answer` auf dieser Ebene nach und erweitert die Referenz-Scan-Oberfläche (misc_cmd.py:74-79). Threads ohne Rohdaten degradieren zu einer thread.json + conversation.md-Hülle (nur same_space / bare-uuid-Kanten können erkannt werden, misc_cmd.py:61-66).

```mermaid
flowchart LR
    RAW["web_archive/*/*/*/raw_entries.json<br/>+ raw_blocks.json"] --> LA["load_archived_conversation<br/>(rerender_cmd.py:34, zero network)"]
    LA --> SUB["adapter.sub_agents → conv.sub_agents<br/>(misc_cmd.py:70-73)"]
    LA --> FB["wf_block_answer backfills turn.answer<br/>(misc_cmd.py:74-79)"]
    SUB --> BE["build_edges (relations.py:200)"]
    FB --> BE
    BE --> SS["same_space: same space<br/>dst = space:&lt;slug&gt;"]
    BE --> SP["same_prompt: first-query normalized equality<br/>(normalize_query, relations.py:111)<br/>in-cluster chaining by created_us (not cliques)<br/>query_source distinguishes scheduled-task reruns<br/>from manual resends (parsers.py:209-215)"]
    BE --> RF["references: answer text / citation URLs<br/>referencing other archived threads (incl. bare uuids)"]
    BE --> SA["subagent_of: main thread → subagent run<br/>dst = toolu_X run id (not a thread uuid)<br/>archived subagent threads recorded in evidence"]
    SS --> OUT[("web_archive/relations/<br/>edges.jsonl + graph.md")]
    SP --> OUT
    RF --> OUT
    SA --> OUT
```

Entscheidungsdisziplin (2026-07-23): Der `branch_of`-Mechanismus ist bestätigt, hat aber keine Instanz im Archiv – keine Kanten erstellt; `related_query` kann nicht aus vorhandenen Daten geparst werden – ebenfalls keine Kanten erstellt: Lieber eine Kante verpassen, als eine geratene zu erstellen.
Beobachteter Umfang: 772 Kanten / 21 Cluster im gesamten Archiv (same_space 559 / subagent_of 154 / same_prompt 49 / references 10).

---

<a id="search-mode-backfill-index-search_mode-enrichment" data-pplx-source-anchor="true"></a>
## search-mode-backfill (Index search_mode-Anreicherung)

`cmd_search_mode_backfill` (search_mode_backfill_cmd.py:81) reichert das plattformautoritative Feld `search_mode` in `index/library_<account>.json` an: **zuerst lokale Rohdaten** (für archivierte Threads, extrahiert aus `entries[].search_mode` von raw_entries.json, kein Netzwerk); nur Threads ohne lokale Rohdaten fallen auf einen Online-Thread-Abruf zurück. Das Schreiben führt Zusammenführung durch und bewahrt vorhandene Indexfelder (Aktualisierungssemantik: Anreicherungsschlüssel überschreiben, alles andere bleibt erhalten), idempotent und fortsetzbar, mit `--limit` für Teilmengen.
Angereicherte Indexzeilen machen den Batch-Filter `--mode` autoritativ:
`index_row_matches_mode` (batch_cmd.py:46) urteilt zuerst nach Index search_mode
(SEARCH_MODE_MAP, normalize.py:50) und fällt nur dann auf Heuristiken zurück, wenn es fehlt.

---

<a id="sync-deleted-remote-deletion-state-machine" data-pplx-source-anchor="true"></a>
## sync-deleted Remote-Löschungs-Zustandsmaschine

`cmd_sync_deleted` (sync_deleted_cmd.py:262) identifiziert Threads, die "vom Benutzer/remote auf der Plattformseite gelöscht" wurden, und zeichnet einen Endzustand auf, zusammen mit abgelaufen. Die Kandidatenbestimmung ist ein **Union-of-all-Account-Indexes-Diff**: Ein archivierter ok-Thread zählt nur dann als Kandidat, wenn er aus **allen** `index/library_*.json`-Dateien verschwunden ist (ein Cross-Account-export_via-Thread erscheint nur im Index seines Besitzers, daher würde ein Einzelaccount-Diff falsch positiv sein; find_candidates, sync_deleted_cmd.py:148); fehlende/unlesbare Indizes werden sicher übersprungen, wobei der Grund aufgezeichnet wird. Der standardmäßige Offline-Trockenlauf listet nur Kandidaten (kein Netzwerk, keine Dateiänderungen); `--online` verifiziert Thread für Thread mit GET: `ENTRY_DELETED` / `ENTRY_EXPIRED` / 404 → Löschung bestätigt, `state.mark_deleted` (state.py:136) + ein thread.json-Grabstein (mark_thread_json_remote_deleted, sync_deleted_cmd.py:215).

```mermaid
stateDiagram-v2
    [*] --> ok : archived (batch_state = ok)
    ok --> candidate : gone from the union of all account indexes<br/>(find_candidates, sync_deleted_cmd.py:148)
    candidate --> skipped : index missing/unreadable<br/>safely skipped, reason recorded
    candidate --> listed : offline dry-run lists only<br/>(no network, no file changes)
    listed --> deleted : --online verifies one by one<br/>ENTRY_DELETED / ENTRY_EXPIRED / 404<br/>(_confirm_deleted, sync_deleted_cmd.py:247)
    deleted --> [*] : terminal mark_deleted (state.py:136) + thread.json tombstone<br/>plan_incremental trims it like expired<br/>(incremental.py:74-75, 84)
```

Fehlertyp-Schichtung: `EntryDeletedError` erbt von `EntryExpiredError` (die Prüfung auf 400 mit einem Rumpf, der ENTRY_DELETED enthält, erfolgt vor ENTRY_EXPIRED, cookie_transport.py:93-98); Batch muss die Unterklasse vor der Elternklasse abfangen (batch_cmd.py:163-174 vor 175-183), sonst würde gelöscht fälschlich als abgelaufen aufgezeichnet. Die Lösch-API selbst:
`DELETE /rest/thread/delete_thread_by_entry_uuid`
(read_write_token aus dem ersten nicht leeren `entries[].read_write_token` entnommen;
in der Praxis verifiziert: 10/10 Löschungen erfolgreich bei selbst erstellten Test-Threads und BOT-Space-Threads).

---

<a id="the-answer_variants-answer-rewrite-variant-detection-chain" data-pplx-source-anchor="true"></a>
## Die answer_variants-Antwort-Umschreibungs-Variantenerkennungskette

Varianten, die in der Plattform "Antwort-Umschreibung / A-B-Experimente" ersetzt wurden, sind auf der API-Seite unsichtbar – die ausgewählte Antwort ist sichtbar, während der verlierende Gegenpart nur eine Spur in `entries[].side_by_side_metadata` hinterlässt und von der Plattform gelöscht werden kann (tote Gegenpart-Links sind nachgewiesen: 403 VIEW_THREAD_NOT_ALLOWED + eine SPA-Weiterleitung zur Startseite; siehe [die API-Referenz §5.2](../reference/api/api-responses-errors.md)). Die Erkennungskette macht "eine Umschreibung ist passiert" beobachtbar und nachvollziehbar:

```mermaid
flowchart LR
    E["entries[].side_by_side_metadata<br/>narrowed criteria"] --> CAV["parsers.collect_answer_variants<br/>(parsers.py:589)"]
    CAV --> AD["adapter.get_thread warns on online hits<br/>(adapter.py:141-147)"]
    CAV --> RR["re-render offline rebuild<br/>warns only on additions/changes (rerender_cmd.py:163-166)"]
    AD --> LOG["variant_log.warn_detections (variant_log.py:65)<br/>single WARNING line ANSWER_VARIANT_DETECTED (variant_log.py:45)<br/>full locating fields + handling guidance, grep-able"]
    RR --> LOG
    AD --> TJ["thread.json.answer_variants registration<br/>(fs_writer.py:247-252)"]
    RR --> TJ
    TJ --> JSONL[("index/answer_variants_log.jsonl<br/>append_registry (variant_log.py:76)<br/>dedup by (web_uuid, entry_uuid), idempotent")]
    LOG --> B["batch summary surfaces ⚠ hit-thread count<br/>(batch_cmd.py:214-223)"]
    JSONL --> B
```

- **Eingeschränkte Kriterien**: Nur die autoritativen Signale von side_by_side_metadata werden akzeptiert; vollständige Lokalisierungsfelder werden aufgezeichnet (vollständige Thread-UUID + UUID8, Titel, entry_uuid, sibling_uuid, selection_status, experiment_role) plus Handhabungshinweise; das Format ist in `format_detection` (variant_log.py:53).
- **Idempotent**: Das JSONL dedupliziert nach (web_uuid, entry_uuid); doppelte Registrierungen aus dem Online- (source=online) und Offline-Pfad (source=offline) erzeugen keine doppelten Zeilen; Neu-Rendering warnt nur, wenn sich der Varianteninhalt ändert, sodass bibliotheksweite Wiederholungsläufe nicht spammen.
- **Handhabungsablauf**: Bei einem Treffer die alternative Antwort so schnell wie möglich manuell bestätigen und aufzeichnen (die Alternative kann von der Plattform gelöscht werden und ist über die API nicht wiederherstellbar); der vollständige Ablauf ist in [der API-Referenz §5.2](../reference/api/api-responses-errors.md).
