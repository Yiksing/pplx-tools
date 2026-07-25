---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-rest-endpoints.md"
translation_source_sha256: "f1eb76feaffc48d910b988b54e4bcfcaa8b52a65502495399536392e4da7d146"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-rest-endpoints" data-pplx-source-anchor="true"></a>
# API-Referenz: REST-Endpunkte

<a id="rest-endpoints-grouped-by-purpose" data-pplx-source-anchor="true"></a>
## REST-Endpunkte (nach Zweck gruppiert)

Konvention: `?version=2.18&source=default` ist der gemeinsame Query-String (von den meisten Endpunkten benötigt).

<a id="thread-content-main-export-path" data-pplx-source-anchor="true"></a>
### Thread-Inhalt (Hauptexportpfad)
| Endpunkt | Anmerkungen |
|---|---|
| `GET /rest/thread/<uuid>` | **Einfache Antwort**: `entries[]` (pro Runde; `text` enthält alle Schritttexte), `background_entries[]` (**Subagenten-Komplettworkflows**), `thread_metadata`. Unterstützt `?cursor=`-Paginierung (`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **Schematisierte Antwort**: `entries[].blocks[]` (`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`), einschließlich Subagenten-Prompts (`workflow_payload.objective_chunks`), signierten Asset-URLs, Dateiinhalten. Anwendungsfälle in `rest.py:SCHEMATIZED_USE_CASES` (workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | Aktuelle Thread-Liste (Home-Sidebar; enthält das Feld `unread`) |
| **`POST /rest/thread/mark_viewed`** | **Lesebestätigung (geknackt 2026-07-21)**: Body `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`; ungelesen wechselt sofort. Das Frontend ruft diesen Endpunkt auf, wenn ein Thread aus der Sidebar geöffnet wird. Hinweis: Das Analytics-Ereignis „thread viewed" **wechselt nicht** den ungelesen-Status (durch wiederholte Tests ausgeschlossen) |
| `GET /rest/thread/<uuid>/members` | **Thread-Freigabemitglieder** (getestet): `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | Gibt `{"will_request_org_join": bool, "org_display_name": str|null}` zurück – organisationsbezogen, **nicht verwandt mit threadAccess-Semantik** (durch Tests ausgeschlossen) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | In der statischen Analyse vorhanden; direkter GET-Test ergab 400 (Parameterform noch offen) |

<a id="asset-metadata-discovered-2026-07-20-lifesaver-for-expired-assets" data-pplx-source-anchor="true"></a>
### Asset-Metadaten (entdeckt 2026-07-20, **Lebensretter für abgelaufene Assets**)

- **`GET /rest/assets/<asset_uuid>/data`** → vollständige Asset-Metadaten (getestet 200):
  - `asset_data.<type>.url` und `asset_data.download_info[].url`: **frische CloudFront-signierte URLs** –
    falls die ursprüngliche signierte URL zum Archivierungszeitpunkt abgelaufen ist, kann die Download-Adresse mit der asset_uuid erneut abgerufen werden
    (sofern die Plattform das Asset nicht gelöscht hat);
  - gibt auch `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space` zurück
    (Asset → Thread-Rückwärtssuche);
  - Felder wie `signed_url: null`, `read_write_token`, `allow_remix`.
- **Anwendbarkeitsgrenzen (getestet)**: echte Asset-UUIDs funktionieren; **`toolu_`-präfixierte Cloud-Workspace-Handles (DOC_FILE/CODE_FILE
  ohne URL-Form) geben 404 ASSET_NOT_FOUND zurück**; `file-repository/download` benötigt eine echte URL und akzeptiert keine
  `file:repo/...`-Handles (400 fehlerhafte Analyse). Es gibt noch keinen API-Downloadkanal für toolu-Typ-Assets.
- Verwandt: `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access` (in der statischen Analyse vorhanden, ungetestet).
- Implementiert: Das Tool bietet `pplx-export assets-backfill` (Inline-Extraktion + Online-Aktualisierung über diesen Endpunkt; siehe Hinweis zu implementierten Tools in [§4](api-responses-errors.md)).

- **ENTRY_EXPIRED**: Threads/Artefakte, die älter als ~3 Monate sind, werden von der Plattform gelöscht; Anfragen geben einen spezifischen Fehlerbody zurück – das Tool markiert sie als endgültig und wiederholt nicht.
- **Thread-Löschung (2026-07-23 WebBridge + Chunk-Recherche, getestet)**:
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, Body `{entry_uuid, read_write_token}`,
  Erfolg `200 {"status":"success"}`; wiederholte Löschung ist idempotent, weiterhin 200; Löschen einer nicht existierenden UUID → 404 `THREAD_NOT_FOUND`;
  **`read_write_token`-Erfassung (am selben Tag in der Praxis verifiziert)**: das erste nicht-leere `entries[].read_write_token`
  in der `GET /rest/thread/<uuid>`-Antwort funktioniert (10/10 Löschungen erfolgreich bei Live-Threads);
  **Schreiboperationen müssen an die www-Domain gehen** (die Apex-Domain gibt 301 für DELETE zurück). Keine GraphQL-Mutation, kein Batch-Lösch-Endpunkt
  (UI-Batch-Löschung ist eine Frontend-Einzelschleife). Löschung ist Zerstörung auf Thread-Ebene, nicht wiederherstellbar; der Thread verschwindet automatisch aus seinen Spaces
  (kein vorheriges `batch_remove_collection_threads` erforderlich).
  Sanfte Option: `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (Body `{context_uuids:[...]}`; nur statische Analyse, ungetestet).
- **ENTRY_DELETED**: Nachdem ein Thread gelöscht wurde, gibt `GET /rest/thread/<uuid>` HTTP 400 `ENTRY_DELETED` zurück
  (gleicher 400 wie ENTRY_EXPIRED, aber ein anderer Code) – das Tool ordnet es `EntryDeletedError` zu
  (Unterklasse von `EntryExpiredError`); batch_state markiert den Endzustand `deleted`.
- Jeder Rundeintrag trägt `context_uuid` (= die Plattform-`past_session_contexts`-UUID – der Schlüssel zur Dual-ID-Namespace-Zuordnung).

<a id="spaces-collections" data-pplx-source-anchor="true"></a>
### Spaces (Sammlungen)
| Endpunkt | Anmerkungen |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **Space-Metadaten**: `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. Beobachtete Berechtigungswerte: 4=Eigentümer, 2=kann bearbeiten. Wenn das aktuelle Konto keinen Lesezugriff hat: `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` (HTTP dennoch 200) |
| `POST /rest/collections/create_collection` | **Space erstellen** (2026-07-21 WebBridge-Aufzeichnung, getestet): Body `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → gibt die vollständige Sammlung zurück (uuid/slug/url/user_permission=4). Der BOT-Space wurde auf diese Weise erstellt |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **Space-Thread-Liste (direkte Cookie-Anfrage; kann den browserbasierten Space-Index ersetzen)**: Die Antwort ist ein Array; jedes Element hat `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview` usw. **Paginierung: `&offset=N` (20 pro Seite)**; `has_next_page` ist auf jedem Element; `total_threads` liest hoch (enthält Computer-Subthreads; beobachtet 99 vs. 27 oberste Ebene) |
| `POST /rest/collections/batch_move_threads` | **Threads in einen Space verschieben** (getestet erfolgreich): Body `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}` – **context_uuid verwenden, nicht entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | Batch-Entfernen aus einem Space (Body `{items:[{collection_uuid,...}]}`; ungetestet) |
| `GET /rest/collections/list_user_collections` | **Space-Liste des aktuellen Kontos** (getestet, 16 Elemente): jedes hat `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page` usw. – umfangreicher als list_recent |
| `GET /rest/collections/list_recent` | Aktuelle Spaces des Kontos (`title/uuid/emoji/is_pinned/link`; getestet, 5 Elemente) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | Space-Zugriffsanfrage-Info (ungetestet) |
| `GET /rest/collections/<uuid>/join-requests` | Beitrittsanfragen (nicht untersucht) |
| `GET /rest/spaces/<uuid>/tasks` | Gibt `{"tasks":[]}` zurück – beobachtet leer; vermutlich geplante/Computer-Aufgaben des Spaces, keine Thread-Liste |
| `GET /rest/spaces/<uuid>/recurring_tasks` | Wiederkehrende Aufgaben (ungetestet) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | Space-angeheftete/geplante Threads (werden beim Seitenladen aufgerufen; nicht untersucht) |

- **Kontoübergreifende Verzweigung (branch_of; benutzerverifiziertes Wissen 2026-07-23)**: Ein über einen Space geteilter Thread kann
  von einem anderen Mitgliedskonto in einen Zweig-Thread „fortgesetzt" werden, der **nur für dieses Konto sichtbar ist und von diesem fortgesetzt wird** – nachdem Konto A's Thread über einen Space geteilt wurde,
  kann B ihn in einen B-privaten Zweig fortsetzen. Das Archiv hat noch kein Beispiel; Beziehungskanten sind vorerst nicht implementiert; die API-Signalfelder des Zweig-Threads
  (Elternzeiger / Verzweigungsmarker) werden verifiziert und aufgezeichnet, sobald das erste Beispiel auftaucht.

<a id="account-session" data-pplx-source-anchor="true"></a>
### Konto / Sitzung
| Endpunkt | Anmerkungen |
|---|---|
| `GET /api/auth/session` | Aktuelle Sitzung `{user:{email,...}}` – wird für Kontoverifizierung und Auto-Switch-Sondierung verwendet |
| `GET /api/auth/linked-accounts` | Siehe [§1.2](api-authentication.md) (vollständige Liste nur, während das primäre Konto aktiv ist) |
| `GET /rest/user/info`, `/rest/user/settings` | Benutzerprofil / Einstellungen (nicht untersucht) |

<a id="credit-usage-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Guthabenverbrauch (entdeckt 2026-07-20)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → Guthabenverbrauch pro Thread (getestet 200):
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **Hinweis**: `thread_id` erwartet die **context_uuid** (psc_uuid); die Übergabe von entryUUID ergibt 403
  `thread_usage_forbidden` („Thread gehört nicht zum aktuellen Benutzer" – eigentlich eine falsche ID-Form).
- context_uuid-Quellen: `list_collection_threads` (der REST-Space-Index deckt bereits 27/27 ab),
  das Feld `context_uuid` des Thread-Eintrags (archiviert als `psc_uuid` in thread.json).
- Nur die Threads des aktuellen Kontos können abgefragt werden (kontoübergreifend → 403) – Multi-Konto-Scraping benötigt kontoübergreifendes Auto-Switching.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`: Listenversion; getestet leer auf beiden Konten
  (vermutlich nur Organisationsabrechnung; noch offen).
- Weitere Abrechnungsendpunkte (`/rest/billing/credits/balance` usw.) im [§7-Anhang](api-discovery-roadmap.md); nicht untersucht.

<a id="official-export-backend-of-the-page-export-button-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Offizieller Export (Backend des „Export"-Buttons auf der Seite; entdeckt 2026-07-20)

- **`POST /rest/thread/export`**, Body: `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<name>"}`
- Antwort: `{"file_content_64": "<base64>", "filename": "..."}`
- Getestete Formate: **`md`** (offizielles Markdown mit einem Logo-`<img>`-Header), **`pdf`** (%PDF-Binär ~880KB),
  **`docx`** (PK-Zip ~350KB) – alle HTTP 200. Andere Formatwerte ungetestet.
- **Inhaltsgrenze (verifiziert)**: gibt **gesamten Thread** als Markdown zurück (Frage + Antwortzusammenfassung + `[^1_N]`-Fußnotenzitate),
  **ohne den RESEARCH_REPORT-Body** – der Deep-Research-Bericht selbst kann nur über seine signierte URL bezogen werden (§3.7);
  d.h. die aktuelle report.md-signierte-URL-Kette **ist die offizielle Berichtsquelle** (gleiche Quelle wie der Download des Seiten-Artefakt-Panels); kein Wechsel zu diesem Endpunkt erforderlich.
- Wert: Das offizielle Thread-Markdown kann als konversationsübergreifende Kreuzvalidierungsquelle dienen (offiziell gerenderte Zitatfußnoten/Format).

<a id="asset-report-download" data-pplx-source-anchor="true"></a>
### Asset / Bericht-Download
- **CloudFront-signierte URLs** in der schematisierten Antwort (`d2z0o16i8xm8ak.cloudfront.net`): direkter urllib-Download,
  kein Cookie/Auth erforderlich; mehrversionierte Dateien nummeriert in `created_at`-Reihenfolge.
- Research-Bericht-Fallback-Quelle: die S3-URL des RESEARCH_ANSWER-Schritts (`ppl-ai-file-upload.s3.amazonaws.com`, **läuft ab**);
  zweiter Fallback: Seiten-Rendering-Extraktion (KaTeX `<annotation>`).
- **~3-Monats-Bereinigung**: Artefakt-/Berichtsquellen-Links laufen unwiederbringlich ab – Exporte müssen rechtzeitig erfolgen.

<a id="other-observed-endpoints-page-load-not-explored" data-pplx-source-anchor="true"></a>
### Andere beobachtete Endpunkte (Seitenladen; nicht untersucht)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates` (SSE), `/api/version`.

<a id="message-submission-and-telemetry-2026-07-20-webbridge-cdp" data-pplx-source-anchor="true"></a>
### Nachrichtenübermittlung und Telemetrie (2026-07-20 WebBridge + CDP)

<a id="submission-endpoint-post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### Übermittlungsendpunkt: `POST /rest/sse/perplexity_ask`
- Vollständige Anfrage-Body-Beispiele (synthetische Beispiele) unter `docs/perplexity-api-samples/`:
  - `ask_envelope_deep_research.json` – Deep-Research-Folgerunde (2026-07-20; 39 Parameter + query_str):
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + die `last_backend_uuid`-Fortsetzungskette
  - `ask_envelope_search.json` – Standardsuche, neue Konversation von der Startseite (2026-07-21; 35 Parameter + query_str):
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json` – Model Council, neue Konversation von der Startseite (2026-07-21; 36 Parameter + query_str):
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- Schlüsselfelder (Deep-Research-Folgerunde, getestet):
  - `mode: "copilot"` (Deep Research); `model_preference: "pplx_alpha"`
  - **Fortsetzungskette**: `last_backend_uuid` (Backend-UUID der vorherigen Runde) + `query_source: "followup"`
  - `frontend_uuid` (neue UUID für diese Runde), `read_write_token`, `target_collection_uuid` (enthaltender Space),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`** (Millisekunden vom ersten Tastendruck bis zum Absenden – Verhaltenstelemetrie, die mit der Übermittlung hochgeladen wird)
  - `use_schematized_api: true`, `supported_block_use_cases` (vollständige Blockliste, passend zu §3.1 schematisiert),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- Die Antwort ist ein SSE-Stream (das Frontend konsumiert ihn mit fetch-event-source `getReader()` – das App-Modul friert die Fetch-Referenz beim Initialisieren ein,
  **seitengebundene Fetch/XHR-Hooks sind wirkungslos**; und **Streaming-Antwortkörper werden vom Browser nicht beibehalten** (`Network.getResponseBody` gibt
  No data found zurück) – Erfassung ist nur über CDP `Network.getRequestPostData` möglich (Anfrage-Body verfügbar)).
- Der Endzustand des Streams sind genau die Einträge/Blöcke von `/rest/thread/<uuid>` (gleiche Daten, inkrementell geliefert) –
  das Export-Tool muss den Stream nicht lesen; es zieht den Endzustand direkt.

<a id="telemetry-post-resteventanalytics-batched-high-frequency" data-pplx-source-anchor="true"></a>
#### Telemetrie: `POST /rest/event/analytics` (gebündelt, hohe Frequenz)
Beobachtete Ereignisse (mit event_data-Grundlagen):
| event_name | Schlüsselfelder | Anmerkungen |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | Seitenansichts-Ereignis – **wechselt nicht den ungelesen-Status** (durch Tests ausgeschlossen; die echte Lesebestätigung ist `POST /rest/thread/mark_viewed`, siehe §3.1) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs` (**Lese-Verweildauer in Millisekunden für diese Runde**), `userId`, `isPro`, `deviceInfo` (Gleichzeitigkeit/Bildschirm/Farbtiefe) | Lese-Dauer-Telemetrie (wechselt nicht den ungelesen-Status, durch Tests ausgeschlossen) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | Absendeaktion |
| `query first llm token` | `startLLMTokenElapsed` (Latenz bis zum ersten Token), vollständig `queryStr` | Leistungstelemetrie |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, vollständig `queryStr` | Erfolgsbestätigung |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | Council-Modellauswahl-Interaktion |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | Rechtes-Bereich-Ansicht |
- Gemeinsame Ereignisfelder: `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info` (hardwareConcurrency/Bildschirm/Farbtiefe/Architektur), `isBrowserExtension`, `web_platform`.
- **Hinweis**: Ein beobachtetes Ereignis trug eine `userId`, die zum **anderen Konto** gehörte (die uid gehörte zu Konto A, während die Sitzung bereits Konto B war) –
  die Profil-ID des Telemetrie-SDKs hat Cache-Verzögerung; beurteilen Sie das aktuelle Konto nicht anhand der Telemetrie-userId.
- Es gibt auch Datadog RUM (`browser-intake-datadoghq.com/api/v2/rum`) mit hochfrequenter Berichterstattung (Scroll/Maus/Leistung; Inhalt nicht analysiert).

<a id="mode-and-model-selection-2026-07-21-tested-on-a-paid-account" data-pplx-source-anchor="true"></a>
#### Modus- und Modellauswahl (2026-07-21, getestet auf einem kostenpflichtigen Konto)
- **`GET /rest/models/config/v2` = maßgebliche Modelltabelle**: `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`, `agentic_research_compare_models` (Council-Standard drei Modelle).
  `pplx-ask models` ruft diesen Endpunkt auf.
  - Offizielle Entsprechung (getestet): **search = `pplx_pro` (UI-Name „Best"), research = `pplx_alpha`
    (UI-Name „Deep research")**.
  - Im Suchmodus über UI auswählbare Modellliste (ohne Deep research): Best (pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **Das Feld `mode` ist immer `"copilot"` – kein Modus-Diskriminator** (gleich für Suche / Deep Research / Model Council).
- Die Diskriminierung liegt in **`model_preference`**:
  - Suche: `pplx_pro` (oder die vom Benutzer ausgewählte Modell-ID, z.B. `experimental`=Sonar 2, `gpt56_sol`…)
  - Deep Research: `pplx_alpha` (**kein Modellauswähler in der UI**, festgelegt)
  - **Model Council**: `pplx_agentic_research` + **`compare_model_preferences: [<2-3 models>]`**
    (beobachteter Standard `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`;
    die UI ist **Einzelauswahl pro Slot**, reduziert auf 2 Modelle bei Folgerunden).
  - Schritt-für-Schritt-Studium: `pplx_study`; Computer: die `pplx_asi*`-Familie.
- Der Modellauswähler im Eingabebereich („model ⌄") und der Council-Auswähler „N models ⌄" bilden die obigen Felder ab;
  das Telemetrie-Ereignis `ask input model selector opened` trägt `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels` (frühere Deep-Research-Threads hatten `searchMode: "research"`).
- Neue Konversation: `query_source: "home"`, kein `last_backend_uuid`, hat `frontend_context_uuid`;
  Fortsetzung: `query_source: "followup"` + `last_backend_uuid`-Kette.

<a id="entrysearch_mode-the-authoritative-record-of-conversation-mode-settled-2026-07-22" data-pplx-source-anchor="true"></a>
#### entry.search_mode: die maßgebliche Aufzeichnung des Konversationsmodus (geklärt 2026-07-22)
**Jeder Eintrag** von `/rest/thread/<uuid>` trägt `search_mode`, die maßgebliche Aufzeichnung der Plattform für den Konversationsmodus dieser Runde
(das Signal mit der höchsten Priorität für die Moduserkennung, `normalize.SEARCH_MODE_MAP`):

| search_mode | Bedeutung (UI/Modell) | Archiv-Modus |
|---|---|---|
| `SEARCH` | normale Suche (default_models.search=pplx_pro „Best" und über UI auswählbare Modelle) | search |
| `STUDIO` | Labs-Sitzung (pplx_beta); die UI gruppiert es unter Suche | search |
| `RESEARCH` | Deep Research (default_models.research=pplx_alpha; UI festgelegt, kein Auswähler) | deep-research |
| `AGENTIC_RESEARCH` | Model Council (pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | Schritt-für-Schritt-Studium (pplx_study) | study |
| `ASI` | Computer (pplx_asi*) | computer |

- Archivweite Werterhebung: Alle sechs Werte haben Instanzen im realen Archiv; SEARCH und RESEARCH dominieren,
  STUDIO als nächstes, ASI / STUDY / AGENTIC_RESEARCH selten.
- **pplx_alpha ⟺ RESEARCH-Kreuzbeweis**: 100+ Plattform-SEARCH-Einträge + pplx_alpha-Threads im Archiv sind zu 100%
  `search_mode=RESEARCH`; 100+ reine pplx_pro-Threads sind alle `search_mode=SEARCH` –
  die alte Statistik „pplx_alpha ist ein häufig verwendetes Modell für einfache Suche" waren tatsächlich Fehlklassifizierungsproben und gilt nicht.
- Mehrere Werte können innerhalb eines Threads auftreten (Moduswechsel, z.B. eine beobachtete SEARCH+RESEARCH-Mischung): Erkennung nimmt den höchsten nach Spezifität
  computer>council>study>deep-research>search.

<a id="model-council-output-structure-and-expansion-behavior" data-pplx-source-anchor="true"></a>
#### Model Council-Ausgabestruktur und Erweiterungsverhalten
- Einzelrunden-Ausgabe = N modellspezifische „Council: <model name>"-Blöcke (jeweils mit Abfragen/Quellen/Antwort) + ein Syntheseteil:
  **Where Models Agree** (Konsensmatrix, pro-Finding Drei-Modell-✓-Vergleich + Evidence),
  **Where Models Disagree** (Abweichungstabelle, Position jedes Modells + Gründe für Abweichung),
  **Unique Discoveries** (einzigartige Erkenntnisse jedes Modells), gefolgt von verwandten Fragen-Empfehlungen – **alle im selben SSE-Stream geliefert**.
- Erweiterungsverhalten (einschließlich Erweiterung **während der Generierung**): Erweiterbare Zeilen tragen ein „>"-Chevron (Schrittzeilen / „Sources"-Zeilen / Council-Zeilen);
  Klicken erweitert sie – **reines clientseitiges Rendering, null Inhaltsanfragen**: von den 1208 Anfragen dieser Sitzung waren 921 Favicon/Schriftart-Statik-Assets;
  Erweiterung selbst löst nur Favicon-Ladevorgänge und /api/version aus. Erweiterung während des Streamings stört die fortgesetzte Lieferung nicht.
- Latenz bis zum ersten Token beobachtet ~204s (drei Modelle generieren parallel, deutlich länger als Einzelmodell); Quellenanzahl beobachtet 236.
- Eingabebereich (Lexical)-Automatisierungsgrundlagen: Text muss über CDP `Input.insertText` injiziert werden (nach execCommand/fill
  desynchronisiert Lexicals interner Zustand und Enter schlägt fehl); Übermittlung kann CDP Enter oder Klick auf den Button mit aria-label="提交" („Absenden") verwenden
  (Council-Modus hat einen expliziten Absendepfeil).

<a id="behavior-when-continuing-a-historical-conversation-tested-2026-07-20" data-pplx-source-anchor="true"></a>
#### Verhalten beim Fortsetzen einer historischen Konversation (getestet 2026-07-20)
1. Thread-Seite laden → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. Folgerunde absenden → `rate-limit/status` → `sse/perplexity_ask` (mit der `last_backend_uuid`-Kette) → hochfrequente Analysen.
3. Während der Generierung → der SSE-Stream rendert inkrementell; nach Abschluss eine weitere Charge Analysen (einschließlich `thread entry exited`-Lesezeit).
4. Deep-Research-Folgerunden erzeugen ebenfalls Berichtsstrukturen (diese Runde hat 5 Schritte abgeschlossen).
