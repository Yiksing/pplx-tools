---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-discovery-roadmap.md"
translation_source_sha256: "60c675dcc583c059cd489ea085f9c2923f9447f7bbafb0a7ac991fee9f8add08"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="endpoint-discovery-and-improvement-roadmap" data-pplx-source-anchor="true"></a>
# Roadmap di scoperta e miglioramento degli endpoint

*Parte del riferimento API web Perplexity — mappa completa all'[indice API](index.md).*

<a id="known-unexplored-tbd-items" data-pplx-source-anchor="true"></a>
## Elementi noti non esplorati / da definire

- Campo di ordinamento `list_collection_threads` e semantica esatta di `total_threads`
  (snapshot account live 2026-07: riportati 99 vs 27 elementi di primo livello).
- Spettro completo dei valori `threadAccess`/`access`/`user_permission` (campione osservato 2026-07:
  threadAccess 5 normale, 1 con 🔒; collection access 1;
  permission 4 owner / 2 can edit; anche i dati assets portano thread_access).
- Forme corrette dei parametri per `list_ask_threads`, `list_scheduled_computer_tasks` (GET diretto 400).
- Strutture delle risposte di `collections/*/request-access-info`, `spaces/<uuid>/recurring_tasks`, `assets/<id>/members`.
- Perché le operazioni GraphQL della dashboard non sono registrate (PERSISTED_QUERY_NOT_FOUND): version skew o context gating;
  quando necessario, rieseguire l'estrazione con hash live da cattura di rete.
- Divisione del lavoro tra `frontend_uuid` vs `uuid` vs `context_uuid` nei thread computer.
- Campi segnale API dei thread ramificati con spazio condiviso cross-account (branch_of)
  (puntatore padre / marcatore di ramo) — meccanismo confermato (fine
  [§3.3](api-rest-endpoints.md)); nessuna istanza archiviata al 2026-07-23;
  verificare e registrare quando appare la prima.

<a id="endpoint-discovery-method-frontend-bundle-static-analysis-zero-api-cost-established-2026-07-20" data-pplx-source-anchor="true"></a>
## Metodo di scoperta degli endpoint: analisi statica del bundle frontend (costo API zero; stabilito 2026-07-20)

Scoperti **147 endpoint `/rest/`** in un unico passaggio; il metodo è riutilizzabile (rieseguire dopo revisioni del frontend):

1. L'entry di caricamento pagina `_spa/assets/index.html-*.js` fa riferimento a `bootstrap-*.js` (il runtime contiene tutte le mappature dei chunk);
2. Estrarre 682 nomi di chunk (pattern `<name>-<hash8>.js`) dal bootstrap; filtrare quelli relativi alle API per nome
   (client/api/thread/collection/space/computer…);
3. Scaricare direttamente dal CDN pubblico `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js`
   (nessun cookie necessario); moduli hub: `platform-core-*` (client API), `spa-shell-*`, `spa-metadata-*`;
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` produce l'elenco degli endpoint (147);
5. I chunk rivelano anche le forme delle chiamate (es. `format:'md'` e `file_content_64` di export).
6. Esistono anche sourcemap: `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (non esplorate).

<a id="appendix-147-endpoints-grouped-by-category-archive-relevance-marked" data-pplx-source-anchor="true"></a>
### Appendice: 147 endpoint raggruppati per categoria (rilevanza per archiviazione contrassegnata)

- **thread**: `/rest/thread/{entry_uuid_or_slug}`, `/rest/thread/export`★, `/rest/thread/{uuid}/members`,
  `/rest/thread/list_recent`, `/rest/thread/list_ask_threads`, `/rest/thread/list_pinned_ask_threads`,
  `/rest/thread/list_scheduled_computer_tasks`, `/rest/thread/request-access-info/{uuid}`
- **collezioni/spazi**★: vedere la tabella completa [§3.3](api-rest-endpoints.md) (incl. batch_move/batch_remove, list_user_collections, request-access-info,
  recurring_tasks, pins/threads, scheduled_threads)
- **assets**★: `/rest/assets/{asset_id}/data`, `/rest/assets/{asset_id}/members`,
  `/rest/assets/{asset_id}/published-access`, `/rest/assets/sites/{site_id}/publish-info`
- **analytics**: `/rest/analytics/computer/usage`, `/rest/analytics/computer/usage/members`
  (entrambi 403 NOT_ORG_MEMBER — solo account organizzativi)
- **modelli/skills**: `/rest/models/config(/v2)`, `/rest/skills`, `/rest/skills/selectable`,
  `/rest/skills/grants`, `/rest/skills/submissions(/source)`
- **file/caricamenti**: `/rest/file-repository/*` (list/download/get-file-upload-urls/delete-files…),
  `/rest/files/list(/list-infinite/list-errors)`, `/rest/uploads/(batch_)create_upload_url(s)`,
  `/rest/connectors/attachments/upload`
- **tasks/computer**: `/rest/tasks/`, `/rest/tasks/{task_id}`, `/rest/tasks/shortcuts/mentions`,
  `/rest/tasks/shortcuts/paste/{copy_token}`, `/rest/computer/asset`, `/rest/computer/menu`,
  `/rest/computer/onboarding_cards`
- **utente/auth**: `/rest/user/settings`, `/rest/user/get_user_ai_profile`, `/rest/user/promotions`,
  `/rest/user/site-instructions`, `/rest/auth/get_special_profile`, `/rest/visitor/*`
- **fatturazione/stripe**: `/rest/billing/*` (credits/paypal/subscription…), `/rest/stripe/*`
- **enterprise/org**: `/rest/enterprise/*`, `/rest/organizations/{id}/credit-limits*`,
  `/rest/pplx-api/v2/enterprise-api-org`
- **sse**: `/rest/sse/attachment_processing/subscribe`, `/rest/sse/index_files`,
  `/rest/sse/perplexity_terminate`, `/rest/sse/related-queries/{entry_uuid}`
- **verticali** (irrilevanti per l'archiviazione): `/rest/finance/*`, `/rest/sports/*`, `/rest/travel/hotels/{slug}`,
  `/rest/health-assistant/*`, `/rest/article/{uuid_or_slug}`
- **varie**: `/rest/pins`, `/rest/rate-limit/(all|status)`, `/rest/notifications/web-push/*`,
  `/rest/attribution/*`, `/rest/homepage-widgets/upsell`, `/rest/ntp/upsell/`, `/rest/sidebar/upsell/`,
  `/rest/incentives/comet-activation`, `/rest/connector-service/usage`

(★ = direttamente rilevante per l'archiviazione)

<a id="endpoint-tool-capability-status-and-roadmap" data-pplx-source-anchor="true"></a>
## Stato endpoint → capacità dello strumento e roadmap

Lo stato di implementazione di seguito è stato sincronizzato con il codice corrente e la suite di test
il **2026-07-24**. Le evidenze API mantengono la data e l'ambito dell'osservazione live originale
o dell'analisi statica; questa sincronizzazione della documentazione non ha riesaminato
endpoint privati. I conteggi account/archivio sono istantanee, non garanzie a livello di piattaforma.

Significati dello stato:

- **Implementato** — un percorso CLI o di produzione corrente utilizza l'endpoint per la
  capacità dichiarata.
- **Parziale** — l'endpoint è in uso, ma la capacità a valle nella roadmap rimane incompleta.
- **Testato, non integrato** — il comportamento live dell'API è stato osservato, ma nessun percorso
  dello strumento lo consuma.
- **Pianificato** — esistono evidenze, ma l'implementazione non è iniziata.
- **Bloccato** — un noto blocco upstream o di protocollo impedisce l'implementazione.
- **Chiuso** — le evidenze hanno confutato l'uso proposto o lo hanno posto fuori ambito.

<a id="capability-status-matrix" data-pplx-source-anchor="true"></a>
### Matrice dello stato delle capacità

| Endpoint / operazione | Base di verifica | Integrazione corrente | Stato | Gap rimanente |
|---|---|---|---|---|
| `collections/get_collection` | osservazione live + codice corrente | `spaces --fetch-meta` costruisce l'indice proprietario/membro dello spazio | **Implementato** | — |
| `collections/list_collection_threads` | osservazione live + codice corrente | `space-index` usa REST per impostazione predefinita con mappatura dual-ID context_uuid; WebBridge è fallback | **Implementato** | Ordine di ordinamento e semantica esatta di `total_threads` rimangono da definire |
| `assets/<uuid>/data` | testato live 2026-07-20 + codice corrente | `assets-backfill --online` aggiorna gli URL firmati per UUID di asset reali | **Implementato** | Gli handle workspace cloud `toolu_` sono al di fuori della copertura di questo endpoint |
| `LibraryThreadsRelayQuery` e query di paginazione | APQ catturato + codice corrente | `index`/`batch` forniscono indicizzazione completa e arresto anticipato incrementale | **Implementato** | Le query di filtro per modalità della dashboard rimangono bloccate separatamente |
| `collections/list_user_collections` | osservato live 2026-07 + codice corrente | `init` usa una corrispondenza esatta del titolo per scoprire lo spazio BOT | **Parziale** | Costruire un registro autoritativo degli spazi dell'account per la scoperta di nuovi spazi e la ricostruzione di `spaces` |
| `credits/thread-usage` | testato live 2026-07-20 + codice corrente | `usage-backfill` scrive `index/credit_usage_<account>.json` | **Parziale** | Decidere se arricchire `thread.json` e/o le righe dell'indice della libreria senza duplicare l'autorità |
| `models/config/v2` | testato live 2026-07-21 + codice corrente | `pplx-ask models` elenca modelli/predefiniti; le costanti di normalizzazione vengono verificate incrociate con esso | **Parziale** | Persistere metadati di visualizzazione del modello stabili nei record di archivio/indice se utili |
| `POST /rest/thread/export` | md/pdf/docx testato live 2026-07-20 | nessuna integrazione CLI | **Testato, non integrato** | Archiviazione multi-formato e riconciliazione Markdown ufficiale |
| `rate-limit/status` | osservazione caricamento pagina; semantica della risposta non esplorata | nessuno | **Pianificato** | Validare la semantica prima di usarlo per la limitazione adattiva |
| `file-repository/list-files` | solo analisi statica frontend | nessuno | **Pianificato** | Validare se può enumerare/recuperare handle `toolu_`; uno snapshot di archivio 2026-07 ha registrato 270 handle senza un canale di download |
| `pins`, `tasks/{id}` | analisi statica frontend / osservazioni caricamento pagina | nessuno | **Pianificato** | Arricchimento dello stato pin e della durata delle attività computer |
| `thread/<uuid>/members` | testato live 2026-07 | nessuno | **Pianificato** | Bordi di condivisione a livello di thread per il grafo delle relazioni |
| Dashboard GraphQL `threadGroup` + filtri modalità | chiamate dirette hanno restituito `PERSISTED_QUERY_NOT_FOUND` | nessuno | **Bloccato** | Recuperare gli hash delle query persistenti live o stabilire il contesto richiesto |
| `related_queries` / `sse/related-queries` | indagini forensi sull'archivio concluse 2026-07-23 | non produce deliberatamente bordi di relazione | **Chiuso** | Riaprire solo se nuove evidenze stabiliscono un'identità di thread risolvibile |

<a id="active-roadmap" data-pplx-source-anchor="true"></a>
### Roadmap attiva

<a id="p0-official-export-integration" data-pplx-source-anchor="true"></a>
#### P0 — Integrazione export ufficiale

- **Archiviazione multi-formato**: conservare opzionalmente i prodotti PDF/DOCX restituiti da
  `POST /rest/thread/export`.
- **Riconciliazione renderer**: confrontare il Markdown ufficiale dell'intero thread con
  `conversation.md` come segnale di regressione indipendente.

<a id="p1-space-discovery" data-pplx-source-anchor="true"></a>
#### P1 — Scoperta spazi

- Promuovere `list_user_collections` da ricerca per titolo BOT a un registro autoritativo
  degli spazi con ambito account, utilizzato per la scoperta di nuovi spazi e la ricostruzione di `spaces`.

<a id="p2-metadata-risk-control-and-asset-rescue" data-pplx-source-anchor="true"></a>
#### P2 — Metadati, controllo del rischio e recupero asset

- Decidere e documentare il confine di autorità per l'utilizzo del credito: mantenere il
  dedicato `credit_usage_<account>.json`, o arricchire anche `thread.json` /
  righe della libreria.
- Aggiungere metadati di visualizzazione del modello, stato pin, durata delle attività computer e relazioni
  di condivisione dei thread solo dove la semantica dell'endpoint è stabile.
- Validare `rate-limit/status` prima di progettare la limitazione adattiva.
- Testare `file-repository/list-files` come possibile percorso di recupero `toolu_` prima
  di aggiungere qualsiasi mutazione dell'archivio.

<a id="p3-blocked-discovery" data-pplx-source-anchor="true"></a>
#### P3 — Scoperta bloccata

- Ricatturare gli hash delle query persistenti GraphQL della dashboard solo se l'indicizzazione
  incrementale per modalità diventa abbastanza preziosa da giustificare il costo
  di manutenzione.

<a id="closed-decisions-not-adopted" data-pplx-source-anchor="true"></a>
### Decisioni chiuse / non adottate

- **Export ufficiale come fonte di report**: confutato. L'endpoint restituisce
  Markdown dell'intero thread senza il corpo del report; la catena di URL firmati rimane
  la fonte ufficiale per `report.md` ([§3.6](api-rest-endpoints.md)).
- **Relazioni da `related_queries`**: confutato 2026-07-23. Gli UUID degli elementi non sono
  UUID dei thread e i testi delle raccomandazioni non si risolvevano in query archiviate;
  non vengono costruiti bordi di relazione ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)`: osservato come solo organizzazione
  (`403 NOT_ORG_MEMBER`) per gli account testati.
- `thread/request-access-info`: testato come relativo all'adesione all'organizzazione, non un
  segnale `threadAccess`.
- Le verticali fatturazione/Stripe/enterprise e finanza/sport rimangono al di fuori
  dell'ambito dello strumento di archiviazione.

---

*Questo documento integra [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md) (architettura dello strumento) e [overview.md](../../architecture/overview.md) (progettazione del sistema).*
