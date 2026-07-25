---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/offline-operations.md"
translation_source_sha256: "c813dedc53caddaa170728bac2152dadca3175bb204ddb9e0cdbca72d7907763"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="offline-operations" data-pplx-source-anchor="true"></a>
# Operazioni offline

Il lato a rete zero di `pplx_export`: rigenerazione offline da JSON grezzo, pipeline di ricostruzione delle relazioni, backfill di arricchimento degli indici, macchina a stati per la cancellazione remota e catena di rilevamento delle varianti di risposta. Le sezioni mantengono la loro numerazione originale dalla [panoramica dell'architettura](overview.md).

---

<a id="offline-regeneration-re-render" data-pplx-source-anchor="true"></a>
## Rigenerazione offline (re-render)

Dopo le correzioni al livello di rendering, rigenera tutti gli artefatti dal JSON grezzo **a rete zero**, in modo idempotente.
Implementazione: `commands/rerender_cmd.py` (single-thread `rerender` rerender_cmd.py:105-190;
batch `cmd_rerender` rerender_cmd.py:193-212).

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

Disciplina:

- **Rete zero**: `PerplexityAdapter(None)` riutilizza solo metodi puri di assemblaggio dati; nessun metodo
  online (get_thread, ecc.) viene mai chiamato.
- **Idempotente**: gli artefatti dipendono solo dal grezzo + renderer; le riesecuzioni sono byte-identiche
  (garantito dai test di regressione degli snapshot, [§13](../development/testing-architecture.md)).
- **Altri file non toccati**: sorgenti, report.md, asset rimangono invariati; thread.json è intoccato per impostazione predefinita —
  con `--thread-json` solo le due chiavi interruptions / answer_variants vengono aggiunte o rimosse.
- `--dry-run` elenca solo le directory senza scrivere file (rerender_cmd.py:204-206); `--limit N` prende i primi N.

---

<a id="relations-offline-rebuild-pipeline" data-pplx-source-anchor="true"></a>
## Pipeline offline di ricostruzione delle relazioni

`cmd_relations` (misc_cmd.py:16) ricostruisce il grafo delle relazioni delle conversazioni a livello di libreria dai
dati grezzi archiviati **a rete zero**: riutilizza la pipeline offline di ricostruzione del re-render
`load_archived_conversation` (rerender_cmd.py:34) per ripristinare ogni Conversazione (analisi/ordinamento/numerazione dei turni,
allegamento _plain/_blocks), riempie `conv.sub_agents` a livello di conversazione tramite
`adapter.sub_agents` thread per thread (misc_cmd.py:70-73; la pipeline di esportazione non esegue il backfill
 di questo campo, models.py:178-182); il fallback per le risposte computer (`wf_block_answer`) esegue il backfill di
`turn.answer` a questo livello, ampliando la superficie di scansione dei riferimenti (misc_cmd.py:74-79). I thread
senza dati grezzi degradano a un guscio thread.json + conversation.md (possono essere rilevati solo bordi same_space / bare-uuid,
misc_cmd.py:61-66).

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

Disciplina decisionale (2026-07-23): il meccanismo `branch_of` è confermato ma non ha istanze
nell'archivio — nessun bordo costruito; `related_query` non può essere analizzato dai dati esistenti — nessun bordo
costruito: meglio perdere un bordo che costruirne uno ipotetico.
Scala osservata: 772 bordi / 21 cluster nell'archivio (same_space 559 / subagent_of 154 /
same_prompt 49 / references 10).

---

<a id="search-mode-backfill-index-search_mode-enrichment" data-pplx-source-anchor="true"></a>
## search-mode-backfill (arricchimento search_mode dell'indice)

`cmd_search_mode_backfill` (search_mode_backfill_cmd.py:81) arricchisce il campo autorevole della piattaforma
`search_mode` in `index/library_<account>.json`: **prima il grezzo locale** (per i thread
archiviati, estratto da `entries[].search_mode` di raw_entries.json, rete zero); solo i thread
senza grezzo locale ricadono in un recupero online del thread. La scrittura unisce e preserva i campi
esistenti dell'indice (semantica di aggiornamento: le chiavi di arricchimento sovrascrivono, tutto il resto viene mantenuto), idempotente
e riprendibile, con `--limit` per sottoinsiemi.
Le righe di indice arricchite rendono autorevole il filtro `--mode` del batch:
`index_row_matches_mode` (batch_cmd.py:46) giudica prima in base a search_mode dell'indice
(SEARCH_MODE_MAP, normalize.py:50), ricadendo su euristiche solo quando è assente.

---

<a id="sync-deleted-remote-deletion-state-machine" data-pplx-source-anchor="true"></a>
## sync-deleted macchina a stati per cancellazione remota

`cmd_sync_deleted` (sync_deleted_cmd.py:262) identifica i thread "cancellati dall'utente/da remoto
sul lato piattaforma" e registra uno stato terminale, insieme a expired. La determinazione dei candidati
è un **diff di unione di tutti gli indici degli account**: un thread archiviato ok conta come candidato
solo quando è scomparso da **tutti** i file `index/library_*.json` (un export_via cross-account
appare solo nell'indice del suo proprietario, quindi un diff di un singolo account darebbe un falso positivo;
find_candidates, sync_deleted_cmd.py:148); gli indici mancanti/illeggibili vengono saltati in sicurezza con
la registrazione del motivo. Il dry-run offline predefinito elenca solo i candidati (nessuna rete, nessuna modifica
dei file); `--online` verifica thread per thread con GET: `ENTRY_DELETED` / `ENTRY_EXPIRED` /
404 → cancellazione confermata, `state.mark_deleted` (state.py:136) + un tombstone thread.json
(mark_thread_json_remote_deleted, sync_deleted_cmd.py:215).

```mermaid
stateDiagram-v2
    [*] --> ok : archived (batch_state = ok)
    ok --> candidate : gone from the union of all account indexes<br/>(find_candidates, sync_deleted_cmd.py:148)
    candidate --> skipped : index missing/unreadable<br/>safely skipped, reason recorded
    candidate --> listed : offline dry-run lists only<br/>(no network, no file changes)
    listed --> deleted : --online verifies one by one<br/>ENTRY_DELETED / ENTRY_EXPIRED / 404<br/>(_confirm_deleted, sync_deleted_cmd.py:247)
    deleted --> [*] : terminal mark_deleted (state.py:136) + thread.json tombstone<br/>plan_incremental trims it like expired<br/>(incremental.py:74-75, 84)
```

Stratificazione dei tipi di errore: `EntryDeletedError` eredita `EntryExpiredError` (il controllo per 400 con un
corpo contenente ENTRY_DELETED viene prima di ENTRY_EXPIRED, cookie_transport.py:93-98); il batch
deve catturare la sottoclasse prima della superclasse (batch_cmd.py:163-174 prima di 175-183), altrimenti deleted
verrebbe registrato erroneamente come expired. L'API di cancellazione stessa:
`DELETE /rest/thread/delete_thread_by_entry_uuid`
(read_write_token preso dal primo `entries[].read_write_token` non vuoto;
verificato in pratica 10/10 cancellazioni riuscite su thread di test auto-creati e thread dello spazio BOT).

---

<a id="the-answer_variants-answer-rewrite-variant-detection-chain" data-pplx-source-anchor="true"></a>
## La catena di rilevamento delle varianti di risposta answer_variants

Le varianti sostituite negli "esperimenti di riscrittura / A-B" della piattaforma sono invisibili dal lato
API — la risposta selezionata è visibile, mentre il fratello perdente lascia solo una traccia in
`entries[].side_by_side_metadata`, e può essere rimosso dalla piattaforma (i collegamenti a fratelli morti sono
provati: 403 VIEW_THREAD_NOT_ALLOWED + un reindirizzamento SPA alla home page; vedere
[il riferimento API §5.2](../reference/api/api-responses-errors.md)). La catena di rilevamento rende osservabile e tracciabile
"una riscrittura è avvenuta":

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

- **Criteri ristretti**: vengono accettati solo i segnali autorevoli di side_by_side_metadata;
  vengono registrati i campi di localizzazione completi (uuid completo del thread + uuid8, titolo,
  entry_uuid, sibling_uuid, selection_status, experiment_role) più le linee guida per la gestione; il formato è in
  `format_detection` (variant_log.py:53).
- **Idempotente**: il jsonl deduplica per (web_uuid, entry_uuid); le registrazioni duplicate dai percorsi
  online (source=online) e offline (source=offline) non producono righe duplicate; il re-render
  avverte solo quando il contenuto della variante cambia, quindi le riesecuzioni a livello di libreria non generano spam.
- **Flusso di gestione**: su un hit, confermare manualmente la risposta alternativa il prima possibile e
  registrarla (l'alternativa potrebbe essere rimossa dalla piattaforma e non può essere recuperata tramite API);
  il flusso completo è in [il riferimento API §5.2](../reference/api/api-responses-errors.md).
