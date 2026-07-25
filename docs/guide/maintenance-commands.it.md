---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/maintenance-commands.md"
translation_source_sha256: "550aca319a6386123658e8d54ede5367bc97765c9a11710e20f1ed1f2854f617"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintenance-commands" data-pplx-source-anchor="true"></a>
# Comandi di manutenzione

I sottocomandi di manutenzione di `pplx-export` mantengono in salute un archivio esistente: ri-rendono le pagine dopo correzioni al renderer, riempiono asset/crediti/metadati delle modalità, contrassegnano thread eliminati da remoto e ricostruiscono il grafo delle relazioni. La maggior parte sono offline-first; le loro fasi online seguono la stessa disciplina di pacing di `batch` (vedi [rate-limiting.md](rate-limiting.md)). Tutti accettano le [opzioni comuni](pplx-export.md) (`--account`, `--out`, `--cookies-from`, `--transport`, …).

- Principio di conservazione dell'archivio locale: nessun comando di manutenzione elimina o sposta il contenuto dei thread archiviati — l'archivio è il backup.
- I comandi offline (`re-render`, `relations`, `sync-space`, `spaces` senza `--fetch-meta` e le fasi predefinite sotto) non necessitano di alcun trasporto; vedi [../architecture/offline-operations.md](../architecture/offline-operations.md).

## re-render

Rigenera `conversation.md` e `turns/` dal JSON grezzo archiviato (`raw_entries.json` / `raw_blocks.json`) dopo correzioni al renderer — zero rete, e ogni altro file viene lasciato intatto.

| Flag | Significato | Predefinito |
|---|---|---|
| `--limit N` | Elabora solo le prime N directory di thread | tutte |
| `--dry-run` | Elenca le directory che verrebbero elaborate, non scrive nulla | disattivato |
| `--thread-json` | Aggiunge/rimuove anche le chiavi `interruptions` e `answer_variants` in `thread.json` sul posto | disattivato |

Comportamenti chiave:

- Ricostruisce i turni offline con la stessa pipeline dell'esportazione: parsing, ordinamento per `created_us`, deduplicazione delle citazioni e — per computer/council — blocchi di workflow, mappatura dei sub-agent e appendice dello sfondo non consumato.
- Solo `conversation.md` e `turns/turn_*.md` vengono (ri)scritti; `sources*`, `assets/`, `report.md` e `thread.json` rimangono invariati. I file `turn_*.md` obsoleti numerati sopra il conteggio dei turni corrente vengono eliminati — nient'altro, quindi i file invariati mantengono il loro mtime.
- `--thread-json` scrive solo quando il contenuto cambia effettivamente; gli `answer_variants` appena aggiunti/modificati generano un avviso `ANSWER_VARIANT_DETECTED` e vengono aggiunti a `index/answer_variants_log.jsonl` (le esecuzioni idempotenti non generano spam).
- Le directory di thread senza `raw_entries.json` vengono saltate e conteggiate.

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

Rimedia agli asset archiviati senza un URL firmato — tre rimedi graduali: recupero dei blocchi mancanti, estrazione inline offline e aggiornamento online opzionale.

| Flag | Significato | Predefinito |
|---|---|---|
| `--fetch-blocks` | Prima recupera i `raw_blocks.json` mancanti e i relativi asset con URL firmato (online) | disattivato |
| `--online` | Abilita l'aggiornamento online degli asset mancanti/obsoleti | disattivato (solo estrazione inline offline, zero richieste) |
| `--limit N` | Elabora solo le prime N directory di thread | tutte |

Comportamenti chiave:

- Fase predefinita (offline, zero richieste): estrae gli asset inline (`ASSET_DIFF` / `CODE_ASSET`) da `raw_blocks.json` in `assets/files/*.md` e registra i tipi di handle del workspace cloud (`DOC_FILE` / `CODE_FILE` / `UNKNOWN` — nessun canale di download ancora) in `assets/assets_manifest.json`. Idempotente: i record noti vengono deduplicati per uuid, poi file_handle; i file con stesso nome e più versioni ottengono un suffisso breve di uuid in modo che le esecuzioni successive non collidano.
- `--fetch-blocks` (online): recupera i `raw_blocks.json` mancanti per i thread deep-research/computer/council/study più i loro asset scaricabili; i thread sono raggruppati per cartella account con un adattatore costruito lazy per account (i cookie cambiano automaticamente), 3 secondi tra i thread.
- `--online`: per le versioni del manifest il cui `downloaded_to` è mancante/obsoleto, recupera un nuovo URL firmato tramite `/rest/assets/<uuid>/data` (chiamate API seriali, a 3 secondi di distanza), poi riscarica dal CDN (6 thread concorrenti, nessun ritardo — CDN, non API). Un 404 `ASSET_NOT_FOUND` imposta il flag terminale `asset_expired`; un 403 cross-account viene ritentato una volta con l'account che possiede la cartella dell'archivio.
- Il `count` del manifest viene ricalcolato come numero totale di versioni ad ogni riscrittura.

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

Riempie l'utilizzo del credito per thread (`credits/thread-usage`) per tutti i thread archiviati dell'account in `index/credit_usage_<account>.json`.

| Flag | Significato | Predefinito |
|---|---|---|
| `--limit N` | Elabora solo i primi N thread | tutti |

Comportamenti chiave:

- Una GET per thread archiviato (`thread_id` = il `psc_uuid` del thread), a 3 secondi di distanza; idempotente — i thread già presenti nel file di output vengono saltati.
- Un 403 (`thread_usage_forbidden`, cioè un thread cross-account) viene registrato come `error` e mai ritentato; altri fallimenti vengono lasciati per l'esecuzione successiva. Il progresso viene salvato ogni 25 thread elaborati.
- Multi-account: esegui una volta per account con `--account` — i cookie cambiano automaticamente tra le esecuzioni.

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

Riempie il campo `search_mode` autorevole della piattaforma in ogni riga di `index/library_<account>.json`, in modo che `batch --mode` possa filtrare esattamente invece di affidarsi a euristiche.

| Flag | Significato | Predefinito |
|---|---|---|
| `--limit N` | Elabora solo le prime N righe in sospeso | tutte |
| `--offline` | Solo estrazione locale — le righe senza dati grezzi locali aspettano il giro successivo, nessun fallback online | disattivato |
| `--delay-min SEC` | Limite inferiore dell'intervallo casuale tra i thread di fallback online | `10` |
| `--delay-max SEC` | Limite superiore dell'intervallo casuale tra i thread di fallback online | `20` |

Comportamenti chiave:

- Memorizza il valore grezzo della piattaforma (`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…); un thread con più valori mantiene il più specifico secondo computer > council > study > deep-research > search.
- Prima locale: i thread archiviati vengono risolti da `raw_entries.json` con zero rete — un'esecuzione completamente locale non costruisce mai un trasporto (nemmeno un probe di sessione).
- Fallback online solo per righe senza dati grezzi locali: `GET /rest/thread/<uuid>` con un intervallo casuale di 10–20 secondi; le righe nello stato terminale `expired` vengono saltate e registrate; i thread trovati appena scaduti/eliminati online vengono contrassegnati in `batch_state.json` per risparmiare richieste future.
- Idempotente e riprendibile: le righe che hanno già `search_mode` vengono saltate, il progresso viene salvato ogni 25 righe, e successivi `index` aggiornamenti preservano l'arricchimento (uniti da `entryUUID`).

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

Identifica i thread che sono scomparsi dalla libreria remota (eliminati dall'utente o dalla piattaforma) e li contrassegna — non elimina né sposta mai alcun file di archivio.

| Flag | Significato | Predefinito |
|---|---|---|
| `--online` | Verifica ogni candidato online | disattivato (dry-run offline: elenca solo i candidati) |
| `--limit N` | Elabora solo i primi N candidati | tutti |
| `--delay-min SEC` | Limite inferiore dell'intervallo casuale tra i candidati | `10` |
| `--delay-max SEC` | Limite superiore dell'intervallo casuale tra i candidati | `20` |

Comportamenti chiave:

- Il rilevamento dei candidati è offline e cross-account: un thread con stato `batch_state` `ok` che manca dall'unione `entryUUID` di **tutti** i file `index/library_*.json` diventa un candidato — qualsiasi singolo indice che lo contiene conta come vivo, quindi i thread esportati cross-account tramite spazi condivisi non vengono falsi positivi. Quando non esiste un indice utilizzabile, tutto viene saltato in sicurezza con un suggerimento di eseguire prima `index`.
- Il predefinito è un dry-run offline: elenca i candidati e le ragioni di skip sicuro — zero rete, zero scritture.
- `--online` verifica ogni candidato con `GET /rest/thread/<uuid>` sotto l'account registrato in `thread.json` `export_via` (i cookie cambiano automaticamente per candidato).
- Confermato da `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 → `batch_state` segna lo stato terminale `deleted` (stessa semantica di `expired`: mai ritentato, `--force` non riesporta; vedi [incremental-sync.md](incremental-sync.md)) e ogni file `thread.json` del thread riceve un timestamp `remote_deleted` sul posto (idempotente — una chiave esistente viene mantenuta).
- Il thread esiste ancora → falso positivo: segnalato così com'è con un suggerimento di eseguire di nuovo `index`, nulla è cambiato. Gli errori di trasporto rimandano al giro successivo; 3 fallimenti di autenticazione consecutivi interrompono l'esecuzione prima che qualcosa venga contrassegnato erroneamente.

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

La prima esecuzione elenca i candidati (dry-run offline); la seconda li verifica online e contrassegna quelli confermati.

## status

Stampa lo stato dell'account dell'archivio e il piano di modifica incrementale — zero rete, sola lettura. Risponde a "com'è l'archivio in questo momento e cosa farebbe la prossima esecuzione di `batch`" senza toccare la rete.

| Flag | Significato | Predefinito |
|---|---|---|
| `--account X` | Segnala su un solo account | tutti gli account che hanno un file `index/library_*.json` |
| `--json` | Report completo machine-readable su stdout (ignora la verbosità) | disattivato (righe di log umane) |

Comportamenti chiave:

- Le fonti dati sono puramente locali: `index/library_*.json` (righe indice per account) e `index/batch_state.json` (l'unica fonte degli stati di esportazione). La classificazione delle modifiche riutilizza la stessa funzione pura `plan_incremental` di `batch`/`schedule`, quindi le semantiche di `new`/`updated`/`done`/`expired`/`deleted` sono identiche a quelle che `batch` calcolerebbe.
- L'output INFO predefinito stampa una riga di riepilogo per account (conteggio indice + freschezza, conteggi stato `ok/expired/deleted/error`, conteggi modifica `new/updated` e il numero di early-stop) più una riga globale dell'account `batch_state` (es. `559 ok + 13 expired + 12 deleted`).
- I livelli di dettaglio seguono il flag di verbosità standard: `-v` aggiunge i titoli dei thread `new`/`updated`/`error` (prima riga, troncata a 60 caratteri); `-vv` aggiunge i thread `done`/`expired`/`deleted` con `lastUpdated`/`exported_at`; `-vvv` stampa tutto senza troncamento con i campi dell'indice `mode`/`search_mode` e l'elenco solo-stato (record presenti in `batch_state` ma mancanti dall'indice di ogni account — candidati alla rimozione remota da riconciliare con [sync-deleted](#sync-deleted)).
- Protezioni: un `index/` mancante o un file di libreria mancante esce con un errore che punta a `pplx-export index`; un `batch_state.json` mancante viene trattato come uno stato vuoto (tutto conta come `new`). Non è richiesta alcuna configurazione a livello utente — gli account vengono enumerati dai nomi dei file di libreria.
- `--json` emette il report completo (account, modifiche, thread, solo-stato, totali) come JSON su una riga su stdout — lo stesso stile di contratto di `pplx-ask`.

```bash
pplx-export status                 # summary for every account
pplx-export status -vv             # five-state thread details
pplx-export status --account alice --json
```

## relations

Ricostruisce il grafo delle relazioni di conversazione dai thread esportati → `relations/edges.jsonl` più un `relations/graph.md` leggibile dall'uomo sotto la radice dell'archivio.

| Flag | Significato | Predefinito |
|---|---|---|
| *(solo opzioni comuni; solo `--out` è rilevante)* | | |

Comportamenti chiave:

- Puramente offline, zero rete, sola lettura sull'archivio: riutilizza la pipeline di ricostruzione offline di re-render (`raw_entries.json` / `raw_blocks.json`), quindi `sub_agents`, `query_source` e i segnali di citazione sono tutti disponibili per il rilevamento degli archi.
- I thread senza dati grezzi degradano a un guscio `thread.json` + `conversation.md` — solo gli archi di riferimento `same_space` e bare-uuid possono attivarsi per loro.

```bash
pplx-export relations
```

## debug-js

Esegue uno snippet JavaScript nel contesto della pagina del browser corrente tramite il demone WebBridge locale (`127.0.0.1:10086`) e stampa il risultato come JSON — un portello di fuga per debug.

| Flag | Significato | Predefinito |
|---|---|---|
| `JS代码` (posizionale) | Codice JavaScript da valutare nel contesto della pagina (il metavar letterale di argparse) | obbligatorio |

Comportamenti chiave:

- Richiede che il demone WebBridge sia raggiungibile e che la pagina Perplexity di destinazione sia aperta nel browser; lo snippet viene eseguito con la sessione propria della pagina.
- Il JSON stampato è troncato a 5000 caratteri.

```bash
pplx-export debug-js 'document.title'
```
