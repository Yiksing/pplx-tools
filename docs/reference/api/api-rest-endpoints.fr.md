---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-rest-endpoints.md"
translation_source_sha256: "f1eb76feaffc48d910b988b54e4bcfcaa8b52a65502495399536392e4da7d146"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-rest-endpoints" data-pplx-source-anchor="true"></a>
# Référence API : Points de terminaison REST

<a id="rest-endpoints-grouped-by-purpose" data-pplx-source-anchor="true"></a>
## Points de terminaison REST (regroupés par objectif)

Convention : `?version=2.18&source=default` est la chaîne de requête commune (requise par la plupart des points de terminaison).

<a id="thread-content-main-export-path" data-pplx-source-anchor="true"></a>
### Contenu des fils (chemin d'exportation principal)
| Point de terminaison | Notes |
|---|---|
| `GET /rest/thread/<uuid>` | **Réponse simple** : `entries[]` (par tour ; `text` contient tous les textes d'étape), `background_entries[]` (**workflows complets des sous-agents**), `thread_metadata`. Prend en charge la pagination `?cursor=` (`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **Réponse schématisée** : `entries[].blocks[]` (`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`), y compris les invites des sous-agents (`workflow_payload.objective_chunks`), les URL signées des ressources, le contenu des fichiers. Cas d'utilisation dans `rest.py:SCHEMATIZED_USE_CASES` (workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | Liste des fils récents (barre latérale d'accueil ; inclut le champ `unread`) |
| **`POST /rest/thread/mark_viewed`** | **Accusé de lecture (découvert le 2026-07-21)** : corps `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}` ; le statut non lu bascule immédiatement. Le frontend appelle ce point de terminaison lorsqu'un fil est ouvert depuis la barre latérale. Remarque : l'événement analytique « fil consulté » **ne bascule pas** le statut non lu (exclu par des tests répétés) |
| `GET /rest/thread/<uuid>/members` | **Membres de partage au niveau du fil** (testé) : `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | Renvoie `{"will_request_org_join": bool, "org_display_name": str|null}` — lié à l'adhésion à une organisation, **sans rapport avec la sémantique threadAccess** (exclu par des tests) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | Présents dans l'analyse statique ; GET direct testé 400 (forme du paramètre à déterminer) |

<a id="asset-metadata-discovered-2026-07-20-lifesaver-for-expired-assets" data-pplx-source-anchor="true"></a>
### Métadonnées des ressources (découvertes le 2026-07-20, **salvatrices pour les ressources expirées**)

- **`GET /rest/assets/<asset_uuid>/data`** → métadonnées complètes de la ressource (testé 200) :
  - `asset_data.<type>.url` et `asset_data.download_info[].url` : **nouvelles URL signées CloudFront** —
    si l'URL signée originale a expiré au moment de l'archivage, l'adresse de téléchargement peut être récupérée avec l'asset_uuid
    (à condition que la plateforme n'ait pas purgé la ressource) ;
  - renvoie également `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    (chaîne de recherche inverse ressource → fil) ;
  - champs tels que `signed_url: null`, `read_write_token`, `allow_remix`.
- **Limites d'applicabilité (testées)** : les vrais uuid de ressources fonctionnent ; **les handles d'espace de travail cloud préfixés par `toolu_` (DOC_FILE/CODE_FILE
  sans forme d'URL) renvoient 404 ASSET_NOT_FOUND** ; `file-repository/download` nécessite une URL réelle et n'accepte pas
  les handles `file:repo/...` (400 échec d'analyse). Aucun canal de téléchargement API n'existe encore pour les ressources de type toolu.
- Connexes : `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access` (présents dans l'analyse statique, non testés).
- Implémenté : l'outil fournit `pplx-export assets-backfill` (extraction en ligne + rafraîchissement en ligne via ce point de terminaison ; voir la note sur les outils implémentés dans [§4](api-responses-errors.md)).

- **ENTRY_EXPIRED** : les fils/artefacts de plus de ~3 mois sont purgés par la plateforme ; les requêtes renvoient un corps d'erreur spécifique — l'outil les marque comme terminaux et ne réessaie pas.
- **Suppression de fil (2026-07-23 WebBridge + recherche par blocs, testé)** :
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, corps `{entry_uuid, read_write_token}`,
  succès `200 {"status":"success"}` ; la suppression répétée est idempotente, toujours 200 ; la suppression d'un uuid inexistant → 404 `THREAD_NOT_FOUND` ;
  **acquisition de `read_write_token` (vérifié en pratique le même jour)** : le premier `entries[].read_write_token` non vide
  dans la réponse `GET /rest/thread/<uuid>` fonctionne (10/10 suppressions réussies sur des fils en direct) ;
  **les opérations d'écriture doivent aller sur le domaine www** (le domaine racine renvoie 301 pour DELETE). Aucune mutation GraphQL, aucun point de terminaison de suppression par lot
  (la suppression par lot dans l'UI est une boucle frontend par élément). La suppression est une destruction au niveau du fil, irrécupérable ; le fil disparaît automatiquement de ses espaces
  (pas besoin de `batch_remove_collection_threads` d'abord).
  Option douce : `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (corps `{context_uuids:[...]}` ; analyse statique uniquement, non testé).
- **ENTRY_DELETED** : après la suppression d'un fil, `GET /rest/thread/<uuid>` renvoie HTTP 400 `ENTRY_DELETED`
  (même 400 que ENTRY_EXPIRED mais un code différent) — l'outil le mappe sur `EntryDeletedError`
  (sous-classe de `EntryExpiredError`) ; batch_state marque l'état terminal `deleted`.
- Chaque entrée de tour porte `context_uuid` (= l'UUID `past_session_contexts` de la plateforme — la clé du mappage d'espace de noms à double ID).

<a id="spaces-collections" data-pplx-source-anchor="true"></a>
### Espaces (collections)
| Point de terminaison | Notes |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **Métadonnées de l'espace** : `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. Valeurs d'autorisation observées : 4=propriétaire, 2=peut modifier. Lorsque le compte actuel n'a pas d'accès en lecture : `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` (HTTP toujours 200) |
| `POST /rest/collections/create_collection` | **Créer un espace** (2026-07-21 capture WebBridge, testé) : corps `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → renvoie la collection complète (uuid/slug/url/user_permission=4). L'espace BOT a été créé de cette façon |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **Liste des fils de l'espace (requête directe par cookie ; peut remplacer l'index d'espace basé sur le navigateur)** : la réponse est un tableau ; chaque élément a `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview`, etc. **Pagination : `&offset=N` (20 par page)** ; `has_next_page` est sur chaque élément ; `total_threads` lit haut (inclut les sous-fils Computer ; observé 99 vs 27 de premier niveau) |
| `POST /rest/collections/batch_move_threads` | **Déplacer des fils dans un espace** (testé avec succès) : corps `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}` — **utiliser context_uuid, pas entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | Suppression par lot d'un espace (corps `{items:[{collection_uuid,...}]}` ; non testé) |
| `GET /rest/collections/list_user_collections` | **Liste des espaces du compte actuel** (testé, 16 éléments) : chacun a `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page`, etc. — plus riche que list_recent |
| `GET /rest/collections/list_recent` | Espaces récents du compte actuel (`title/uuid/emoji/is_pinned/link` ; testé, 5 éléments) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | Informations sur la demande d'accès à l'espace (non testé) |
| `GET /rest/collections/<uuid>/join-requests` | Demandes d'adhésion (non exploré) |
| `GET /rest/spaces/<uuid>/tasks` | Renvoie `{"tasks":[]}` — observé vide ; soupçonné d'être des tâches planifiées/informatiques de l'espace, pas une liste de fils |
| `GET /rest/spaces/<uuid>/recurring_tasks` | Tâches récurrentes (non testé) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | Fils épinglés/planifiés de l'espace (appelés au chargement de la page ; non exploré) |

- **Branchement inter-comptes (branch_of ; connaissance utilisateur vérifiée le 2026-07-23)** : un fil partagé via un espace peut être
  « continué » par un autre compte membre dans un fil de branche qui est **visible uniquement par, et continué par, ce compte** — après que le fil du compte A est partagé via un espace,
  B peut le continuer dans une branche privée de B. L'archive n'a pas encore d'instance ; les arêtes de relations ne sont pas implémentées pour l'instant ; les champs de signal API du fil de branche
  (pointeur parent / marqueur de branche) seront vérifiés et enregistrés lorsque la première instance apparaîtra.

<a id="account-session" data-pplx-source-anchor="true"></a>
### Compte / session
| Point de terminaison | Notes |
|---|---|
| `GET /api/auth/session` | `{user:{email,...}}` de la session actuelle — utilisé pour la vérification du compte et le sondage de changement automatique |
| `GET /api/auth/linked-accounts` | Voir [§1.2](api-authentication.md) (liste complète uniquement lorsque le compte principal est actif) |
| `GET /rest/user/info`, `/rest/user/settings` | Profil utilisateur / paramètres (non exploré) |

<a id="credit-usage-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Utilisation du crédit (découvert le 2026-07-20)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → utilisation du crédit par fil (testé 200) :
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **Remarque** : `thread_id` attend le **context_uuid** (psc_uuid) ; passer entryUUID donne 403
  `thread_usage_forbidden` ("Le fil n'appartient pas à l'utilisateur actuel" — en fait une forme d'ID incorrecte).
- Sources de context_uuid : `list_collection_threads` (l'index d'espace REST couvre déjà 27/27),
  le champ `context_uuid` de l'entrée du fil (archivé comme `psc_uuid` dans thread.json).
- Seuls les fils du compte actuel peuvent être interrogés (inter-compte → 403) — le scraping multi-compte nécessite un changement automatique par compte.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind` : version liste ; testé vide sur les deux comptes
  (soupçonné d'être réservé à la facturation d'organisation ; à déterminer).
- Autres points de terminaison de facturation (`/rest/billing/credits/balance`, etc.) dans l'[annexe §7](api-discovery-roadmap.md) ; non explorés.

<a id="official-export-backend-of-the-page-export-button-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Exportation officielle (backend du bouton « Exporter » de la page ; découvert le 2026-07-20)

- **`POST /rest/thread/export`**, corps : `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<name>"}`
- Réponse : `{"file_content_64": "<base64>", "filename": "..."}`
- Formats testés : **`md`** (markdown officiel avec un en-tête logo `<img>`), **`pdf`** (binaire PDF ~880 Ko),
  **`docx`** (zip PK ~350 Ko) — tous HTTP 200. Autres valeurs de format non testées.
- **Limite de contenu (vérifiée)** : renvoie le markdown **du fil entier** (résumé de la requête + réponse + citations en note de bas de page `[^1_N]`),
  **sans le corps RESEARCH_REPORT** — le rapport de recherche approfondie lui-même ne peut être obtenu que via son URL signée (§3.7) ;
  c'est-à-dire que la chaîne d'URL signée report.md actuelle **est la source officielle du rapport** (même source que le téléchargement du panneau d'artefact de la page) ; pas besoin de basculer vers ce point de terminaison.
- Valeur : le markdown officiel au niveau du fil peut servir de source de validation croisée au niveau de la conversation (notes de bas de page/format de citation officiellement rendus).

<a id="asset-report-download" data-pplx-source-anchor="true"></a>
### Téléchargement de ressources / rapports
- **URL signées CloudFront** dans la réponse schématisée (`d2z0o16i8xm8ak.cloudfront.net`) : téléchargement direct urllib,
  pas de cookie/auth nécessaire ; fichiers multi-versions numérotés dans l'ordre `created_at`.
- Source de repli du rapport de recherche : l'URL S3 de l'étape RESEARCH_ANSWER (`ppl-ai-file-upload.s3.amazonaws.com`, **expire**) ;
  second repli : extraction par rendu de page (KaTeX `<annotation>`).
- **Purge ~3 mois** : les liens sources des artefacts/rapports expirent de manière irrécupérable — les exportations doivent être faites en temps utile.

<a id="other-observed-endpoints-page-load-not-explored" data-pplx-source-anchor="true"></a>
### Autres points de terminaison observés (chargement de page ; non explorés)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates` (SSE), `/api/version`.

<a id="message-submission-and-telemetry-2026-07-20-webbridge-cdp" data-pplx-source-anchor="true"></a>
### Soumission de message et télémétrie (2026-07-20 WebBridge + CDP)

<a id="submission-endpoint-post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### Point de terminaison de soumission : `POST /rest/sse/perplexity_ask`
- Échantillons complets du corps de la requête (exemples synthétiques) sous `docs/perplexity-api-samples/` :
  - `ask_envelope_deep_research.json` — tour de suivi de recherche approfondie (2026-07-20 ; 39 paramètres + query_str) :
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + la chaîne de continuation `last_backend_uuid`
  - `ask_envelope_search.json` — recherche standard, nouvelle conversation depuis l'accueil (2026-07-21 ; 35 paramètres + query_str) :
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json` — conseil de modèles, nouvelle conversation depuis l'accueil (2026-07-21 ; 36 paramètres + query_str) :
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- Champs clés (tour de suivi de recherche approfondie, testé) :
  - `mode: "copilot"` (recherche approfondie) ; `model_preference: "pplx_alpha"`
  - **Chaîne de continuation** : `last_backend_uuid` (uuid backend du tour précédent) + `query_source: "followup"`
  - `frontend_uuid` (nouvel uuid pour ce tour), `read_write_token`, `target_collection_uuid` (espace contenant),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`** (millisecondes de la première frappe à la soumission — télémétrie comportementale téléchargée avec la soumission)
  - `use_schematized_api: true`, `supported_block_use_cases` (liste complète des blocs, correspondant à §3.1 schématisé),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- La réponse est un flux SSE (le frontend le consomme avec fetch-event-source `getReader()` — le module d'application fige la référence fetch à l'initialisation,
  **les hooks fetch/XHR attachés à la page sont inefficaces** ; et **les corps de réponse en streaming ne sont pas conservés par le navigateur** (`Network.getResponseBody` renvoie
  No data found) — la capture n'est possible que via CDP `Network.getRequestPostData` (corps de la requête disponible)).
- L'état final du flux est exactement les entrées/blocs de `/rest/thread/<uuid>` (mêmes données, livrées de manière incrémentielle) —
  l'outil d'exportation n'a pas besoin de lire le flux ; il récupère l'état final directement.

<a id="telemetry-post-resteventanalytics-batched-high-frequency" data-pplx-source-anchor="true"></a>
#### Télémétrie : `POST /rest/event/analytics` (par lots, haute fréquence)
Événements observés (avec l'essentiel de event_data) :
| event_name | Champs clés | Notes |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | Événement de vue de page — **ne bascule pas le statut non lu** (exclu par des tests ; le véritable accusé de lecture est `POST /rest/thread/mark_viewed`, voir §3.1) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs` (**durée de lecture en millisecondes pour ce tour**), `userId`, `isPro`, `deviceInfo` (concurrence/écran/profondeur de couleur) | Télémétrie de durée de lecture (ne bascule pas le statut non lu, exclu par des tests) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | Action de soumission |
| `query first llm token` | `startLLMTokenElapsed` (latence du premier jeton), `queryStr` complet | Télémétrie de performance |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, `queryStr` complet | Accusé de réception de succès |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | Interaction avec le sélecteur de modèle du conseil |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | Vue du panneau de droite |
- Champs d'événement communs : `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info` (hardwareConcurrency/écran/profondeur de couleur/architecture), `isBrowserExtension`, `web_platform`.
- **Remarque** : un événement observé portait un `userId` appartenant à **l'autre compte** (l'uid appartenait au compte A alors que la session était déjà le compte B) —
  l'ID de profil du SDK de télémétrie a un décalage de cache ; ne jugez pas le compte actuel par le userId de la télémétrie.
- Il y a aussi le reporting haute fréquence datadog RUM (`browser-intake-datadoghq.com/api/v2/rum`) (défilement/souris/performance ; contenu non analysé).

<a id="mode-and-model-selection-2026-07-21-tested-on-a-paid-account" data-pplx-source-anchor="true"></a>
#### Sélection du mode et du modèle (2026-07-21, testé sur un compte payant)
- **`GET /rest/models/config/v2` = table des modèles faisant autorité** : `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`, `agentic_research_compare_models` (conseil par défaut trois modèles).
  `pplx-ask models` appelle ce point de terminaison.
  - Correspondance officielle (testée) : **search = `pplx_pro` (nom UI « Best »), research = `pplx_alpha`
    (nom UI « Deep research »)**.
  - Liste des modèles sélectionnables dans l'UI en mode search (sans Deep research) : Best (pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **Le champ `mode` est toujours `"copilot"` — pas un discriminateur de mode** (identique pour search / deep research / model council).
- La discrimination réside dans **`model_preference`** :
  - Search : `pplx_pro` (ou l'ID de modèle sélectionné par l'utilisateur, par ex. `experimental`=Sonar 2, `gpt56_sol`…)
  - Deep research : `pplx_alpha` (**pas de sélecteur de modèle dans l'UI**, fixe)
  - **Model council** : `pplx_agentic_research` + **`compare_model_preferences: [<2-3 models>]`**
    (valeur par défaut observée `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]` ;
    l'UI est **sélection unique par emplacement**, passant à 2 modèles lors du suivi).
  - Step-by-step study : `pplx_study` ; Computer : la famille `pplx_asi*`.
- Le sélecteur de modèle de la zone de composition ("model ⌄") et le sélecteur "N models ⌄" du conseil correspondent aux champs ci-dessus ;
  l'événement de télémétrie `ask input model selector opened` porte `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels` (les fils de recherche approfondie plus anciens avaient `searchMode: "research"`).
- Nouvelle conversation : `query_source: "home"`, pas de `last_backend_uuid`, a `frontend_context_uuid` ;
  continuation : chaîne `query_source: "followup"` + `last_backend_uuid`.

<a id="entrysearch_mode-the-authoritative-record-of-conversation-mode-settled-2026-07-22" data-pplx-source-anchor="true"></a>
#### entry.search_mode : l'enregistrement faisant autorité du mode de conversation (réglé le 2026-07-22)
**Chaque entrée** de `/rest/thread/<uuid>` porte `search_mode`, l'enregistrement faisant autorité par la plateforme du mode de conversation de ce tour
(le signal de détection de mode le plus prioritaire, `normalize.SEARCH_MODE_MAP`) :

| search_mode | Signification (UI/modèle) | Mode d'archive |
|---|---|---|
| `SEARCH` | recherche normale (default_models.search=pplx_pro « Best » et modèles sélectionnables dans l'UI) | search |
| `STUDIO` | session labs (pplx_beta) ; l'UI le regroupe sous search | search |
| `RESEARCH` | Deep research (default_models.research=pplx_alpha ; UI fixe, pas de sélecteur) | deep-research |
| `AGENTIC_RESEARCH` | model council (pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | step-by-step study (pplx_study) | study |
| `ASI` | Computer (pplx_asi*) | computer |

- Sondage des valeurs dans l'archive : les six valeurs ont des instances dans l'archive réelle ; SEARCH et RESEARCH dominent,
  STUDIO ensuite, ASI / STUDY / AGENTIC_RESEARCH rares.
- **pplx_alpha ⟺ RESEARCH preuve croisée** : 100+ entrées SEARCH de la plateforme + fils pplx_alpha dans l'archive sont 100%
  `search_mode=RESEARCH` ; 100+ fils pplx_pro purs sont tous `search_mode=SEARCH` —
  l'ancienne statistique « pplx_alpha est un modèle couramment utilisé pour la recherche simple » était en fait des échantillons de mauvaise classification du classifieur et ne tient pas.
- Plusieurs valeurs peuvent apparaître dans un même fil (changement de mode, par exemple un mélange SEARCH+RESEARCH observé) : la détection prend la plus élevée par spécificité
  computer>council>study>deep-research>search.

<a id="model-council-output-structure-and-expansion-behavior" data-pplx-source-anchor="true"></a>
#### Structure de sortie du conseil de modèles et comportement d'expansion
- Sortie d'un seul tour = N blocs spécifiques au modèle « Council : <model name> » (chacun avec requêtes de récupération/sources/réponse) + une partie de synthèse :
  **Where Models Agree** (matrice de consensus, comparaison ✓ des trois modèles par constatation + Evidence),
  **Where Models Disagree** (tableau de désaccord, position de chaque modèle + raisons de divergence),
  **Unique Discoveries** (constatations uniques de chaque modèle), suivis de recommandations de questions connexes — **le tout livré dans le même flux SSE**.
- Comportement d'expansion (y compris l'expansion **pendant la génération**) : les lignes extensibles portent un chevron ">" (lignes d'étape / lignes « Sources » / lignes du conseil) ;
  cliquer les développe — **rendu purement côté client, zéro requête de contenu** : sur les 1208 requêtes de cette session, 921 étaient des ressources statiques favicon/police ;
  l'expansion elle-même ne déclenche que des chargements de favicon et /api/version. L'expansion pendant le streaming ne perturbe pas la livraison continue.
- Latence du premier jeton observée ~204 s (trois modèles générant en parallèle, nettement plus long qu'un seul modèle) ; nombre de sources observé 236.
- Automatisation de la zone de composition (Lexical) essentielle : le texte doit être injecté via CDP `Input.insertText` (après execCommand/remplissage,
  l'état interne de Lexical se désynchronise et Entrée échoue) ; la soumission peut utiliser CDP Entrée ou cliquer sur le bouton avec aria-label="提交" ("Soumettre")
  (le mode conseil a une flèche de soumission explicite).

<a id="behavior-when-continuing-a-historical-conversation-tested-2026-07-20" data-pplx-source-anchor="true"></a>
#### Comportement lors de la continuation d'une conversation historique (testé le 2026-07-20)
1. Charger la page du fil → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. Soumettre un suivi → `rate-limit/status` → `sse/perplexity_ask` (avec la chaîne `last_backend_uuid`) → analyses haute fréquence.
3. Pendant la génération → le flux SSE rend de manière incrémentielle ; après achèvement, un autre lot d'analyses (y compris la durée de lecture `thread entry exited`).
4. Les tours de suivi de recherche approfondie produisent également des structures de rapport (ce tour a complété 5 étapes).
