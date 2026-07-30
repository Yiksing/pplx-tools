---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/pplx-export.md"
translation_source_sha256: "09f79a39d95641d1816d529b4471c245bb60e11c49266417504b27a495c90231"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` est l'interface en ligne de commande d'archivage : elle récupère les index de conversations depuis Perplexity, exporte les fils dans l'archive locale et maintient les vues dérivées (index des espaces, extrait cron). Cette page couvre les sous-commandes de capture — `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule` — ainsi que la commande de configuration unique `init`. Les sous-commandes de rattrapage/réparation se trouvent dans [maintenance-commands.md](maintenance-commands.md) ; l'interface de requête est couverte dans [pplx-ask.md](pplx-ask.md).

<a id="common-options" data-pplx-source-anchor="true"></a>
## Options communes

Chaque sous-commande accepte ces drapeaux (définis une fois dans `pplx_export/commands/common.py`) :

| Drapeau | Signification | Défaut |
|---|---|---|
| `--account NAME` | Compte cible. Lorsque l'email du cookie ne correspond pas à l'email enregistré, les jetons de session du navigateur par compte sont énumérés pour basculer automatiquement | `default_account` de la configuration utilisateur |
| `--config PATH` | Fichier de configuration utilisateur (registre des comptes). Priorité : `--config` > env `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | chaîne de recherche par défaut |
| `--skip-auth-check` | Ignorer la sonde de session d'attribution de compte au démarrage et se fier à la connexion actuelle, évitant une longue attente au démarrage sur un réseau lent ; `batch` exécute une vérification de compte différée si des erreurs s'accumulent — voir [Configuration](configuration.md) | désactivé |
| `--site NAME` | Adaptateur de site | `perplexity` |
| `--out DIR` | Racine de sortie de l'archive | `--out` > config `archive_root` > `./web_archive` |
| `--cookies-from BROWSER` | Importer les cookies depuis un navigateur (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | Fichier de cookies Netscape ou fichier de cookies JSON | — |
| `--transport MODE` | `cookie` = requêtes directes avec cookies ; `webbridge` = récupération dans le contexte de la page du navigateur | `cookie` |
| `-v`, `--verbose` | Sortie DEBUG (traces de requêtes, décisions internes) ; répétable | désactivé |
| `--log-file [PATH]` | Écrire le journal complet sur le disque ; sans valeur, chemin automatique `<out>/index/logs/<cmd>-<timestamp>.log` | désactivé |

- `--cookies-from` / `--cookies` sont mutuellement exclusifs avec `--transport webbridge` — le pont s'exécute dans le contexte de la page et transporte déjà les cookies du navigateur.
- `pplx-export --version` affiche la version du paquet et quitte (niveau supérieur uniquement, pas un drapeau de sous-commande).
- Enregistrement du compte, sources de cookies et basculement multi-comptes : [configuration.md](configuration.md). Où tout atterrit sur le disque : [archive-layout.md](archive-layout.md).

## init

Découvrir les comptes à partir des cookies du navigateur et écrire la configuration utilisateur — l'alternative automatique à la copie manuelle de `config.example.toml` (voir [configuration.md](configuration.md)).

| Drapeau | Signification | Défaut |
|---|---|---|
| `--force` | Écraser un fichier de configuration existant | désactivé (refuse d'écraser) |
| `--create-bot-space [TITLE]` | Créer l'espace BOT via l'API lorsqu'aucun titre d'espace ne correspond (une opération d'écriture sur le compte) ; un TITRE explicite pilote à la fois la correspondance et la création, sinon le titre provient de `--bot-title` ; sans ce drapeau `[bot_space]` est écrit vide | désactivé |
| `--bot-title TITLE` | Titre de l'espace utilisé à la fois pour correspondre à un espace existant et pour nommer un espace créé | `BOT` |
| *(les options communes s'appliquent)* | Les drapeaux de source de cookies choisissent où les comptes sont découverts ; pour `init` uniquement, `--config` est le chemin **d'écriture** (le chargement strict de la configuration est ignoré) | |

Comportements clés :

- Énumération des jetons : les cookies de session par compte (`__Secure-pplx.session.<uid>`) sont collectés depuis les magasins du navigateur — ou, avec `--cookies FILE`, scannés depuis le fichier de cookies (un export complet peut contenir plusieurs comptes). Sans jetons énumérables, seule la session active actuelle est sondée.
- Sonde de session : chaque jeton est essayé contre `GET /api/auth/session` pour apprendre l'email / le nom d'affichage du compte ; les jetons qui échouent ou ne retournent pas d'email sont ignorés avec un avertissement.
- Assemblage du registre : chaque clé de compte est dérivée de la partie locale de l'email (les collisions reçoivent des suffixes `-2`/`-3`…) ; `default_account` est défini sur le compte actuellement actif, sinon le premier découvert.
- Espace BOT : un espace est mis en correspondance par titre exact (insensible à la casse) via `list_user_collections` ; lorsque rien ne correspond, `--create-bot-space [TITLE]` le crée sur place (un TITRE explicite remplace `--bot-title` pour la correspondance et la création), sinon `[bot_space]` est laissé vide.
- Le TOML est écrit atomiquement (fichier temporaire + renommage) avec les permissions 0600, et un fichier existant n'est jamais écrasé sans `--force`. La commande se termine par une ligne JSON récapitulative : chemin de configuration, clés de compte, compte par défaut, uuid/slug de l'espace BOT.
- Amorçage du modèle (au mieux) : après avoir écrit la configuration, `init` récupère `models/config/v2` et remplit la table `[models]` gérée par la machine afin qu'une configuration fraîche porte déjà les modèles/catalogue par défaut actuels ; en cas d'échec, il est ignoré avec un avertissement (rafraîchir plus tard avec `pplx-ask models --refresh`). Voir [Configuration](configuration.md).
- `--transport webbridge` est rejeté — le canal de contexte de page ne peut pas énumérer les jetons par compte.

```bash
pplx-export init                          # write the default ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --config /path/to/config.toml --force   # custom path, overwrite allowed
```

## index

Rafraîchir l'index de la liste des conversations du compte `index/library_<account>.json` — la base de référence que chaque autre commande compare.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--full` | Paginer toute la bibliothèque et réécrire l'index ; réinitialise le compteur incrémental | incrémental |

Comportements clés :

- **Incrémental par défaut.** Il pagine du plus récent au plus ancien et s'arrête dès qu'une page complète (`_STOP_RUN`) de lignes consécutives est déjà connue et inchangée, puis fusionne l'en-tête récupérée dans l'index existant — les lignes plus anciennes sont reprises textuellement (aucune perte). La première exécution, ou toute exécution sans index existant, est un balayage complet.
- **`--full`** pagine tout et réécrit l'index ; utilisez-le comme frontal de réconciliation périodique.
- **Angle mort du chemin incrémental :** les *suppressions* et *changements d'espace* à distance des fils plus anciens n'apparaissent jamais dans l'en-tête récupérée, donc ils ne sont pas observés. L'autorité de suppression reste avec `sync-deleted --online`. Le document d'index suit `incremental_runs_since_full` ; après suffisamment d'exécutions incrémentales, il vous avertit d'exécuter `--full` (et `sync-deleted --online`).
- Préserve l'enrichissement `search_mode` écrit par `search-mode-backfill`, fusionné en retour par `entryUUID`.
- Exécutez-le avant `batch`, `sync-space` et `sync-deleted` — leurs différences ne sont aussi fraîches que cet index.

```bash
pplx-export index --account alice          # incremental refresh
pplx-export index --account alice --full   # full sweep + reconciliation front-end
```

## sync

Point d'entrée pratique haute fréquence : **`index` incrémental + `batch` incrémental**, concentré uniquement sur les conversations.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--full` | Réconciliation complète : balayage complet `index` + complet `batch` (et exécute les étapes de suppression/espace ci-dessous) | désactivé |
| `--check-deleted` | Exécuter également `sync-deleted --online` pour vérifier et marquer les fils supprimés à distance | désactivé |
| `--refresh-spaces` | Également reconstruire `spaces --fetch-meta` et exécuter `sync-space` | désactivé |
| `--limit N` / `--mode X` / `--delay-min` / `--delay-max` | Transmis à la phase `batch` | — |

Comportements clés :

- L'exécution par défaut récupère uniquement les conversations nouvelles/mises à jour et **ignore la détection de suppression et le rafraîchissement des espaces** — la forme la moins coûteuse pour une synchronisation fréquente.
- La réconciliation des suppressions/espaces est optionnelle (`--check-deleted` / `--refresh-spaces`) ou groupée par `--full`. Le compteur `index` (`incremental_runs_since_full`) est la sécurité : il vous rappelle quand une réconciliation `--full` est en retard.

```bash
pplx-export sync --account alice                     # conversations only (fast)
pplx-export sync --account alice --full              # periodic full reconciliation
pplx-export sync --account alice --check-deleted     # also mark remote deletions
```

## space-index

Extraire la liste de conversations "Tout" d'un espace — y compris les fils partagés par d'autres membres — dans `index/space_<slug>.json`.

| Drapeau | Signification | Défaut |
|---|---|---|
| `SPACE_URL` (positionnel) | URL de la page de l'espace | requis |
| `--transport webbridge` | Utiliser le chemin de rendu navigateur hérité au lieu de REST | `cookie` (REST direct) |

Comportements clés :

- Le chemin par défaut est REST direct : `list_collection_threads` via le transport de cookies avec pagination par décalage ; les lignes incluent `context_uuid` et `answer_preview`.
- Avec `--transport webbridge`, il revient au défilement de la page d'espace rendue et au grattage des propriétés de ligne — une sauvegarde au cas où la structure REST changerait.
- Les lignes sont écrites du plus récent au plus ancien par `lastUpdated`.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

Exporter un seul fil (URL ou UUID nu) dans son répertoire d'archive `<out>/<account-folder>/<mode>/<thread-dir>/`.

| Drapeau | Signification | Défaut |
|---|---|---|
| `THREAD` (positionnel) | URL du fil ou UUID | requis |
| `--force` | Ré-exporter même lorsque `lastUpdated` est inchangé | désactivé |

Comportements clés :

- Si la copie archivée est déjà à jour, l'export est ignoré sans écriture ; `--force` remplace la vérification.
- `lastUpdated` est tiré de l'index de la bibliothèque locale lorsque le fil y est listé (mêmes sémantique et format que `batch`), en utilisant la valeur de la plateforme sinon.
- Les états terminaux sont enregistrés gracieusement, sans traceback : `ENTRY_DELETED` marque `deleted` dans `batch_state.json`, `ENTRY_EXPIRED` marque `expired` — l'archive locale existante est conservée intacte dans les deux cas.
- Un export réussi écrit `ok` dans `index/batch_state.json`, de sorte que le plan incrémental compte le fil comme "exporté et inchangé".
- Ce qui atterrit dans le répertoire du fil : [archive-layout.md](archive-layout.md) ; le pipeline d'export lui-même : [../architecture/export-pipeline.md](../architecture/export-pipeline.md).

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

Export en masse des fils d'un compte — l'outil quotidien, avec arrêt précoce incrémental et points de contrôle reproductibles.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--force` | Ré-exporter tous les fils (états terminaux exclus) | désactivé |
| `--full` | Balayage complet : les fils inchangés sont toujours ignorés, mais pas d'arrêt précoce | désactivé |
| `--limit N` | Traiter uniquement les N premières lignes de la liste (du plus récent au plus ancien) | tous |
| `--mode MODE` | Exporter uniquement les fils `search` / `deep-research` / `computer` / `council` / `study` | tous les modes |
| `--delay-min SEC` | Borne inférieure de l'intervalle aléatoire entre les fils | `10` |
| `--delay-max SEC` | Borne supérieure de l'intervalle aléatoire entre les fils | `20` |

Comportements clés :

- Nécessite `index/library_<account>.json` — exécutez `index` d'abord.
- **Arrêt précoce incrémental par défaut** : la liste est triée du plus récent au plus ancien et la séquence finale de fils "exportés et inchangés" est supprimée en bloc ; les lacunes laissées par des exécutions interrompues (erreur/jamais exporté) se situent au-dessus de ce suffixe et sont toujours réparées. `--full` désactive l'arrêt précoce (sécurité périodique, ou lorsque des lacunes d'archive sont suspectées) ; `--force` ré-exporte tout sauf les états terminaux, qui ne sont jamais réessayés. Sémantique complète : [incremental-sync.md](incremental-sync.md).
- Filtrage `--mode` : les lignes portant `search_mode` (le champ faisant autorité sur la plateforme enrichi par `search-mode-backfill`) correspondent exactement via `SEARCH_MODE_MAP` — sur ce chemin `--mode search` n'inclut plus les fils deep-research/council/study. Les lignes sans `search_mode` utilisent des heuristiques d'index : `computer` = mode `COMPUTER` ; `deep-research` = displayModel `pplx_alpha` ; `council` = `pplx_agentic_research` ; `study` = `pplx_study` ; `search` = les lignes restantes de mode `SEARCH` (y compris ces trois types — filtrez-les précisément en exportant les modes spécifiques séparément).
- L'état est sauvegardé dans `index/batch_state.json` après chaque fil — interrompez et réexécutez librement.
- Échec rapide d'authentification : 3 réponses 401/403 consécutives abandonnent l'exécution (un cookie expiré ne peut pas s'auto-réparer, et continuer échouerait des centaines de fils un par un).
- Rythme : une pause aléatoire `--delay-min`–`--delay-max` entre les fils ; les 429/5xx sont gérés par la couche de transport. Détails : [rate-limiting.md](rate-limiting.md).
- Les fils rencontrant des variantes de réponse réécrites sont enregistrés dans `index/answer_variants_log.jsonl` avec un avertissement pour les traiter manuellement dès que possible (voir [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md)).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

Reconstruire l'index de vue des espaces — une page Markdown par espace plus un registre `spaces.json` — à partir des index de la bibliothèque locale.

| Drapeau | Signification | Défaut |
|---|---|---|
| `--fetch-meta` | Rafraîchir les métadonnées propriétaire/membre avant la reconstruction | désactivé |

Comportements clés :

- Sans `--fetch-meta` la commande est purement locale (zéro réseau) : elle agrège les fils par slug d'espace dans tous les fichiers `library_*.json`, avec des statistiques de comptes participants et des liens retour vers les répertoires de fils exportés.
- La sortie va dans `./spaces/` relatif au répertoire de travail actuel — exécutez-la depuis le répertoire contenant `web_archive/` pour que les liens retour dans les pages d'espace se résolvent.
- `--fetch-meta` rafraîchit d'abord le cache propriétaire/membre de chaque espace via `get_collection` (1 requête par espace, intervalle de 3s) dans `index/space_meta.json` ; lorsque le compte actuel ne peut pas voir un espace, un compte qui le peut est réessayé automatiquement (les cookies basculent d'eux-mêmes).

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

Synchroniser le champ `space` des fichiers `thread.json` déjà archivés avec l'index actuel — purement local, zéro réseau.

| Drapeau | Signification | Défaut |
|---|---|---|
| *(options communes uniquement ; seul `--out` importe)* | | |

Comportements clés :

- Prérequis : exécutez `index` d'abord — le `library_*.json` rafraîchi est la source de vérité pour la propriété actuelle des espaces.
- Compare les slugs d'espace par fil et corrige `thread.json` sur place en cas de divergence ; les 30 premiers changements sont journalisés.
- Après tout changement, l'index `spaces/` est reconstruit automatiquement en parallèle.

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

Calculer le plan d'export incrémental de ce tour et écrire un extrait cron que le cron système peut appeler directement.

| Drapeau | Signification | Défaut |
|---|---|---|
| *(options communes uniquement)* | | |

Comportements clés :

- Récupère un index en direct et rapporte le plan sous forme de comptes total/nouveau/mis à jour, en utilisant la même fonction pure d'arrêt précoce (`plan_incremental`) que `batch` — voir [incremental-sync.md](incremental-sync.md).
- Écrit `<out>/index/cron_snippet.txt` contenant une ligne `17 3 * * *` de la forme `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'` — les chemins sont absolus et entre guillemets car le répertoire de travail et le PATH de cron sont imprévisibles. Le chemin de l'exécutable est résolu via `shutil.which` ; en cas d'échec, l'extrait utilise le nom nu `pplx-export`.
- Les exécutions planifiées sont uniquement incrémentales par conception ; exécutez `batch --full` manuellement comme sécurité périodique.

```bash
pplx-export schedule --account alice
```
