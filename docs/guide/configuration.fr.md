---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "0c5f1be9b103913deee332caa4397a3dc356027148beac491834f6791f3b73db"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# Configuration

pplx-export conserve vos données d'identité — le registre des comptes (noms d'affichage, emails de connexion, identifiants utilisateur) et l'espace BOT — dans un fichier TOML au niveau utilisateur situé en dehors du dépôt. Cette page couvre l'emplacement de ce fichier, chaque champ qu'il accepte, ce qui se passe lorsqu'il est manquant, et comment le registre gère les cookies multi-comptes.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## Pourquoi la configuration vit en dehors du dépôt

Le registre des comptes et l'espace BOT sont des données personnelles et ne sont **jamais commités** dans le dépôt (`pplx_export/config.py:7-12`). Le dépôt ne fournit qu'un modèle d'espace réservé, `config.example.toml` ; vos valeurs réelles vont dans une copie privée. Tout le reste dont l'outil a besoin — le domaine du site, les URL de l'API, la racine d'archive par défaut — est une constante de code (`pplx_export/config.py:50-58`), pas une configuration utilisateur.

Le TOML ne contient que des données d'identité. La source des cookies et la sélection du transport sont des indicateurs CLI par invocation, pas des champs de configuration — voir [Indicateurs CLI, pas champs de configuration](#cli-flags-not-config-fields) ci-dessous.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## Emplacement et priorité de chargement

`configure()` (`pplx_export/config.py:113`) résout le chemin de configuration avec cette priorité (`pplx_export/config.py:95-110`) :

| Priorité | Source | Compté comme explicite |
|---|---|---|
| 1 | Indicateur CLI `--config PATH` | oui |
| 2 | Variable d'environnement `PPLX_EXPORT_CONFIG` | oui |
| 3 | `~/.config/pplx-export/config.toml` (chemin par défaut) | non |

« Explicite » est important pour le comportement en cas d'erreur lorsque le fichier est manquant — voir [mode dégradé](#missing-config-degraded-mode). Les deux entrées CLI rechargent la configuration en mode strict après l'analyse des arguments (`pplx_export/cli.py:223`, `pplx_export/ask_cli.py:278`) ; le chargement au moment de l'importation (`pplx_export/config.py:174-179`) est tolérant aux pannes, donc l'importation du paquet ne plante jamais sur un fichier manquant.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## Création de votre configuration

!!! tip "Alternative automatique"
    `pplx-export init` peut générer ce fichier automatiquement — il découvre les comptes connectés à partir des cookies de votre navigateur et écrit le TOML avec les permissions 0600. Voir [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

Modifiez ensuite la copie. Le modèle utilise des espaces réservés purs — copiez la structure, remplacez chaque valeur :

```toml
# Default account used when --account is not given (a key of [accounts.<name>] below)
default_account = "alice"

# Account registry: key = account username (the username in thread URLs / library)
[accounts.alice]
# Full display name: used for archive directory naming (web_archive/<display name>/…)
display_name = "Alice Example"
# Login email: verifies cookie ownership
email = "alice@example.com"
# Account uid (required for thread-viewed telemetry)
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT space: where threads created by pplx-ask are collected after completion
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

Style d'espace réservé : `alice`/`bob` sont des noms d'utilisateur de compte fictifs, les emails utilisent `example.com`, et les UUID utilisent la forme `00000000-0000-4000-8000-…` tout zéros. Dans votre fichier réel, la clé de table **doit être le nom d'utilisateur réel du compte** tel qu'il apparaît dans les URL de fil et votre bibliothèque.

!!! warning "Gardez-le privé"
    La configuration réelle contient des données personnelles (emails, identifiants utilisateur). La permission recommandée est `0o600` ; ne la commitez jamais dans un dépôt git (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## Référence des champs

<a id="top-level" data-pplx-source-anchor="true"></a>
### Niveau supérieur

| Champ | Type | Signification |
|---|---|---|
| `default_account` | chaîne | Clé d'une table `[accounts.<name>]`, utilisée lorsque `--account` n'est pas fourni (`pplx_export/commands/common.py:84-85`). Vide/manquant = mode dégradé. |
| `archive_root` | chaîne | Optionnel. Racine de sortie d'archive utilisée comme solution de repli `--out`, afin que les commandes quotidiennes puissent omettre `--out`. Priorité : `--out` > `archive_root` > `./web_archive` (`pplx_export/config.py`, chargé dans `ARCHIVE_ROOT` ; résolu dans `cli.py` / `ask_cli.py`). `~` est développé. |
| `[models]` (table) | table | **Auto-géré, pas rédigé à la main.** Catalogue de modèles actualisable écrit par `pplx-ask models --refresh` et amorcé par `pplx-export init` ; il remplace la référence de base épinglée dans `pplx_export/sites/perplexity/platform.py`. Clés : `last_refreshed` (UTC), `source_version`, `auto_refresh` (booléen), `mode_defaults`, `council_defaults`, `search_models`, et un `[models.catalog]` complet (`id → {label, provider, mode}`). Les requêtes le lisent (avec la référence de base `platform.py` comme solution de repli) ; un TTL de 7 jours imprime un rappel d'actualisation, ou s'actualise automatiquement lorsque `auto_refresh = true`. L'écriture aller-retour préserve vos autres tables et commentaires (via la dépendance d'exécution `tomlkit`) et reste `0600`. |

### `[accounts.<name>]`

Une table par compte ; `<name>` est le nom d'utilisateur du compte. Le registre se charge dans trois dictionnaires indexés par nom d'utilisateur : `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Champ | Type | Requis | Signification |
|---|---|---|---|
| `display_name` | chaîne | non | Nom d'affichage complet, utilisé pour le nommage du répertoire d'archive (`web_archive/<display name>/…`) ; se replie sur le nom d'utilisateur lorsqu'il est omis. Voir [Structure de l'archive](archive-layout.md). |
| `email` | chaîne | recommandé | Email de connexion. Le transport vérifie la propriété du cookie par rapport à celui-ci, empêchant « une exportation pour le compte B transportant la session du compte A » (`pplx_export/config.py:69-72`). En cas de non-correspondance, l'outil énumère les jetons de session par compte dans le navigateur et bascule automatiquement — voir [Modèle de cookie multi-comptes](#multi-account-cookie-model). |
| `user_id` | chaîne | pour la télémétrie `pplx-ask` | Identifiant du compte, requis par la télémétrie de vue de fil (`pplx_export/config.py:73-75`). Lisez-le depuis `GET /api/auth/linked-accounts`, qui renvoie pour chaque compte connecté `user_id` / `email` / `display_name` — voir [Authentification API](../reference/api/api-authentication.md). |

### `[bot_space]`

L'espace BOT est le point de collecte des fils créés par `pplx-ask` après leur achèvement (`pplx_export/config.py:76-79`). Créez l'espace lui-même avec `pplx-ask space-create` (voir [pplx-ask](pplx-ask.md)), puis enregistrez-le ici.

| Champ | Type | Signification |
|---|---|---|
| `uuid` | chaîne | UUID de l'espace. `pplx-ask` déplace les fils terminés ici (`pplx_export/ask_cli.py:156-158`) ; lorsqu'il est vide, l'étape de déplacement est ignorée. |
| `slug` | chaîne | Slug d'URL de l'espace. Chargé dans `BOT_SPACE_SLUG` (`pplx_export/config.py:79`) ; la CLI d'exécution ne le lit pas — l'outil de maintenance des fixtures le consomme, construisant une paire de remplacement d'identité à partir de celui-ci (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### Indicateurs CLI, pas champs de configuration

Le TOML n'a pas de paramètres de transport ou de cookies. Ceux-ci sont choisis par invocation :

| Préoccupation | Où c'est défini |
|---|---|
| Chemin du fichier de configuration | `--config PATH`, ou `PPLX_EXPORT_CONFIG` |
| Source des cookies | `--cookies-from BROWSER` / `--cookies FILE` |
| Transport | `--transport cookie\|webbridge` (`pplx-export` uniquement ; défaut `cookie`) |
| Ignorer la vérification de compte au démarrage | `--skip-auth-check` (les deux entrées) — voir [Modèle de cookie multi-comptes](#multi-account-cookie-model) |

Voir [pplx-export](pplx-export.md) pour la référence complète des indicateurs.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## Configuration manquante : mode dégradé

Lorsque rien n'est chargé, les registres au niveau du module restent vides et `LOADED_CONFIG_PATH` est `None` (`pplx_export/config.py:83-85`). Comportement par scénario (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`) :

| Scénario | Comportement |
|---|---|
| Aucune configuration au chemin par défaut, `--account` non fourni | Mode dégradé : un avertissement est journalisé et les commandes s'exécutent avec un compte d'espace réservé (`username='default'`) ; la vérification de propriété de l'email est ignorée. Les commandes hors ligne quotidiennes ne sont pas affectées (`pplx_export/commands/common.py:86-90`). |
| Aucune configuration, `--account` explicite | `SystemExit` nommant l'ordre de recherche et pointant vers `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| Configuration chargée, `--account` non enregistré | `SystemExit` nommant le fichier chargé, vous demandant d'ajouter `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| Chemin explicite (`--config` / variable d'environnement) n'existe pas | `ConfigError` en mode strict (`pplx_export/config.py:140-146`). |
| Le fichier existe mais ne peut pas être analysé | Toujours `ConfigError` — une configuration corrompue ne doit pas se dégrader silencieusement (`pplx_export/config.py:147-150`). |
| `--account` omis, configuration chargée | `default_account` est utilisé (`pplx_export/commands/common.py:84-85`). |

Ce que couvrent les « commandes hors ligne » et comment les exécutions dégradées interagissent avec l'archive est détaillé dans [Opérations hors ligne](../architecture/offline-operations.md).

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## Modèle de cookie multi-comptes

Avec plusieurs comptes connectés dans le même navigateur, le magasin contient un cookie de session **par compte**, et le champ `email` de la configuration indique à l'outil lequel il a besoin :

- Chaque compte connecté a un cookie `__Secure-pplx.session.<uid>` (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`) ; le suffixe `<uid>` est le `user_id` du compte.
- Le compte **actif** est celui dont le jeton se trouve actuellement dans `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). Changer de compte = écrire la valeur du cookie par compte du compte cible dans ce cookie — pas besoin d'interface utilisateur du navigateur (`pplx_export/core/cookies/loaders.py:180-187`).
- Au démarrage, le transport sonde `GET https://www.perplexity.ai/api/auth/session` et compare l'email renvoyé à `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- En cas de non-correspondance, `_try_switch_account` (`pplx_export/commands/common.py:190-215`) énumère chaque jeton de compte dans le navigateur via `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`, en préférant les entrées sur le sous-domaine `www.`), essaie chacun dans `__Secure-next-auth.session-token`, et reconstruit le transport sur la première correspondance.
- Si aucun jeton ne correspond, la commande se termine en nommant les deux emails et en vous demandant de connecter d'abord le compte cible dans le navigateur (`pplx_export/commands/common.py:142-145`) — voir [Dépannage](troubleshooting.md).
- Un compte sans `email` enregistré procède sans vérification, avec un avertissement vous demandant de confirmer vous-même la connexion du navigateur (`pplx_export/commands/common.py:146-149`).

Pour le flux de basculement complet et la sémantique des points de terminaison de session, voir [Ask et comptes](../architecture/ask-and-accounts.md) et [Authentification API](../reference/api/api-authentication.md).

**Ignorer la vérification (`--skip-auth-check`).** La sonde de session au démarrage ci-dessus
troque quelques secondes — parfois minutes sur un réseau médiocre — contre la
garantie de propriété « compte B utilisé comme compte A ». Lorsque vous savez
que le navigateur est connecté au bon compte, `--skip-auth-check` (partagé par
`pplx-export` et `pplx-ask`) ignore cette sonde entièrement et va
directement au travail (`pplx_export/commands/common.py`,
`make_transport`) :

- Pas de `GET /api/auth/session` au démarrage, donc un réseau instable ne produit plus
  une longue attente silencieuse (maintenant avec battement de cœur) avant la première vraie requête.
- L'outil fait confiance au compte actuellement connecté ; la vérification
  préalable de propriété de l'email et le basculement automatique multi-comptes ci-dessus ne sont pas
  exécutés.
- **Filet de sécurité différé** : dans `batch`, une fois que les erreurs d'exportation génériques s'accumulent
  (trois échecs), une vérification de compte unique s'exécute et vous avertit de ce qu'elle a trouvé —
  le cookie a expiré, le compte ne correspond pas à la cible, ou le compte est
  correct (donc les erreurs sont réseau / limite de débit, pas d'authentification)
  (`pplx_export/commands/common.py`, `report_account_status` ;
  `pplx_export/commands/batch_cmd.py`).
- **Compromis** : la vérification différée attrape un cookie expiré, mais elle ne peut pas
  attraper un compte *erroné-mais-valide* qui exporte sans erreur — avec
  `--skip-auth-check` vous assumez la responsabilité que le compte connecté est celui
  prévu.

Utilisez-le pour des exécutions rapides et non supervisées sur une connexion connue comme bonne ; omettez-le lorsque vous comptez
sur la garantie de propriété préalable ou le basculement automatique de compte.

<a id="cookie-cache" data-pplx-source-anchor="true"></a>
## Cache de cookies

Après validation réussie, les cookies résolus sont mis en cache afin que les exécutions ultérieures ignorent le navigateur :

| Propriété | Valeur |
|---|---|
| Chemin | `<archive root>/index/.cookies.json` — suit `--out` (`pplx_export/commands/common.py:111`) |
| Fraîcheur | 12 heures (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`) ; un cache périmé ou corrompu est traité comme absent |
| Contenu | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Écriture | Atomique : fichier temporaire créé avec le mode `0o600`, puis `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Couvert par `.gitignore` (`**/index/.cookies.json`) |

Ordre de résolution des cookies (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`) : `--cookies-from` explicite → fichier `--cookies` explicite → cache frais → détection automatique des navigateurs (edge → chrome → firefox → safari). Le cache est actualisé après chaque validation de compte réussie (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## Protection de vos fichiers

- `chmod 600` votre `config.toml` — il contient des données personnelles (emails, identifiants utilisateur).
- Le cache de cookies est déjà écrit avec le mode `0o600` par l'outil ; les cookies de session sont des identifiants équivalents à une connexion.
- Si vous créez manuellement un fichier de cookies pour `--cookies`, appliquez `chmod 600` également.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## En cas d'échec d'authentification

Les cookies expirés, un compte que le basculement automatique ne trouve pas, les erreurs de permission du trousseau du navigateur, et autres échecs d'authentification sont couverts dans [Dépannage](troubleshooting.md).
