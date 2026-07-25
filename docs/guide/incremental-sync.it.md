---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/incremental-sync.md"
translation_source_sha256: "35868edfb3e8e914afd9afa1b00370bffb9f8a50ca374691229f41d51ffa9b64"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="incremental-sync" data-pplx-source-anchor="true"></a>
# Sincronizzazione Incrementale

`pplx-export batch` è progettato per essere eseguito spesso: ogni esecuzione esporta solo ciò che è nuovo o
modificato, sana i gap lasciati da esecuzioni interrotte e non ritocca mai i thread che la
piattaforma ha già archiviato. L'unica fonte di verità per "cosa è stato esportato" è `index/batch_state.json` (`BatchState`,
`pplx_export/core/state.py:63`), aggiornato dopo ogni thread — non esiste una
copia shadow separata.

<a id="prerequisites-and-basic-usage" data-pplx-source-anchor="true"></a>
## Prerequisiti e utilizzo di base

```bash
pplx-export index --account alice   # refresh index/library_alice.json first
pplx-export batch --account alice   # incremental export (early stop, resumable)
```

`batch` rifiuta di funzionare senza l'indice
(`pplx_export/commands/batch_cmd.py:79-81`). `--limit N` e `--mode <mode>`
filtrano le righe dell'indice prima di pianificare; le righe prive di `entryUUID` vengono saltate
con un avviso invece di far crashare l'esecuzione (`batch_cmd.py:95-100`).

<a id="how-the-incremental-plan-works" data-pplx-source-anchor="true"></a>
## Come funziona il piano incrementale

1. **Ordina.** Le righe dell'indice vengono ordinate per `lastUpdated`, dalla più recente per prima
   (`batch_cmd.py:89`). Le conversazioni nuove e quelle vecchie riprese (il cui
   `lastUpdated` le ha appena spostate verso l'alto) si trovano entrambe in cima — questo ordinamento è
   ciò che rende sicuro l'arresto anticipato.
2. **Classifica.** `plan_incremental`
   (`pplx_export/hooks/incremental.py:36-87`) — una funzione pura condivisa da
   `batch` e `schedule` — assegna a ogni riga esattamente un'azione:

   | azione | condizione | cosa fa il batch |
   |---|---|---|
   | `new` | uuid mai visto in `batch_state` | esporta |
   | `updated` | `lastUpdated` differisce dal valore registrato, o `--force` | riesporta |
   | `done` | stato `ok` e `lastUpdated` invariati | salta |
   | `expired` | la piattaforma ha restituito `ENTRY_EXPIRED` in un tentativo precedente | salta — terminale, mai ritentato |
   | `deleted` | `sync-deleted` ha confermato una cancellazione remota | salta — terminale, mai ritentato |

3. **Arresto anticipato.** Per impostazione predefinita (né `--full` né `--force`) la sequenza
   finale più lunga di voci terminali (`done` / `expired` / `deleted`) viene tagliata
   completamente e conteggiata come `n_stopped` (`incremental.py:83-87`). Poiché l'elenco è
   ordinato dalla più recente, tutto ciò che si trova sotto una voce invariata è necessariamente
   più vecchio e anch'esso invariato — scansionare oltre sprecherebbe solo tempo.

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

4. **Esegui.** Ogni thread esportato viene marcato immediatamente (`mark_ok` /
   `mark_error` / `mark_expired` / `mark_deleted`) e il file di stato viene salvato
   dopo ogni elemento (`batch_cmd.py:154-201`); un `KeyboardInterrupt` salva anche
   prima di propagare (`batch_cmd.py:158-161`). Le scritture sono atomiche — file temporaneo
   più `os.replace` (`state.py:145-152`) — quindi un'esecuzione interrotta non lascia mai
   JSON troncato.

<a id="gap-healing-after-interrupted-runs" data-pplx-source-anchor="true"></a>
## Guarigione dei gap dopo esecuzioni interrotte

L'arresto anticipato non seppellisce mai un gap. I thread che hanno fallito (stato `error`) o non sono
mai stati raggiunti si trovano **sopra** il suffisso terminale, quindi l'esecuzione successiva li ripianifica
come `updated` / `new` e li esporta prima che venga raggiunto il punto di arresto anticipato
(`incremental.py:12-14`, `batch_cmd.py:206-208`). Combinato con i salvataggi di stato per elemento,
un'esecuzione batch può essere interrotta in qualsiasi punto e semplicemente rieseguita.

Se `batch_state.json` stesso è corrotto, non viene azzerato silenziosamente: l'originale
viene rinominato in `batch_state.json.corrupt-<timestamp>` in modo che gli stati terminali registrati
non vengano persi e ritentati inutilmente (`state.py:68-81`).

<a id="-full-and-force" data-pplx-source-anchor="true"></a>
## `--full` e `--force`

| flag | effetto | stati terminali | quando usare |
|---|---|---|---|
| *(predefinito)* | arresto anticipato sulla sequenza terminale finale | saltati | ogni esecuzione regolare / programmata |
| `--full` | scansione completa, nessun arresto anticipato; i thread invariati vengono comunque saltati come `done` | saltati | backstop periodico, o quando si sospettano gap nell'archivio |
| `--force` | riesporta tutto, anche i thread invariati | ancora esclusi — mai ritentati | dopo correzioni della pipeline che devono recuperare nuovamente i dati grezzi |

Gli stati terminali sono esclusi da `--force` per progettazione: ritentare un thread scaduto o
cancellato remotamente spreca solo richieste e budget di backoff
(`batch_cmd.py:120-127`).

Vedi anche [`status`](maintenance-commands.md#status): un report senza rete dello
stato dell'account e del piano di modifica calcolato con la stessa semantica `plan_incremental`
(`new`/`updated`/conteggio arresto anticipato).

Il confronto `lastUpdated` normalizza gli zeri finali nella parte dei
frazioni di secondo (`.18033Z` è uguale a `.180330Z`; `state.py:23-55`),
perché la piattaforma occasionalmente li omette — un confronto esatto di stringhe
giudicherebbe erroneamente "modificato" e causerebbe esportazioni duplicate.

<a id="terminal-states-expired-and-deleted" data-pplx-source-anchor="true"></a>
## Stati terminali: `expired` e `deleted`

| | `expired` | `deleted` |
|---|---|---|
| significato | la piattaforma ha eliminato il thread (~finestra di conservazione di 3 mesi); il tentativo di esportazione ha restituito `ENTRY_EXPIRED` | cancellazione utente/remota, confermata da `sync-deleted` |
| registrato da | `batch` stesso (`mark_expired`, `state.py:131-134`) | `pplx-export sync-deleted --online` (`mark_deleted`, `state.py:136-143`) |
| ritentato? | mai — nemmeno con `--force` | mai — nemmeno con `--force` |
| evidenza | la risposta `ENTRY_EXPIRED` | campo `note`: assenza dall'indice + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted-confirming-remote-deletions" data-pplx-source-anchor="true"></a>
### sync-deleted: conferma delle cancellazioni remote

```bash
pplx-export sync-deleted --account alice            # offline dry-run: list candidates only
pplx-export sync-deleted --account alice --online   # confirm each candidate online
```

1. **Candidati (offline, zero rete).** Qualsiasi thread con stato `ok` in
   `batch_state` che manca dall'unione `entryUUID` di **tutti**
   gli indici degli account `index/library_*.json` è un sospetto candidato di cancellazione
   remota (`pplx_export/commands/sync_deleted_cmd.py:148-212`). L'unione
   tra account è necessaria: un thread di proprietà di `bob` ma esportato da `alice`
   attraverso uno spazio condiviso non appare mai nell'indice di `alice` — un
   diff su un singolo account genererebbe falsi positivi per tutto quel set. Quando non esiste
   alcun indice utilizzabile, ogni candidato viene saltato in sicurezza con il motivo registrato.
2. **Dry-run per impostazione predefinita.** Senza `--online` il comando elenca solo
   i candidati — nessuna rete, nessuna modifica ai file.
3. **Conferma `--online`.** Ogni candidato viene verificato con
   `GET /rest/thread/<uuid>`, utilizzando l'account `export_via` del candidato da
   `thread.json` (il cookie cambia automaticamente):

   | risultato | esito |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | confermato: `batch_state` segna terminale `deleted` (`note` registra il motivo), e ogni `thread.json` di quel thread riceve un timestamp `remote_deleted` al suo posto |
   | thread ancora esistente | falso positivo: segnalato così com'è (l'indice potrebbe non essere completamente aggiornato — riesegui `index` e controlla di nuovo), nulla è cambiato |
   | 5xx / errore di rete | nessuna modifica di stato; il candidato viene lasciato per il prossimo giro |
   | 3 consecutivi 401/403 | interruzione rapida — un cookie scaduto non può guarire da solo, e continuare segnerebbe erroneamente thread attivi (`sync_deleted_cmd.py:333-337`) |

   I segni confermati vengono persistiti per elemento, quindi un'esecuzione `--online` interrotta
   non perde nulla e le riesecuzioni sono idempotenti (`sync_deleted_cmd.py:254-256`).

<a id="the-tombstone-principle" data-pplx-source-anchor="true"></a>
## Il principio della lapide

!!! warning "Gli archivi locali non vengono mai eliminati"
    Questo archivio è il backup di riferimento per le conversazioni esportate.
    `sync-deleted` solo *identifica e segna* (lapide): **non elimina
    né sposta alcun file di archivio**. La conferma cambia esattamente due cose — lo
    stato `batch_state` e una chiave marcatore in `thread.json`:

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    Il timbro è idempotente: una chiave `remote_deleted` esistente non viene
    né riscritta né sovrascritta (`sync_deleted_cmd.py:215-244`).

<a id="idempotence-and-offline-re-render" data-pplx-source-anchor="true"></a>
## Idempotenza e ri-rendering offline

- Rieseguire `batch` su un indice invariato non esporta nulla: ogni riga
  viene classificata come `done` e l'esecuzione si ferma al punto di arresto anticipato. Le scritture di stato
  sono atomiche, i segni sono per thread e le cancellazioni riconfermate non duplicano
  mai il timbro `remote_deleted`.
- L'archivio conserva i payload API grezzi (`raw_entries.json` /
  `raw_blocks.json`), quindi i file renderizzati possono essere rigenerati in qualsiasi momento
  con zero accesso alla rete:

  ```bash
  pplx-export re-render                 # rebuild conversation.md + turns/ everywhere
  pplx-export re-render --dry-run       # only list the thread directories
  pplx-export re-render --thread-json   # also sync interruptions / answer_variants keys
  ```

  `re-render` ri-analizza il JSON grezzo con il renderer corrente
  (`pplx_export/commands/rerender_cmd.py:105-190`): `conversation.md` e
  `turns/turn_*.md` vengono riscritti, i file di turno obsoleti numerati sopra il conteggio
  di turno corrente vengono rimossi, e fonti, asset, `report.md` e `thread.json`
  vengono lasciati intatti. È così che le correzioni del renderer si distribuiscono su tutto
  l'archivio senza una singola richiesta.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Vedi anche

- [pplx-export.md](pplx-export.md) — riferimento completo del comando `batch` (`--mode`, `--limit`, ritardi)
- [maintenance-commands.md](maintenance-commands.md) — `sync-deleted`, `re-render` e i comandi di backfill
- [archive-layout.md](archive-layout.md) — dove si trovano `batch_state.json` e `thread.json`
- [rate-limiting.md](rate-limiting.md) — pacing tra i thread, backoff, fail-fast per autenticazione
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) — la pipeline di esportazione completa
- [../architecture/offline-operations.md](../architecture/offline-operations.md) — la pipeline di ricostruzione offline in profondità
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — tassonomia degli errori e gestione degli stati terminali
