---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing-architecture.md"
translation_source_sha256: "ca93c1e43ccc41337097685ec6268f2d1f6a9997504b4a67683bce250b443b66"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing-architecture" data-pplx-source-anchor="true"></a>
# Architecture de test

Le système de test `pplx_export` est entièrement hors ligne, utilise des données simulées archivées et verrouille le comportement du moteur de rendu par instantanés. Cette page décrit l'architecture et les garanties ; la liste actuelle des modules se trouve dans [Testing](../development/testing.md), et les détails des fixtures dans [Test fixtures](../development/fixtures.md).

La section conserve sa numérotation issue de la [vue d'ensemble de l'architecture](../architecture/overview.md).

---

<a id="test-system" data-pplx-source-anchor="true"></a>
## Système de test

Exécutez la suite avec `uv run pytest tests`. Les comptes de tests sont rapportés à partir de l'exécution en cours et ne sont pas traités comme une constante architecturale.

<a id="layers" data-pplx-source-anchor="true"></a>
### Couches

| Couche | Modules représentatifs | Contrat |
|---|---|---|
| Comportement unitaire pur | `test_units.py`, tests de credentials/cookies/config | isoler les fonctions, classes, validation et normalisation avec des entrées simulées |
| Sémantique des composants | tests d'interruption, de workflow factice, de variante de réponse et de relations | exercer la coopération entre le code d'analyse, de rendu, d'état et d'index sans accès réseau |
| Comportement hors ligne des commandes/états | tests de backfill, synchronisation de suppression, initialisation et régressions de revue | exécuter les chemins de commande avec des répertoires temporaires et des transports simulés |
| Instantanés de rendu | `test_render_snapshots.py` | passer du JSON simulé au format API via le chemin de re-rendu de production et comparer tous les octets Markdown avec des golden commits |

Les identifiants de revue tels que N, V3, V4 et V5 sont des métadonnées de traçabilité à travers ces couches. Ils ne définissent pas une architecture d'exécution distincte, et leur relation avec les modules de test n'est pas nécessairement biunivoque.

<a id="snapshot-data-flow" data-pplx-source-anchor="true"></a>
### Flux de données des instantanés

1. Une fixture simulée fournit `raw_entries.json`, `raw_blocks.json` optionnel, et `thread.json`.
2. `tests/conftest.py::render_fixture` copie ces fichiers dans `tmp_path`.
3. La fixture appelle `commands.rerender_cmd.rerender`, le chemin de reconstruction hors ligne de production.
4. Les nouveaux fichiers `conversation.md` et `turns/turn_*.md` sont comparés octet par octet avec les produits `golden/` commités.

Les golden sont des attentes générées, pas une source de données indépendante. Tout changement du moteur de rendu qui modifie les octets des artefacts rend la suite d'instantanés rouge jusqu'à ce que le changement soit revu et que les golden soient intentionnellement régénérés.

<a id="isolation-and-trust-boundaries" data-pplx-source-anchor="true"></a>
### Frontières d'isolation et de confiance

- **Origine des fixtures** — toutes les entrées de fixtures commitées sont des données simulées. Elles ne sont pas copiées à partir de comptes réels, de réponses API réelles, de `web_archive/` ou d'archives privées.
- **Frontière réseau** — les tests utilisent des fausses et des chemins hors ligne ; les fixtures commitées ne nécessitent ni identifiants ni accès réseau.
- **Frontière de configuration** — la fixture autouse installe une configuration de compte factice, de sorte que le `~/.config` réel d'un développeur ne détermine pas les résultats.
- **Frontière du système de fichiers** — le comportement des commandes et des migrations s'exécute sous `tmp_path` ; les archives utilisateur ne sont pas des cibles de test.
- **Frontière des résidus** — `tests/scrub_fixtures.py --check` rejette les chaînes configurées spécifiques à l'environnement, les chemins absolus locaux et les identifiants d'URL signée sans modifier les fichiers.

Ensemble, les assertions unitaires, la sémantique des composants, les tests d'état de commande et les instantanés au niveau des octets protègent à la fois la logique locale et le contrat de re-rendu de bout en bout.
