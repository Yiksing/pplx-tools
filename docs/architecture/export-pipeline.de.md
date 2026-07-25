---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/export-pipeline.md"
translation_source_sha256: "d86951e600924ff10dbdbbad78ffb40dc1697fc719ff05c51781cf2d4e831a28"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# Export-Pipeline

---

<a id="export-pipeline-in-detail" data-pplx-source-anchor="true"></a>
## Export-Pipeline im Detail

Die vollständige Single-Thread-Export-Pipeline (`cmd_export`, export_cmd.py:42-86; der Batch-Pfad `cmd_batch`
verwendet dieselbe Pipeline, batch_cmd.py:117-204). Wichtige Funktionen und Zeilennummern in Klammern:

```mermaid
flowchart TD
    START(["thread URL / UUID"]) --> IDX

    subgraph S1["① indexing (pre-step of index / batch)"]
        IDX["GraphQLClient.list_threads<br/>(graphql.py:51)<br/>LibraryThreadsRelayQuery first page 25 items<br/>LibraryRecentThreadsPaginationQuery pagination<br/>stop when endCursor is empty (graphql.py:81-85)"]
        IDX --> IDXO[("index/library_&lt;account&gt;.json<br/>cmd_index (index_cmd.py:17)")]
    end

    subgraph S2["② incremental planning (batch only)"]
        PLAN["plan_incremental pure function<br/>(hooks/incremental.py:36)<br/>sorted by lastUpdated desc, four-state classification:<br/>new / updated / done / expired"]
        PLAN --> ES{"neither full nor force?"}
        ES -->|"yes"| TRIM["trim the longest trailing done/expired run<br/>(early stop, incremental.py:83-86)"]
        ES -->|"no"| KEEP["return item by item (full-scan fallback)"]
    end

    subgraph S3["③ fetching (adapter.get_thread)"]
        GT["PerplexityAdapter.get_thread<br/>(adapter.py:58)"]
        GT --> PLAIN["ThreadFetcher.get_thread<br/>plain response (rest.py:59)<br/>GET /rest/thread/uuid<br/>entries + background_entries<br/>cursor pagination ≤20 pages, 3s between pages (rest.py:43-57)"]
        DM{"detect_mode<br/>(normalize.py:66)<br/>mode detection after parse_turn, see §4"}
        DM -->|"computer / deep-research / council / study"| BLK["ThreadFetcher.get_thread_blocks<br/>schematized response (rest.py:67)<br/>8 SCHEMATIZED_USE_CASES (rest.py:26)<br/>sleep blocks_delay=4s before fetching (adapter.py:28,88)"]
        DM -->|"search (all signals present)"| NOBLK["skip blocks<br/>(search is simple query+answer)"]
        DM -->|"all-signals-missing fallback (adapter.py:84-87)<br/>mode=search and no entry has display_model"| BLK
        BLK --> ANOM["scan_wf_anomalies<br/>log.warning on any non-COMPLETED workflow<br/>(parsers.py:646; call site adapter.py:131-134)"]
    end

    subgraph S4["④ in-memory parsing and assembly (before persistence)"]
        PT["parse_turn × N (parsers.py:173)<br/>steps / three-channel citation collection<br/>(entry.sources + FINAL.web_results<br/>+ WORKFLOW_ITEM_SOURCES)<br/>report_info / locked_reason into metadata"]
        EA["extract_answer (parsers.py:80)<br/>FINAL.answer JSON → plan.goals fallback"]
        BASE["Base Conversation assembled in memory<br/>raw responses retained on conv._plain / conv._blocks"]
        ATT["attach_workflow_blocks (parsers.py:231)<br/>wf_block attached to turns by entry uuid<br/>wf_status into turn.metadata"]
        STUB["attach_stub_workflows (parsers.py:470)<br/>stub-turn 10s time-window matching"]
        UNC["collect_unconsumed_background<br/>(parsers.py:491) attribution waterfall ③"]
        READY["Conversation ready for export<br/>(adapter.py:91-157)"]
        BASE -->|"other modes"| READY
        BASE -->|"computer/council only<br/>(adapter.py:150-157)"| ATT
        ATT --> STUB
        STUB -.-> UNC
        UNC --> READY
    end

    subgraph S5["⑤ asset preparation (before writer)"]
        ADL["adapter.get_assets (adapter.py:196)<br/>collect_downloadable_assets (parsers.py:696)<br/>same-name multi-version numbered v1..vN by created_at"]
        CDN["CloudFront signed-URL direct download<br/>AssetDownloader.download_all (assets.py:80)<br/>resolve_ext three-source extension resolution (assets.py:122)"]
    end

    subgraph S6["⑥ persistence (fs_writer.write_thread)"]
        WJ[("thread.json (fs_writer.py:224-253)<br/>+ interruptions registration collect_interruptions (parsers.py:535)<br/>+ answer_variants registration collect_answer_variants (parsers.py:589)")]
        RAW1[("raw_entries.json<br/>retained plain response (fs_writer.py:257-261)")]
        RAW2[("raw_blocks.json<br/>retained schematized response (fs_writer.py:262-266)<br/>absent when blocks were not fetched")]
        WM[("conversation.md compact version<br/>render_conversation (render.py:641)")]
        WT[("turns/turn_NNNN.md full version<br/>render_turn (render.py:596)")]
        WS[("sources.json + sources.md<br/>(fs_writer.py:270-278)")]
        WR[("report.md (fs_writer.py:308-316)<br/>adapter.get_report fallback when needed")]
        MF[("assets/assets_manifest.json<br/>versioned manifest (fs_writer.py:320-330)")]
    end

    IDX --> S2
    S2 -->|"per-thread new/updated"| S3
    PLAIN --> PT
    PT --> EA
    EA --> DM
    ANOM --> BASE
    NOBLK --> BASE
    READY --> ADL
    ADL --> CDN
    CDN --> WJ
    WJ --> RAW1
    WJ -. "when blocks fetched" .-> RAW2
    RAW1 --> WS
    RAW1 -. "offline re-runnable<br/>(re-render, see offline-operations.md §12)" .-> PT
    WS --> WM
    WM --> WT
    WT --> WR
    WR --> MF
    MF --> DONE(["state.mark_ok<br/>BatchState checkpoint (state.py:123)"])
```

Wichtige Entwurfsentscheidungen:

1. **Rohe Antworten für Offline-Wiedergabe beibehalten**: `adapter.get_thread` parst und
   setzt die Konversation im Speicher zusammen, bevor `FilesystemWriter.write_thread`
   ausgeführt wird (adapter.py:58-157). Ein erfolgreicher Schreibvorgang speichert `thread.json` zuerst und
   dann die verfügbaren Plain-/Blocks-Antworten als `raw_*.json`
   (fs_writer.py:224-266); Parsing/Rendering kann später aus diesen Dateien erneut ausgeführt werden,
   ohne Netzwerkzugriff.
2. **Plain wird immer abgerufen; Blocks durch Moduserkennung**: Suche überspringt Blocks (spart eine Anfrage);
   wenn alle Erkennungssignale fehlschlagen, **holt der Fallback ebenfalls ab** (adapter.py:74-85 Kommentar und Entscheidung: besser übermäßig abrufen, als
   `raw_blocks.json` nach einer Plattformfeldänderung stillschweigend verschwinden zu lassen).
3. **Einheitlicher Parsing-Punkt**: alle Feldextraktion ist in `parsers.py` zentralisiert (`_g` mehrstufiger sicherer Zugriff parsers.py:23,
   `_loads` Fehlertoleranz parsers.py:33, `to_int` nachsichtiger Sortierschlüssel parsers.py:44) — bei Website-Überarbeitungen muss nur eine Stelle geändert werden.
4. **Writer ist schreibgeschützt**: das Einhängen von `wf_block`/`stub_wfs`/`unconsumed_bgs` erfolgt in
   `adapter.get_thread` (adapter.py:150-157); `FilesystemWriter` hängt nicht ein, sondern konsumiert nur
   (fs_writer.py:217 Kommentar).

---

<a id="mode-detection-decision-tree-detect_mode" data-pplx-source-anchor="true"></a>
## Moduserkennungs-Entscheidungsbaum (detect_mode)

Die vollständige Entscheidungslogik von `normalize.detect_mode` (normalize.py:66-128). Fünf Modi:
`computer / council / deep-research / study / search` (Suche ist der Standard).

Das Signal mit der höchsten Priorität ist das plattformautoritative Feld **`entry.search_mode`** (SEARCH_MODE_MAP,
normalize.py:50-59): offizielle Modellkonfiguration getestet (`GET /rest/models/config/v2`)
`default_models.search=pplx_pro` (UI "Best"), `default_models.research=pplx_alpha`
(UI "Deep Research"); search_mode-Werte werden eins-zu-eins auf Konversationsmodi abgebildet (Archivverifikation: 100+
SEARCH-Eintrag + pplx_alpha Threads sind zu 100 % search_mode=RESEARCH; 100+ reine pplx_pro Threads sind alle
SEARCH). Nur wenn search_mode vollständig fehlt, wird auf die ursprüngliche Schrittnamen- + display_model-Kette zurückgegriffen.

```mermaid
flowchart TD
    IN["Input: metadata + idx_thread + url<br/>+ turns + entries"] --> SMQ{"search_mode hit on any entry?<br/>(any over all entries, normalize.py:106-115)<br/>ASI→computer / AGENTIC_RESEARCH→council<br/>STUDY→study / RESEARCH→deep-research<br/>SEARCH/STUDIO→search"}
    SMQ -->|"hit"| MULTI{"multi-value conflict within thread?<br/>(mode switching, normalize.py:116-119)"}
    MULTI -->|"multiple values"| SPEC["take highest by specificity:<br/>computer &gt; council &gt; study<br/>&gt; deep-research &gt; search<br/>(_MODE_SPECIFICITY, normalize.py:63)<br/>+ log.warning"]
    MULTI -->|"single value"| SMCF{"conflict with downstream signals (step names/<br/>display_model)?<br/>(normalize.py:120-123)"}
    SPEC --> SMCF
    SMCF -->|"conflict"| SMWARN["log.warning recorded<br/>search_mode wins"]
    SMCF -->|"consistent or no downstream signal"| SMWIN["return the search_mode-mapped mode"]
    SMWARN --> SMWIN

    SMQ -->|"all absent"| Q1{"primary signal A: URL contains /computer/tasks/<br/>or metadata.mode == '4'<br/>or index mode ∈ ASI/COMPUTER?"}
    Q1 -->|"yes"| SM1["step_mode = computer"]
    Q1 -->|"no"| Q2{"primary signal B: a COUNCIL_RESEARCH step exists?"}
    Q2 -->|"yes"| SM2["step_mode = council"]
    Q2 -->|"no"| Q3{"primary signal C: a RESEARCH_ANSWER step exists?<br/>(content-based, not relying on Chinese labels)"}
    Q3 -->|"yes"| SM3["step_mode = deep-research"]
    Q3 -->|"no"| SM0["step_mode = (empty)"]

    SM1 --> DMS
    SM2 --> DMS
    SM3 --> DMS
    SM0 --> DMS

    subgraph DMS["fallback-chain redundant signal: display_model (DISPLAY_MODEL_MODE, normalize.py:32-37)"]
        DMQ{"display_model hit on any entry?<br/>(any over all entries, not just the first —<br/>the first entry of a mixed thread may not represent the whole)"}
        MAP["mapping table:<br/>pplx_agentic_research → council<br/>pplx_asi_opus → computer<br/>pplx_asi_opus_thinking → computer<br/>pplx_study → study"]
    end

    DMQ -->|"hit"| CF{"conflicts with step_mode?"}
    CF -->|"conflict"| WARN["log.warning records the conflict<br/>display_model wins"]
    CF -->|"consistent or step_mode empty"| DMWIN["return the display_model-mapped mode"]
    WARN --> DMWIN
    DMQ -->|"no hit"| FB{"step_mode non-empty?"}
    FB -->|"yes"| SMWIN2["return step_mode"]
    FB -->|"no"| SEARCH["return search (default)"]
```

Erkennungsdisziplin (getestete Grundlage):

- **`pplx_alpha` ist bewusst nicht in der Zuordnungstabelle** (normalize.py:15-31 Kommentar): es ist das RESEARCH-gewidmete Modell
  (`default_models.research`; UI fest, kein Auswahlfeld) — es ist das **Ziel, das dieser Klassifikator erkennen muss**,
  kein Erkennungshinweis. Die frühere Statistik "121 Such-Threads verwendeten pplx_alpha" waren tatsächlich Stichproben der eigenen
  Fehleinschätzung dieses Klassifikators (ohne das search_mode-Signal wurden RESEARCH-Sitzungen ohne RESEARCH_ANSWER-Schritt als
  Suche eingestuft) — durch search_mode neu bewertet und 124 Threads migriert.
- **search_mode gewinnt bei Konflikten mit nachgelagerten Signalen**: es ist die autoritative Aufzeichnung der Plattform über den Konversationsmodus;
  Schrittnamen sind die änderungsanfälligsten Oberflächenfelder der Plattform, display_model nur eine Modellebene-Aufzählung. Konflikte protokollieren immer
  log.warning (normalize.py:120-123).
- **Moduswechsel innerhalb eines Threads nimmt den höchsten nach Spezifität**: computer > council > study > deep-research >
  search (normalize.py:63, 116-119), mit log.warning.
- **Alle-Signale-fehlen schließt nicht auf Suche**: Rückfall auf den Pipeline-Ebenen-Blocks-Abruf (adapter.py:84-87),
  um sicherzustellen, dass schematisierte Daten aufgrund von Feldabweichungen nicht stillschweigend verschwinden.
