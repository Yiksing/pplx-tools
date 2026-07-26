---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "39f85a86f94a3b326e9d3b9a74e9452a379a4745667b57c124c9512bfd1d9755"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# Configuration

pplx-export conserve vos données d'identité — le registre des comptes (noms d'affichage, emails de connexion, ID utilisateur) et l'espace BOT — dans un fichier TOML au niveau utilisateur qui se trouve en dehors du dépôt. Cette page couvre l'emplacement de ce fichier, chaque champ qu'il accepte, ce qui se passe lorsqu'il est manquant, et comment le registre gère la gestion des cookies multi-comptes.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## Pourquoi la configuration se trouve en dehors du dépôt

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

Ensuite, modifiez la copie. Le modèle utilise des espaces réservés purs — copiez la structure, remplacez chaque valeur :

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
    La configuration réelle contient des données personnelles (emails, ID utilisateur). La permission recommandée est `0o600` ; ne la commitez jamais dans un dépôt git (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## Référence des champs

<a id="top-level" data-pplx-source-anchor="true"></a>
### Niveau supérieur

| Champ | Type | Signification |
|---|---|---|
| `default_account` | chaîne | Clé d'une table `[accounts.<name>]`, utilisée lorsque `--account` n'est pas fourni (`pplx_export/commands/common.py:84-85`). Vide/manquant = mode dégradé. |

### `[accounts.<name>]`

Une table par compte ; `<name>` est le nom d'utilisateur du compte. Le registre se charge dans trois dictionnaires indexés par nom d'utilisateur : `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Champ | Type | Requis | Signification |
|---|---|---|---|
| `display_name` | chaîne | non | Nom d'affichage complet, utilisé pour le nommage des répertoires d'archive (`web_archive/<display name>/…`) ; revient au nom d'utilisateur lorsqu'il est omis. Voir [Structure d'archive](archive-layout.md). |
| `email` | chaîne | recommandé | Email de connexion. Le transport vérifie la propriété du cookie par rapport à celui-ci, empêchant « une exportation pour le compte B transportant la session du compte A » (`pplx_export/config.py:69-72`). En cas de non-correspondance, l'outil énumère les jetons de session par compte dans le navigateur et bascule automatiquement — voir [Modèle de cookies multi-comptes](#multi-account-cookie-model). |
| `user_id` | chaîne | pour la télémétrie `pplx-ask` | UID du compte, requis par la télémétrie de visualisation de fil (`pplx_export/config.py:73-75`). Lisez-le depuis `GET /api/auth/linked-accounts`, qui renvoie `user_id` / `email` / `display_name` de chaque compte connecté — voir [Authentification API](../reference/api/api-authentication.md). |

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

Voir [pplx-export](pplx-export.md) pour la référence complète des indicateurs.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## Configuration manquante : mode dégradé

Lorsque rien n'est chargé, les registres au niveau du module restent vides et `LOADED_CONFIG_PATH` est `None` (`pplx_export/config.py:83-85`). Comportement par scénario (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`) :

| Scénario | Comportement |
|---|---|
| Aucune configuration au chemin par défaut, `--account` non fourni | Mode dégradé : un avertissement est enregistré et les commandes s'exécutent avec un compte fictif (`username='default'`) ; la vérification de propriété de l'email est ignorée. Les commandes hors ligne quotidiennes ne sont pas affectées (`pplx_export/commands/common.py:86-90`). |
| Aucune configuration, `--account` explicite | `SystemExit` nommant l'ordre de recherche et pointant vers `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| Configuration chargée, `--account` non enregistré | `SystemExit` nommant le fichier chargé, vous demandant d'ajouter `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| Chemin explicite (`--config` / variable d'env.) n'existe pas | `ConfigError` en mode strict (`pplx_export/config.py:140-146`). |
| Le fichier existe mais ne peut pas être analysé | Toujours `ConfigError` — une configuration corrompue ne doit pas se dégrader silencieusement (`pplx_export/config.py:147-150`). |
| `--account` omis, configuration chargée | `default_account` est utilisé (`pplx_export/commands/common.py:84-85`). |

Ce que couvrent les « commandes hors ligne » et comment les exécutions en mode dégradé interagissent avec l'archive est détaillé dans [Opérations hors ligne](../architecture/offline-operations.md).

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## Modèle de cookies multi-comptes

Avec plusieurs comptes connectés dans le même navigateur, le magasin contient un cookie de session **par compte**, et le champ `email` de la configuration indique à l'outil lequel il a besoin :

- Chaque compte connecté a un cookie `__Secure-pplx.session.<uid>` (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`) ; le suffixe `<uid>` est le `user_id` du compte.
- Le compte **actif** est celui dont le jeton se trouve actuellement dans `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). Changer de compte = écrire la valeur du cookie par compte du compte cible dans ce cookie — pas besoin d'interface navigateur (`pplx_export/core/cookies/loaders.py:180-187`).
- Au démarrage, le transport sonde `GET https://www.perplexity.ai/api/auth/session` et compare l'email retourné avec `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- En cas de non-correspondance, `_try_switch_account` (`pplx_export/commands/common.py:190-215`) énumère chaque jeton de compte dans le navigateur via `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`, en préférant les entrées sur le sous-domaine `www.`), essaie chacun dans `__Secure-next-auth.session-token`, et reconstruit le transport sur la première correspondance.
- Si aucun jeton ne correspond, la commande se termine en nommant les deux emails et en vous demandant de connecter d'abord le compte cible dans le navigateur (`pplx_export/commands/common.py:142-145`) — voir [Dépannage](troubleshooting.md).
- Un compte sans `email` enregistré procède sans vérification, avec un avertissement vous demandant de confirmer vous-même la connexion dans le navigateur (`pplx_export/commands/common.py:146-149`).

Pour le flux de basculement complet et la sémantique des points de terminaison de session, voir [Ask et comptes](../architecture/ask-and-accounts.md) et [Authentification API](../reference/api/api-authentication.md).

<a id="cookie-cache" data-pplx-source-anchor="true"></a>
## Cache de cookies

Après une validation réussie, les cookies résolus sont mis en cache afin que les exécutions ultérieures évitent le navigateur :

| Propriété | Valeur |
|---|---|
| Chemin | `<archive root>/index/.cookies.json` — suit `--out` (`pplx_export/commands/common.py:111`) |
| Fraîcheur | 12 heures (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`) ; un cache obsolète ou corrompu est traité comme absent |
| Contenu | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Écriture | Atomique : fichier temporaire créé avec le mode `0o600`, puis `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Couvert par `.gitignore` (`**/index/.cookies.json`) |

Ordre de résolution des cookies (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`) : `--cookies-from` explicite → fichier `--cookies` explicite → cache frais → détection automatique des navigateurs (edge → chrome → firefox → safari). Le cache est rafraîchi après chaque validation de compte réussie (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## Protéger vos fichiers

- `chmod 600` votre `config.toml` — il contient des données personnelles (emails, ID utilisateur).
- Le cache de cookies est déjà écrit avec le mode `0o600` par l'outil ; les cookies de session sont des identifiants équivalents à une connexion.
- Si vous créez manuellement un fichier de cookies pour `--cookies`, appliquez-lui également `chmod 600`.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## En cas d'échec d'authentification

Les cookies expirés, un compte que le basculement automatique ne trouve pas, les erreurs de permission du trousseau du navigateur et autres échecs d'authentification sont couverts dans [Dépannage](troubleshooting.md).
