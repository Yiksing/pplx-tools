---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-discovery-roadmap.md"
translation_source_sha256: "60c675dcc583c059cd489ea085f9c2923f9447f7bbafb0a7ac991fee9f8add08"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="endpoint-discovery-and-improvement-roadmap" data-pplx-source-anchor="true"></a>
# Feuille de route de découverte et d'amélioration des points d'accès

*Partie de la référence API web Perplexity — carte complète à l'[index API](index.md).*

<a id="known-unexplored-tbd-items" data-pplx-source-anchor="true"></a>
## Éléments connus non explorés / à déterminer

- Champ de tri `list_collection_threads` et sémantique exacte de `total_threads`
  (instantané du compte actif 2026-07 : 99 vs 27 éléments de premier niveau signalés).
- Spectre complet des valeurs `threadAccess`/`access`/`user_permission` (échantillon observé en 2026-07 :
  threadAccess 5 normal, 1 avec 🔒 ; collection access 1 ;
  permission 4 owner / 2 can edit ; les données assets contiennent également thread_access).
- Formes correctes des paramètres pour `list_ask_threads`, `list_scheduled_computer_tasks` (GET direct 400).
- Structures de réponse de `collections/*/request-access-info`, `spaces/<uuid>/recurring_tasks`, `assets/<id>/members`.
- Pourquoi les opérations GraphQL du tableau de bord ne sont pas enregistrées (PERSISTED_QUERY_NOT_FOUND) : décalage de version ou restriction de contexte ;
  si nécessaire, réextraire avec les hachages en direct de la capture réseau.
- Répartition des tâches entre `frontend_uuid` vs `uuid` vs `context_uuid` dans les threads computer.
- Champs de signal API des threads de branche partagée entre comptes (branch_of)
  (pointeur parent / marqueur de branche) — mécanisme confirmé (fin de
  [§3.3](api-rest-endpoints.md)) ; aucune instance archivée au 2026-07-23 ;
  vérifier et enregistrer dès la première apparition.

<a id="endpoint-discovery-method-frontend-bundle-static-analysis-zero-api-cost-established-2026-07-20" data-pplx-source-anchor="true"></a>
## Méthode de découverte des points d'accès : analyse statique du bundle frontend (coût API nul ; établie le 2026-07-20)

Découverte de **147 points d'accès `/rest/`** en un passage ; la méthode est réutilisable (réexécuter après les refontes frontend) :

1. L'entrée de chargement de page `_spa/assets/index.html-*.js` référence `bootstrap-*.js` (l'exécutable contient tous les mappages de chunks) ;
2. Extraire 682 noms de fichiers de chunks (motif `<name>-<hash8>.js`) du bootstrap ; filtrer ceux liés à l'API par nom
   (client/api/thread/collection/space/computer…) ;
3. Télécharger directement depuis le CDN public `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js`
   (aucun cookie nécessaire) ; modules hub : `platform-core-*` (client API), `spa-shell-*`, `spa-metadata-*` ;
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` produit la liste des points d'accès (147) ;
5. Les chunks divulguent également les formes d'appel (par exemple, `format:'md'` et `file_content_64` de l'export).
6. Les sourcemaps existent aussi : `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (non exploré).

<a id="appendix-147-endpoints-grouped-by-category-archive-relevance-marked" data-pplx-source-anchor="true"></a>
### Annexe : 147 points d'accès regroupés par catégorie (pertinence pour l'archivage marquée)

- **thread** : `/rest/thread/{entry_uuid_or_slug}`, `/rest/thread/export`★, `/rest/thread/{uuid}/members`,
  `/rest/thread/list_recent`, `/rest/thread/list_ask_threads`, `/rest/thread/list_pinned_ask_threads`,
  `/rest/thread/list_scheduled_computer_tasks`, `/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★ : voir le tableau complet [§3.3](api-rest-endpoints.md) (incl. batch_move/batch_remove, list_user_collections, request-access-info,
  recurring_tasks, pins/threads, scheduled_threads)
- **assets**★ : `/rest/assets/{asset_id}/data`, `/rest/assets/{asset_id}/members`,
  `/rest/assets/{asset_id}/published-access`, `/rest/assets/sites/{site_id}/publish-info`
- **analytics** : `/rest/analytics/computer/usage`, `/rest/analytics/computer/usage/members`
  (les deux 403 NOT_ORG_MEMBER — comptes organisation uniquement)
- **models/skills** : `/rest/models/config(/v2)`, `/rest/skills`, `/rest/skills/selectable`,
  `/rest/skills/grants`, `/rest/skills/submissions(/source)`
- **files/uploads** : `/rest/file-repository/*` (list/download/get-file-upload-urls/delete-files…),
  `/rest/files/list(/list-infinite/list-errors)`, `/rest/uploads/(batch_)create_upload_url(s)`,
  `/rest/connectors/attachments/upload`
- **tasks/computer** : `/rest/tasks/`, `/rest/tasks/{task_id}`, `/rest/tasks/shortcuts/mentions`,
  `/rest/tasks/shortcuts/paste/{copy_token}`, `/rest/computer/asset`, `/rest/computer/menu`,
  `/rest/computer/onboarding_cards`
- **user/auth** : `/rest/user/settings`, `/rest/user/get_user_ai_profile`, `/rest/user/promotions`,
  `/rest/user/site-instructions`, `/rest/auth/get_special_profile`, `/rest/visitor/*`
- **billing/stripe** : `/rest/billing/*` (credits/paypal/subscription…), `/rest/stripe/*`
- **enterprise/org** : `/rest/enterprise/*`, `/rest/organizations/{id}/credit-limits*`,
  `/rest/pplx-api/v2/enterprise-api-org`
- **sse** : `/rest/sse/attachment_processing/subscribe`, `/rest/sse/index_files`,
  `/rest/sse/perplexity_terminate`, `/rest/sse/related-queries/{entry_uuid}`
- **verticaux** (non pertinents pour l'archivage) : `/rest/finance/*`, `/rest/sports/*`, `/rest/travel/hotels/{slug}`,
  `/rest/health-assistant/*`, `/rest/article/{uuid_or_slug}`
- **divers** : `/rest/pins`, `/rest/rate-limit/(all|status)`, `/rest/notifications/web-push/*`,
  `/rest/attribution/*`, `/rest/homepage-widgets/upsell`, `/rest/ntp/upsell/`, `/rest/sidebar/upsell/`,
  `/rest/incentives/comet-activation`, `/rest/connector-service/usage`

(★ = directement pertinent pour l'archivage)

<a id="endpoint-tool-capability-status-and-roadmap" data-pplx-source-anchor="true"></a>
## Statut et feuille de route des capacités des outils par point d'accès

Le statut d'implémentation ci-dessous a été synchronisé avec le code actuel et la suite de tests
le **2026-07-24**. Les preuves API conservent la date et la portée de l'observation
en direct ou de l'analyse statique d'origine ; cette synchronisation de documentation n'a pas re-sondé
les points d'accès privés. Les comptes d'archives sont des instantanés, pas des garanties
à l'échelle de la plateforme.

Signification des statuts :

- **Implémenté** — un chemin CLI ou de production actuel utilise le point d'accès pour la
  capacité indiquée.
- **Partiel** — le point d'accès est utilisé, mais la capacité en aval dans la
  feuille de route reste incomplète.
- **Testé, non intégré** — le comportement de l'API en direct a été observé, mais aucun
  chemin d'outil ne le consomme.
- **Planifié** — des preuves existent, mais l'implémentation n'a pas commencé.
- **Bloqué** — un bloqueur amont ou de protocole connu empêche l'implémentation.
- **Fermé** — les preuves ont réfuté l'utilisation proposée ou l'ont placée hors de portée.

<a id="capability-status-matrix" data-pplx-source-anchor="true"></a>
### Matrice des statuts des capacités

| Point d'accès / opération | Base de vérification | Intégration actuelle | Statut | Écart restant |
|---|---|---|---|---|
| `collections/get_collection` | observation en direct + code actuel | `spaces --fetch-meta` construit l'index propriétaire/membre de l'espace | **Implémenté** | — |
| `collections/list_collection_threads` | observation en direct + code actuel | `space-index` utilise REST par défaut avec mappage d'ID double context_uuid ; WebBridge est le repli | **Implémenté** | L'ordre de tri et la sémantique exacte de `total_threads` restent à déterminer |
| `assets/<uuid>/data` | testé en direct 2026-07-20 + code actuel | `assets-backfill --online` rafraîchit les URL signées pour les UUID d'actifs réels | **Implémenté** | Les handles d'espace de travail cloud `toolu_` sont en dehors de la couverture de ce point d'accès |
| `LibraryThreadsRelayQuery` et requête de pagination | APQ capturé + code actuel | `index`/`batch` fournissent un indexage complet et un arrêt précoce incrémental | **Implémenté** | Les requêtes de filtre de mode du tableau de bord restent bloquées séparément |
| `collections/list_user_collections` | observé en direct 2026-07 + code actuel | `init` utilise une correspondance de titre exact pour découvrir l'espace BOT | **Partiel** | Construire un registre d'espaces de compte faisant autorité pour la découverte de nouveaux espaces et la reconstruction de `spaces` |
| `credits/thread-usage` | testé en direct 2026-07-20 + code actuel | `usage-backfill` écrit `index/credit_usage_<account>.json` | **Partiel** | Décider s'il faut enrichir `thread.json` et/ou les lignes d'index de la bibliothèque sans dupliquer l'autorité |
| `models/config/v2` | testé en direct 2026-07-21 + code actuel | `pplx-ask models` liste les modèles/paramètres par défaut ; les constantes de normalisation sont recoupées avec lui | **Partiel** | Persister les métadonnées d'affichage stables du modèle dans les enregistrements d'archive/index si utile |
| `POST /rest/thread/export` | md/pdf/docx testé en direct 2026-07-20 | aucune intégration CLI | **Testé, non intégré** | Archivage multi-format et réconciliation officielle Markdown |
| `rate-limit/status` | observation du chargement de page ; sémantique de réponse non explorée | aucun | **Planifié** | Valider la sémantique avant de l'utiliser pour un throttling adaptatif |
| `file-repository/list-files` | analyse statique frontend uniquement | aucun | **Planifié** | Valider s'il peut énumérer/récupérer les handles `toolu_` ; un instantané d'archive de 2026-07 a enregistré 270 handles sans canal de téléchargement |
| `pins`, `tasks/{id}` | analyse statique frontend / observations du chargement de page | aucun | **Planifié** | Enrichissement de l'état et de la durée des tâches computer |
| `thread/<uuid>/members` | testé en direct 2026-07 | aucun | **Planifié** | Arêtes de partage au niveau du thread pour le graphe de relations |
| GraphQL du tableau de bord `threadGroup` + filtres de mode | appels directs ont retourné `PERSISTED_QUERY_NOT_FOUND` | aucun | **Bloqué** | Récupérer les hachages de requêtes persistées en direct ou établir le contexte requis |
| `related_queries` / `sse/related-queries` | enquêtes médico-légales à l'échelle de l'archive réglées le 2026-07-23 | ne produit délibérément aucune arête de relation | **Fermé** | Rouvrir uniquement si de nouvelles preuves établissent une identité de thread résoluble |

<a id="active-roadmap" data-pplx-source-anchor="true"></a>
### Feuille de route active

<a id="p0-official-export-integration" data-pplx-source-anchor="true"></a>
#### P0 — Intégration de l'export officiel

- **Archivage multi-format** : conserver optionnellement les produits PDF/DOCX retournés par
  `POST /rest/thread/export`.
- **Réconciliation du rendu** : comparer le Markdown officiel du thread entier avec
  `conversation.md` comme signal de régression indépendant.

<a id="p1-space-discovery" data-pplx-source-anchor="true"></a>
#### P1 — Découverte d'espaces

- Promouvoir `list_user_collections` d'une recherche par titre BOT à un registre d'espaces
  faisant autorité et couvrant le compte, utilisé pour la découverte de nouveaux espaces et la reconstruction
  de `spaces`.

<a id="p2-metadata-risk-control-and-asset-rescue" data-pplx-source-anchor="true"></a>
#### P2 — Métadonnées, contrôle des risques et récupération d'actifs

- Décider et documenter la limite d'autorité pour l'utilisation du crédit : conserver le
  `credit_usage_<account>.json` dédié, ou également enrichir `thread.json` /
  les lignes de la bibliothèque.
- Ajouter les métadonnées d'affichage du modèle, l'état d'épingle, la durée des tâches computer, et les relations
  de partage de thread uniquement là où la sémantique du point d'accès est stable.
- Valider `rate-limit/status` avant de concevoir un throttling adaptatif.
- Tester `file-repository/list-files` comme chemin de récupération possible pour `toolu_` avant
  d'ajouter toute mutation d'archive.

<a id="p3-blocked-discovery" data-pplx-source-anchor="true"></a>
#### P3 — Découverte bloquée

- Recapturer les hachages de requêtes persistées GraphQL du tableau de bord uniquement si l'indexation
  incrémentielle par mode devient suffisamment précieuse pour justifier le coût
  de maintenance.

<a id="closed-decisions-not-adopted" data-pplx-source-anchor="true"></a>
### Décisions fermées / non adoptées

- **Export officiel comme source de rapport** : réfuté. Le point d'accès retourne
  le Markdown du thread entier sans le corps du rapport ; la chaîne d'URL signée reste
  la source officielle pour `report.md` ([§3.6](api-rest-endpoints.md)).
- **Relations depuis `related_queries`** : réfuté le 2026-07-23. Les UUID d'éléments ne sont pas
  des UUID de thread et les textes de recommandation n'ont pas résolu en requêtes archivées ;
  aucune arête de relation n'est construite ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)` : observé comme réservé aux organisations
  (`403 NOT_ORG_MEMBER`) pour les comptes testés.
- `thread/request-access-info` : testé comme lié à l'adhésion à une organisation, pas un
  signal `threadAccess`.
- Les verticaux Billing/Stripe/enterprise et finance/sports restent en dehors du
  périmètre de l'outil d'archivage.

---

*Ce document complète [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md) (architecture de l'outil) et [overview.md](../../architecture/overview.md) (conception du système).*
