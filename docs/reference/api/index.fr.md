---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/index.md"
translation_source_sha256: "ca4f72f6b2dd481ccfbaebc2b4a1c807271077753873ce318b60d94c60f54228"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-reference" data-pplx-source-anchor="true"></a>
# Référence de l'API Web

Comportement REST et GraphQL observé utilisé par Perplexity et
`pplx-export` et `pplx-ask`.

!!! warning "Interface observée, pas une garantie de stabilité"

    Ces pages décrivent le comportement que le projet a observé à partir de l'application
    web, des réponses archivées, des bundles frontend et de l'implémentation
    actuelle. Elles ne constituent pas un contrat officiel de l'API Perplexity. Les observations
    datées doivent être revalidées avant de modifier le code réseau.

<a id="reading-order" data-pplx-source-anchor="true"></a>
## Ordre de lecture

1. [Modèle d'authentification](api-authentication.md) — cookies de session, jetons,
   comptes liés et identité.
2. [GraphQL](api-graphql.md) — requêtes persistées, identifiants APQ et
   opérations utilisées.
3. [Points de terminaison REST](api-rest-endpoints.md) — points de terminaison observés regroupés par
   objectif.
4. [Réponses et sémantique des erreurs](api-responses-errors.md) — formes des réponses,
   règles d'analyse, états terminaux et comportement de contrôle des risques.
5. [Méthodes de découverte et feuille de route](api-discovery-roadmap.md) — comment les points de terminaison
   sont trouvés et quelles incertitudes subsistent.

<a id="related-implementation-documents" data-pplx-source-anchor="true"></a>
## Documents d'implémentation connexes

- [pplx-ask et comptes](../../architecture/ask-and-accounts.md)
- [Limitation de débit et gestion des erreurs](../../architecture/rate-limiting-errors.md)
- [Dépannage](../../guide/troubleshooting.md)
