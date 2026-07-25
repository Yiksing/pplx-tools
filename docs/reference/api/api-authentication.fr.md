---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-authentication.md"
translation_source_sha256: "dc9067f0d08c997245ee548a335fc762ad0cbe986661ba0ad7f976150131dd72"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="authentication-model" data-pplx-source-anchor="true"></a>
# Modèle d'authentification

> Cette page présente la zone de référence de l'API — l'enregistrement éprouvé sur le terrain du projet pplx_export de l'API web privée de Perplexity.
> Public : mainteneurs et utilisateurs de ce projet. Tous les points de terminaison ont été vérifiés via capture réseau WebBridge + requêtes directes authentifiées par cookie (2026-07).
> **Toute modification ou ajout à la connaissance de l'API doit être synchronisé dans ces pages** (exigence explicite de l'utilisateur).
> Dernière mise à jour : 2026-07-23
>
> La zone de référence est divisée en : **1. Modèle d'authentification** (cette page) · [2. GraphQL (requêtes persistées / APQ)](api-graphql.md) · [3. Points de terminaison REST (groupés par objectif)](api-rest-endpoints.md) · [4–5. Structure des réponses et sémantique des erreurs](api-responses-errors.md) · [6–8. Éléments à déterminer, découverte des points de terminaison et feuille de route](api-discovery-roadmap.md) — pour la conception système environnante, voir la [carte de lecture de l'architecture](../../architecture/index.md).

---

<a id="authentication-model_1" data-pplx-source-anchor="true"></a>
## Modèle d'authentification

<a id="cookie-session" data-pplx-source-anchor="true"></a>
### Session cookie
- Toutes les requêtes API nécessitent uniquement le cookie de session du navigateur (aucun jeton CSRF requis ; les requêtes GET et POST ont été vérifiées fonctionnelles via des requêtes directes).
- Cookie clé : `__Secure-next-auth.session-token` (jeton de session du **compte actuellement actif**).
- Cloudflare se trouve devant : `cf_clearance`/`__cf_bm` sont liés à l'empreinte TLS du navigateur — **les requêtes curl nues reçoivent un 403** ;
  l'outil passe avec Python urllib + cookies importés du navigateur (UA déguisé en Chrome de bureau).

<a id="multi-account-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Multi-comptes (découvert le 2026-07-20)
- Lorsque plusieurs comptes sont connectés dans le même navigateur, chaque compte possède son propre cookie `__Secure-pplx.session.<user_id>`
  (domaine www.perplexity.ai ; la valeur évolue avec les réponses).
- La valeur de `__Secure-next-auth.session-token` = la valeur du cookie par compte du compte actif.
- **Changer de compte sur le web** = naviguer vers `https://www.perplexity.ai/?pplx_account=<user_id>` ; le serveur réécrit le jeton actif.
- **Changement automatique côté outil** (implémenté dans pplx_export) : énumérer les cookies `__Secure-pplx.session.*` du navigateur,
  remplacer `__Secure-next-auth.session-token` par chacun à tour de rôle, et sonder `/api/auth/session` jusqu'à ce que l'email cible corresponde.
- `GET /api/auth/linked-accounts` retourne `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`,
  mais **retourne la liste complète des comptes uniquement lorsque le compte principal est actif** (seulement le compte actuel lorsqu'un compte non principal est actif) — donc l'outil ne s'y fie pas.
- Exemples de comptes enregistrés (la table réelle des comptes réside dans `config.toml` au niveau utilisateur ; des espaces réservés sont montrés ici) :
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa` (Max) ;
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb` (Pro, principal).
