---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing.md"
translation_source_sha256: "a552c25a28367f384140a2e5cc2e9fa2a8546034b668772f5df79133d4995648"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing" data-pplx-source-anchor="true"></a>
# Tests

La suite de tests se trouve dans `tests/`, en dehors du paquet `pplx_export`, et s'exécute
entièrement hors ligne. Ses entrées en forme d'API sont des données simulées déterministes validées
sous `tests/fixtures/` ; les tests ne dépendent pas de services en direct ni d'une configuration
réelle au niveau utilisateur.

Cette page contient l'inventaire actuel des modules de test et le flux de travail du contributeur.
Pour la conception des régressions, voir
[Architecture du système de test](testing-architecture.md). Pour le contrat
des données d'entrée, voir [Accessoires de test](fixtures.md).

<a id="running-the-tests" data-pplx-source-anchor="true"></a>
## Exécution des tests

```bash
uv run pytest tests
```

pytest est une dépendance de développement déclarée. La suite garantit :

- **Zéro réseau** — les entrées simulées sont validées ; les chemins réseau sont
  couverts par des simulations, `tmp_path` et `monkeypatch`.
- **Aucune configuration utilisateur réelle** — avant d'importer un module de production,
  `tests/conftest.py` crée une configuration temporaire locale au processus et
  remplace `PPLX_EXPORT_CONFIG`. Chaque test reçoit ensuite sa propre configuration
  `alice` / `bob` et restaure celle locale au processus
  après. Les régressions de sous-processus vérifient qu'une configuration d'appelant manquante ou
  cassée ne peut pas casser la collecte des tests.
- **Retour rapide** — le 2026-07-25, le projet observait 435 tests collectés
  à partir de 32 modules `test_*.py` et exécutait la suite complète en environ 13 à 25 secondes
  lors des exécutions de vérification locales.
  Les comptages sont un instantané daté du dépôt et augmenteront.

Sélections utiles :

| Commande | Effet |
|---|---|
| `uv run pytest tests` | suite complète |
| `uv run pytest tests/test_units.py` | un module |
| `uv run pytest tests -k snapshot` | tests dont l'identifiant de nœud correspond à `snapshot` |
| `uv run pytest tests -x -q` | s'arrêter à la première erreur, sortie silencieuse |
| `uv run pytest --collect-only -q` | rafraîchir le nombre de cas collectés |

<a id="current-module-inventory" data-pplx-source-anchor="true"></a>
## Inventaire actuel des modules

Inventaire synchronisé avec le dépôt le **2026-07-27** :

<!-- audit:inventory test-modules -->

| Famille fonctionnelle | Modules | Objectif |
|---|---|---|
| Instantanés de rendu | `test_render_snapshots.py` | re-rendre tous les accessoires simulés en mode complet et scénario réduit, puis comparer les produits validés octet par octet |
| Utilitaires centraux et partagés | `test_units.py` | état, limitation, planification, normalisation, nommage des actifs, détection de mode, chemins sécurisés et régressions transversales |
| Contrats de documentation, compétences et localisation | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | contrats de compétences locaux au dépôt plus tests de mini-dépôts isolés pour l'auditeur de documentation en lecture seule et le pipeline de traduction automatique |
| Configuration, authentification et amorçage | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | isolation de la configuration externe, profils de source de cookies, sélection d'identifiants et initialisation |
| Sémantique de rendu et de flux de travail | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | attribution de flux de travail, états d'interruption, variantes de réponse, journalisation d'audit et arêtes de relation |
| Maintenance d'archive hors ligne et d'index | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | enrichissement, comportement de reprise/idempotence, détection de suppression inter-comptes, états terminaux et niveaux de rapport de compte/état hors ligne |
| Régressions de revue | 16 modules `test_fix_*.py` listés ci-dessous | correctifs issus des résultats de revue ; les noms de modules conservent la lignée de revue |

<a id="review-regression-lineage" data-pplx-source-anchor="true"></a>
### Lignée des régressions de revue

Les identifiants de revue expliquent pourquoi une régression existe ; ils ne constituent pas
l'architecture principale de la suite de tests. Le mappage est délibérément plusieurs-à-plusieurs : un
module peut couvrir plusieurs résultats, et un résultat peut également ajouter des cas à un
module thématique existant.

| Lignée | Modules dédiés |
|---|---|
| Revue N | `test_fix_n01_inline_assets.py`, `test_fix_n02_spaces_link.py`, `test_fix_n03_n12.py`, `test_fix_n04_cookies.py`, `test_fix_n05_n06_n09.py`, `test_fix_n07_usage_checkpoint.py`, `test_fix_n08_throttle_overflow.py`, `test_fix_n10_table_header.py`, `test_fix_n11_batch_total.py` |
| Revue V3 | `test_fix_v301_nested_sources_text.py`, `test_fix_v305_export_products.py` |
| Revue V4 | `test_fix_v401_thread_dir_migration.py`, `test_fix_v402_manifest_count.py`, `test_fix_v403_handle_assets_idempotency.py`, `test_fix_v405_ask_post_steps.py` |
| Revue V5 | `test_fix_v5_review.py`, plus des ajouts ciblés aux modules thématiques existants |
| Revue V6 | `test_fix_v6_atomic_writes.py` |

<!-- /audit:inventory test-modules -->

Les docstrings des modules restent l'explication faisant autorité de l'ancien comportement de chaque
résultat, du comportement corrigé et de la limite de régression.

<a id="how-snapshot-tests-reuse-the-production-re-render-path" data-pplx-source-anchor="true"></a>
## Comment les tests d'instantanés réutilisent le chemin de re-rendu de production

Les tests d'instantanés n'implémentent pas un moteur de rendu parallèle :

1. `render_fixture` dans `tests/conftest.py` copie les `raw_entries.json` simulés d'un accessoire,
   `raw_blocks.json` facultatif et `thread.json` dans un
   répertoire temporaire.
2. Il appelle `pplx_export.commands.rerender_cmd.rerender`, la même fonction
   utilisée par `pplx-export re-render`.
3. La fabrique d'accessoires `rendered` renvoie la sortie fraîche et le répertoire
   `golden/` validé de l'accessoire.
4. Les tests comparent `conversation.md` et chaque `turns/turn_*.md` octet par octet.

Les invariants de contenu complètent l'égalité des octets : les réponses ne doivent pas se réduire à
l'espace réservé `(无)` vide, et les résidus de représentation de dictionnaire tels que `{'type': ...` ne doivent pas
fuir dans le texte rendu.

<a id="adding-a-test" data-pplx-source-anchor="true"></a>
## Ajout d'un test

- **Logique existante** — ajoutez un test au module thématique correspondant. Utilisez
  `tmp_path`, des simulations et `monkeypatch` ; n'accédez jamais au réseau ou à
  `~/.config` réel.
- **Régression de bogue** — préférez le module thématique correspondant. Créez un
  module `test_fix_<lineage>_<slug>.py` lorsque la conservation de la lignée de revue améliore
  matériellement la traçabilité ; ne supposez pas un module par résultat.
- **Régression de rendu** — ajoutez ou réduisez un accessoire simulé, régénérez ses
  produits dorés avec l'outil de maintenance, puis enregistrez-le dans
  `test_render_snapshots.py` ou ajoutez des assertions spécifiques au scénario.

Suivez le style voisin : annotations de type,
`from __future__ import annotations` et docstrings de module bilingues.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Voir aussi

- [Accessoires de test](fixtures.md) — entrées simulées, produits dorés et le
  contrat de maintenance
- [Architecture du système de test](testing-architecture.md) — couches de test
  et garanties de régression
- [Opérations hors ligne](../architecture/offline-operations.md) — le chemin
  de re-rendu de production utilisé par les tests d'instantanés
