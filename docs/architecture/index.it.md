---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/index.md"
translation_source_sha256: "a64006f8b94ad04a3bc498468e674f3b8a22f27242c9bb7b8c5a9252019cc751"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="architecture-reading-map" data-pplx-source-anchor="true"></a>
# Mappa di lettura dell'architettura

Riferimento a livello di meccanismo per gli strumenti pplx (`pplx-export` / `pplx-ask`):
dipendenze, pipeline, macchine a stati, contratti dati e confini di affidabilità.
Per un utilizzo orientato alle attività, inizia con la [Guida utente](../guide/index.md).

!!! note "Ambito e fonte di verità"

    Queste pagine spiegano l'architettura di `pplx_export/` per agenti e
    ingegneri che mantengono il progetto. I riferimenti alle righe usano `file.py:NN`,
    relativi a `pplx_export/`. Le descrizioni sono state verificate rispetto al
    repository il 2026-07-23 (`__version__ = "0.1.0"`,
    `pplx_export/__init__.py:31`); il codice e i test correnti rimangono autorevoli.

<a id="start-with-the-system-map" data-pplx-source-anchor="true"></a>
## Inizia con la mappa del sistema

- [Panoramica dell'architettura](overview.md) — livelli, responsabilità dei moduli e
  grafico delle dipendenze a livello di import.

<a id="follow-a-runtime-flow" data-pplx-source-anchor="true"></a>
## Segui un flusso di esecuzione

- [Pipeline di esportazione](export-pipeline.md) — recupero, conservazione della risposta grezza,
  rilevamento della modalità e rendering Markdown.
- [Sub-agenti e interruzioni](subagents-interruptions.md) — attribuzione del
  payload e semantica di interruzione/ripresa.
- [pplx-ask e account](ask-and-accounts.md) — query in streaming e
  cambio cookie multi-account.

<a id="understand-data-and-reliability" data-pplx-source-anchor="true"></a>
## Comprendi dati e affidabilità

- [Modello dati e contratto di directory](data-model.md) — modelli, confini di
  scrittura e contratto di archivio su disco.
- [Limitazione della frequenza e gestione degli errori](rate-limiting-errors.md) — throttling,
  backoff, stati terminali e instradamento degli errori.
- [Operazioni offline](offline-operations.md) — re-rendering senza rete,
  ricostruzione delle relazioni e pipeline di manutenzione locale.

<a id="related-references" data-pplx-source-anchor="true"></a>
## Riferimenti correlati

- [Riferimento API Web](../reference/api/index.md) — contratti REST/GraphQL osservati,
  semantica delle risposte e note di scoperta.
- [Guida per il manutentore](../development/index.md) — architettura dei test, flusso di lavoro
  del contributore e contratti di fixture simulati.
