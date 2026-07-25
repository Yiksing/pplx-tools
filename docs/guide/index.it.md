---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/index.md"
translation_source_sha256: "4687af317a6aa8c7f17c6b758463042f3f6fa6f00ba78bc0ec76464bc1bec69b"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="user-guide" data-pplx-source-anchor="true"></a>
# Guida utente

Documentazione orientata alle attività per installare, configurare e utilizzare
`pplx-export` e `pplx-ask`.

<a id="start-here" data-pplx-source-anchor="true"></a>
## Inizia qui

- [Per iniziare](getting-started.md) — installa i comandi, inizializza la
  configurazione ed esegui la prima esportazione.
- [Configurazione](configuration.md) — account, fonti di cookie, directory di output
  e impostazioni dello spazio BOT.

<a id="command-reference" data-pplx-source-anchor="true"></a>
## Riferimento comandi

- [pplx-export](pplx-export.md) — comandi di indicizzazione, esportazione e archiviazione batch.
- [pplx-ask](pplx-ask.md) — ricerca in streaming, deep-research, council e query
  di studio.
- [Comandi di manutenzione](maintenance-commands.md) — operazioni di re-render, backfill,
  relazioni e sincronizzazione.

<a id="archives-and-synchronization" data-pplx-source-anchor="true"></a>
## Archivi e sincronizzazione

- [Struttura dell'archivio](archive-layout.md) — file, indici, stato e risposte
  grezze conservate.
- [Modalità di conversazione](modes.md) — confini degli artefatti per ogni modalità supportata.
- [Sincronizzazione incrementale](incremental-sync.md) — arresto anticipato, checkpoint e comportamento
  di ripresa.

<a id="operations" data-pplx-source-anchor="true"></a>
## Operazioni

- [Limitazione della frequenza](rate-limiting.md) — cadenza sicura delle richieste e pianificazione.
- [Risoluzione dei problemi](troubleshooting.md) — guasti comuni e percorsi di ripristino.

Per i dettagli implementativi, proseguire con la
[mappa di lettura dell'architettura](../architecture/index.md).
