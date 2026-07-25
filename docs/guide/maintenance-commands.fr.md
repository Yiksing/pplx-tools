---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/maintenance-commands.md"
translation_source_sha256: "550aca319a6386123658e8d54ede5367bc97765c9a11710e20f1ed1f2854f617"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintenance-commands" data-pplx-source-anchor="true"></a>
# Commandes de maintenance

Les sous-commandes de maintenance de `pplx-export` maintiennent une archive existante en bonne santé : ré-afficher les pages après des corrections du moteur de rendu, remplir les actifs / l'utilisation du crédit / les métadonnées de mode, marquer les fils supprimés à distance, et reconstruire le graphe de relations. La plupart sont hors ligne en priorité ; leurs phases en ligne suivent la même discipline de rythme que `batch` (voir [rate-limiting.md](rate-limiting.md)). Toutes acceptent les [options communes](pplx-export.md) (`--account`, `--out`, `--cookies-from`, `--transport`, …).

- Principe de rétention de l'archive locale : aucune commande de maintenance ne supprime ni ne déplace le contenu des fils archivés — l'archive est la sauvegarde.
- Les commandes hors ligne (`re-render`, `relations`, `sync-space`, `spaces` sans `--fetch-meta`, et les phases par défaut ci-dessous) n'ont besoin d'aucun transport ; voir [../architecture/offline-operations.md](../architecture/offline-operations.md).

## re-render

Régénérer `conversation.md` et `turns/` à partir du JSON brut archivé (`raw_entries.json` / `raw_blocks.json`) après des corrections du moteur de rendu — zéro réseau, et tous les autres fichiers sont laissés intacts.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--limit N` | Traiter seulement les N premiers répertoires de fils | tous |
| `--dry-run` | Lister les répertoires qui seraient traités, n'écrire rien | désactivé |
| `--thread-json` | Ajouter/supprimer aussi les clés `interruptions` et `answer_variants` dans `thread.json` sur place | désactivé |

Comportements clés :

- Reconstruit les tours hors ligne avec le même pipeline que l'export : analyse, ordre par `created_us`, déduplication des citations, et — pour computer/council — blocs de workflow, mappage des sous-agents et l'annexe du fond non consommé.
- Seuls `conversation.md` et `turns/turn_*.md` sont (ré)écrits ; `sources*`, `assets/`, `report.md` et `thread.json` restent tels quels. Les fichiers `turn_*.md` obsolètes numérotés au-dessus du nombre de tours actuel sont supprimés — rien d'autre, donc les fichiers inchangés conservent leur mtime.
- `--thread-json` écrit seulement lorsque le contenu change réellement ; les `answer_variants` nouvellement ajoutés/modifiés déclenchent un avertissement `ANSWER_VARIANT_DETECTED` et sont ajoutés à `index/answer_variants_log.jsonl` (les réexécutions idempotentes ne spamment pas).
- Les répertoires de fils sans `raw_entries.json` sont ignorés et comptés.

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

Corriger les actifs qui ont été archivés sans URL signée — trois remèdes par étapes : récupérer les blocs manquants, extraction en ligne hors ligne, et rafraîchissement en ligne optionnel.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--fetch-blocks` | D'abord récupérer les `raw_blocks.json` manquants et leurs actifs avec URL signée (en ligne) | désactivé |
| `--online` | Activer le rafraîchissement en ligne des actifs manquants/obsolètes | désactivé (extraction en ligne hors ligne uniquement, zéro requête) |
| `--limit N` | Traiter seulement les N premiers répertoires de fils | tous |

Comportements clés :

- Phase par défaut (hors ligne, zéro requête) : extraire les actifs en ligne (`ASSET_DIFF` / `CODE_ASSET`) de `raw_blocks.json` vers `assets/files/*.md`, et enregistrer les types de handles d'espace de travail cloud (`DOC_FILE` / `CODE_FILE` / `UNKNOWN` — pas encore de canal de téléchargement) dans `assets/assets_manifest.json`. Idempotent : les enregistrements connus sont dédupliqués par uuid, puis file_handle ; les fichiers multi-versions de même nom reçoivent un suffixe court d'uuid pour que les réexécutions n'entrent pas en collision.
- `--fetch-blocks` (en ligne) : récupérer les `raw_blocks.json` manquants pour les fils deep-research/computer/council/study plus leurs actifs téléchargeables ; les fils sont regroupés par dossier de compte avec un adaptateur construit paresseusement par compte (les cookies changent automatiquement), 3s entre les fils.
- `--online` : pour les versions de manifeste dont `downloaded_to` est manquant/obsolète, récupérer une nouvelle URL signée via `/rest/assets/<uuid>/data` (appels API en série, espacés de 3s), puis retélécharger depuis le CDN (6 fils concurrents, sans délai — CDN, pas API). Un `ASSET_NOT_FOUND` 404 définit le drapeau terminal `asset_expired` ; un 403 inter-compte est réessayé une fois avec le compte propriétaire du dossier d'archive.
- Le `count` du manifeste est recalculé comme le nombre total de versions à chaque réécriture.

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

Remplir l'utilisation du crédit par fil (`credits/thread-usage`) pour tous les fils archivés du compte dans `index/credit_usage_<account>.json`.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--limit N` | Traiter seulement les N premiers fils | tous |

Comportements clés :

- Un GET par fil archivé (`thread_id` = le `psc_uuid` du fil), espacés de 3s ; idempotent — les fils déjà présents dans le fichier de sortie sont ignorés.
- Un 403 (`thread_usage_forbidden`, c'est-à-dire un fil inter-compte) est enregistré comme `error` et jamais réessayé ; les autres échecs sont laissés pour la prochaine exécution. La progression est sauvegardée tous les 25 fils traités.
- Multi-compte : exécuter une fois par compte avec `--account` — les cookies changent automatiquement entre les exécutions.

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

Remplir le champ `search_mode` faisant autorité sur la plateforme dans chaque ligne de `index/library_<account>.json`, afin que `batch --mode` puisse filtrer exactement au lieu de se fier à des heuristiques.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--limit N` | Traiter seulement les N premières lignes en attente | toutes |
| `--offline` | Extraction locale uniquement — les lignes sans données brutes locales attendent le prochain tour, pas de repli en ligne | désactivé |
| `--delay-min SEC` | Borne inférieure de l'intervalle aléatoire entre les fils de repli en ligne | `10` |
| `--delay-max SEC` | Borne supérieure de l'intervalle aléatoire entre les fils de repli en ligne | `20` |

Comportements clés :

- Stocke la valeur brute de la plateforme (`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…) ; un fil portant plusieurs valeurs conserve la plus spécifique selon computer > council > study > deep-research > search.
- Local d'abord : les fils archivés sont résolus depuis `raw_entries.json` avec zéro réseau — une exécution entièrement locale ne construit même pas de transport (pas même une sonde de session).
- Repli en ligne uniquement pour les lignes sans données brutes locales : `GET /rest/thread/<uuid>` avec un intervalle aléatoire de 10–20s ; les lignes dans l'état terminal `expired` sont ignorées et enregistrées ; les fils nouvellement trouvés expirés/supprimés en ligne sont marqués dans `batch_state.json` pour épargner les futures requêtes.
- Idempotent et reprenable : les lignes qui ont déjà `search_mode` sont ignorées, la progression est sauvegardée toutes les 25 lignes, et les `index` ultérieurs préservent l'enrichissement (fusionné en retour par `entryUUID`).

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

Identifier les fils qui ont disparu de la bibliothèque distante (supprimés par l'utilisateur ou la plateforme) et les marquer — cela ne supprime ni ne déplace jamais de fichier d'archive.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--online` | Vérifier chaque candidat en ligne | désactivé (simulation hors ligne : lister les candidats uniquement) |
| `--limit N` | Traiter seulement les N premiers candidats | tous |
| `--delay-min SEC` | Borne inférieure de l'intervalle aléatoire entre les candidats | `10` |
| `--delay-max SEC` | Borne supérieure de l'intervalle aléatoire entre les candidats | `20` |

Comportements clés :

- La détection des candidats est hors ligne et inter-compte : un fil avec le statut `batch_state` `ok` qui est absent de l'union `entryUUID` de **tous** les fichiers `index/library_*.json` devient un candidat — tout index unique le contenant compte comme vivant, donc les fils exportés entre comptes via des espaces partagés ne sont pas des faux positifs. Lorsqu'aucun index utilisable n'existe, tout est ignoré en toute sécurité avec un conseil d'exécuter d'abord `index`.
- Par défaut, c'est une simulation hors ligne : elle liste les candidats et les raisons d'ignorance sécurisée — zéro réseau, zéro écriture.
- `--online` vérifie chaque candidat avec `GET /rest/thread/<uuid>` sous le compte enregistré dans `thread.json` `export_via` (les cookies changent automatiquement par candidat).
- Confirmé par `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 → `batch_state` marque l'état terminal `deleted` (même sémantique que `expired` : jamais réessayé, `--force` ne réexporte pas ; voir [incremental-sync.md](incremental-sync.md)) et chacun des fichiers `thread.json` du fil reçoit un horodatage `remote_deleted` sur place (idempotent — une clé existante est conservée).
- Le fil existe toujours → faux positif : signalé tel quel avec un conseil de réexécuter `index`, rien n'est modifié. Les erreurs de transport reportent au prochain tour ; 3 échecs d'authentification consécutifs interrompent l'exécution avant que quoi que ce soit ne soit mal marqué.

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

La première exécution liste les candidats (simulation hors ligne) ; la seconde les vérifie en ligne et marque les confirmés.

## status

Afficher l'état du compte d'archive et le plan de modification incrémentale — zéro réseau, lecture seule. Il répond à "à quoi ressemble l'archive maintenant, et que ferait la prochaine exécution de `batch`" sans toucher au réseau.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--account X` | Rapporter sur un seul compte | tous les comptes qui ont un fichier `index/library_*.json` |
| `--json` | Rapport complet lisible par machine sur stdout (ignore la verbosité) | désactivé (lignes de journal humain) |

Comportements clés :

- Les sources de données sont purement locales : `index/library_*.json` (lignes d'index par compte) et `index/batch_state.json` (la source unique des états d'export). La classification des modifications réutilise la même fonction pure `plan_incremental` que `batch`/`schedule`, donc les sémantiques `new`/`updated`/`done`/`expired`/`deleted` sont identiques à ce que `batch` calculerait.
- La sortie INFO par défaut imprime une ligne de résumé par compte (nombre d'index + fraîcheur, comptes d'état `ok/expired/deleted/error`, comptes de modification `new/updated`, et le nombre d'arrêt précoce) plus une ligne globale de compte `batch_state` (par exemple `559 ok + 13 expired + 12 deleted`).
- Les niveaux de détail suivent le drapeau de verbosité standard : `-v` ajoute les titres des fils `new`/`updated`/`error` (première ligne, tronquée à 60 caractères) ; `-vv` ajoute les fils `done`/`expired`/`deleted` avec `lastUpdated`/`exported_at` ; `-vvv` imprime tout sans troncature avec les champs d'index `mode`/`search_mode` et la liste des états seuls (enregistrements présents dans `batch_state` mais absents de l'index de chaque compte — candidats à la suppression distante à réconcilier avec [sync-deleted](#sync-deleted)).
- Garde-fous : un fichier `index/` ou fichier de bibliothèque manquant se termine par une erreur pointant vers `pplx-export index` ; un `batch_state.json` manquant est traité comme un état vide (tout compte comme `new`). Aucune configuration au niveau utilisateur n'est requise — les comptes sont énumérés à partir des noms de fichiers de bibliothèque.
- `--json` émet le rapport complet (comptes, modifications, fils, états seuls, totaux) sous forme d'un JSON sur une seule ligne sur stdout — le même style de contrat que `pplx-ask`.

```bash
pplx-export status                 # summary for every account
pplx-export status -vv             # five-state thread details
pplx-export status --account alice --json
```

## relations

Reconstruire le graphe de relations de conversation à partir des fils exportés → `relations/edges.jsonl` plus un `relations/graph.md` lisible par l'homme sous la racine de l'archive.

| Drapeau | Signification | Défaut |
|---|---|---|
| *(options communes uniquement ; seul `--out` importe)* | | |

Comportements clés :

- Puremenent hors ligne, zéro réseau, lecture seule sur l'archive : il réutilise le pipeline de reconstruction hors ligne de re-render (`raw_entries.json` / `raw_blocks.json`), donc `sub_agents`, `query_source` et les signaux de citation sont tous disponibles pour la détection d'arêtes.
- Les fils sans données brutes se dégradent en une coquille `thread.json` + `conversation.md` — seules les arêtes de référence `same_space` et uuid nu peuvent se déclencher pour eux.

```bash
pplx-export relations
```

## debug-js

Exécuter un extrait JavaScript dans le contexte de la page du navigateur actuel via le démon WebBridge local (`127.0.0.1:10086`) et afficher le résultat sous forme de JSON — une trappe de débogage.

| Drapeau | Signification | Défaut |
|---|---|---|
| `JS代码` (positionnel) | Code JavaScript à évaluer dans le contexte de la page (le métavar littéral d'argparse) | requis |

Comportements clés :

- Nécessite que le démon WebBridge soit accessible et que la page Perplexity cible soit ouverte dans le navigateur ; l'extrait s'exécute avec la propre session de la page.
- Le JSON affiché est tronqué à 5000 caractères.

```bash
pplx-export debug-js 'document.title'
```
