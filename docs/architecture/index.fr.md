---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/index.md"
translation_source_sha256: "a64006f8b94ad04a3bc498468e674f3b8a22f27242c9bb7b8c5a9252019cc751"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="architecture-reading-map" data-pplx-source-anchor="true"></a>
# Carte de lecture de l'architecture

Référence au niveau mécanisme pour les outils pplx (`pplx-export` / `pplx-ask`) :
dépendances, pipelines, machines d'état, contrats de données et limites
de fiabilité. Pour une utilisation orientée tâches, commencez par le [Guide utilisateur](../guide/index.md).

!!! note "Périmètre et source de vérité"

    Ces pages expliquent l'architecture de `pplx_export/` pour les agents et
    les ingénieurs qui maintiennent le projet. Les références de lignes utilisent `file.py:NN`,
    relatives à `pplx_export/`. Les descriptions ont été vérifiées par rapport au
    dépôt le 2026-07-23 (`__version__ = "0.1.0"`,
    `pplx_export/__init__.py:31`) ; le code et les tests actuels restent faisant autorité.

<a id="start-with-the-system-map" data-pplx-source-anchor="true"></a>
## Commencez par la carte système

- [Vue d'ensemble de l'architecture](overview.md) — couches, responsabilités des modules et
  le graphe de dépendances au niveau des importations.

<a id="follow-a-runtime-flow" data-pplx-source-anchor="true"></a>
## Suivez un flux d'exécution

- [Pipeline d'exportation](export-pipeline.md) — récupération, conservation de la réponse brute,
  détection de mode et rendu Markdown.
- [Sous-agents et interruptions](subagents-interruptions.md) — attribution de
  charge utile et sémantique d'interruption/reprise.
- [pplx-ask et comptes](ask-and-accounts.md) — requêtes en streaming et
  changement de cookie multi-compte.

<a id="understand-data-and-reliability" data-pplx-source-anchor="true"></a>
## Comprenez les données et la fiabilité

- [Modèle de données et contrat de répertoire](data-model.md) — modèles, limites
  d'écriture et contrat d'archive sur disque.
- [Limitation de débit et gestion des erreurs](rate-limiting-errors.md) — limitation,
  backoff, états terminaux et routage des erreurs.
- [Opérations hors ligne](offline-operations.md) — re-rendu sans réseau,
  reconstruction des relations et pipelines de maintenance locaux.

<a id="related-references" data-pplx-source-anchor="true"></a>
## Références connexes

- [Référence de l'API Web](../reference/api/index.md) — contrats REST/GraphQL observés,
  sémantique des réponses et notes de découverte.
- [Guide du mainteneur](../development/index.md) — architecture de test, flux de travail
  du contributeur et contrats de fixtures simulés.
