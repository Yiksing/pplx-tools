---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/archive-layout.md"
translation_source_sha256: "6302a47c60b6c8703d36f420cee6c18017110fcbb6127926eedb5c77e3e1f8e2"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="archive-layout" data-pplx-source-anchor="true"></a>
# Structure de l'archive

Tout ce que `pplx-export` télécharge atterrit dans une arborescence de sortie unique — `./web_archive/` par défaut
(remplaçable avec `--out`). Cette page est un guide de lecture de cette arborescence : ce que sont chaque dossier et fichier,
quelles clés `thread.json` transporte, et comment l'outil maintient un dossier par fil lorsqu'une
conversation se poursuit sur plusieurs jours. Tout est généré par l'outil ; la profondeur du mécanisme se trouve dans
[Modèle de données et contrat de répertoire](../architecture/data-model.md) et
[Pipeline d'exportation](../architecture/export-pipeline.md).

<a id="the-output-tree" data-pplx-source-anchor="true"></a>
## L'arborescence de sortie

```
web_archive/
├── alice/                                # one folder per account (author display name)
│   ├── search/                           # mode: search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # one directory per thread
│   │       ├── thread.json               # metadata + optional registries
│   │       ├── conversation.md           # compact read: per-turn Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # full read: complete work-process detail
│   │       │   └── ...
│   │       ├── sources.json              # thread-wide citations (deduped by url)
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research report (only when one exists)
│   │       ├── raw_entries.json          # plain API response, verbatim (always present)
│   │       ├── raw_blocks.json           # schematized API response (absent for search)
│   │       └── assets/
│   │           ├── assets_manifest.json  # versioned manifest
│   │           └── files/                # downloaded asset bodies
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # state files and indexes (see below)
├── relations/                            # edges.jsonl + graph.md (rebuilt by `pplx-export relations`)
├── crosscheck/                           # cross-validation reports (manual/review artifacts)
└── bob/ ...
```

<a id="the-thread-directory" data-pplx-source-anchor="true"></a>
## Le dossier du fil

Chaque fil reçoit exactement un dossier, calculé par `thread_dir_for` (`fs_writer.py:58-72`) :

```
<account display name>/<mode>/<YYYY-MM-DD>_<title-slug>_<uuid8>/
```

| Composant | Source | Remarques |
|---|---|---|
| `<account display name>` | auteur du fil, via `author_folder` → `_safe_folder` (`fs_writer.py:40-51`) | les séparateurs de chemin et les caractères illégaux sous Windows (`:*?"<>\|`) deviennent `_` ; `.`/`..` rejetés (garde de traversée de chemin pour les espaces partagés) ; tout le reste — y compris les espaces — est conservé |
| `<mode>` | `detect_mode` | un des cinq modes ; voir [Modes de conversation](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` `lastUpdated` préfixe de date | la date de dernière mise à jour de la plateforme, **pas** la date d'exportation — elle bouge lorsqu'un fil continué est mis à jour (voir migration ci-dessous) |
| `<title-slug>` | `slugify(title)` (`normalize.py:261-263`) | max 40 caractères, les caractères non verbaux → `-`, vide → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | 8 premiers caractères de l'UUID du fil — l'ancre d'identité du dossier |

<a id="files-in-a-thread-directory" data-pplx-source-anchor="true"></a>
## Fichiers dans un dossier de fil

<a id="threadjson-metadata-and-registries" data-pplx-source-anchor="true"></a>
### thread.json — métadonnées et registres

Écrit par `write_thread` (`fs_writer.py:224-253`). Clés toujours présentes :

| Clé | Contenu |
|---|---|
| `web_uuid` | entryUUID web — l'UUID dans l'URL du fil ; l'identité du fil |
| `psc_uuid` | `context_uuid` de la plateforme (nullable ; du premier tour non vide) — l'ID double utilisé par les index d'espaces |
| `url` | URL canonique du fil |
| `title` | titre du fil |
| `mode` | mode détecté (`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | nom d'affichage du compte auteur |
| `export_via` | nom d'utilisateur du compte ayant effectué l'exportation — important pour les fils d'espaces partagés exportés via un autre compte |
| `space` | `{"uuid", "title", "slug"}` ou `null` |
| `lastUpdated` | horodatage de dernière mise à jour de la plateforme (contrat de comparaison machine pour la synchronisation incrémentielle) |
| `threadAccess` | indicateur d'accès de la plateforme |
| `n_turns` | nombre de tours |
| `n_sources` | nombre de citations à l'échelle du fil |
| `metadata` | `thread_metadata` de la réponse API, textuellement |
| `report_info` | `{"title", "file_name", "url"}` ou `null` |
| `exported_at` | heure d'exportation (UTC ISO 8601) |

Clés optionnelles — absentes lorsqu'il n'y a rien à enregistrer :

| Clé | Ajoutée quand | Contenu |
|---|---|---|
| `interruptions` | tout workflow non terminé (`fs_writer.py:242-244`) | liste de `{location, kind, headline, status}` ; voir [Modes de conversation — Interruptions](modes.md#interruptions-non-completed-workflows) |
| `answer_variants` | une variante de réécriture de réponse est détectée (`fs_writer.py:247-252`) | `side_by_side_metadata` réduit localisant les champs ; voir [Modes de conversation — Variantes de réécriture de réponse](modes.md#answer-rewrite-variants-answer_variants) |
| `remote_deleted` | `pplx-export sync-deleted --online` confirme la suppression distante | horodatage de pierre tombale, écrit sur place, idempotent (la valeur existante n'est jamais écrasée ; `sync_deleted_cmd.py:215-244`) — l'archive locale elle-même est conservée |

<a id="conversationmd-the-compact-read" data-pplx-source-anchor="true"></a>
### conversation.md — la lecture compacte

`render_conversation` (`render.py:641`) : en-tête de titre (mode / auteur / tours / nombre de citations),
puis par tour une paire `### Query` + `### Answer` avec les réponses complètes, et — lorsqu'il est présent —
l'annexe de tâche en arrière-plan au niveau du fil à la fin. C'est le fichier à ouvrir en premier ; les processus
de travail par tour se trouvent dans `turns/`.

<a id="turnsturn_nnnnmd-the-full-read" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md — la lecture complète

`render_turn` (`render.py:596`) : un fichier par tour (`turn_0001.md` …), chacun avec le processus
de travail complet — étapes, appels d'outils, exécutions de sous-agents, tableaux, citations par tour. Lorsque le
nombre de tours d'un fil diminue, les fichiers `turn_*.md` obsolètes de numéro élevé sont supprimés mais les fichiers
non touchés conservent leur mtime (`fs_writer.py:287-301`).

### sources.json / sources.md

Citations à l'échelle du fil, dédoublonnées par URL (`fs_writer.py:270-278`). `sources.json` est
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}` ; `sources.md` est la même
liste sous forme de liste de liens Markdown numérotés.

### report.md

Le produit du rapport de recherche approfondie, écrit uniquement lorsque le fil en contient un
(`fs_writer.py:308-316`) : titre du rapport, nom de fichier du produit original, puis le rapport complet
en Markdown.

<a id="raw_entriesjson-raw_blocksjson-raw-fidelity" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json — fidélité brute

Les réponses API, conservées textuellement **avant** tout analyse (`fs_writer.py:257-266`) :

- `raw_entries.json` — la réponse simple : `{"thread_metadata", "entries", "background_entries"}`.
  Toujours présent.
- `raw_blocks.json` — la réponse schématisée, même forme. Absent pour les fils `search`
  (pas de récupération de blocs) ; récupéré pour les quatre autres modes, et également comme solution de repli lorsque
  tout signal de détection de mode est manquant.

Ces deux fichiers sont l'ancre de fidélité de l'archive : l'analyse, le rendu et les registres peuvent
tous être reconstruits à partir d'eux hors ligne, avec zéro réseau. Voir
[Opérations hors ligne](../architecture/offline-operations.md).

<a id="assets-products-and-their-manifest" data-pplx-source-anchor="true"></a>
### assets/ — produits et leur manifeste

Les produits téléchargeables (fichiers du mode Computer, et tout autre actif listé par l'API) sont récupérés
depuis des URL signées CloudFront dans `assets/files/` ; l'extension est décidée au moment du téléchargement
à partir du chemin URL, des octets magiques du contenu ou du type d'actif. `assets/assets_manifest.json`
(`fs_writer.py:320-330`) enregistre chaque version :

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` est toujours le **nombre total de versions** (Σ `len(versions)`), pas le nombre de groupes
de fichiers — utilisez `len(files)` pour cela.

<a id="the-index-layer" data-pplx-source-anchor="true"></a>
## La couche index/

`web_archive/index/` contient l'état géré par l'outil et les index — ne pas modifier manuellement :

| Fichier | Écrit par | Sémantique |
|---|---|---|
| `library_<account>.json` | `pplx-export index` (`index_cmd.py:17-43`) | index complet des fils du compte (GraphQL) ; entrée pour les index par lot / planification / espace |
| `batch_state.json` | `BatchState` (`state.py`) | point de contrôle reprenable : uuid → statut (ok/error/expired/deleted) + lastUpdated ; écritures atomiques ; fichiers corrompus automatiquement sauvegardés sous `.corrupt-<ts>` |
| `.cookies.json` | cache de cookies (`common.py:111`, `common.py:150`) | cache de cookies de fraîcheur 12h avec source et email du compte ; écrit `0o600` puis remplacé atomiquement (identifiants de session, lisible uniquement par le propriétaire) |
| `space_<slug>.json` | `pplx-export space-index` (`spaces_cmd.py:106-167`) | liste des fils par espace, incluant le mappage d'ID double `context_uuid` |
| `space_meta.json` | `pplx-export spaces --fetch-meta` (`spaces_cmd.py:299-330`) | cache des propriétaires/membres d'espace réutilisé lors des reconstructions |
| `credit_usage_<account>.json` | `pplx-export usage-backfill` (`usage_backfill_cmd.py:17`) | utilisation de crédits par fil (idempotent, reprenable, vidé toutes les 25 entrées) |
| `cron_snippet.txt` | `pplx-export schedule` (`scheduler.py:48-78`) | extrait d'invocation cron (chemins absolus) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (`variant_log.py:76`) | registre central des variantes de réécriture de réponse, dédoublonné par (thread, entry), idempotent |
| `logs/` | `--log-file` (`common.py:218-229`) | journaux DEBUG complets |

<a id="the-spaces-layer" data-pplx-source-anchor="true"></a>
## La couche spaces/

`pplx-export spaces` agrège `index/library_*.json` dans un index d'espace (`spaces_cmd.py:259-389`) :
un `<slug>.md` par espace (comptes participants, en-tête propriétaire/membre, tableau des fils,
liens retour vers l'emplacement d'exportation) plus un registre `spaces.json`.

!!! note "Emplacement de sortie"
    `spaces/` est écrit relativement au répertoire de travail courant (`spaces_cmd.py:332`) — il
    ne **suit pas** `--out`. Ne pas modifier manuellement : la prochaine reconstruction écrase.

<a id="cross-day-continuation-directory-migration-by-uuid-identity" data-pplx-source-anchor="true"></a>
## Continuation sur plusieurs jours : migration de dossier par identité UUID

Le nom du dossier intègre la date `lastUpdated`, donc lorsque vous continuez un fil un jour ultérieur,
le calcul naïf produit un *nouveau* dossier. L'écrivain empêche les doublons par identité UUID
(`thread_dir_for`, `fs_writer.py:58-72`) :

1. **Trouver** : `find_thread_dirs` (`fs_writer.py:74-105`) recherche dans toute l'archive les
   dossiers se terminant par `_<uuid8>` — tous comptes et tous modes confondus. Un candidat n'est accepté que
   si son `thread.json` existe, s'analyse et que son `web_uuid` correspond exactement ; les dossiers
   manquants, corrompus ou non correspondants ne sont jamais touchés (mieux vaut sauter une migration que de mal fusionner).
2. **Fusionner** : `_merge_into` (`fs_writer.py:107-178`) fusionne l'ancien dossier dans le nouveau —
   union des fichiers (rien d'unique à l'ancien dossier n'est perdu) ; même nom + même contenu → sauter ;
   les conflits de même nom **gardent toujours le côté cible** (le plus récent sémantiquement), chaque
   conflit étant journalisé. Chaque fichier copié est vérifié par sha256 avant la suppression de l'ancien dossier ; tout
   échec laisse l'ancien dossier intact et les tentatives sont idempotentes.
3. **Nettoyer les doublons historiques** : `consolidate_uuid` (`fs_writer.py:180-209`) fusionne
   les dossiers de date en double d'un UUID dans toute l'archive, en conservant celui avec le `lastUpdated`
   maximal — le filet de sécurité pour les doublons laissés par les versions plus anciennes.

La même rigueur d'UUID protège les liens retour de l'index d'espace : les dossiers candidats avec un
`thread.json` manquant/corrompu/non correspondant ne sont jamais liés.

<a id="hand-editable-vs-tool-managed" data-pplx-source-anchor="true"></a>
## Modifiable manuellement vs géré par l'outil

- **Géré par l'outil (ne pas modifier manuellement)** : tout ce qui se trouve dans les dossiers de fil, plus `index/`,
  `spaces/` et `relations/`. Si le contenu est erroné, corrigez l'outil et régénérez — les corrections
  de rendu passent par `pplx-export re-render`, les corrections de données par la commande de remplissage correspondante
  (voir [Commandes de maintenance](maintenance-commands.md)) — ainsi chaque artefact reste reproductible à partir
  des données brutes.
- **Modifiable manuellement** : la documentation et les rapports de révision `web_archive/crosscheck/`.
  Une exception au niveau utilisateur : une réponse alternative sauvée manuellement peut être enregistrée sous
  `rewritten_answer_variant.md` dans le dossier du fil — voir
  [Modes de conversation — Variantes de réécriture de réponse](modes.md#answer-rewrite-variants-answer_variants).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Voir aussi

- [Modes de conversation](modes.md) — les cinq modes et ce que chacun produit
- [Synchronisation incrémentielle](incremental-sync.md) — comment `lastUpdated` pilote les réexportations
- [Commandes de maintenance](maintenance-commands.md) — re-rendu, remplissages, sync-desupprimés
- [Modèle de données et contrat de répertoire](../architecture/data-model.md) — les classes de données sous-jacentes
- [Pipeline d'exportation](../architecture/export-pipeline.md) — comment ces fichiers sont écrits
- [Opérations hors ligne](../architecture/offline-operations.md) — tout reconstruire à partir de `raw_*.json`
