---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/index.md"
translation_source_sha256: "7a016c35bbb11272395a246fd23c0c27be794585c5b1cda9fdc9c6181fe32e48"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# Perplexity CLI toolkit

<p class="homepage-scope-note" role="note">
  <strong>PAS pour l'API pay-as-you-go</strong>
</p>

Perplexity archive de conversations & toolkit de requêtes interactives (`pplx-export` / `pplx-ask`).

Il communique directement avec l'API REST/GraphQL de Perplexity en utilisant les cookies de connexion de votre navigateur, et archive les conversations — étapes, citations, rapports de recherche approfondie, ressources du mode Computer et workflows de sous-agents — sous forme de Markdown + JSON local. Les exportations réussies conservent les réponses brutes de l'API aux côtés des artefacts rendus, de sorte que le rendu puisse être relancé hors ligne à tout moment.

## Introduction

Au-delà de l'archivage des conversations historiques, ce projet vise principalement à donner aux agents locaux — plus proches des données et souvent soutenus par plus de calcul — une mesure des capacités de Perplexity Computer. En leur permettant d'accéder aux rapports produits par Perplexity Deep Research directement dans leur boucle de travail, ils peuvent utiliser des informations de haute qualité pour ajuster plus précisément les paramètres clés du code tout en utilisant plus pleinement un abonnement Perplexity Max existant.

> Au 20 juillet, Perplexity ne proposait pas de CLI officielle pour les environnements de type Unix. Le 23 juillet, Perplexity a publié publiquement l'outil `pplx` utilisé en mode Computer, mais cet outil utilise toujours une facturation à l'utilisation.

Ce n'est pas un remplacement complet du mode Computer. Deux capacités restent hors de portée :

- la liberté de la compétence Deep Research de choisir un modèle arbitraire ;
- la capacité de la compétence Council à effectuer des recherches approfondies avec plusieurs modèles spécifiés par l'utilisateur, à produire des rapports et à les comparer côte à côte.

Le répertoire [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context) comprend des invites système archivées et des règles de fonctionnement qui peuvent aider à approximer localement certaines parties du workflow Computer, y compris la sélection du mode Deep Research et la sélection du modèle de sous-agent.

<a id="features" data-pplx-source-anchor="true"></a>
## Fonctionnalités

<a id="pplx-export-archive-your-library" data-pplx-source-anchor="true"></a>
### `pplx-export` — archivez votre bibliothèque

- Index de la bibliothèque et index des espaces
- Exportation mono-thread / par lots avec arrêt précoce incrémental + points de contrôle reproductibles
- Remplissage des ressources et remplissage de l'utilisation du crédit
- Graphe des relations de conversation
- Rendu hors ligne (`re-render`, zéro réseau)
- Extrait cron incrémental périodique

<a id="pplx-ask-query-perplexity-from-the-shell" data-pplx-source-anchor="true"></a>
### `pplx-ask` — interrogez Perplexity depuis le shell

- Requêtes SSE en streaming dans quatre modes : search / deep-research / council / study
- Déplacement automatique dans un espace BOT à la fin, accusés de réception
- Archivage automatique de chaque fil qu'il crée — conçu pour que d'autres agents puissent l'appeler afin d'obtenir des informations en temps réel

Limites des artefacts par mode (citations / rapports / ressources / sous-agents) : voir [Modes](guide/modes.md) ; principes de fidélité du rendu : voir [Pipeline d'exportation](architecture/export-pipeline.md).

!!! note "Provenance de la documentation"

    La plupart des pages de ce site MkDocs ont été générées ou reconstruites à partir du code et des tests actuels. Certaines pages conservent également le contexte de conception, les observations et les décisions issues de discussions antérieures avec des agents. Lorsqu'une déclaration de documentation et l'implémentation diffèrent, considérez le code et les tests actuels comme la source de vérité.

<a id="where-to-next" data-pplx-source-anchor="true"></a>
## Par où continuer

- **Utilisez les outils** — suivez le [Guide utilisateur](guide/index.md) orienté tâches.
- **Comprenez l'implémentation** — utilisez la [Carte de lecture de l'architecture](architecture/index.md).
- **Travaillez avec l'interface web observée** — consultez la [Référence de l'API Web](reference/api/index.md).
- **Modifiez le projet en toute sécurité** — suivez le [Guide du mainteneur](development/index.md).
