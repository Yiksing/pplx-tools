---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/fixtures.md"
translation_source_sha256: "72f6f6faa0f4c2ef3a63b3f0a7c6bc0a16f9be6cb03225850e4d5d4b22193b30"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="test-fixtures" data-pplx-source-anchor="true"></a>
# Fixture di test

`tests/fixtures/` contiene **dati simulati** deterministici, a forma di API, per la
[suite di test](testing.md). Gli input modellano strutture rappresentative di thread e
workflow; i loro prodotti renderizzati sono impegnati come snapshot golden.

<a id="source-contract" data-pplx-source-anchor="true"></a>
## Contratto delle sorgenti

<!-- audit:contract fixture-source=simulated -->

Il contenuto corrente delle fixture impegnate è simulato:

- Le fixture nuove o aggiornate devono essere costruite come dati simulati; i contributori
  non devono popolarle importando `web_archive/`, dati di account utente, risposte API
  live o archivi privati.
- Nomi, identità, identificatori, prompt, risposte, payload di workflow, percorsi
  e URL nei file impegnati sono segnaposto di test.
- Il JSON rispecchia gli schemi di risposta e archivio di produzione solo per esercitare
  il comportamento del parser, renderer, stato e relazioni.
- Il repository non impegna una mappatura inversa dai segnaposto agli
  identificatori privati.

I termini **fixture a modalità completa** e **fixture a scenario ridotto** descrivono la
copertura del test e la forma dell'input, non la provenienza. Entrambi sono dati simulati.

<a id="directory-contract" data-pplx-source-anchor="true"></a>
## Contratto delle directory

Ogni directory di fixture contiene input simulati a forma di risposta grezza e,
dove è necessario il confronto con snapshot, un albero `golden/`:

| Percorso | Ruolo |
|---|---|
| `raw_entries.json` | voci di thread simulate nella forma della risposta di produzione |
| `raw_blocks.json` | blocchi di workflow simulati; assenti dove la modalità non ha risposta a blocchi |
| `thread.json` | metadati di thread archiviati simulati |
| `golden/conversation.md` + `golden/turns/turn_*.md` | prodotti generati dagli input simulati e confrontati byte per byte |

Le convenzioni deterministiche attuali includono:

- account segnaposto `alice` / `bob`, identità di esempio, uno spazio BOT
  segnaposto e un `read_write_token` segnaposto fisso;
- identificatori derivati da uuid5 etichettati con `5cbeef00`, preservando riferimenti
  incrociati intenzionali tra record simulati;
- identificatori `toolu_` simulati a lunghezza fissa etichettati con `5crub0`;
- prompt, titoli, testo di workflow e percorsi file generici; e
- stringhe di query di URL firmati rimosse.

Queste convenzioni rendono facile rilevare residui accidentali specifici dell'ambiente;
non implicano che gli identificatori simulati siano stati derivati da oggetti live.

<a id="inventory" data-pplx-source-anchor="true"></a>
## Inventario

<!-- audit:inventory fixture-directories -->

<a id="full-mode-fixtures" data-pplx-source-anchor="true"></a>
### Fixture a modalità completa

Queste sono conversazioni simulate complete per ogni modalità supportata:

| Fixture | Copertura |
|---|---|
| `search_demo` | ricerca, un turno; blocco di codice R e codice inline |
| `deep_research_demo` | deep research; conversione end-to-end dei delimitatori matematici |
| `computer_demo` | computer, rendering di workflow a sette turni |
| `council_demo` | rendering del comitato di modelli council con un grande payload annidato |
| `study_demo` | rendering della modalità studio |

<a id="reduced-scenario-fixtures" data-pplx-source-anchor="true"></a>
### Fixture a scenario ridotto

Questi sono payload simulati focalizzati contenenti solo le voci e
relazioni necessarie per una regressione. “Ridotto” non significa estratto da un
thread reale.

| Fixture | Copertura |
|---|---|
| `scenario_computer_answer_fallback` | recuperare la risposta da un blocco di workflow schematizzato quando il percorso FINAL semplice non è disponibile |
| `scenario_subagent_fallback` | renderizzare un titolo di sub-agente e i suoi propri elementi quando non esiste una corrispondenza di background |
| `scenario_user_response` | rendering domanda/risposta `WORKFLOW_ITEM_USER_RESPONSE` |
| `scenario_subagent_stub` | finestra di associazione di dieci secondi per uno stub di risultato di sub-agente non ancorato |
| `scenario_workflow_item_nested` | rendering di blocco collassato `WORKFLOW_ITEM_WORKFLOW` annidato |
| `scenario_limit_interrupted` | interruzione per limite di spesa, cascata di attribuzione, posizionamento dell'appendice e nessun doppio rendering |
| `scenario_canceled` | annotazione `WORKFLOW_CANCELED` |

<!-- /audit:inventory fixture-directories -->

<a id="maintaining-fixtures" data-pplx-source-anchor="true"></a>
## Manutenzione delle fixture

`tests/scrub_fixtures.py` normalizza i dati simulati, rigenera i prodotti
golden attraverso il renderer offline di produzione e impone un gate sui residui:

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **Rigenerazione** — ogni fixture viene renderizzata in una directory temporanea attraverso
  `pplx_export.commands.rerender_cmd.rerender`; le discrepanze nel conteggio dei turni causano l'aborto.
- **Normalizzazione deterministica** — testo segnaposto, UUID, valori `toolu_`,
  token e URL firmati vengono normalizzati in modo idempotente.
- **Gli input di sicurezza non sono provenienza** — la configurazione locale opzionale
  `tests/scrub_pairs.local.json` e la configurazione dell'account a livello utente estendono
  solo i controlli di sostituzione e residuo. Non devono essere usati come input per
  costruire scenari di fixture.
- **Modalità di controllo** — `--check` non esegue scritture e fallisce su residui configurati,
  percorsi assoluti locali o credenziali di URL firmati.

Esegui lo strumento di manutenzione dopo aver modificato l'input JSON simulato o l'output del renderer,
ed esegui `--check` prima di impegnare modifiche alle fixture.

<a id="golden-snapshot-authority" data-pplx-source-anchor="true"></a>
## Autorità dello snapshot golden

Il JSON simulato impegnato è l'autorità di input. Il Markdown golden è output
derivato: viene rigenerato da quel JSON con il percorso corrente di re-render di produzione
e poi impegnato per il confronto di regressione a livello di byte. Non deve essere modificato
come fonte di verità indipendente.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Vedi anche

- [Testing](testing.md) — come la suite consuma le fixture
- [Architettura del sistema di test](testing-architecture.md) — livelli di regressione
  e garanzie
- `tests/fixtures/README.md` — inventario delle fixture locale al repository
