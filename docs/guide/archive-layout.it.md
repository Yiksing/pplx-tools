---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/archive-layout.md"
translation_source_sha256: "6302a47c60b6c8703d36f420cee6c18017110fcbb6127926eedb5c77e3e1f8e2"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="archive-layout" data-pplx-source-anchor="true"></a>
# Layout dell'archivio

Tutto ciò che `pplx-export` scarica finisce in un unico albero di output — `./web_archive/` per impostazione predefinita
(sovrascrivibile con `--out`). Questa pagina è una guida alla lettura di quell'albero: cosa sono ciascuna directory e file,
quali chiavi `thread.json` trasporta e come lo strumento mantiene una directory per thread quando una
conversazione prosegue per giorni. Tutto è generato dallo strumento; la profondità del meccanismo risiede in
[Modello dati e contratto delle directory](../architecture/data-model.md) e
[Pipeline di esportazione](../architecture/export-pipeline.md).

<a id="the-output-tree" data-pplx-source-anchor="true"></a>
## L'albero di output

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
## La directory del thread

Ogni thread riceve esattamente una directory, calcolata da `thread_dir_for` (`fs_writer.py:58-72`):

```
<account display name>/<mode>/<YYYY-MM-DD>_<title-slug>_<uuid8>/
```

| Componente | Fonte | Note |
|---|---|---|
| `<account display name>` | autore del thread, tramite `author_folder` → `_safe_folder` (`fs_writer.py:40-51`) | i separatori di percorso e i caratteri illegali in Windows (`:*?"<>\|`) diventano `_`; `.`/`..` rifiutati (protezione da path traversal per spazi condivisi); tutto il resto — inclusi gli spazi — viene mantenuto |
| `<mode>` | `detect_mode` | una delle cinque modalità; vedi [Modalità di conversazione](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` `lastUpdated` prefisso data | la data dell'ultimo aggiornamento della piattaforma, **non** la data di esportazione — si sposta quando un thread continuato viene aggiornato (vedi migrazione sotto) |
| `<title-slug>` | `slugify(title)` (`normalize.py:261-263`) | massimo 40 caratteri, caratteri non alfanumerici → `-`, vuoto → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | primi 8 caratteri dell'UUID del thread — l'ancora identitaria della directory |

<a id="files-in-a-thread-directory" data-pplx-source-anchor="true"></a>
## File in una directory del thread

<a id="threadjson-metadata-and-registries" data-pplx-source-anchor="true"></a>
### thread.json — metadati e registri

Scritto da `write_thread` (`fs_writer.py:224-253`). Chiavi sempre presenti:

| Chiave | Contenuto |
|---|---|
| `web_uuid` | entryUUID web — l'UUID nell'URL del thread; l'identità del thread |
| `psc_uuid` | `context_uuid` della piattaforma (nullable; dal primo turno non vuoto) — l'ID duale usato dagli indici degli spazi |
| `url` | URL canonico del thread |
| `title` | titolo del thread |
| `mode` | modalità rilevata (`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | nome visualizzato dell'autore dell'account |
| `export_via` | nome utente dell'account che ha eseguito l'esportazione — importante per thread di spazi condivisi esportati tramite un altro account |
| `space` | `{"uuid", "title", "slug"}` o `null` |
| `lastUpdated` | timestamp dell'ultimo aggiornamento della piattaforma (contratto di confronto macchina per sincronizzazione incrementale) |
| `threadAccess` | flag di accesso della piattaforma |
| `n_turns` | conteggio dei turni |
| `n_sources` | conteggio delle citazioni a livello di thread |
| `metadata` | `thread_metadata` dalla risposta API, testuale |
| `report_info` | `{"title", "file_name", "url"}` o `null` |
| `exported_at` | ora di esportazione (UTC ISO 8601) |

Chiavi opzionali — assenti quando non c'è nulla da registrare:

| Chiave | Aggiunta quando | Contenuto |
|---|---|---|
| `interruptions` | qualsiasi flusso di lavoro non completato (`fs_writer.py:242-244`) | elenco di `{location, kind, headline, status}`; vedi [Modalità di conversazione — Interruzioni](modes.md#interruptions-non-completed-workflows) |
| `answer_variants` | viene rilevata una variante di riscrittura della risposta (`fs_writer.py:247-252`) | `side_by_side_metadata` ristretto che individua i campi; vedi [Modalità di conversazione — Varianti di riscrittura della risposta](modes.md#answer-rewrite-variants-answer_variants) |
| `remote_deleted` | `pplx-export sync-deleted --online` conferma l'eliminazione remota | timestamp del tombstone, scritto in loco, idempotente (il valore esistente non viene mai sovrascritto; `sync_deleted_cmd.py:215-244`) — l'archivio locale viene mantenuto |

<a id="conversationmd-the-compact-read" data-pplx-source-anchor="true"></a>
### conversation.md — la lettura compatta

`render_conversation` (`render.py:641`): intestazione del titolo (modalità / autore / turni / conteggio citazioni),
poi per ogni turno una coppia `### Query` + `### Answer` con le risposte complete e — quando presente — l'appendice
delle attività in background a livello di thread alla fine. Questo è il file da aprire per primo; i processi
di lavoro per turno sono in `turns/`.

<a id="turnsturn_nnnnmd-the-full-read" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md — la lettura completa

`render_turn` (`render.py:596`): un file per turno (`turn_0001.md` …), ciascuno con il processo
di lavoro completo — passaggi, chiamate a strumenti, esecuzioni di sub-agent, tabelle, citazioni per turno. Quando il conteggio
dei turni di un thread diminuisce, i file `turn_*.md` obsoleti con numeri alti vengono eliminati, ma i file non toccati mantengono
il loro mtime (`fs_writer.py:287-301`).

### sources.json / sources.md

Citazioni a livello di thread, deduplicate per URL (`fs_writer.py:270-278`). `sources.json` è
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`; `sources.md` è lo stesso
eleco come elenco di link Markdown numerati.

### report.md

Il prodotto del report di Deep Research, scritto solo quando il thread ne contiene uno
(`fs_writer.py:308-316`): titolo del report, nome file originale del prodotto, quindi il report completo
in Markdown.

<a id="raw_entriesjson-raw_blocksjson-raw-fidelity" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json — fedeltà grezza

Le risposte API, persistite testualmente **prima** di qualsiasi analisi (`fs_writer.py:257-266`):

- `raw_entries.json` — la risposta semplice: `{"thread_metadata", "entries", "background_entries"}`.
  Sempre presente.
- `raw_blocks.json` — la risposta schematizzata, stessa forma. Assente per thread `search`
  (nessun fetch di blocchi); recuperata per le altre quattro modalità, e anche come fallback quando ogni
  segnale di rilevamento della modalità è assente.

Questi due file sono l'ancora di fedeltà dell'archivio: analisi, rendering e registri possono
tutti essere ricostruiti da essi offline, con zero traffico di rete. Vedi
[Operazioni offline](../architecture/offline-operations.md).

<a id="assets-products-and-their-manifest" data-pplx-source-anchor="true"></a>
### assets/ — prodotti e loro manifest

I prodotti scaricabili (file della modalità Computer e qualsiasi altra risorsa elencata dall'API) vengono recuperati
da URL firmati CloudFront in `assets/files/`; l'estensione viene decisa al momento del download
dal percorso URL, dai byte magici del contenuto o dal tipo di risorsa. `assets/assets_manifest.json`
(`fs_writer.py:320-330`) registra ogni versione:

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` è sempre il **numero totale di versioni** (Σ `len(versions)`), non il numero di gruppi
di file — usa `len(files)` per quello.

<a id="the-index-layer" data-pplx-source-anchor="true"></a>
## Il livello index/

`web_archive/index/` contiene stato e indici gestiti dallo strumento — non modificare a mano:

| File | Scritto da | Semantica |
|---|---|---|
| `library_<account>.json` | `pplx-export index` (`index_cmd.py:17-43`) | indice completo dei thread dell'account (GraphQL); input per indici batch / scheduling / spazio |
| `batch_state.json` | `BatchState` (`state.py`) | checkpoint riprendibile: uuid → stato (ok/error/expired/deleted) + lastUpdated; scritture atomiche; file corrotti salvati automaticamente come `.corrupt-<ts>` |
| `.cookies.json` | cache dei cookie (`common.py:111`, `common.py:150`) | cache dei cookie con freschezza di 12h con fonte ed email dell'account; scritto `0o600` poi sostituito atomicamente (credenziali di sessione, leggibile solo dal proprietario) |
| `space_<slug>.json` | `pplx-export space-index` (`spaces_cmd.py:106-167`) | elenco dei thread per spazio, incl. la mappatura ID duale `context_uuid` |
| `space_meta.json` | `pplx-export spaces --fetch-meta` (`spaces_cmd.py:299-330`) | cache dei proprietari/membri dello spazio riutilizzata nelle ricostruzioni |
| `credit_usage_<account>.json` | `pplx-export usage-backfill` (`usage_backfill_cmd.py:17`) | utilizzo crediti per thread (idempotente, riprendibile, scaricato ogni 25 voci) |
| `cron_snippet.txt` | `pplx-export schedule` (`scheduler.py:48-78`) | snippet di invocazione cron (percorsi assoluti) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (`variant_log.py:76`) | registro centrale delle varianti di riscrittura della risposta, deduplicato per (thread, entry), idempotente |
| `logs/` | `--log-file` (`common.py:218-229`) | log DEBUG completi |

<a id="the-spaces-layer" data-pplx-source-anchor="true"></a>
## Il livello spaces/

`pplx-export spaces` aggrega `index/library_*.json` in un indice dello spazio (`spaces_cmd.py:259-389`):
un `<slug>.md` per spazio (account partecipanti, intestazione proprietario/membro, tabella dei thread,
backlink alla posizione di esportazione) più un registro `spaces.json`.

!!! note "Posizione di output"
    `spaces/` viene scritto relativamente alla directory di lavoro corrente (`spaces_cmd.py:332`) — non
    segue `--out`. Non modificare a mano: la prossima ricostruzione lo sovrascrive.

<a id="cross-day-continuation-directory-migration-by-uuid-identity" data-pplx-source-anchor="true"></a>
## Continuazione tra giorni: migrazione della directory per identità UUID

Il nome della directory incorpora la data `lastUpdated`, quindi quando continui un thread in un giorno successivo
il calcolo ingenuo produce una directory *nuova*. Lo scrittore previene i duplicati tramite identità UUID
(`thread_dir_for`, `fs_writer.py:58-72`):

1. **Trova**: `find_thread_dirs` (`fs_writer.py:74-105`) cerca in tutto l'archivio le
   directory che terminano con `_<uuid8>` — cross-account e cross-modalità. Un candidato viene accettato solo
   se il suo `thread.json` esiste, viene analizzato e il suo `web_uuid` corrisponde esattamente; le directory
   mancanti, corrotte o non corrispondenti non vengono mai toccate (meglio saltare una migrazione che unire male).
2. **Unisci**: `_merge_into` (`fs_writer.py:107-178`) unisce la vecchia directory nella nuova —
   unione di file (nulla di unico nella vecchia directory viene perso); stesso nome + stesso contenuto → salta;
   conflitti di stesso nome **mantengono sempre il lato di destinazione** (quello semanticamente più recente), con ogni
   conflitto registrato. Ogni file copiato viene verificato con sha256 prima che la vecchia directory venga eliminata; qualsiasi
   fallimento lascia intatta la vecchia directory e i tentativi sono idempotenti.
3. **Pulisci duplicati storici**: `consolidate_uuid` (`fs_writer.py:180-209`) unisce
   le directory di data duplicate di un UUID nell'intero archivio, mantenendo quella con il max
   `lastUpdated` — la rete di sicurezza per i duplicati lasciati da versioni precedenti.

La stessa rigorosità UUID protegge i backlink dell'indice dello spazio: le directory candidate con un
`thread.json` mancante/corrotto/non corrispondente non vengono mai collegate.

<a id="hand-editable-vs-tool-managed" data-pplx-source-anchor="true"></a>
## Modificabile a mano vs gestito dallo strumento

- **Gestito dallo strumento (non modificare a mano)**: tutto all'interno delle directory dei thread, più `index/`,
  `spaces/` e `relations/`. Se il contenuto è sbagliato, correggi lo strumento e rigenera — le correzioni
  di rendering passano attraverso `pplx-export re-render`, le correzioni dei dati attraverso il comando di backfill corrispondente
  (vedi [Comandi di manutenzione](maintenance-commands.md)) — così ogni artefatto rimane riproducibile
  dai dati grezzi.
- **Modificabile a mano**: la documentazione e i report di revisione `web_archive/crosscheck/`.
  Un'eccezione a livello utente: una risposta alternativa recuperata manualmente può essere registrata come
  `rewritten_answer_variant.md` all'interno della directory del thread — vedi
  [Modalità di conversazione — Varianti di riscrittura della risposta](modes.md#answer-rewrite-variants-answer_variants).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Vedi anche

- [Modalità di conversazione](modes.md) — le cinque modalità e cosa produce ciascuna
- [Sincronizzazione incrementale](incremental-sync.md) — come `lastUpdated` guida le riesportazioni
- [Comandi di manutenzione](maintenance-commands.md) — re-render, backfill, sync-deleted
- [Modello dati e contratto delle directory](../architecture/data-model.md) — le dataclass sottostanti
- [Pipeline di esportazione](../architecture/export-pipeline.md) — come vengono scritti questi file
- [Operazioni offline](../architecture/offline-operations.md) — ricostruire tutto da `raw_*.json`
