# API Reference: REST Endpoints

## REST endpoints (grouped by purpose)

Convention: `?version=2.18&source=default` is the common query string (required by most endpoints).

### Thread content (main export path)
| Endpoint | Notes |
|---|---|
| `GET /rest/thread/<uuid>` | **Plain response**: `entries[]` (per turn; `text` contains all step texts), `background_entries[]` (**subagent complete workflows**), `thread_metadata`. Supports `?cursor=` pagination (`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **Schematized response**: `entries[].blocks[]` (`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`), including subagent prompts (`workflow_payload.objective_chunks`), asset signed URLs, file contents. Use cases in `rest.py:SCHEMATIZED_USE_CASES` (workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | Recent thread list (home sidebar; includes the `unread` field) |
| **`POST /rest/thread/mark_viewed`** | **Read receipt (cracked 2026-07-21)**: body `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`; unread flips immediately. The frontend calls this endpoint when a thread is opened from the sidebar. Note: the analytics "thread viewed" event **does not flip** unread (ruled out by repeated tests) |
| `GET /rest/thread/<uuid>/members` | **Thread-level share members** (tested): `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | Returns `{"will_request_org_join": bool, "org_display_name": str|null}` — org-join related, **unrelated to threadAccess semantics** (ruled out by testing) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | Present in static analysis; direct GET tested 400 (parameter shape TBD) |

### Asset metadata (discovered 2026-07-20, **lifesaver for expired assets**)

- **`GET /rest/assets/<asset_uuid>/data`** → full asset metadata (tested 200):
  - `asset_data.<type>.url` and `asset_data.download_info[].url`: **fresh CloudFront signed URLs** —
    if the original signed URL has expired at archive time, the download address can be re-fetched with the asset_uuid
    (provided the platform has not purged the asset);
  - also returns `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    (asset → thread reverse-lookup chain);
  - fields such as `signed_url: null`, `read_write_token`, `allow_remix`.
- **Applicability boundaries (tested)**: real asset uuids work; **`toolu_`-prefixed cloud-workspace handles (DOC_FILE/CODE_FILE
  without URL form) return 404 ASSET_NOT_FOUND**; `file-repository/download` requires a real URL and does not accept
  `file:repo/...` handles (400 failed to parse). No API download channel exists for toolu-type assets yet.
- Related: `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access` (present in static analysis, untested).
- Implemented: the tool provides `pplx-export assets-backfill` (inline extraction + online refresh via this endpoint; see the implemented-tools note in [§4](api-responses-errors.md)).

- **ENTRY_EXPIRED**: threads/artifacts older than ~3 months are purged by the platform; requests return a specific error body — the tool marks them terminal and does not retry.
- **Thread deletion (2026-07-23 WebBridge + chunk research, tested)**:
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, body `{entry_uuid, read_write_token}`,
  success `200 {"status":"success"}`; repeat deletion is idempotent, still 200; deleting a nonexistent uuid → 404 `THREAD_NOT_FOUND`;
  **`read_write_token` acquisition (verified in practice the same day)**: the first non-empty `entries[].read_write_token`
  in the `GET /rest/thread/<uuid>` response works (10/10 deletions succeeded on live threads);
  **write operations must go to the www domain** (the apex domain returns 301 for DELETE). No GraphQL mutation, no batch-delete endpoint
  (UI batch delete is a frontend per-item loop). Deletion is thread-level destruction, unrecoverable; the thread automatically disappears from its spaces
  (no need to `batch_remove_collection_threads` first).
  Soft option: `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (body `{context_uuids:[...]}`; static analysis only, untested).
- **ENTRY_DELETED**: after a thread is deleted, `GET /rest/thread/<uuid>` returns HTTP 400 `ENTRY_DELETED`
  (same 400 as ENTRY_EXPIRED but a different code) — the tool maps it to `EntryDeletedError`
  (subclass of `EntryExpiredError`); batch_state marks the terminal state `deleted`.
- Each turn entry carries `context_uuid` (= the platform `past_session_contexts` UUID — the key to the dual-ID namespace mapping).

### Spaces (collections)
| Endpoint | Notes |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **Space metadata**: `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. Observed permission values: 4=owner, 2=can edit. When the current account has no view access: `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` (HTTP still 200) |
| `POST /rest/collections/create_collection` | **Create space** (2026-07-21 WebBridge capture, tested): body `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → returns the full collection (uuid/slug/url/user_permission=4). The BOT space was created this way |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **Space thread list (direct cookie request; can replace the browser-based space-index)**: the response is an array; each item has `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview`, etc. **Pagination: `&offset=N` (20 per page)**; `has_next_page` is on each item; `total_threads` reads high (includes computer sub-threads; observed 99 vs 27 top-level) |
| `POST /rest/collections/batch_move_threads` | **Move threads into a space** (tested succeeded): body `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}` — **use context_uuid, not entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | Batch remove from a space (body `{items:[{collection_uuid,...}]}`; untested) |
| `GET /rest/collections/list_user_collections` | **Current account's space list** (tested, 16 items): each has `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page`, etc. — richer than list_recent |
| `GET /rest/collections/list_recent` | Current account's recent spaces (`title/uuid/emoji/is_pinned/link`; tested, 5 items) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | Space access-request info (untested) |
| `GET /rest/collections/<uuid>/join-requests` | Join requests (not explored) |
| `GET /rest/spaces/<uuid>/tasks` | Returns `{"tasks":[]}` — observed empty; suspected to be scheduled/computer tasks of the space, not a thread list |
| `GET /rest/spaces/<uuid>/recurring_tasks` | Recurring tasks (untested) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | Space pinned/scheduled threads (called on page load; not explored) |

- **Cross-account branching (branch_of; user-verified knowledge 2026-07-23)**: a thread shared via a space can be
  "continued" by another member account into a branch thread that is **visible only to, and continued by, that account** — after account A's thread is shared through a space,
  B can continue it into a B-private branch. The archive has no instance yet; relations edges are not implemented for now; the branch thread's API signal fields
  (parent pointer / branch marker) will be verified and recorded when the first instance appears.

### Account / session
| Endpoint | Notes |
|---|---|
| `GET /api/auth/session` | Current session `{user:{email,...}}` — used for account verification and auto-switch probing |
| `GET /api/auth/linked-accounts` | See [§1.2](api-authentication.md) (full list only while primary is active) |
| `GET /rest/user/info`, `/rest/user/settings` | User profile / settings (not explored) |

### Credit usage (discovered 2026-07-20)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → per-thread credit usage (tested 200):
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **Note**: `thread_id` expects the **context_uuid** (psc_uuid); passing entryUUID yields 403
  `thread_usage_forbidden` ("Thread does not belong to the current user" — actually a wrong id form).
- context_uuid sources: `list_collection_threads` (the REST space-index already covers 27/27),
  the thread entry's `context_uuid` field (archived as `psc_uuid` in thread.json).
- Only the current account's threads can be queried (cross-account → 403) — multi-account scraping needs per-account auto-switching.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`: list version; tested empty on both accounts
  (suspected org-billing only; TBD).
- Other billing endpoints (`/rest/billing/credits/balance`, etc.) in the [§7 appendix](api-discovery-roadmap.md); not explored.

### Official export (backend of the page "Export" button; discovered 2026-07-20)

- **`POST /rest/thread/export`**, body: `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<name>"}`
- Response: `{"file_content_64": "<base64>", "filename": "..."}`
- Tested formats: **`md`** (official markdown with a logo `<img>` header), **`pdf`** (%PDF binary ~880KB),
  **`docx`** (PK zip ~350KB) — all HTTP 200. Other format values untested.
- **Content boundary (verified)**: returns **whole-thread** markdown (query + answer summary + `[^1_N]` footnote citations),
  **without the RESEARCH_REPORT body** — the deep-research report itself can only be obtained via its signed URL (§3.7);
  i.e. the current report.md signed-URL chain **is the official report source** (same source as the page artifact-panel download); no need to switch to this endpoint.
- Value: the official thread-level markdown can serve as a conversation-level cross-validation source (officially rendered citation footnotes/format).

### Asset / report download
- **CloudFront signed URLs** in the schematized response (`d2z0o16i8xm8ak.cloudfront.net`): direct urllib download,
  no cookie/auth needed; multi-version files numbered in `created_at` order.
- Research report fallback source: the S3 URL of the RESEARCH_ANSWER step (`ppl-ai-file-upload.s3.amazonaws.com`, **expires**);
  second fallback: page-render extraction (KaTeX `<annotation>`).
- **~3-month purge**: artifact/report source links expire irrecoverably — exports must be timely.

### Other observed endpoints (page load; not explored)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates` (SSE), `/api/version`.

### Message submission and telemetry (2026-07-20 WebBridge + CDP)

#### Submission endpoint: `POST /rest/sse/perplexity_ask`
- Full request body samples (synthetic examples) under `docs/perplexity-api-samples/`:
  - `ask_envelope_deep_research.json` — deep-research follow-up turn (2026-07-20; 39 params + query_str):
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + the `last_backend_uuid` continuation chain
  - `ask_envelope_search.json` — standard search, new conversation from home (2026-07-21; 35 params + query_str):
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json` — model council, new conversation from home (2026-07-21; 36 params + query_str):
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- Key fields (deep-research follow-up turn, tested):
  - `mode: "copilot"` (deep research); `model_preference: "pplx_alpha"`
  - **Continuation chain**: `last_backend_uuid` (previous turn's backend uuid) + `query_source: "followup"`
  - `frontend_uuid` (new uuid for this turn), `read_write_token`, `target_collection_uuid` (containing space),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`** (milliseconds from first keystroke to submit — behavioral telemetry uploaded with the submission)
  - `use_schematized_api: true`, `supported_block_use_cases` (full block list, matching §3.1 schematized),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- The response is an SSE stream (the frontend consumes it with fetch-event-source `getReader()` — the app module freezes the fetch reference at init,
  **page-attached fetch/XHR hooks are ineffective**; and **streaming response bodies are not retained by the browser** (`Network.getResponseBody` returns
  No data found) — capture is only possible via CDP `Network.getRequestPostData` (request body available)).
- The stream's final state is exactly the entries/blocks of `/rest/thread/<uuid>` (same data, delivered incrementally) —
  the export tool doesn't need to read the stream; it pulls the final state directly.

#### Telemetry: `POST /rest/event/analytics` (batched, high frequency)
Observed events (with event_data essentials):
| event_name | Key fields | Notes |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | page-view event — **does not flip unread** (ruled out by testing; the real read receipt is `POST /rest/thread/mark_viewed`, see §3.1) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs` (**reading dwell milliseconds for that turn**), `userId`, `isPro`, `deviceInfo` (concurrency/screen/color depth) | reading-duration telemetry (does not flip unread, ruled out by testing) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | submit action |
| `query first llm token` | `startLLMTokenElapsed` (first-token latency), full `queryStr` | performance telemetry |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, full `queryStr` | success receipt |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | council model selector interaction |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | right-pane view |
- Common event fields: `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info` (hardwareConcurrency/screen/color depth/architecture), `isBrowserExtension`, `web_platform`.
- **Note**: one observed event carried a `userId` belonging to the **other account** (the uid belonged to account A while the session was already account B) —
  the telemetry SDK's profile id has cache lag; don't judge the current account by telemetry userId.
- There is also datadog RUM (`browser-intake-datadoghq.com/api/v2/rum`) high-frequency reporting (scroll/mouse/performance; content not parsed).

#### Mode and model selection (2026-07-21, tested on a paid account)
- **`GET /rest/models/config/v2` = authoritative model table**: `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`, `agentic_research_compare_models` (council default three models).
  `pplx-ask models` calls this endpoint.
  - Official correspondence (tested): **search = `pplx_pro` (UI name "Best"), research = `pplx_alpha`
    (UI name "Deep research")**.
  - search-mode UI selectable model list (no Deep research): Best (pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **The `mode` field is always `"copilot"` — not a mode discriminator** (same for search / deep research / model council).
- Discrimination lives in **`model_preference`**:
  - Search: `pplx_pro` (or the user-selected model id, e.g. `experimental`=Sonar 2, `gpt56_sol`…)
  - Deep research: `pplx_alpha` (**no model selector in UI**, fixed)
  - **Model council**: `pplx_agentic_research` + **`compare_model_preferences: [<2-3 models>]`**
    (observed default `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`;
    the UI is **per-slot single-select**, dropping to 2 models on follow-up).
  - Step-by-step study: `pplx_study`; Computer: the `pplx_asi*` family.
- The compose-area model selector ("model ⌄") and the council "N models ⌄" selector map to the fields above;
  the telemetry event `ask input model selector opened` carries `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels` (earlier deep-research threads had `searchMode: "research"`).
- New conversation: `query_source: "home"`, no `last_backend_uuid`, has `frontend_context_uuid`;
  continuation: `query_source: "followup"` + `last_backend_uuid` chain.

#### entry.search_mode: the authoritative record of conversation mode (settled 2026-07-22)
**Every entry** of `/rest/thread/<uuid>` carries `search_mode`, the platform's authoritative record of that turn's conversation mode
(the highest-priority mode-detection signal, `normalize.SEARCH_MODE_MAP`):

| search_mode | Meaning (UI/model) | Archive mode |
|---|---|---|
| `SEARCH` | normal search (default_models.search=pplx_pro "Best" and UI-selectable models) | search |
| `STUDIO` | labs session (pplx_beta); the UI groups it under search | search |
| `RESEARCH` | Deep research (default_models.research=pplx_alpha; UI fixed, no selector) | deep-research |
| `AGENTIC_RESEARCH` | model council (pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | step-by-step study (pplx_study) | study |
| `ASI` | Computer (pplx_asi*) | computer |

- Archive-wide value survey: all six values have instances in the real archive; SEARCH and RESEARCH dominate,
  STUDIO next, ASI / STUDY / AGENTIC_RESEARCH rare.
- **pplx_alpha ⟺ RESEARCH cross-proof**: 100+ platform-SEARCH-entry + pplx_alpha threads in the archive are 100%
  `search_mode=RESEARCH`; 100+ pure pplx_pro threads are all `search_mode=SEARCH` —
  the old statistic "pplx_alpha is a commonly used model for plain search" was actually classifier-misjudgment samples and does not hold.
- Multiple values can appear within one thread (mode switching, e.g. an observed SEARCH+RESEARCH mix): detection takes the highest by specificity
  computer>council>study>deep-research>search.

#### Model council output structure and expansion behavior
- Single-turn output = N model-specific "Council: <model name>" blocks (each with retrieval queries/sources/answer) + a synthesis part:
  **Where Models Agree** (consensus matrix, per-Finding three-model ✓ comparison + Evidence),
  **Where Models Disagree** (disagreement table, each model's position + reasons for divergence),
  **Unique Discoveries** (each model's unique findings), followed by related-question recommendations — **all delivered in the same SSE stream**.
- Expansion behavior (including expansion **during generation**): expandable rows carry a ">" chevron (step rows / "Sources" rows / Council rows);
  clicking expands them — **pure client-side rendering, zero content requests**: of this session's 1208 requests, 921 were favicon/font static assets;
  expansion itself only triggers favicon loads and /api/version. Expanding during streaming does not disturb continued delivery.
- First-token latency observed ~204s (three models generating in parallel, markedly longer than single-model); source count observed 236.
- Compose-area (Lexical) automation essentials: text must be injected via CDP `Input.insertText` (after execCommand/fill,
  Lexical's internal state desyncs and Enter fails); submission can use CDP Enter or click the button with aria-label="提交" ("Submit")
  (council mode has an explicit submit arrow).

#### Behavior when continuing a historical conversation (tested 2026-07-20)
1. Load thread page → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. Submit follow-up → `rate-limit/status` → `sse/perplexity_ask` (with the `last_backend_uuid` chain) → high-frequency analytics.
3. During generation → the SSE stream renders incrementally; after completion, another batch of analytics (including `thread entry exited` reading duration).
4. deep-research follow-up turns also produce report structures (this turn completed 5 steps).
