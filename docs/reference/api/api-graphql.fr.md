---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-graphql.md"
translation_source_sha256: "3963e26d58d8dc1ad0835fe715357592295f31dd7c3b7c3f1ca67854fa3c98a0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-graphql" data-pplx-source-anchor="true"></a>
# Référence API : GraphQL

<a id="graphql-persisted-queries-apq" data-pplx-source-anchor="true"></a>
## GraphQL (requêtes persistées / APQ)

- **Point d'accès** : `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **Forme** : requête persistée — le corps contient operationName + variables + un hash sha256 (pas de texte de requête nécessaire).
- Implémentation : `pplx_export/sites/perplexity/graphql.py`.

<a id="librarythreadsrelayquery-list-first-page" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery (liste première page)
- sha256 : `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- Variables : `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- Chemin de réponse : `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- Champs de nœud (utilisés par l'adaptateur) : `name(title)`, `entryId(entryUUID)`, `slug(href)`, `mode`, `displayModel.modelID`,
  `updatedAt(lastUpdated)`, `status`, `space{spaceUuid,title,slug}`
- **Contrat côté archive (2026-07-22 V5-01)** : le `lastUpdated` de `web_archive/**/thread.json` est toujours égal à ce champ
  (écrit sur le disque avec une précision ISO complète, textuellement) ; la comparaison d'idempotence d'exportation par lot/unique (`is_unchanged`) est basée sur celui-ci,
  et non plus sur le format de présentation de la couche de rendu (`YYYY-MM-DD HH:MM UTC`).
- **Enrichissement côté archive (2026-07-23)** : la clé `search_mode` des lignes d'index (`index/library_*.json`) est un
  champ d'enrichissement côté archive — le nœud de cette requête ne contient pas search_mode ; il est rempli par `pplx-export search-mode-backfill`
  à partir des données au niveau du fil (`entries[].search_mode` de `GET /rest/thread/<uuid>`) (d'abord local brut,
  repli en ligne) ; l'actualisation `index` le fusionne et le préserve par entryUUID. Le filtrage `batch --mode` préfère le mappage faisant autorité de ce champ.

### LibraryRecentThreadsPaginationQuery (pagination)
- sha256 : `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- Variables : variables de première page + `{cursor, count}` (**les noms de variables sont cursor/count, pas after/first**)
- Même structure de réponse que ci-dessus. Lorsque `hasNextPage` est vrai mais que `endCursor` est vide, arrêtez (sinon la même page se répète).

<a id="computer-dashboard-operation-group-extracted-from-route-chunk-2026-07-20-not-registered-on-the-server" data-pplx-source-anchor="true"></a>
### Groupe d'opérations du tableau de bord Computer (extrait du chunk de route 2026-07-20, **non enregistré sur le serveur**)

Le chunk `ComputerDashboardPage-*.js` intègre les textes complets des requêtes Relay + les identifiants persistés (méthode d'extraction dans [§7](api-discovery-roadmap.md)).
Essentiels structurels : `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— c'est-à-dire une liste de fils filtrée par threadGroup + mode ; le nœud contient `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`.

| opération | identifiant persisté (16 premiers caractères) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (abonnement WebSocket) |

**Testé** : appeler `/rest/perplexity_ask/graphql` avec ces identifiants retourne `PERSISTED_QUERY_NOT_FOUND`
(non enregistré dans le déploiement actuel — décalage de version ou contexte de tableau de bord requis ; les textes complets des requêtes et les identifiants sont conservés dans les notes d'exploration `/tmp` ;
si nécessaire, envoyez le texte de la requête directement ou extrayez-le à nouveau du bundle en direct).

<a id="notes" data-pplx-source-anchor="true"></a>
### Remarques
- Aucun appel graphql observé sur la page de l'espace web ou la page d'accueil (tout passe par /rest) ; graphql est confirmé pour la liste /library et le tableau de bord Computer.
- Les hash sha256 peuvent changer avec les versions du frontend ; le mode de défaillance est `PERSISTED_QUERY_NOT_FOUND` — puis extrayez à nouveau depuis la
  capture réseau du navigateur (outil WebBridge `network` filtrant `perplexity_ask/graphql`), ou extrayez à nouveau du bundle en direct ([§7](api-discovery-roadmap.md)).

<a id="extracted-dashboard-connection-keys-relay-cache-keys-for-debugging" data-pplx-source-anchor="true"></a>
### Clés de connexion du tableau de bord extraites (clés de cache Relay, pour débogage)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
