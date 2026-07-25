---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing.md"
translation_source_sha256: "1d44ab1bb1faabe00f9539537eb1048a3c363dd3c62485f795de1eb2ddbd9ac0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing" data-pplx-source-anchor="true"></a>
# Test

La suite di test risiede in `tests/`, al di fuori del pacchetto `pplx_export`, e viene eseguita completamente offline. I suoi input a forma di API sono dati simulati deterministici committati sotto `tests/fixtures/`; i test non dipendono da servizi live o da una configurazione utente reale.

Questa pagina contiene l'inventario corrente dei moduli di test e il flusso di lavoro per i contributori. Per la progettazione delle regressioni, vedere [Architettura del sistema di test](testing-architecture.md). Per il contratto dei dati di input, vedere [Fixture di test](fixtures.md).

<a id="running-the-tests" data-pplx-source-anchor="true"></a>
## Esecuzione dei test

```bash
uv run pytest tests
```

pytest è una dipendenza di sviluppo dichiarata. La suite garantisce:

- **Zero rete** — gli input simulati sono verificati; i percorsi che interagiscono con la rete sono coperti con fakes, `tmp_path` e `monkeypatch`.
- **Nessuna configurazione utente reale** — prima di importare qualsiasi modulo di produzione, `tests/conftest.py` crea una configurazione temporanea locale al processo e sovrascrive `PPLX_EXPORT_CONFIG`. Ogni test riceve quindi la propria configurazione placeholder `alice` / `bob` e ripristina il placeholder locale al processo successivamente. Le regressioni dei sottoprocessi verificano che una configurazione mancante o danneggiata del chiamante non possa interrompere la raccolta dei test.
- **Feedback rapido** — al 2026-07-25 il progetto ha osservato 435 test raccolti da 32 moduli `test_*.py` e ha eseguito l'intera suite in circa 13–25 secondi nelle esecuzioni di verifica locali. I conteggi sono un'istantanea datata del repository e cresceranno.

Selezioni utili:

| Comando | Effetto |
|---|---|
| `uv run pytest tests` | suite completa |
| `uv run pytest tests/test_units.py` | un modulo |
| `uv run pytest tests -k snapshot` | test il cui ID nodo corrisponde a `snapshot` |
| `uv run pytest tests -x -q` | fermati al primo fallimento, output silenzioso |
| `uv run pytest --collect-only -q` | aggiorna il conteggio dei casi raccolti |

<a id="current-module-inventory" data-pplx-source-anchor="true"></a>
## Inventario corrente dei moduli

Inventario sincronizzato con il repository il **2026-07-24**:

<!-- audit:inventory test-modules -->

| Famiglia funzionale | Moduli | Scopo |
|---|---|---|
| Snapshot di rendering | `test_render_snapshots.py` | ri-renderizza tutte le fixture simulate in modalità completa e scenario ridotto, quindi confronta i prodotti committati byte per byte |
| Utility core e condivise | `test_units.py` | stato, throttling, pianificazione, normalizzazione, denominazione degli asset, rilevamento della modalità, percorsi sicuri e regressioni trasversali |
| Contratti di documentazione, competenze e localizzazione | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | contratti di competenza locali al repository più test isolati su repository in miniatura per il revisore di documentazione in sola lettura e la pipeline di traduzione automatica |
| Configurazione, autenticazione e bootstrap | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | isolamento della configurazione esterna, profili di origine dei cookie, selezione delle credenziali e inizializzazione |
| Semantica di rendering e flusso di lavoro | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | attribuzione del flusso di lavoro, stati di interruzione, varianti di risposta, registrazione di audit e archi di relazione |
| Manutenzione di archivio offline e indice | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | arricchimento, comportamento di ripresa/idempotenza, rilevamento di eliminazione cross-account, stati terminali e livelli di report di stato/variazione dell'account offline |
| Regressioni di revisione | 16 moduli `test_fix_*.py` elencati di seguito | correzioni derivate dai risultati della revisione; i nomi dei moduli mantengono la discendenza della revisione |

<a id="review-regression-lineage" data-pplx-source-anchor="true"></a>
### Discendenza delle regressioni di revisione

Gli identificatori di revisione spiegano perché esiste una regressione; non sono l'architettura primaria della suite di test. La mappatura è deliberatamente molti-a-molti: un modulo può coprire diversi risultati, e un risultato può anche aggiungere casi a un modulo tematico esistente.

| Discendenza | Moduli dedicati |
|---|---|
| Revisione N | `test_fix_n01_inline_assets.py`, `test_fix_n02_spaces_link.py`, `test_fix_n03_n12.py`, `test_fix_n04_cookies.py`, `test_fix_n05_n06_n09.py`, `test_fix_n07_usage_checkpoint.py`, `test_fix_n08_throttle_overflow.py`, `test_fix_n10_table_header.py`, `test_fix_n11_batch_total.py` |
| Revisione V3 | `test_fix_v301_nested_sources_text.py`, `test_fix_v305_export_products.py` |
| Revisione V4 | `test_fix_v401_thread_dir_migration.py`, `test_fix_v402_manifest_count.py`, `test_fix_v403_handle_assets_idempotency.py`, `test_fix_v405_ask_post_steps.py` |
| Revisione V5 | `test_fix_v5_review.py`, più aggiunte mirate ai moduli tematici esistenti |

<!-- /audit:inventory test-modules -->

Le docstring dei moduli rimangono la spiegazione autorevole del vecchio comportamento di ogni risultato, del comportamento corretto e del confine della regressione.

<a id="how-snapshot-tests-reuse-the-production-re-render-path" data-pplx-source-anchor="true"></a>
## Come i test snapshot riutilizzano il percorso di ri-rendering di produzione

I test snapshot non implementano un renderer parallelo:

1. `render_fixture` in `tests/conftest.py` copia il `raw_entries.json` simulato di una fixture, l'opzionale `raw_blocks.json` e `thread.json` in una directory temporanea.
2. Chiama `pplx_export.commands.rerender_cmd.rerender`, la stessa funzione utilizzata da `pplx-export re-render`.
3. La factory di fixture `rendered` restituisce l'output fresco e la directory `golden/` committata della fixture.
4. I test confrontano `conversation.md` e ogni `turns/turn_*.md` byte per byte.

Gli invarianti di contenuto integrano l'uguaglianza byte: le risposte non devono collassare nel placeholder vuoto `(无)`, e residui di rappresentazione dict come `{'type': ...` non devono trapelare nel testo renderizzato.

<a id="adding-a-test" data-pplx-source-anchor="true"></a>
## Aggiunta di un test

- **Logica esistente** — aggiungi un test al modulo tematico corrispondente. Usa `tmp_path`, fakes e `monkeypatch`; non accedere mai alla rete o a `~/.config` reale.
- **Regressione di bug** — preferisci il modulo tematico corrispondente. Crea un modulo `test_fix_<lineage>_<slug>.py` quando mantenere la discendenza della revisione migliora materialmente la tracciabilità; non assumere un modulo per risultato.
- **Regressione di rendering** — aggiungi o riduci una fixture simulata, rigenera i suoi prodotti golden con lo strumento di manutenzione, quindi registrala in `test_render_snapshots.py` o aggiungi asserzioni specifiche dello scenario.

Segui lo stile vicino: annotazioni di tipo, `from __future__ import annotations` e docstring bilingue dei moduli.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Vedi anche

- [Fixture di test](fixtures.md) — input simulati, prodotti golden e contratto di manutenzione
- [Architettura del sistema di test](testing-architecture.md) — livelli di test e garanzie di regressione
- [Operazioni offline](../architecture/offline-operations.md) — il percorso di ri-rendering di produzione utilizzato dai test snapshot
