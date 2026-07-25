---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-rest-endpoints.md"
translation_source_sha256: "f1eb76feaffc48d910b988b54e4bcfcaa8b52a65502495399536392e4da7d146"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-rest-endpoints" data-pplx-source-anchor="true"></a>
# Riferimento API: Endpoint REST

<a id="rest-endpoints-grouped-by-purpose" data-pplx-source-anchor="true"></a>
## Endpoint REST (raggruppati per scopo)

Convenzione: `?version=2.18&source=default` è la stringa di query comune (richiesta dalla maggior parte degli endpoint).

<a id="thread-content-main-export-path" data-pplx-source-anchor="true"></a>
### Contenuto del thread (percorso di esportazione principale)
| Endpoint | Note |
|---|---|
| `GET /rest/thread/<uuid>` | **Risposta semplice**: `entries[]` (per turno; `text` contiene tutti i testi dei passaggi), `background_entries[]` (**flussi di lavoro completi dei subagenti**), `thread_metadata`. Supporta la paginazione `?cursor=` (`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **Risposta strutturata**: `entries[].blocks[]` (`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`), inclusi i prompt dei subagenti (`workflow_payload.objective_chunks`), URL firmati degli asset, contenuti dei file. Casi d'uso in `rest.py:SCHEMATIZED_USE_CASES` (workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | Elenco thread recenti (barra laterale home; include il campo `unread`) |
| **`POST /rest/thread/mark_viewed`** | **Conferma di lettura (scoperta 2026-07-21)**: corpo `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`; il non letto passa immediatamente. Il frontend chiama questo endpoint quando un thread viene aperto dalla barra laterale. Nota: l'evento analitico "thread visualizzato" **non cambia** lo stato non letto (escluso da test ripetuti) |
| `GET /rest/thread/<uuid>/members` | **Membri di condivisione a livello di thread** (testato): `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | Restituisce `{"will_request_org_join": bool, "org_display_name": str|null}` — relativo all'iscrizione all'organizzazione, **non correlato alla semantica di threadAccess** (escluso dai test) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | Presenti nell'analisi statica; GET diretto testato 400 (forma del parametro da determinare) |

<a id="asset-metadata-discovered-2026-07-20-lifesaver-for-expired-assets" data-pplx-source-anchor="true"></a>
### Metadati degli asset (scoperti 2026-07-20, **salvavita per asset scaduti**)

- **`GET /rest/assets/<asset_uuid>/data`** → metadati completi dell'asset (testato 200):
  - `asset_data.<type>.url` e `asset_data.download_info[].url`: **nuovi URL firmati CloudFront** —
    se l'URL firmato originale è scaduto al momento dell'archiviazione, l'indirizzo di download può essere recuperato con l'asset_uuid
    (a condizione che la piattaforma non abbia eliminato l'asset);
  - restituisce anche `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    (catena di ricerca inversa asset → thread);
  - campi come `signed_url: null`, `read_write_token`, `allow_remix`.
- **Limiti di applicabilità (testati)**: gli uuid reali degli asset funzionano; **gli handle di spazio di lavoro cloud con prefisso `toolu_` (DOC_FILE/CODE_FILE
  senza modulo URL) restituiscono 404 ASSET_NOT_FOUND**; `file-repository/download` richiede un URL reale e non accetta
  handle `file:repo/...` (400 failed to parse). Non esiste ancora un canale di download API per asset di tipo toolu.
- Correlati: `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access` (presenti nell'analisi statica, non testati).
- Implementato: lo strumento fornisce `pplx-export assets-backfill` (estrazione in linea + aggiornamento online tramite questo endpoint; vedere la nota sugli strumenti implementati in [§4](api-responses-errors.md)).

- **ENTRY_EXPIRED**: thread/artefatti più vecchi di ~3 mesi vengono eliminati dalla piattaforma; le richieste restituiscono un corpo di errore specifico — lo strumento li contrassegna come terminali e non riprova.
- **Eliminazione thread (2026-07-23 WebBridge + ricerca chunk, testata)**:
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, corpo `{entry_uuid, read_write_token}`,
  successo `200 {"status":"success"}`; l'eliminazione ripetuta è idempotente, restituisce ancora 200; l'eliminazione di un uuid inesistente → 404 `THREAD_NOT_FOUND`;
  **acquisizione di `read_write_token` (verificata in pratica lo stesso giorno)**: il primo `entries[].read_write_token` non vuoto
  nella risposta `GET /rest/thread/<uuid>` funziona (10/10 eliminazioni riuscite su thread live);
  **le operazioni di scrittura devono andare al dominio www** (il dominio apex restituisce 301 per DELETE). Nessuna mutazione GraphQL, nessun endpoint di eliminazione batch
  (l'eliminazione batch dell'interfaccia utente è un ciclo frontend per elemento). L'eliminazione è la distruzione a livello di thread, irreversibile; il thread scompare automaticamente dai suoi spazi
  (non è necessario `batch_remove_collection_threads` prima).
  Opzione soft: `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (corpo `{context_uuids:[...]}`; solo analisi statica, non testata).
- **ENTRY_DELETED**: dopo l'eliminazione di un thread, `GET /rest/thread/<uuid>` restituisce HTTP 400 `ENTRY_DELETED`
  (stesso 400 di ENTRY_EXPIRED ma codice diverso) — lo strumento lo mappa a `EntryDeletedError`
  (sottoclasse di `EntryExpiredError`); batch_state segna lo stato terminale `deleted`.
- Ogni voce di turno porta `context_uuid` (= l'UUID `past_session_contexts` della piattaforma — la chiave per il mapping dello spazio dei nomi a doppio ID).

<a id="spaces-collections" data-pplx-source-anchor="true"></a>
### Spazi (raccolte)
| Endpoint | Note |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **Metadati dello spazio**: `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. Valori di autorizzazione osservati: 4=proprietario, 2=può modificare. Quando l'account corrente non ha accesso in visualizzazione: `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` (HTTP ancora 200) |
| `POST /rest/collections/create_collection` | **Crea spazio** (2026-07-21 WebBridge capture, testato): corpo `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → restituisce la raccolta completa (uuid/slug/url/user_permission=4). Lo spazio BOT è stato creato in questo modo |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **Elenco thread dello spazio (richiesta cookie diretta; può sostituire l'indice spazio basato su browser)**: la risposta è un array; ogni elemento ha `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview`, ecc. **Paginazione: `&offset=N` (20 per pagina)**; `has_next_page` è su ogni elemento; `total_threads` legge alto (include sottothread computer; osservato 99 vs 27 di primo livello) |
| `POST /rest/collections/batch_move_threads` | **Sposta thread in uno spazio** (testato con successo): corpo `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}` — **usa context_uuid, non entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | Rimozione batch da uno spazio (corpo `{items:[{collection_uuid,...}]}`; non testato) |
| `GET /rest/collections/list_user_collections` | **Elenco spazi dell'account corrente** (testato, 16 elementi): ognuno ha `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page`, ecc. — più ricco di list_recent |
| `GET /rest/collections/list_recent` | Spazi recenti dell'account corrente (`title/uuid/emoji/is_pinned/link`; testato, 5 elementi) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | Informazioni sulla richiesta di accesso allo spazio (non testato) |
| `GET /rest/collections/<uuid>/join-requests` | Richieste di adesione (non esplorato) |
| `GET /rest/spaces/<uuid>/tasks` | Restituisce `{"tasks":[]}` — osservato vuoto; si sospetta siano attività pianificate/computer dello spazio, non un elenco di thread |
| `GET /rest/spaces/<uuid>/recurring_tasks` | Attività ricorrenti (non testato) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | Thread fissati/pianificati dello spazio (chiamati al caricamento della pagina; non esplorato) |

- **Diramazione tra account (branch_of; conoscenza verificata dall'utente 2026-07-23)**: un thread condiviso tramite uno spazio può essere
  "continuato" da un altro account membro in un thread di diramazione che è **visibile solo a, e continuato da, quell'account** — dopo che il thread dell'account A è condiviso tramite uno spazio,
  B può continuarlo in una diramazione privata di B. L'archivio non ha ancora istanze; i bordi delle relazioni non sono implementati per ora; i campi del segnale API del thread di diramazione
  (puntatore genitore / marcatore di diramazione) saranno verificati e registrati quando apparirà la prima istanza.

<a id="account-session" data-pplx-source-anchor="true"></a>
### Account / sessione
| Endpoint | Note |
|---|---|
| `GET /api/auth/session` | Sessione corrente `{user:{email,...}}` — utilizzata per la verifica dell'account e il probing del cambio automatico |
| `GET /api/auth/linked-accounts` | Vedi [§1.2](api-authentication.md) (elenco completo solo mentre il primario è attivo) |
| `GET /rest/user/info`, `/rest/user/settings` | Profilo utente / impostazioni (non esplorato) |

<a id="credit-usage-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Utilizzo del credito (scoperto 2026-07-20)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → utilizzo del credito per thread (testato 200):
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **Nota**: `thread_id` si aspetta il **context_uuid** (psc_uuid); passare entryUUID restituisce 403
  `thread_usage_forbidden` ("Il thread non appartiene all'utente corrente" — in realtà una forma ID errata).
- Fonti di context_uuid: `list_collection_threads` (l'indice spazio REST copre già 27/27),
  il campo `context_uuid` della voce del thread (archiviato come `psc_uuid` in thread.json).
- Solo i thread dell'account corrente possono essere interrogati (cross-account → 403) — lo scraping multi-account necessita di cambio automatico per account.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`: versione elenco; testato vuoto su entrambi gli account
  (sospetta fatturazione organizzativa; da determinare).
- Altri endpoint di fatturazione (`/rest/billing/credits/balance`, ecc.) nell'[appendice §7](api-discovery-roadmap.md); non esplorati.

<a id="official-export-backend-of-the-page-export-button-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Esportazione ufficiale (backend del pulsante "Esporta" della pagina; scoperto 2026-07-20)

- **`POST /rest/thread/export`**, corpo: `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<name>"}`
- Risposta: `{"file_content_64": "<base64>", "filename": "..."}`
- Formati testati: **`md`** (markdown ufficiale con intestazione logo `<img>`), **`pdf`** (binario PDF ~880KB),
  **`docx`** (zip PK ~350KB) — tutti HTTP 200. Altri valori di formato non testati.
- **Limite di contenuto (verificato)**: restituisce markdown **dell'intero thread** (riepilogo domanda + risposta + citazioni in nota a piè di pagina `[^1_N]`),
  **senza il corpo RESEARCH_REPORT** — il rapporto di deep research stesso può essere ottenuto solo tramite il suo URL firmato (§3.7);
  cioè l'attuale catena di URL firmati report.md **è la fonte ufficiale del rapporto** (stessa fonte del download del pannello artefatto della pagina); non è necessario passare a questo endpoint.
- Valore: il markdown ufficiale a livello di thread può servire come fonte di convalida incrociata a livello di conversazione (note a piè di pagina/formato citazione resi ufficialmente).

<a id="asset-report-download" data-pplx-source-anchor="true"></a>
### Download asset / rapporto
- **URL firmati CloudFront** nella risposta strutturata (`d2z0o16i8xm8ak.cloudfront.net`): download urllib diretto,
  nessun cookie/auth necessario; file multiversione numerati in ordine `created_at`.
- Fonte di fallback del rapporto di ricerca: l'URL S3 del passaggio RESEARCH_ANSWER (`ppl-ai-file-upload.s3.amazonaws.com`, **scade**);
  secondo fallback: estrazione dal rendering della pagina (KaTeX `<annotation>`).
- **Eliminazione ~3 mesi**: i collegamenti alle fonti di artefatti/rapporti scadono in modo irreversibile — le esportazioni devono essere tempestive.

<a id="other-observed-endpoints-page-load-not-explored" data-pplx-source-anchor="true"></a>
### Altri endpoint osservati (caricamento pagina; non esplorati)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates` (SSE), `/api/version`.

<a id="message-submission-and-telemetry-2026-07-20-webbridge-cdp" data-pplx-source-anchor="true"></a>
### Invio messaggi e telemetria (2026-07-20 WebBridge + CDP)

<a id="submission-endpoint-post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### Endpoint di invio: `POST /rest/sse/perplexity_ask`
- Esempi di corpo richiesta completi (esempi sintetici) sotto `docs/perplexity-api-samples/`:
  - `ask_envelope_deep_research.json` — turno di follow-up di deep research (2026-07-20; 39 parametri + query_str):
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + la catena di continuazione `last_backend_uuid`
  - `ask_envelope_search.json` — ricerca standard, nuova conversazione dalla home (2026-07-21; 35 parametri + query_str):
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json` — model council, nuova conversazione dalla home (2026-07-21; 36 parametri + query_str):
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- Campi chiave (turno di follow-up di deep research, testato):
  - `mode: "copilot"` (deep research); `model_preference: "pplx_alpha"`
  - **Catena di continuazione**: `last_backend_uuid` (uuid backend del turno precedente) + `query_source: "followup"`
  - `frontend_uuid` (nuovo uuid per questo turno), `read_write_token`, `target_collection_uuid` (spazio contenitore),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`** (millisecondi dalla prima pressione del tasto all'invio — telemetria comportamentale caricata con l'invio)
  - `use_schematized_api: true`, `supported_block_use_cases` (elenco blocchi completo, corrispondente a §3.1 strutturato),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- La risposta è uno stream SSE (il frontend lo consuma con fetch-event-source `getReader()` — il modulo app congela il riferimento fetch all'inizializzazione,
  **gli hook fetch/XHR collegati alla pagina sono inefficaci**; e **i corpi di risposta in streaming non vengono conservati dal browser** (`Network.getResponseBody` restituisce
  No data found) — la cattura è possibile solo tramite CDP `Network.getRequestPostData` (corpo richiesta disponibile)).
- Lo stato finale dello stream è esattamente le voci/blocchi di `/rest/thread/<uuid>` (stessi dati, consegnati in modo incrementale) —
  lo strumento di esportazione non ha bisogno di leggere lo stream; recupera lo stato finale direttamente.

<a id="telemetry-post-resteventanalytics-batched-high-frequency" data-pplx-source-anchor="true"></a>
#### Telemetria: `POST /rest/event/analytics` (in batch, alta frequenza)
Eventi osservati (con elementi essenziali event_data):
| event_name | Campi chiave | Note |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | evento di visualizzazione pagina — **non cambia lo stato non letto** (escluso dai test; la vera conferma di lettura è `POST /rest/thread/mark_viewed`, vedere §3.1) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs` (**millisecondi di permanenza in lettura per quel turno**), `userId`, `isPro`, `deviceInfo` (concorrenza/schermo/profondità colore) | telemetria della durata di lettura (non cambia lo stato non letto, escluso dai test) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | azione di invio |
| `query first llm token` | `startLLMTokenElapsed` (latenza primo token), `queryStr` completo | telemetria delle prestazioni |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, `queryStr` completo | ricevuta di successo |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | interazione con il selettore del modello council |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | visualizzazione pannello destro |
- Campi evento comuni: `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info` (hardwareConcurrency/schermo/profondità colore/architettura), `isBrowserExtension`, `web_platform`.
- **Nota**: un evento osservato portava un `userId` appartenente all'**altro account** (l'uid apparteneva all'account A mentre la sessione era già l'account B) —
  l'ID profilo dell'SDK di telemetria ha un ritardo nella cache; non giudicare l'account corrente dalla userId della telemetria.
- C'è anche il reporting ad alta frequenza di datadog RUM (`browser-intake-datadoghq.com/api/v2/rum`) (scroll/mouse/prestazioni; contenuto non analizzato).

<a id="mode-and-model-selection-2026-07-21-tested-on-a-paid-account" data-pplx-source-anchor="true"></a>
#### Selezione modalità e modello (2026-07-21, testato su un account a pagamento)
- **`GET /rest/models/config/v2` = tabella modelli autorevole**: `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`, `agentic_research_compare_models` (council default tre modelli).
  `pplx-ask models` chiama questo endpoint.
  - Corrispondenza ufficiale (testata): **search = `pplx_pro` (nome UI "Best"), research = `pplx_alpha`
    (nome UI "Deep research")**.
  - Elenco modelli selezionabili dall'UI in modalità search (senza Deep research): Best (pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **Il campo `mode` è sempre `"copilot"` — non un discriminatore di modalità** (uguale per search / deep research / model council).
- La discriminazione risiede in **`model_preference`**:
  - Search: `pplx_pro` (o l'ID modello selezionato dall'utente, ad es. `experimental`=Sonar 2, `gpt56_sol`…)
  - Deep research: `pplx_alpha` (**nessun selettore modello nell'UI**, fisso)
  - **Model council**: `pplx_agentic_research` + **`compare_model_preferences: [<2-3 models>]`**
    (default osservato `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`;
    l'UI è **selezione singola per slot**, che scende a 2 modelli nel follow-up).
  - Studio passo-passo: `pplx_study`; Computer: la famiglia `pplx_asi*`.
- Il selettore modello dell'area di composizione ("model ⌄") e il selettore council "N models ⌄" mappano i campi sopra;
  l'evento di telemetria `ask input model selector opened` porta `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels` (i thread di deep research precedenti avevano `searchMode: "research"`).
- Nuova conversazione: `query_source: "home"`, nessun `last_backend_uuid`, ha `frontend_context_uuid`;
  continuazione: catena `query_source: "followup"` + `last_backend_uuid`.

<a id="entrysearch_mode-the-authoritative-record-of-conversation-mode-settled-2026-07-22" data-pplx-source-anchor="true"></a>
#### entry.search_mode: il record autorevole della modalità di conversazione (definito 2026-07-22)
**Ogni voce** di `/rest/thread/<uuid>` porta `search_mode`, il record autorevole della piattaforma della modalità di conversazione di quel turno
(il segnale di rilevamento della modalità con la priorità più alta, `normalize.SEARCH_MODE_MAP`):

| search_mode | Significato (UI/modello) | Modalità archivio |
|---|---|---|
| `SEARCH` | ricerca normale (default_models.search=pplx_pro "Best" e modelli selezionabili dall'UI) | search |
| `STUDIO` | sessione labs (pplx_beta); l'UI lo raggruppa sotto search | search |
| `RESEARCH` | Deep research (default_models.research=pplx_alpha; UI fissa, nessun selettore) | deep-research |
| `AGENTIC_RESEARCH` | model council (pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | studio passo-passo (pplx_study) | study |
| `ASI` | Computer (pplx_asi*) | computer |

- Sondaggio valori nell'archivio: tutti e sei i valori hanno istanze nell'archivio reale; SEARCH e RESEARCH dominano,
  STUDIO successivo, ASI / STUDY / AGENTIC_RESEARCH rari.
- **pplx_alpha ⟺ RESEARCH prova incrociata**: 100+ voci platform-SEARCH + thread pplx_alpha nell'archivio sono al 100%
  `search_mode=RESEARCH`; 100+ thread pplx_pro puri sono tutti `search_mode=SEARCH` —
  la vecchia statistica "pplx_alpha è un modello comunemente usato per la ricerca semplice" era in realtà campioni di errore di classificazione e non è valida.
- Più valori possono apparire all'interno di un thread (cambio di modalità, ad esempio un mix SEARCH+RESEARCH osservato): il rilevamento prende il più alto per specificità
  computer>council>study>deep-research>search.

<a id="model-council-output-structure-and-expansion-behavior" data-pplx-source-anchor="true"></a>
#### Struttura dell'output del model council e comportamento di espansione
- Output a turno singolo = N blocchi specifici del modello "Council: <model name>" (ciascuno con query di recupero/sorgenti/risposta) + una parte di sintesi:
  **Where Models Agree** (matrice di consenso, per Finding confronto tre modelli ✓ + Evidence),
  **Where Models Disagree** (tabella di disaccordo, posizione di ciascun modello + ragioni della divergenza),
  **Unique Discoveries** (risultati unici di ciascun modello), seguiti da raccomandazioni di domande correlate — **tutto consegnato nello stesso stream SSE**.
- Comportamento di espansione (inclusa l'espansione **durante la generazione**): le righe espandibili portano un chevron ">" (righe dei passaggi / righe "Sources" / righe Council);
  cliccando si espandono — **rendering puramente lato client, zero richieste di contenuto**: delle 1208 richieste di questa sessione, 921 erano asset statici favicon/font;
  l'espansione stessa attiva solo caricamenti favicon e /api/version. L'espansione durante lo streaming non disturba la consegna continua.
- Latenza primo token osservata ~204s (tre modelli che generano in parallelo, marcatamente più lunga del singolo modello); conteggio sorgenti osservato 236.
- Elementi essenziali dell'automazione dell'area di composizione (Lexical): il testo deve essere iniettato tramite CDP `Input.insertText` (dopo execCommand/fill,
  lo stato interno di Lexical si desincronizza e Invio fallisce); l'invio può usare Invio CDP o fare clic sul pulsante con aria-label="提交" ("Submit")
  (la modalità council ha una freccia di invio esplicita).

<a id="behavior-when-continuing-a-historical-conversation-tested-2026-07-20" data-pplx-source-anchor="true"></a>
#### Comportamento quando si continua una conversazione storica (testato 2026-07-20)
1. Carica pagina thread → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. Invia follow-up → `rate-limit/status` → `sse/perplexity_ask` (con la catena `last_backend_uuid`) → analisi ad alta frequenza.
3. Durante la generazione → lo stream SSE viene renderizzato in modo incrementale; dopo il completamento, un altro batch di analisi (inclusa la durata di lettura `thread entry exited`).
4. I turni di follow-up di deep research producono anche strutture di rapporto (questo turno ha completato 5 passaggi).
