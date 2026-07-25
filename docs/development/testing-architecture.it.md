---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing-architecture.md"
translation_source_sha256: "ca93c1e43ccc41337097685ec6268f2d1f6a9997504b4a67683bce250b443b66"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing-architecture" data-pplx-source-anchor="true"></a>
# Architettura dei test

Il sistema di test di `pplx_export` è completamente offline, utilizza dati simulati verificati e blocca tramite snapshot il comportamento del renderer. Questa pagina descrive l'architettura e le garanzie; l'elenco dei moduli attuali si trova in [Testing](../development/testing.md), e i dettagli delle fixture in [Test fixtures](../development/fixtures.md).

La sezione mantiene la propria numerazione dalla [panoramica dell'architettura](../architecture/overview.md).

---

<a id="test-system" data-pplx-source-anchor="true"></a>
## Sistema di test

Esegui la suite con `uv run pytest tests`. I conteggi dei test vengono riportati dall'esecuzione corrente e non sono trattati come una costante architetturale.

<a id="layers" data-pplx-source-anchor="true"></a>
### Livelli

| Livello | Moduli rappresentativi | Contratto |
|---|---|---|
| Comportamento unitario puro | `test_units.py`, test di credenziali/cookie/config | isolare funzioni, classi, validazione e normalizzazione con input simulati |
| Semantica dei componenti | test di interruzione, stub-workflow, variante di risposta e relazioni | esercitare la cooperazione tra parser, renderer, stato e codice indice senza accesso alla rete |
| Comportamento offline comando/stato | test di backfill, sincronizzazione eliminazioni, inizializzazione e regressioni di revisione | eseguire percorsi di comando su directory temporanee e trasporti fittizi |
| Snapshot del rendering | `test_render_snapshots.py` | passare JSON simulato in formato API attraverso il percorso di re-rendering di produzione e confrontare tutti i byte Markdown con golden file committati |

Identificatori di revisione come N, V3, V4 e V5 sono metadati di tracciabilità attraverso questi livelli. Non definiscono un'architettura runtime separata e la loro relazione con i moduli di test non è necessariamente uno-a-uno.

<a id="snapshot-data-flow" data-pplx-source-anchor="true"></a>
### Flusso dei dati degli snapshot

1. Una fixture simulata fornisce `raw_entries.json`, `raw_blocks.json` opzionale e `thread.json`.
2. `tests/conftest.py::render_fixture` copia questi file in `tmp_path`.
3. La fixture chiama `commands.rerender_cmd.rerender`, il percorso di ricostruzione offline di produzione.
4. I nuovi file `conversation.md` e `turns/turn_*.md` vengono confrontati byte per byte con i prodotti golden `golden/` committati.

I golden sono aspettative generate, non una fonte di dati indipendente. Qualsiasi modifica al renderer che alteri i byte degli artefatti renderà rossa la suite di snapshot finché la modifica non viene revisionata e i golden non vengono rigenerati intenzionalmente.

<a id="isolation-and-trust-boundaries" data-pplx-source-anchor="true"></a>
### Confini di isolamento e fiducia

- **Origine delle fixture** — tutti gli input delle fixture committati sono dati simulati. Non sono copiati da account live, risposte API live, `web_archive/` o archivi privati.
- **Confine di rete** — i test utilizzano finti e percorsi offline; le fixture committate non richiedono credenziali o accesso alla rete.
- **Confine di configurazione** — la fixture autouse installa una configurazione dell'account segnaposto, quindi il vero `~/.config` di uno sviluppatore non determina i risultati.
- **Confine del filesystem** — il comportamento dei comandi e delle migrazioni viene eseguito sotto `tmp_path`; gli archivi utente non sono obiettivi di test.
- **Confine dei residui** — `tests/scrub_fixtures.py --check` rifiuta stringhe specifiche dell'ambiente configurate, percorsi assoluti locali e credenziali URL firmate senza modificare i file.

Insieme, le asserzioni unitarie, la semantica dei componenti, i test di stato dei comandi e gli snapshot a livello di byte proteggono sia la logica locale che il contratto di re-rendering end-to-end.
