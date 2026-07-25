---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/modes.md"
translation_source_sha256: "dda1cfaf9d60ef912d922e65babafb68ec80cd1cdf046d661960d0de47ab77ff"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="conversation-modes" data-pplx-source-anchor="true"></a>
# Modalità di conversazione

Le conversazioni Perplexity sono disponibili in cinque modalità: `search` / `deep-research` / `computer` / `council` / `study`. La modalità viene rilevata per thread durante l'esportazione; determina quali risposte API vengono recuperate, cosa finisce nella directory del thread e quale [percorso di archivio](archive-layout.md) ottiene il thread (`<account>/<mode>/…`). La modalità rilevata viene registrata in `thread.json` (chiave `mode`) e utilizzata dal filtro `pplx-export batch --mode`. `pplx-ask` può anche *creare* nuovi thread in quattro delle cinque modalità (tutte tranne `computer`) — vedere [pplx-ask](pplx-ask.md).

<a id="the-five-modes-at-a-glance" data-pplx-source-anchor="true"></a>
## Le cinque modalità a colpo d'occhio

| Modalità | Nome UI / modello | Contenuto del turno | Citazioni | Prodotti | Blocchi schematizzati recuperati |
|---|---|---|---|---|---|
| `search` | "Best" (`pplx_pro`; anche labs `STUDIO`/`pplx_beta` mappa qui) | Query + Risposta, passaggi di testo | a livello di turno + a livello di thread `sources.*` | — | No (`raw_blocks.json` assente) |
| `deep-research` | "Deep research" (`pplx_alpha`, fisso, nessun selettore) | passaggi di ricerca incl. `RESEARCH_ANSWER` | sì | `report.md` (rapporto completo) | Sì |
| `computer` | Computer (`pplx_asi_opus`, `pplx_asi_opus_thinking`) | `workflow_block` completo: narrazione, chiamate a strumenti, prompt/passaggi del sotto-agente, citazioni per passaggio | per passaggio + turno + thread | file versionati in `assets/` + esecuzioni del sotto-agente | Sì |
| `council` | Model council (`pplx_agentic_research`; tre modelli di default) | Passaggio `COUNCIL_RESEARCH`; flusso di lavoro `LLM_COUNCIL` annidato di ogni modello piegato in `<details>` (round di ricerca, tutte le fonti, risposta completa per modello) | per modello + aggregato | risposte per modello confrontate affiancate | Sì |
| `study` | Study (`pplx_study`) | passaggi/citazioni tramite blocchi (verificato per contenere anche asset) | sì | asset quando presenti | Sì |

<a id="how-the-mode-is-decided" data-pplx-source-anchor="true"></a>
## Come viene decisa la modalità

L'autorità di rilevamento è il campo **`entry.search_mode`** della piattaforma (`SEARCH_MODE_MAP`, `normalize.py:50-59`), raccolto tra tutte le voci (`normalize.py:106-115`). È stato verificato rispetto alla configurazione ufficiale del modello (`GET /rest/models/config/v2`): `default_models.search=pplx_pro` (UI "Best"), `default_models.research=pplx_alpha` (UI "Deep research"), e i valori corrispondono uno a uno alle modalità di conversazione:

| Valore `search_mode` | Modalità |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`, `STUDIO` | `search` |

Regole di conflitto (`detect_mode`, `normalize.py:66-128`):

- **Cambio di modalità all'interno di un thread** (voci in disaccordo): prendere la più alta per specificità — **computer > council > study > deep-research > search** (`_MODE_SPECIFICITY`, `normalize.py:63`) — e `log.warning`.
- **Conflitto con segnali a valle** (nomi dei passaggi / `display_model`): `search_mode` vince, `log.warning` (`normalize.py:120-123`).
- **`search_mode` completamente assente** → la catena originale: l'URL contiene `/computer/tasks/` o `metadata.mode == '4'` o la modalità indice ∈ `ASI`/`COMPUTER` → `computer`; un passaggio `COUNCIL_RESEARCH` → `council`; un passaggio `RESEARCH_ANSWER` → `deep-research`; segnale `display_model` ridondante (`DISPLAY_MODEL_MODE`, `normalize.py:32-37`) vince in caso di conflitto; nessun riscontro → `search` per impostazione predefinita.
- **Tutti i segnali mancanti non concludono la ricerca**: la pipeline recupera comunque i blocchi schematizzati (`adapter.py:83-89`) in modo che una deriva del campo della piattaforma non possa eliminare silenziosamente `raw_blocks.json`.

!!! note "Perché `pplx_alpha` non è un indizio di rilevamento"
    `pplx_alpha` è il modello dedicato a RESEARCH — è il *bersaglio* che il classificatore deve rilevare, non una prova per il rilevamento, quindi è deliberatamente escluso dalla tabella di mappatura (commento `normalize.py:15-31`).

L'albero decisionale completo con ogni ramo: [Pipeline di esportazione — rilevamento modalità](../architecture/export-pipeline.md).

<a id="where-sub-agent-payloads-land" data-pplx-source-anchor="true"></a>
## Dove finiscono i payload dei sotto-agenti

Le esecuzioni Computer/Council generano flussi di lavoro di sotto-agenti in background. Ogni `workflow_payload` di background viene renderizzato in **esattamente un posto, mai due**; a livello utente i tre possibili punti di atterraggio sono:

1. **Ancorato — all'interno del turno iniziatore**: il turno che ha avviato il sotto-agente porta un ID payload corrispondente, quindi l'esecuzione viene renderizzata in linea nel processo di lavoro di quel turno (`turns/turn_NNNN.md`), con prompt, passaggi, risposta e fonti.
2. **Turno stub — sezione "子代理工作" (Lavoro sotto-agente)**: un turno stub `subagent_result` all'interno di una finestra di completamento di 10 secondi assorbe il payload; la risposta non viene retrocompilata.
3. **Appendice del thread — fine di `conversation.md`**: tutto ciò che rimane (le esecuzioni interrotte non producono notifica di completamento, quindi i primi due livelli necessariamente mancano) viene archiviato testualmente sotto "## 后台任务（未归入轮次）" (Attività in background (non assegnate ai turni)) — nessuna ipotesi di attribuzione temporale, qualsiasi stato accettato.

Regole di corrispondenza, strutture dati e garanzie di consumo singolo: [Sotto-agenti e interruzioni](../architecture/subagents-interruptions.md).

<a id="interruptions-non-completed-workflows" data-pplx-source-anchor="true"></a>
## Interruzioni: flussi di lavoro non COMPLETATI

I flussi di lavoro che non sono stati completati vengono annotati in linea ovunque vengano renderizzati — nelle intestazioni del processo di lavoro, nelle intestazioni dei sotto-agenti e nei riepiloghi `<details>` annidati. Le tre annotazioni (`parsers.classify_wf_status`, `parsers.py:263-284`):

| Annotazione | Condizione | Significato |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` (limit-interrupted — il contenuto si ferma al punto di interruzione) | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | limite di spesa esaurito; il flusso di lavoro si è fermato a metà esecuzione |
| `⏸ 中断待续` (interrotto, in attesa di continuazione) | `WORKFLOW_AWAITING_NEXT_STEPS` senza `locked_reason` | interrotto, può essere continuato sulla piattaforma |
| `⛔ 已取消` (annullato) | `WORKFLOW_CANCELED` | annullato dall'utente o dalla piattaforma |

- `COMPLETED` non viene mai annotato (i thread sani ottengono zero diff); i futuri valori di stato sconosciuti rimangono silenziosi.
- Ogni caso annotato viene anche registrato in `thread.json.interruptions` come `{location, kind, headline, status}` — le posizioni assomigliano a `turn_0007`, `turn_0011/subagent`, `turn_0024/subagent_stub`, `background_unassigned` (`parsers.py:535-583`; chiave assente nei thread sani).
- **La ripresa non necessita di casi speciali**: quando continui un thread interrotto sulla piattaforma, il suo `lastUpdated` cambia, la successiva esportazione incrementale lo recupera di nuovo e le annotazioni semplicemente scompaiono una volta che il flusso di lavoro viene completato. Vedere [Sincronizzazione incrementale](incremental-sync.md).

Valori di stato osservati e distribuzione: [Risposte API ed errori](../reference/api/api-responses-errors.md); macchina a stati: [Sotto-agenti e interruzioni](../architecture/subagents-interruptions.md).

<a id="answer-rewrite-variants-answer_variants" data-pplx-source-anchor="true"></a>
## Varianti di riscrittura della risposta (answer_variants)

Quando la piattaforma riscrive una risposta (esperimenti A/B), la variante sostituita è invisibile nell'API — viene restituita solo la risposta selezionata, mentre il fratello perdente lascia una traccia in `entries[].side_by_side_metadata` e potrebbe essere successivamente eliminato (collegamenti a fratelli morti confermati: 403 `VIEW_THREAD_NOT_ALLOWED`). Lo strumento rende osservabile "una riscrittura è avvenuta":

- **Registrazione**: i riscontri con criteri ristretti vengono scritti in `thread.json.answer_variants` (`fs_writer.py:247-252`; chiave assente senza riscontri) e aggiunti al registro centrale `index/answer_variants_log.jsonl`, deduplicati per (thread, entry) e idempotenti (`variant_log.py:76`).
- **Avvisi**: una singola riga WARNING greppabile `ANSWER_VARIANT_DETECTED` con campi di localizzazione completi (thread uuid/uuid8, entry_uuid, sibling_uuid, selection_status, experiment_role) su ogni riscontro online; `re-render` si registra di nuovo offline e avvisa solo quando il contenuto viene aggiunto o modificato, quindi le riesecuzioni a livello di libreria rimangono silenziose; il riepilogo batch aggiunge un conteggio dei riscontri ⚠.
- **Ri-archiviazione manuale**: le varianti fratelli sono empiricamente collegamenti morti, quindi la risposta alternativa di solito **non può essere recuperata tramite API**. In caso di riscontro, confermare tempestivamente la risposta alternativa manualmente (interfaccia utente della piattaforma, propri record, screenshot); se la ottieni, registrala come `rewritten_answer_variant.md` all'interno della directory del thread. In caso contrario, `thread.json.answer_variants` più il registro jsonl sono il record tracciabile finale.

Catena di rilevamento e ri-registrazione offline: [Operazioni offline](../architecture/offline-operations.md); semantica dei campi e prove di collegamenti morti: [Risposte API ed errori](../reference/api/api-responses-errors.md).

<a id="rendering-fidelity-principles" data-pplx-source-anchor="true"></a>
## Principi di fedeltà del rendering

Indipendentemente dalla modalità, il rendering segue lo stesso contratto di fedeltà:

- **Risposte complete, mai troncate** — il vecchio limite `[:4000]` è stato rimosso perché tagliava le frasi a metà (`render.py:645-647`).
- **Tabelle mai troncate** — `WORKFLOW_ITEM_TABLE` renderizza ogni riga e colonna, escape di `|` e nuove righe in intestazioni e celle in modo che la struttura Markdown sopravviva (`render.py:211-243`).
- **Citazioni complete** — tre canali di raccolta (`entry.sources` + `FINAL.web_results` + `WORKFLOW_ITEM_SOURCES`), deduplicati per URL in `sources.*`; nulla di citato viene eliminato.
- **Il JSON grezzo dell'API è il confine del contenuto** — tutto ciò che viene renderizzato proviene da `raw_entries.json` / `raw_blocks.json`; ciò che l'API non restituisce (ad esempio una variante di risposta sostituita) non può essere renderizzato e viene invece reso visibile tramite registri, senza essere inventato.
- **L'interfaccia utente piega, l'archivio espande** — i dettagli che l'interfaccia utente web nasconde dietro pieghe e clic (narrazione del flusso di lavoro del computer e I/O degli strumenti, esecuzioni per modello del council, passaggi del sotto-agente) vengono renderizzati per intero; i blocchi `<details>` mantengono la struttura del documento leggibile senza perdere informazioni (`render.py:46`, `render.py:404-413`).
- **Robustezza strutturale** — i blocchi di codice sono dimensionati in base al loro contenuto (`_fence_for`, `render.py:28-43`) in modo che l'output dello strumento contenente i propri blocchi non possa invertire l'accoppiamento, e i delimitatori LaTeX sono normalizzati a `$$` / `$` con segmenti di codice protetti (`normalize_math_delims`).

Come le risposte grezze conservate rendono tutto ciò rigenerabile offline: [Pipeline di esportazione](../architecture/export-pipeline.md) e [Operazioni offline](../architecture/offline-operations.md).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Vedi anche

- [Layout dell'archivio](archive-layout.md) — dove finiscono i file di ogni modalità
- [pplx-ask](pplx-ask.md) — creazione di nuovi thread in ogni modalità
- [Sincronizzazione incrementale](incremental-sync.md) — recupero di thread continuati
- [Pipeline di esportazione](../architecture/export-pipeline.md) — albero decisionale completo del rilevamento modalità
- [Sotto-agenti e interruzioni](../architecture/subagents-interruptions.md) — cascata di attribuzione e macchina a stati
- [Risposte API ed errori](../reference/api/api-responses-errors.md) — valori di campo osservati
