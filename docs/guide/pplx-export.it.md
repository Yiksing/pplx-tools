---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/pplx-export.md"
translation_source_sha256: "6ef4d5b78ce748c1fd97d6d1dfaea40f0bdfd427f23a089b6110c2fb0e4f9c53"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` è la CLI di archiviazione: recupera gli indici delle conversazioni da Perplexity, esporta i thread nell'archivio locale e mantiene le viste derivate (indice spazio, snippet cron). Questa pagina copre i sottocomandi di acquisizione — `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule` — più il comando di configurazione una tantum `init`. I sottocomandi di backfill/riparazione si trovano in [maintenance-commands.md](maintenance-commands.md); la CLI di interrogazione è trattata in [pplx-ask.md](pplx-ask.md).

<a id="common-options" data-pplx-source-anchor="true"></a>
## Opzioni comuni

Ogni sottocomando accetta questi flag (definiti una volta in `pplx_export/commands/common.py`):

| Flag | Significato | Predefinito |
|---|---|---|
| `--account NAME` | Account di destinazione. Quando l'email del cookie non corrisponde all'email registrata, i token di sessione del browser per account vengono enumerati per passare automaticamente | `default_account` dalla configurazione a livello utente |
| `--config PATH` | File di configurazione a livello utente (registro account). Priorità: `--config` > env `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | catena di ricerca predefinita |
| `--site NAME` | Adattatore sito | `perplexity` |
| `--out DIR` | Directory di output dell'archivio | `./web_archive` |
| `--cookies-from BROWSER` | Importa cookie da un browser (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | File cookie Netscape o file cookie JSON | — |
| `--transport MODE` | `cookie` = richieste dirette con cookie; `webbridge` = recupero nel contesto della pagina del browser | `cookie` |
| `-v`, `--verbose` | Output DEBUG (tracce delle richieste, decisioni interne); ripetibile | off |
| `--log-file [PATH]` | Scrivi il log completo su disco; senza valore, percorso automatico `<out>/index/logs/<cmd>-<timestamp>.log` | off |

- `--cookies-from` / `--cookies` si escludono a vicenda con `--transport webbridge` — il bridge viene eseguito nel contesto della pagina e trasporta già i cookie del browser.
- `pplx-export --version` stampa la versione del pacchetto ed esce (solo a livello superiore, non un flag di sottocomando).
- Registrazione account, fonti dei cookie e commutazione multi-account: [configuration.md](configuration.md). Dove finisce tutto su disco: [archive-layout.md](archive-layout.md).

## init

Scopri gli account dai cookie del browser e scrivi la configurazione a livello utente — l'alternativa automatica alla copia manuale di `config.example.toml` (vedi [configuration.md](configuration.md)).

| Flag | Significato | Predefinito |
|---|---|---|
| `--force` | Sovrascrivi un file di configurazione esistente | off (rifiuta di sovrascrivere) |
| `--create-bot-space [TITLE]` | Crea lo spazio BOT tramite API quando nessun titolo spazio corrisponde (un'operazione di scrittura sull'account); un TITLE esplicito guida sia la corrispondenza che la creazione, altrimenti il titolo proviene da `--bot-title`; senza questo flag `[bot_space]` viene scritto vuoto | off |
| `--bot-title TITLE` | Titolo spazio utilizzato sia per corrispondere a uno spazio esistente che per nominarne uno creato | `BOT` |
| *(si applicano le opzioni comuni)* | I flag della fonte dei cookie scelgono dove scoprire gli account; per `init` solo, `--config` è il percorso di **scrittura** (il caricamento rigoroso della configurazione viene saltato) | |

Comportamenti chiave:

- Enumerazione token: i cookie di sessione per account (`__Secure-pplx.session.<uid>`) vengono raccolti dagli archivi del browser — o, con `--cookies FILE`, scansionati dal file cookie (un'esportazione completa può contenere diversi account). Senza token enumerabili, viene sondata solo la sessione attualmente attiva.
- Sondaggio sessione: ogni token viene provato contro `GET /api/auth/session` per apprendere l'email/nome visualizzato dell'account; i token che falliscono o non restituiscono email vengono saltati con un avviso.
- Assemblaggio registro: ogni chiave account deriva dalla parte locale dell'email (le collisioni ottengono suffissi `-2`/`-3`…); `default_account` è impostato sull'account attualmente attivo, altrimenti sul primo scoperto.
- Spazio BOT: uno spazio viene abbinato per titolo esatto (senza distinzione tra maiuscole e minuscole) tramite `list_user_collections`; quando non c'è corrispondenza, `--create-bot-space [TITLE]` lo crea sul momento (un TITLE esplicito sovrascrive `--bot-title` sia per la corrispondenza che per la creazione), altrimenti `[bot_space]` viene lasciato vuoto.
- Il TOML viene scritto atomicamente (file temporaneo + rinomina) con permessi 0600, e un file esistente non viene mai sovrascritto senza `--force`. Il comando termina con una riga JSON di riepilogo: percorso configurazione, chiavi account, account predefinito, uuid/slug spazio BOT.
- `--transport webbridge` viene rifiutato — il canale del contesto pagina non può enumerare i token per account.

```bash
pplx-export init                          # write the default ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --config /path/to/config.toml --force   # custom path, overwrite allowed
```

## index

Recupera l'elenco completo delle conversazioni dell'account (GraphQL) e scrive l'indice principale `index/library_<account>.json` — la baseline rispetto a cui ogni altro comando fa diff.

| Flag | Significato | Predefinito |
|---|---|---|
| *(solo opzioni comuni)* | | |

Comportamenti chiave:

- Preserva l'arricchimento `search_mode` scritto da `search-mode-backfill`: le righe dell'indice non lo portano nativamente, quindi all'aggiornamento viene riunito dal vecchio indice tramite `entryUUID`.
- Eseguilo prima di `batch`, `sync-space` e `sync-deleted` — i loro diff sono freschi solo quanto questo indice.

```bash
pplx-export index --account alice
```

## space-index

Estrai l'elenco "Tutto" delle conversazioni di uno spazio — inclusi i thread condivisi da altri membri — in `index/space_<slug>.json`.

| Flag | Significato | Predefinito |
|---|---|---|
| `SPACE_URL` (posizionale) | URL della pagina spazio | obbligatorio |
| `--transport webbridge` | Usa il percorso legacy di rendering del browser invece di REST | `cookie` (REST diretto) |

Comportamenti chiave:

- Il percorso predefinito è REST diretto: `list_collection_threads` sul trasporto cookie con paginazione offset; le righe includono `context_uuid` e `answer_preview`.
- Con `--transport webbridge` torna a scorrere la pagina spazio renderizzata e raschiare le proprietà delle righe — un backup nel caso la struttura REST cambi.
- Le righe vengono scritte dalla più recente alla più vecchia tramite `lastUpdated`.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

Esporta un singolo thread (URL o UUID nudo) nella sua directory di archivio `<out>/<account-folder>/<mode>/<thread-dir>/`.

| Flag | Significato | Predefinito |
|---|---|---|
| `THREAD` (posizionale) | URL thread o UUID | obbligatorio |
| `--force` | Riesporta anche quando `lastUpdated` è invariato | off |

Comportamenti chiave:

- Se la copia archiviata è già aggiornata, l'esportazione viene saltata senza scritture; `--force` sovrascrive il controllo.
- `lastUpdated` viene preso dall'indice della libreria locale quando il thread è elencato lì (stessa semantica e formato di `batch`), ricadendo al valore della piattaforma altrimenti.
- Gli stati terminali vengono registrati con garbo, senza traceback: `ENTRY_DELETED` segna `deleted` in `batch_state.json`, `ENTRY_EXPIRED` segna `expired` — l'archivio locale esistente viene comunque mantenuto intatto.
- Un'esportazione riuscita scrive `ok` in `index/batch_state.json`, così il piano incrementale conta il thread come "esportato e invariato".
- Cosa finisce nella directory del thread: [archive-layout.md](archive-layout.md); la pipeline di esportazione stessa: [../architecture/export-pipeline.md](../architecture/export-pipeline.md).

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

Esporta in blocco i thread di un account — il driver quotidiano, con arresto anticipato incrementale e checkpoint riprendibili.

| Flag | Significato | Predefinito |
|---|---|---|
| `--force` | Riesporta tutti i thread (stati terminali esclusi) | off |
| `--full` | Scansione completa: i thread invariati vengono comunque saltati, ma nessun arresto anticipato | off |
| `--limit N` | Elabora solo le prime N righe dell'elenco (dalla più recente) | tutti |
| `--mode MODE` | Esporta solo thread `search` / `deep-research` / `computer` / `council` / `study` | tutte le modalità |
| `--delay-min SEC` | Limite inferiore dell'intervallo casuale tra i thread | `10` |
| `--delay-max SEC` | Limite superiore dell'intervallo casuale tra i thread | `20` |

Comportamenti chiave:

- Richiede `index/library_<account>.json` — esegui prima `index`.
- **Arresto anticipato incrementale** predefinito: l'elenco è ordinato dalla più recente e la sequenza finale di thread "esportati e invariati" viene tagliata interamente; i buchi lasciati da esecuzioni interrotte (errore/mai esportati) si trovano sopra quel suffisso e vengono comunque riparati. `--full` disabilita l'arresto anticipato (backstop periodico, o quando si sospettano buchi nell'archivio); `--force` riesporta tutto tranne gli stati terminali, che non vengono mai riprovati. Semantica completa: [incremental-sync.md](incremental-sync.md).
- Filtraggio `--mode`: le righe che portano `search_mode` (il campo autorevole della piattaforma arricchito da `search-mode-backfill`) corrispondono esattamente tramite `SEARCH_MODE_MAP` — su quel percorso `--mode search` non include più thread deep-research/council/study. Le righe senza `search_mode` ricadono su euristiche dell'indice: `computer` = modalità `COMPUTER`; `deep-research` = displayModel `pplx_alpha`; `council` = `pplx_agentic_research`; `study` = `pplx_study`; `search` = le restanti righe modalità-`SEARCH` (incluse quelle tre tipologie — filtralle esportando separatamente le modalità specifiche).
- Lo stato viene salvato in `index/batch_state.json` dopo ogni thread — interrompi e riesegui liberamente.
- Auth fail-fast: 3 risposte 401/403 consecutive interrompono l'esecuzione (un cookie scaduto non può auto-ripararsi, e continuare fallirebbe centinaia di thread uno per uno).
- Ritmo: una pausa casuale `--delay-min`–`--delay-max` tra i thread; 429/5xx vengono gestiti con backoff dal livello di trasporto. Dettagli: [rate-limiting.md](rate-limiting.md).
- I thread che incontrano varianti di risposta riscritte vengono registrati in `index/answer_variants_log.jsonl` con un avviso per gestirli manualmente il prima possibile (vedi [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md)).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

Ricostruisci l'indice della vista spazio — una pagina Markdown per spazio più un registro `spaces.json` — dagli indici della libreria locale.

| Flag | Significato | Predefinito |
|---|---|---|
| `--fetch-meta` | Aggiorna i metadati proprietario/membro prima di ricostruire | off |

Comportamenti chiave:

- Senza `--fetch-meta` il comando è puramente locale (zero rete): aggrega i thread per slug spazio attraverso tutti i file `library_*.json`, con statistiche degli account partecipanti e backlink alle directory dei thread esportati.
- L'output va in `./spaces/` relativo alla directory di lavoro corrente — eseguilo dalla directory che contiene `web_archive/` in modo che i backlink nelle pagine spazio si risolvano.
- `--fetch-meta` prima aggiorna la cache proprietario/membro di ogni spazio tramite `get_collection` (1 richiesta per spazio, intervallo 3s) in `index/space_meta.json`; quando l'account corrente non può vedere uno spazio, un account che può viene riprovato automaticamente (i cookie cambiano da soli).

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

Sincronizza il campo `space` dei file `thread.json` già archiviati con l'indice corrente — puramente locale, zero rete.

| Flag | Significato | Predefinito |
|---|---|---|
| *(solo opzioni comuni; solo `--out` conta)* | | |

Comportamenti chiave:

- Prerequisito: esegui prima `index` — il `library_*.json` aggiornato è la fonte di verità per la proprietà corrente dello spazio.
- Confronta gli slug spazio per thread e corregge `thread.json` sul posto in caso di divergenza; le prime 30 modifiche vengono registrate.
- Dopo qualsiasi modifica, l'indice `spaces/` viene ricostruito automaticamente insieme.

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

Calcola il piano di esportazione incrementale di questo ciclo e scrive uno snippet cron che il cron di sistema può chiamare direttamente.

| Flag | Significato | Predefinito |
|---|---|---|
| *(solo opzioni comuni)* | | |

Comportamenti chiave:

- Recupera un indice live e riporta il piano come conteggi totali/nuovi/aggiornati, usando la stessa funzione pura di arresto anticipato (`plan_incremental`) di `batch` — vedi [incremental-sync.md](incremental-sync.md).
- Scrive `<out>/index/cron_snippet.txt` contenente una riga `17 3 * * *` della forma `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'` — i percorsi sono assoluti e tra virgolette perché cwd e PATH di cron sono imprevedibili. Il percorso eseguibile viene risolto tramite `shutil.which`; quando fallisce, lo snippet ricade sul nome nudo `pplx-export`.
- Le esecuzioni pianificate sono solo incrementali per progettazione; esegui `batch --full` manualmente come backstop periodico.

```bash
pplx-export schedule --account alice
```
