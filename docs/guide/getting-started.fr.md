---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/getting-started.md"
translation_source_sha256: "d98ba1f32b1e75bff7b3d51ef17e833417ecaf283996152cfa3342455b6eca7a"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="getting-started" data-pplx-source-anchor="true"></a>
# Premiers pas

D'un checkout frais à une première archive locale : installez les deux commandes, créez la
configuration utilisateur, choisissez un canal de cookies, et parcourez une première exportation.

<a id="requirements" data-pplx-source-anchor="true"></a>
## Prérequis

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — utilisé pour installer les outils et exécuter la suite de tests
- **Un navigateur de bureau connecté à Perplexity** — les outils réutilisent ses cookies de session ;
  aucun jeton n'est jamais stocké dans la configuration

Le déchiffrement des cookies utilise `browser_cookie3`. La détection automatique couvre Edge, Chrome, Firefox et
Safari ; Brave, Chromium, Opera et Vivaldi fonctionnent via `--cookies-from`.

<a id="install" data-pplx-source-anchor="true"></a>
## Installation

Pas besoin de clone — installez directement depuis l'URL git :

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

Depuis un clone local (racine du dépôt) :

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

Ceci installe deux commandes : `pplx-export` (archivage) et `pplx-ask` (requêtes
interactives). Vérifiez :

```bash
pplx-export --version
pplx-export --help           # overview with examples; each subcommand has its own --help
pplx-ask --help
```

`uvx --from . pplx-export` exécute une commande ponctuelle sans installation.

<a id="create-the-user-level-config" data-pplx-source-anchor="true"></a>
## Créer la configuration utilisateur

Le registre des comptes (nom d'affichage / email / user_id) et l'espace BOT sont des données
personnelles et **ne sont pas commités dans le dépôt** ; ils résident dans un fichier TOML externe.
Modèle : `config.example.toml` à la racine du dépôt.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

1. Créez le répertoire de configuration.
2. Copiez le modèle vers le chemin par défaut.
3. `chmod 600` — le fichier contient des données personnelles ; gardez-le accessible uniquement par le propriétaire.
4. Remplissez `[accounts.<name>]` — la clé est le nom d'utilisateur du compte (tel qu'il apparaît dans
   les URL de fils / la bibliothèque) ; définissez `display_name`, `email`, `user_id`, et choisissez un
   `default_account`.
5. Remplissez `[bot_space]` — où les fils créés par `pplx-ask` sont collectés après
   leur achèvement (un espace réel peut être créé avec `pplx-ask space-create`).

**Alternative automatique :** `pplx-export init` dérive ce fichier pour vous — il
énumère les cookies de session par compte dans votre navigateur, sonde
`/api/auth/session` pour l'email / nom d'affichage de chaque jeton, définit
`default_account` sur le compte actuellement actif, fait correspondre l'espace BOT par
titre, et écrit le TOML de manière atomique avec les permissions 0600 (un fichier existant
n'est écrasé qu'avec `--force`).

```bash
pplx-export init                     # discover accounts, write the default config path
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --bot-title TITLE   # match/create a different space title (default BOT)
pplx-export init --config /path/to/config.toml   # write to a custom path
```

Drapeaux : `--force` écrase une configuration existante ; `--create-bot-space [TITLE]`
crée l'espace via l'API lorsqu'aucun titre ne correspond (une opération d'écriture sur le
compte ; un TITLE explicite pilote à la fois la correspondance et la création) ; `--bot-title TITLE`
est utilisé à la fois pour la correspondance et la création. Notez que pour
`init` — contrairement à toutes les autres commandes — `--config` est le chemin **d'écriture**, pas
le chemin de chargement. Détails complets : [pplx-export → init](pplx-export.md#init).

La référence complète des champs se trouve dans [Configuration](configuration.md).

**Priorité de chargement** (la plus élevée d'abord) :

| # | Source |
|---|--------|
| 1 | `--config PATH` |
| 2 | `PPLX_EXPORT_CONFIG` variable d'environnement |
| 3 | `~/.config/pplx-export/config.toml` (par défaut) |

!!! note "Quand la configuration est manquante"
    Les commandes sans `--account` s'exécutent en mode dégradé — la vérification de propriété de l'email est
    ignorée avec un avertissement (les commandes hors ligne ne sont pas affectées) ; un `--account` explicite
    génère une erreur pointant vers `config.example.toml`. Lorsque `--account` est omis,
    `default_account` de la configuration est utilisé.

<a id="choose-a-cookie-channel" data-pplx-source-anchor="true"></a>
## Choisir un canal de cookies

Les identifiants proviennent des cookies de session de votre navigateur local connecté à Perplexity, lus
via `browser_cookie3` — y compris l'énumération des jetons multi-comptes et la commutation
automatique. Quatre canaux :

| Canal | Comment | Notes |
|---------|-----|-------|
| Détection automatique (par défaut) | aucun drapeau | cache frais de 12 h d'abord, puis magasins du navigateur dans l'ordre edge→chrome→firefox→safari |
| Navigateur nommé | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| Fichier de cookies | `--cookies /path/to/cookies.txt` | Fichier de cookies Netscape ou JSON exporté |
| WebBridge | `--transport webbridge` | Récupération dans le contexte de la page — le canal de repli, utilisé uniquement lorsqu'il est explicitement demandé |

Sous Linux, les installations de navigateurs snap et flatpak sont également détectées automatiquement — leurs chemins
de profil sont couverts par le registre intégré. La matrice Linux complète (trousseau, environnements
de bureau, paquets de distribution) :
[Dépannage → Déchiffrement des cookies Linux](troubleshooting.md#linux-cookie-decryption).

```bash
pplx-export export <thread_url>                                 # default: auto-detect browser store
pplx-export export <thread_url> --cookies-from edge             # import from a specific browser
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # use a cookie file
pplx-export export <thread_url> --transport webbridge           # WebBridge page context (explicit fallback)
```

Après l'obtention des cookies, l'outil appelle `/api/auth/session` et affiche l'email du compte
actuel afin que vous puissiez confirmer que le bon compte est utilisé — faites attention si `--account`
est en désaccord avec le compte du cookie. La conception du transport/des identifiants est couverte dans
[Ask & comptes](../architecture/ask-and-accounts.md).

<a id="first-run" data-pplx-source-anchor="true"></a>
## Première exécution

```bash
pplx-export index --account alice     # fetch the library index
pplx-export export <thread_url>       # export a single thread
pplx-export batch --account alice     # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run       # offline re-render, zero network
```

1. **`index`** récupère l'index de la bibliothèque du compte — le point d'entrée sur lequel `batch` et
   les autres commandes à l'échelle du compte s'appuient.
2. **`export`** archive un fil de bout en bout : il conserve les réponses brutes de l'API
   (`raw_*.json`) ainsi que le Markdown afin que le rendu puisse être rejoué hors ligne.
3. **`batch`** parcourt toute la bibliothèque. Il s'arrête tôt une fois que tout ce qui reste est
   déjà archivé (arrêt précoce incrémental), écrit des points de contrôle reprise, et accepte
   `--full` pour un parcours complet. Détails : [Synchronisation incrémentale](incremental-sync.md).
4. **`re-render --dry-run`** prouve le chemin hors ligne : il régénère `conversation.md`
   + `turns/` à partir des fichiers bruts locaux sans réseau. Ajoutez `--dry-run` pour écrire les
   résultats. Voir [Opérations hors ligne](../architecture/offline-operations.md).

Une fois que cela fonctionne, `pplx-ask ask "<prompt>"` exécute une requête en streaming et archive le
fil résultant automatiquement — voir [pplx-ask](pplx-ask.md).

<a id="where-archives-land" data-pplx-source-anchor="true"></a>
## Où les archives atterrissent

Les archives sont écrites dans `./web_archive/` par défaut (remplacez avec `--out`) : un
répertoire par fil.

| Chemin | Contenu |
|------|---------|
| `conversation.md`, `turns/` | conversation rendue |
| `thread.json` | métadonnées du fil + registre des interruptions |
| `sources.md` / `sources.json` | citations |
| `report.md` | rapport deep-research / council / study |
| `assets/` | ressources téléchargées (mode Computer) |
| `raw_*.json` | réponses brutes de l'API conservées — les archives réussies peuvent être re-rendues hors ligne sans re-récupération |

Le contrat complet du répertoire : [Disposition des archives](archive-layout.md).

<a id="next-steps" data-pplx-source-anchor="true"></a>
## Prochaines étapes

- Quelque chose s'est mal passé ? → [Dépannage](troubleshooting.md)
- Référence commande par commande → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [Commandes de maintenance](maintenance-commands.md)
- Les cinq modes de conversation → [Modes](modes.md)
