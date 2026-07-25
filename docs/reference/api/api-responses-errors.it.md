---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-responses-errors.md"
translation_source_sha256: "4a9de23e2a900f4922480decf1b89d417310b94ce8116649dd2b2dd5c77b6bde"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-response-structure-and-error-semantics" data-pplx-source-anchor="true"></a>
# Struttura delle Risposte API e Semantica degli Errori

*Parte del riferimento API web Perplexity — mappa completa nell'[indice API](index.md).*

<a id="response-structure-essentials-parsing-discipline" data-pplx-source-anchor="true"></a>
## Elementi essenziali della struttura della risposta (disciplina di parsing)

- **Dati grezzi conservati negli archivi riusciti**: `raw_entries.json` (plain) e
  `raw_blocks.json` (schematizzato, quando recuperato) sono memorizzati insieme agli
  artefatti renderizzati; il parsing/rendering può essere rieseguito offline (`pplx-export re-render`)
  senza dover recuperare nuovamente i dati.
- **Estrazione dei campi centralizzata** in `sites/perplexity/parsers.py` (la deriva dello schema richiede una modifica in un solo punto).
- Rilevamento della modalità (`normalize.detect_mode`; albero decisionale in [export-pipeline.md](../../architecture/export-pipeline.md)): il segnale con priorità più alta è il
  campo **`search_mode`** di qualsiasi voce (mappatura alla fine del [§3.9](api-rest-endpoints.md)); quando tutti i segnali falliscono, ricaduta — computer = URL
  `/computer/tasks/` o metadata.mode=="4" o index mode ∈ {ASI,COMPUTER}; council = esiste
  un passaggio COUNCIL_RESEARCH; deep-research = esiste un passaggio RESEARCH_ANSWER (basato sul contenuto, non su etichette cinesi);
  altrimenti search.
- L'interfaccia utente di computer collassa tutto — **basarsi sempre sulle voci/blocchi API**; non usare mai il testo dell'interfaccia utente come confine del contenuto.
- Canale duale del subagente (scoperto il 19-07-2026): prompt in `workflow_payload.objective_chunks` schematizzato;
  passaggi/conclusione in `background_entries` plain; collegati tramite `workflow_payload.id` (`toolu_X`).
- Gli elementi `WORKFLOW_ITEM_SOURCES` spesso contengono `text_payload`
  (testo di estrazione pagina del subagente / tabelle di confronto; 450 occorrenze nell'intera libreria, 408 all'interno di payload nidificati di background)
  oltre a `sources_payload.sources` (elenco di link);
  lo stesso contenuto appare sia nel `text` della voce plain di background (JSON del passaggio incorporato) sia nel payload nidificato schematizzato —
  i subagenti ancorati renderizzati tramite il percorso plain preservano già il testo (verifica sull'intera libreria il 22-07-2026: 408/408 presenti, nessuno mancante).
- **`related_queries` / `related_query_items` (risolto il 23-07-2026)**: ogni voce contiene
  **raccomandazioni per la domanda successiva** — suggerimenti di follow-up che la piattaforma genera per una risposta completata; `related_queries` è un array di testi di raccomandazione,
  `related_query_items` gli elementi strutturati (uuid/upsell_type, ecc.). Conclusione forense: l'uuid di un elemento
  **non è un uuid di thread** (0/988 corrispondenze incrociate con gli uuid di thread della libreria), e i testi di raccomandazione non hanno sovrapposizioni con le query di altri thread —
  **per ora non risolvibile in relazioni inter-thread**; l'ipotesi di "uuid di thread pre-allocati (materializzati al clic)" rimane non verificata.
  I dati sono naturalmente preservati nell'archivio `raw_entries.json` (presenti in oltre la metà dei thread di una libreria di archivio); nessuna azione di raccolta aggiuntiva necessaria;
  il grafo delle relazioni non costruisce archi a partire da essi.

<a id="error-and-risk-control-semantics" data-pplx-source-anchor="true"></a>
## Semantica degli errori e del controllo del rischio

| Sintomo | Significato / gestione |
|---|---|
| 403 (con pagina di sfida cf) | Blocco Cloudflare (impronta TLS / controllo della frequenza) — arretrare; urllib + cookie del browser generalmente non lo attivano |
| 401 / 403 a livello API (nessuna pagina di sfida cf) | Cookie di sessione scaduto/invalido — lo strumento solleva immediatamente l'eccezione, nessun backoff; il batch fallisce rapidamente dopo 3 errori di autenticazione consecutivi (aggiornare il cookie) |
| 429 | Limitazione della frequenza — backoff esponenziale (implementato nello strumento) |
| 5xx (500/502/503/504) | Errori server transitori (504 è comunemente un timeout di Cloudflare) — arretrare e riprovare (implementato nello strumento) |
| ENTRY_EXPIRED | Rimosso dalla piattaforma (~3 mesi) — terminale, non riprovare |
| ENTRY_DELETED | Eliminato dall'utente/remoto (anche HTTP 400, codice diverso) — terminale `deleted`, non riprovare |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED` (HTTP 200) | L'account corrente non può visualizzare lo spazio — riprovare con un account che possa |
| `error_code: VIEW_THREAD_NOT_ALLOWED` (HTTP 403) | L'account corrente non può visualizzare il thread (testato il 23-07-2026: probing uuid di varianti sorelle; l'oggetto esiste ma non è accessibile, non "inesistente") |
| `status:"failed"` dati vuoti | Stessa classe (la forma di fallimento di get_collection) |

**Disciplina di limitazione della frequenza (anti-ban, requisito esplicito dell'utente)**: 10–20 secondi casuali tra thread batch, nessuna concorrenza, backoff 429/403, backoff-riprova 5xx;
paginazione ≥3s; recupero schematizzato ≥4s; recupero metadati spazio ≥3s. Esportazione thread singolo = 1–2 richieste ≈ aprire la pagina una volta.

<a id="interruption-semantics-observed-values-2026-07-22-classification-source-of-truth-parsersclassify_wf_status" data-pplx-source-anchor="true"></a>
### Semantica delle interruzioni — valori osservati (22-07-2026; fonte di verità per la classificazione: `parsers.classify_wf_status`)

Il campo `locked_reason`: appare in `thread_metadata` / `entries[]` / `background_entries[]`
(sia sul lato plain che schematizzato). Unico valore osservato:

| locked_reason | Significato | Distribuzione osservata |
|---|---|---|
| `spending_limit_exceeded` | interruzione per limite di spesa (quota esaurita; il flusso di lavoro si ferma al punto di interruzione) | esattamente un thread nell'intera libreria (marcatori sia in raw_entries che in raw_blocks) |

Campo stato del flusso di lavoro (`workflow_block.status` e `workflow_payload.status` nidificato condividono lo stesso enum) valori osservati:

| status | Semantica | Annotazione di rendering (COMPLETED non ne ha) |
|---|---|---|
| `WORKFLOW_COMPLETED` | completamento normale | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | in attesa di passaggi successivi; con `locked_reason=spending_limit_exceeded` è una **interruzione per limite di spesa** (il contenuto si ferma al punto di interruzione); senza locked_reason, interrotto in attesa di continuazione | `⏸ 限额中断（内容截至中断点）` (⏸ limit-interrupted — il contenuto si ferma al punto di interruzione) / `⏸ 中断待续` (⏸ interrotto, in attesa di continuazione) |
| `WORKFLOW_CANCELED` | annullato (aborto utente/piattaforma) | `⛔ 已取消` (⛔ annullato) |

- `WORKFLOW_CANCELED` osservato 19 volte (16 principali + 3 nidificati), in 7 thread computer
  (a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff).
- Nota: lo stato del payload dell'ancora della voce principale potrebbe essere in ritardo (osservato ancora COMPLETED mentre il background era effettivamente CANCELED) —
  lo stato reale di un subagente è `workflow_block.status` lato background.
- I task di background interrotti non producono notifica di completamento subagent_result; i payload di background non consumati ricadono nell'appendice del thread
  (vedere "cascata di attribuzione" in [subagents-interruptions.md](../../architecture/subagents-interruptions.md)).
- Risposte vuote in modalità computer (doppiamente verificate a luglio 2026, non recuperabili): in modalità computer, alcuni turni hanno una
  risposta vuota semplicemente perché il server non ne ha — un recupero API restituisce dati identici all'archivio, e
  l'espansione della barra "N passaggi completati" dell'interfaccia utente attiva zero richieste dati (rendering puramente lato client; l'interfaccia utente e
  l'API condividono una fonte), quindi l'API non può recuperarli. Solo un sottoinsieme di tali turni è collegato a
  `locked_reason=spending_limit_exceeded`; gli altri non portano alcun marcatore lato server.

<a id="side_by_side_metadata-answer-rewrite-variant-signal-settled-2026-07-23" data-pplx-source-anchor="true"></a>
### `side_by_side_metadata`: segnale di variante di riscrittura della risposta (risolto il 23-07-2026)

Percorso del campo: `entries[].side_by_side_metadata` (risposta `/rest/thread/<uuid>` plain).
Quando la piattaforma genera più versioni di risposta per la stessa query (esperimento A/B o riscrittura), questa è l'unica
traccia lasciata sulla voce attualmente attiva — **il corpo della variante sostituita (testo/passaggi/citazioni) non è nella risposta API del thread** (caso reale
b2d2632b: la risposta ha solo 1 voce, 1 FINAL; variante 2 completamente invisibile).

Chiavi e valori osservati (evidenza: b2d2632b raw; scansione dell'intera libreria di 2442 voci):

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| Chiave | Semantica (osservata/ipotizzata) |
|---|---|
| `sibling_uuid` | Punta alla **variante di risposta sorella** della stessa query (un altro identificatore di voce/contesto). 7 thread trovati nell'intera libreria; **le analisi online (23-07-2026) confermano un link morto**: `GET /rest/thread/<sibling_uuid>` di entrambi gli account restituiscono 403 `VIEW_THREAD_NOT_ALLOWED` (non 404/ENTRY_EXPIRED — il server lo riconosce come un oggetto esistente ma non visualizzabile), e l'apertura di `/search/<sibling_uuid>` nel browser (account proprietario) viene reindirizzata SPA alla home — le varianti sostituite non possono essere recuperate tramite sibling_uuid |
| `selection_status` | `SELECTED` = la risposta di questa voce è la versione scelta per la visualizzazione; le istanze del gruppo di controllo sono tutte `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | Ruolo dell'esperimento. Il gruppo di controllo porta un prefisso `[control]` (6 casi nell'intera libreria: `[control]default-model-class:gpt41`, ecc.); il caso reale non ha prefisso (`override-default-model-class:qwen3_instruct-01f7f`, cioè il gruppo di trattamento di un esperimento di override del modello) |
| `experiment_override` | Parametri di override dell'esperimento (ad es. `override-default-model-class: qwen3_instruct`); osservato solo su istanze del gruppo di trattamento |
| `execution_log` | Osservato come un oggetto vuoto; semantica sconosciuta |

**Criteri di restringimento** (distinguere "riscrittura genuina che mantiene entrambe le versioni" da "controllo A/B di routine"):
`sibling_uuid` non vuoto AND (`selection_status` non vuoto e non `SELECTION_STATUS_UNSPECIFIED`,
OR `experiment_role` senza il prefisso `[control]`) → **solo b2d2632b corrisponde** tra le 2442 voci dell'intera libreria
(l'unico caso reale confermato; precisione e richiamo sono entrambi 1 su questa libreria, ma n=1 non può essere estrapolato).

Comportamento dello strumento: `parsers.collect_answer_variants` estrae le corrispondenze; `adapter.get_thread`
registra un avviso + scrive `thread.json.answer_variants` (chiave assente quando nessuna corrispondenza);
`re-render --thread-json` aggiunge/rimuove sul posto (idempotente). Evidenza temporale: il delta `created→updated` della voce del caso reale
è 53,66 s (generata alle 17:13, poi riscritta/selezionata), e la riscrittura ha avanzato `lastUpdated` a livello di thread (una riesportazione incrementale
può attivare un recupero, ma la risposta recuperata contiene ancora solo la risposta attiva; le varianti vecchie non sono recuperabili).

**Log di rilevamento e flusso di gestione (23-07-2026, `sites/perplexity/variant_log.py`)**:

- **Marcatore di log**: ogni corrispondenza emette una singola riga WARNING con il marcatore uniforme greppabile `ANSWER_VARIANT_DETECTED`,
  includendo tutti i campi di localizzazione e le indicazioni di gestione, nella forma:
  `ANSWER_VARIANT_DETECTED thread=<full uuid> uuid8=<8 chars> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | action: …`
  Il percorso online (`adapter.get_thread`) produce output su ogni corrispondenza di recupero effettiva; offline `re-render`
  **produce output solo quando il contenuto registrato viene aggiunto/modificato** (le esecuzioni idempotenti non generano spam); `batch` passa anche un promemoria
  del conteggio delle corrispondenze su una riga nel riepilogo finale (senza rompere il formato di riepilogo esistente).
- **Registro centrale**: `<out>/index/answer_variants_log.jsonl` (**un file tracciato**, non sotto
  `logs/` gitignorato) — un JSON per riga (detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role), deduplicato per (web_uuid, entry_uuid); esportazioni/rendering ripetuti non aggiungono all'infinito;
  detected_at mantiene l'ora del primo avvistamento.
- **Azione raccomandata in caso di corrispondenza**: i fratelli sono empiricamente link morti (vedere la tabella sopra); la risposta alternativa di solito
  **non può essere recuperata tramite API** — confermare prontamente manualmente se la risposta alternativa è ancora ottenibile (conversazione sulla piattaforma / memoria dell'utente / screenshot); se ottenibile,
  registrarla manualmente come file `rewritten_answer_variant.md` nella directory del thread; in caso contrario, `thread.json.answer_variants` +
  il registro jsonl fungono da record tracciabile finale.
