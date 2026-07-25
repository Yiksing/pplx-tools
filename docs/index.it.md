---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/index.md"
translation_source_sha256: "7a016c35bbb11272395a246fd23c0c27be794585c5b1cda9fdc9c6181fe32e48"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="perplexity-cli-toolkit" data-pplx-source-anchor="true"></a>
# Toolkit CLI Perplexity

<p class="homepage-scope-note" role="note">
  <strong>NON per API a consumo</strong>
</p>

Perplexity archivio conversazioni e toolkit per interrogazioni interattive (`pplx-export` / `pplx-ask`).

Parla direttamente con l'API REST/GraphQL di Perplexity utilizzando i cookie di accesso del tuo browser e archivia le conversazioni — passaggi, citazioni, report di ricerca approfondita, risorse della modalità computer e flussi di lavoro sub-agente — come Markdown + JSON locali. Le esportazioni riuscite conservano le risposte API grezze insieme agli artefatti renderizzati, in modo che il rendering possa essere eseguito nuovamente offline in qualsiasi momento.

<a id="introduction" data-pplx-source-anchor="true"></a>
## Introduzione

Oltre all'archiviazione delle conversazioni storiche, questo progetto mira principalmente a fornire agli agenti locali — più vicini ai dati e spesso supportati da più potenza di calcolo — una misura delle capacità di Perplexity Computer. Consentendo loro di accedere ai report prodotti da Perplexity Deep Research direttamente nel loro ciclo di lavoro, possono utilizzare informazioni di alta qualità per ottimizzare i parametri chiave nel codice in modo più preciso, sfruttando al contempo un abbonamento Perplexity Max esistente.

> A partire dal 20 luglio, Perplexity non offriva una CLI ufficiale per ambienti Unix-like. Il 23 luglio, Perplexity ha rilasciato pubblicamente lo strumento `pplx` utilizzato in modalità Computer, ma tale strumento utilizza ancora la fatturazione a consumo.

Non è una sostituzione completa della modalità Computer. Due capacità rimangono fuori portata:

- la libertà della skill Deep Research di scegliere un modello arbitrario;
- la capacità della skill Council di eseguire ricerche approfondite con diversi modelli specificati dall'utente, produrre report e confrontarli affiancati.

La directory [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context) include prompt di sistema archiviati e regole operative che possono aiutare ad approssimare parti del flusso di lavoro Computer localmente, inclusa la selezione della modalità Deep Research e la selezione del modello sub-agente.

<a id="features" data-pplx-source-anchor="true"></a>
## Funzionalità

<a id="pplx-export-archive-your-library" data-pplx-source-anchor="true"></a>
### `pplx-export` — archivia la tua libreria

- Indice della libreria e indice degli spazi
- Esportazione thread singolo / batch con arresto anticipato incrementale + checkpoint riprendibili
- Backfill delle risorse e backfill dell'utilizzo del credito
- Grafo delle relazioni delle conversazioni
- Re-rendering offline (`re-render`, zero rete)
- Frammento cron incrementale periodico

<a id="pplx-ask-query-perplexity-from-the-shell" data-pplx-source-anchor="true"></a>
### `pplx-ask` — interroga Perplexity dalla shell

- Query di streaming SSE in quattro modalità: ricerca / deep-research / council / studio
- Spostamento automatico in uno spazio BOT al completamento, conferme di lettura
- Archiviazione automatica di ogni thread creato — costruito in modo che altri agenti possano chiamarlo per ottenere informazioni in tempo reale

Confini degli artefatti per modalità (citazioni / report / risorse / sub-agenti): vedere [Modalità](guide/modes.md); principi di fedeltà del rendering: vedere [Pipeline di esportazione](architecture/export-pipeline.md).

!!! note "Provenienza della documentazione"

    La maggior parte delle pagine di questo sito MkDocs sono state generate o ricostruite dal codice e dai test correnti. Alcune pagine conservano anche il contesto di progettazione, le osservazioni e le decisioni tratte da discussioni precedenti con gli agenti. Quando un'affermazione della documentazione e l'implementazione differiscono, considerare il codice e i test correnti come fonte di verità.

<a id="where-to-next" data-pplx-source-anchor="true"></a>
## Dove andare ora

- **Usa gli strumenti** — segui la [Guida utente](guide/index.md) orientata alle attività.
- **Comprendi l'implementazione** — usa la [Mappa di lettura dell'architettura](architecture/index.md).
- **Lavora con l'interfaccia web osservata** — consulta il [Riferimento API Web](reference/api/index.md).
- **Modifica il progetto in sicurezza** — segui la [Guida per il manutentore](development/index.md).
