---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/troubleshooting.md"
translation_source_sha256: "3feeb14ea77ad45275ccca583b2fbcbee34745db32dca749c70e0b7a77302623"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="troubleshooting" data-pplx-source-anchor="true"></a>
# Dépannage

Format FAQ : chaque entrée est **problème → cause → correctif**. Pour la référence complète sur la sémantique des erreurs (codes de statut, états terminaux, discipline de nouvelle tentative), voir
[Réponses et erreurs](../reference/api/api-responses-errors.md) et
[Limitation de débit et erreurs](../architecture/rate-limiting-errors.md).

<a id="bare-requests-to-the-api-get-a-cloudflare-403" data-pplx-source-anchor="true"></a>
## Requêtes brutes vers l'API obtiennent un Cloudflare 403

**Problème** : un `curl` / script fait maison contre les points de terminaison REST `www.perplexity.ai`
renvoie 403 avec une page de défi Cloudflare — même avec les cookies copiés depuis le
navigateur — alors que les mêmes points de terminaison fonctionnent via l'outil.

**Cause** : Cloudflare se trouve devant le site, et `cf_clearance` / `__cf_bm` sont
liés à l'empreinte TLS du navigateur. L'empreinte d'un client brut ne correspond pas, donc
le défi se déclenche. L'outil réussit car il utilise Python `urllib` avec des cookies
importés du navigateur et un `User-Agent` de Chrome de bureau
(`pplx_export/core/http/cookie_transport.py:29`). Cloudflare peut aussi renvoyer 403 sous contrôle de débit —
dans ce cas, la réponse porte la même forme de défi.

**Correctif** :

- Ne contournez pas le transport de l'outil ; exécutez votre appel via `pplx-export` / `pplx-ask`
  au lieu de scripts ad-hoc.
- Dans l'outil, une réponse 200 avec un corps non JSON (l'interstitiel Cloudflare) est
  classée comme une erreur de transport, pas des données (`pplx_export/core/http/cookie_transport.py:133`).
- Si des 403 commencent à apparaître dans l'outil, ralentissez (voir
  [Limitation de débit](rate-limiting.md)) et rafraîchissez les cookies ; un défi
  persistant signifie une reconnexion dans le navigateur.
- Attention aux deux visages du 403 : un défi de contrôle de risque Cloudflare (disparaît une fois que vous
  ralentissez) versus un 403 au niveau API (cookie mort — levé immédiatement sans backoff ; voir
  la section suivante). La page de conception cartographie ce dernier
  ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

Contexte : [Authentification API](../reference/api/api-authentication.md).

<a id="401-errors-expired-cookies" data-pplx-source-anchor="true"></a>
## Erreurs 401 / cookies expirés

**Problème** : les commandes échouent avec une erreur d'authentification — `AuthTransportError: 鉴权失败 401`
de `pplx-export`, ou `pplx-ask ask` se terminant avec un code HTTP 401/403 indiquant de mettre à jour le
cookie.

**Cause** : le cookie de session a expiré ou a été invalidé. `401`/`403` sont traités
comme des échecs d'authentification et levés immédiatement — sans backoff, car le backoff ne peut pas
autoréparer une session morte (`pplx_export/core/http/cookie_transport.py:82` ;
`pplx_export/core/errors.py:68`). `batch` échoue en outre rapidement après 3 échecs d'authentification
consécutifs afin qu'un cookie mort ne brûle pas toute la file d'attente.

**Correctif** :

1. Reconnectez-vous (ou rouvrez le site) dans le navigateur pour que les cookies de session soient renouvelés.
2. Rafraîchissez le cache de cookies de l'outil. Le cache à `<out>/index/.cookies.json` est réutilisé
   dans une fenêtre de fraîcheur de 12 heures (`pplx_export/core/cookies/cache.py:22`), donc après
   reconnexion, soit :
   - exécutez une fois avec `--cookies-from <browser>` pour forcer une nouvelle importation depuis le navigateur, ou
   - supprimez `<out>/index/.cookies.json` et laissez la prochaine exécution réimporter automatiquement.
3. Chaque exécution qui réussit la validation réenregistre le cache
   (`pplx_export/commands/common.py:150`), donc les exécutions quotidiennes restent fraîches d'elles-mêmes.

Détails de configuration : [Pour commencer](getting-started.md) · [Configuration](configuration.md).

<a id="linux-cookie-decryption" data-pplx-source-anchor="true"></a>
## Déchiffrement des cookies sous Linux

**Problème** : sous Linux, la détection automatique (ou `--cookies-from chrome` & co.) ne peut pas lire le
magasin de cookies du navigateur même si le navigateur est connecté.

**Mécanisme** : les navigateurs de la famille Chromium sous Linux chiffrent la base de données de cookies avec une
clé stockée dans le trousseau de l'OS, lue à l'exécution via l'API Secret Service D-Bus.
`browser_cookie3` dialogue avec D-Bus via le Python pur `jeepney` — déjà installé avec l'outil
sous Linux, rien de plus à configurer — et se rabat sur le mot de passe `peanuts` hérité
lorsqu'aucun trousseau ne répond, ce qui ne déchiffre que les cookies que Chrome a également écrits
sans trousseau. Lorsque le trousseau existe mais que la recherche D-Bus elle-même échoue au niveau du
transport (par exemple, un bus de session rejetant l'authentification anonyme), la propre
chaîne de repli de `browser_cookie3` ne s'engage jamais ; l'outil détecte ce cas et réessaie une fois avec
le trousseau contourné, en utilisant le mot de passe par défaut de Chromium — la même clé que Chromium
utilise lui-même lorsqu'aucun trousseau n'est disponible (`pplx_export/core/cookies/loaders.py:62-104`,
câblé dans le chemin de chargement à `loaders.py:136-153`). Firefox n'a besoin de rien de tout cela : son
`cookies.sqlite` n'est pas chiffré.

**La matrice** :

| Couche | Cas | Ce qui se passe |
|---|---|---|
| Navigateur | Firefox | Zéro friction — `cookies.sqlite` n'est pas chiffré |
| Navigateur | Chromium + trousseau accessible | Fonctionne — la clé est récupérée via Secret Service |
| Navigateur | Chromium + pas de trousseau | Chemin `peanuts` — fonctionne uniquement si Chrome a également écrit sans trousseau |
| Navigateur | Chromium + trousseau inaccessible (échec au niveau D-Bus) | L'outil réessaie automatiquement avec le mot de passe par défaut de Chromium — même portée que le chemin `peanuts` |
| Méthode d'installation | Paquet natif | Détection automatique (chemins intégrés de browser_cookie3) |
| Méthode d'installation | snap / flatpak | Détection automatique — le registre de profils intégré couvre les profils sous `~/snap/<name>/...` resp. `~/.var/app/<app-id>/...` (`pplx_export/core/cookies/profiles.py:37-67`) |
| Environnement de bureau | GNOME | Fonctionne généralement directement (gnome-keyring) |
| Environnement de bureau | KDE | Activez **Utiliser KWallet pour l'interface Secret Service** dans les paramètres KWallet |
| Environnement de bureau | Sans tête / minimal | Pas de bus de session D-Bus → chemin `peanuts` |
| Famille de distribution | Debian / Ubuntu | Installez `libsecret-1-0` + `gnome-keyring` |
| Famille de distribution | Fedora / RHEL | Installez `libsecret` + `gnome-keyring` ; les installations minimales / serveur manquent souvent complètement de trousseau — l'échec le plus courant |
| Famille de distribution | Arch | Même mécanisme, seuls les noms de paquets diffèrent |

Les installations en bac à sable n'ont besoin d'aucun indicateur supplémentaire : le chemin natif est sondé en premier, puis les
bases de données de cookies snap/flatpak du registre via un `cookie_file=` explicite
(`pplx_export/core/cookies/loaders.py:155-168`).

**Scénario → canal recommandé** :

| Scénario | Canal recommandé |
|---|---|
| Firefox installé | `--cookies-from firefox` — zéro friction |
| Bureau GNOME / KDE | La détection automatique fonctionne directement |
| Navigateur snap / flatpak | Détection automatique — le registre le couvre ; sinon `--cookies FILE` exporté via une extension de navigateur |
| Serveur sans tête | `--cookies FILE` — le repli universel ; `--transport webbridge` en dernier recours |

<a id="an-export-ran-under-the-wrong-account-multi-account" data-pplx-source-anchor="true"></a>
## Une exportation a été exécutée sous le mauvais compte (multi-compte)

**Problème** : les fils archivés ont été récupérés avec la session du mauvais compte — par exemple, une
exécution `--account alice` a extrait des données en tant que `bob`, ou l'archive montre des fils qui n'appartiennent
pas au compte prévu.

**Cause** : avec plusieurs comptes connectés au même navigateur, le jeton de session actif
(`__Secure-next-auth.session-token`) peut appartenir à un compte différent de celui que vous
avez ciblé. Si le `email` du compte cible n'est pas enregistré dans la configuration au niveau utilisateur,
l'outil ne peut pas le détecter et enregistre seulement un avertissement.

**Comment l'outil le prévient** (`pplx_export/commands/common.py:93`) : au démarrage, le
transport appelle `GET /api/auth/session` et compare l'email actif avec celui enregistré.
En cas de non-correspondance, il énumère automatiquement les cookies de session par compte du navigateur
(`__Secure-pplx.session.<user_id>`), substitue chacun dans le jeton actif, et sonde
la session jusqu'à ce que l'email cible corresponde (`pplx_export/commands/common.py:190` ;
`pplx_export/core/cookies/loaders.py:175`). Si aucun jeton ne correspond, la commande s'arrête avec une erreur
claire — elle ne continue jamais silencieusement avec le mauvais compte.

**Correctif** :

- Enregistrez le `email` de chaque compte sous `[accounts.<name>]` (voir
  [Configuration](configuration.md)) et passez `--account` explicitement.
- Vérifiez la ligne de journal de démarrage `[auth] cookie 来源 …，当前账户: …` — elle nomme l'email de session
  actif avant que quoi que ce soit ne soit récupéré.
- Pour auditer une archive existante, le `thread.json` de chaque fil porte un champ `export_via`
  enregistrant quel compte a effectué l'exportation
  (`pplx_export/sites/perplexity/fs_writer.py:229`). `pplx-export sync-deleted` utilise le
  même champ pour choisir le compte pour la vérification en ligne.

Profondeur du mécanisme : [Authentification API](../reference/api/api-authentication.md) ·
[Ask et comptes](../architecture/ask-and-accounts.md).

<a id="config-file-not-found-degraded-mode" data-pplx-source-anchor="true"></a>
## "Fichier de configuration introuvable" — mode dégradé

**Problème** : un avertissement au démarrage indique qu'aucun fichier de configuration au niveau utilisateur n'a été trouvé et la commande
s'exécute en mode dégradé ; ou un `--account alice` explicite échoue avec une erreur pointant vers
`config.example.toml`.

**Cause** : aucun fichier de configuration à aucun des trois emplacements de recherche — `--config PATH`, la
variable d'environnement `PPLX_EXPORT_CONFIG`, ou le chemin par défaut
`~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). Deux cas liés mais
distincts : un **chemin de configuration explicitement spécifié** qui n'existe pas lève
`ConfigError` ; une configuration corrompue (non analysable) lève toujours `ConfigError` — une configuration
cassée ne se dégrade jamais silencieusement.

**Effets du mode dégradé** :

- Le registre des comptes est vide, donc la vérification de propriété des cookies est ignorée avec un
  avertissement et les commandes s'exécutent avec le compte fictif `default`
  (`pplx_export/commands/common.py:51`). Un `--account` explicite génère une erreur à la place.
- `pplx-ask ask` ignore le déplacement automatique dans l'espace BOT (`moved_to_bot` reste `false`
  dans le JSON de résultat) et la télémétrie porte un identifiant utilisateur vide ; demander et archiver
  fonctionnent sinon.
- Les archives atterrissent dans le dossier de compte de repli dérivé du nom d'utilisateur.

**Correctif** : copiez `config.example.toml` vers `~/.config/pplx-export/config.toml`, remplissez
`[accounts.<name>]` (`display_name` / `email` / `user_id`), `[bot_space]`, et
`default_account` — voir [Configuration](configuration.md).

## ENTRY_EXPIRED vs ENTRY_DELETED

**Problème** : l'exportation ou la resynchronisation d'un fil signale `ENTRY_EXPIRED` ou
`ENTRY_DELETED`, et le fil ne peut plus jamais être récupéré.

**Cause** : les deux arrivent sous forme de HTTP 400 depuis `GET /rest/thread/<uuid>` avec des codes
d'erreur différents, et les deux sont terminaux — le fil n'existe plus sur la plateforme :

| Code | Signification | Mappage dans l'outil | État terminal |
|---|---|---|---|
| `ENTRY_EXPIRED` | La plateforme a purgé le fil (~3 mois de rétention) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | Le fil a été activement supprimé par l'utilisateur / le côté distant (l'effet en aval de `DELETE /rest/thread/delete_thread_by_entry_uuid`) | `EntryDeletedError`, une sous-classe de `EntryExpiredError` (`pplx_export/core/errors.py:30`) | `deleted` |

**Ce que cela signifie pour votre archive** :

- Aucun des deux états n'est jamais réessayé — ni par synchronisation incrémentielle, ni avec `--force`. La
  marque terminale vit dans `<out>/index/batch_state.json`.
- Votre **archive locale n'est jamais supprimée ni déplacée** par l'outil — la copie du dépôt est
  la sauvegarde. La commande d'exportation enregistre l'état terminal et se termine gracieusement
  (`pplx_export/commands/export_cmd.py:51`).
- Parce que la relation de sous-classe est délibérée, les chemins de code qui ne connaissent que
  `EntryExpiredError` traitent toujours `ENTRY_DELETED` comme terminal ; les chemins conscients (batch /
  export / sync-deleted / search-mode-backfill) le classifient précisément comme `deleted`.
- Conclusion pratique : exportez en temps utile. Passé la purge d'environ 3 mois, les liens sources des artefacts/rapports
  expirent également de manière irrécupérable.

Connexe : [Synchronisation incrémentielle](incremental-sync.md) ·
[Réponses et erreurs](../reference/api/api-responses-errors.md).

<a id="assets-that-cannot-be-downloaded-toolu_-handles" data-pplx-source-anchor="true"></a>
## Ressources qui ne peuvent pas être téléchargées (gestionnaires `toolu_`)

**Problème** : certaines entrées dans `assets/assets_manifest.json` ont des versions marquées
`"no_download_channel": true`, et aucun fichier correspondant n'existe sous
`assets/files/`.

**Cause** : les gestionnaires d'espace de travail cloud préfixés par `toolu_` (DOC_FILE / CODE_FILE / UNKNOWN sans
forme d'URL) n'ont pas de canal de téléchargement API : `GET /rest/assets/<asset_uuid>/data` renvoie
404 `ASSET_NOT_FOUND` pour eux, et `file-repository/download` rejette les gestionnaires `file:repo/...`
(400). Il s'agit d'une **limite connue de complétude de l'archive**, pas d'un bogue dans l'exportation.
`pplx-export assets-backfill` marque ces versions `no_download_channel` et
les ignore (`pplx_export/commands/assets_backfill_cmd.py:356`).

**Correctif** :

- Rien à télécharger aujourd'hui — le drapeau est l'enregistrement délibéré de la limite.
- Le contenu survit souvent en ligne : le texte d'extraction de page du sous-agent et les charges utiles des étapes
  sont conservés dans le JSON brut du fil (`raw_entries.json` / `raw_blocks.json`) et
  dans le `turns/` rendu — vérifiez d'abord là.
- `file-repository/list-files` est suivi comme un chemin de sauvetage potentiel futur ; voir
  [Feuille de route de découverte API](../reference/api/api-discovery-roadmap.md).

Disposition du manifeste : [Disposition de l'archive](archive-layout.md).

<a id="command-seems-hung-long-silences" data-pplx-source-anchor="true"></a>
## La commande semble bloquée / longs silences

**Symptôme** : `index` / `batch` / `export` n'affiche rien pendant plusieurs minutes ;
un gestionnaire de tâches externe peut le tuer comme "délai dépassé".

**Cause** : presque toujours une attente de backoff, pas un blocage. Sur les erreurs 429 / 5xx / réseau,
le transport dort entre les tentatives — jusqu'à 300 s par attente
(`pplx_export/core/throttle.py:38-50`). Au niveau DEBUG, l'attente est explicite :

```
19:39:31 GET www.perplexity.ai/rest/thread/<uuid> 网络错误: Remote end closed connection without response
19:39:31 退避 200.9s（连续失败 2 次）
```

**Comment le savoir** : exécutez avec `-v` (ou `--log-file`) et cherchez les lignes de backoff
; tant que le processus est vivant, aucune intervention n'est nécessaire.
L'interruption est sûre à tout moment — l'état est écrit de manière atomique et la prochaine
exécution répare l'écart.

**Anti-patron** : envelopper la CLI dans un gestionnaire de tâches avec un délai d'attente dur
court (tâches d'arrière-plan d'agent, wrappers cron de style `timeout(1)`) *tout en*
chaînant des comptes avec `&&` — la cascade de backoff du premier compte brûle tout le
délai d'attente et le compte chaîné ne s'exécute jamais. Un compte par
invocation, budget généreux : voir
[Budget d'exécution pour les appelants](rate-limiting.md#runtime-budget-for-callers).

<a id="where-are-the-logs" data-pplx-source-anchor="true"></a>
## Où sont les journaux ?

**Console** : progression de niveau INFO par défaut ; `-v` / `--verbose` passe en DEBUG
(traçage des requêtes, décisions internes) ; les avertissements et erreurs sont toujours affichés.

**Fichier** : passez `--log-file` pour capturer le flux DEBUG complet
(`pplx_export/core/logging.py:45`) :

- `--log-file` sans valeur atterrit à `<out>/index/logs/<cmd>-<timestamp>.log`
  (`pplx_export/commands/common.py:218`) — par exemple `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH` écrit dans le chemin donné.

**Autres fichiers d'état utiles pour le diagnostic** (sous `<out>/index/`) :

| Fichier | Contenu |
|---|---|
| `.cookies.json` | Cache de cookies (fraîcheur de 12 h ; écrit de manière atomique avec 0o600 — c'est un identifiant équivalent à une connexion, gardez-le privé) |
| `batch_state.json` | État d'exportation par fil, incluant les marques terminales `expired` / `deleted` |
| `answer_variants_log.jsonl` | Registre de variantes de réécriture de réponses |
| `library_*.json` | Instantanés d'index de bibliothèque par compte |

<a id="see-also" data-pplx-source-anchor="true"></a>
## Voir aussi

- [Pour commencer](getting-started.md) — configuration initiale et importation de cookies
- [Configuration](configuration.md) — comptes, espace BOT, mode dégradé
- [pplx-ask](pplx-ask.md) — la CLI de requête interactive
- [pplx-export](pplx-export.md) — la CLI d'archivage
- [Limitation de débit](rate-limiting.md) — cadence et discipline de backoff
