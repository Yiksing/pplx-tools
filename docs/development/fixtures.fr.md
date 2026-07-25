---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/fixtures.md"
translation_source_sha256: "72f6f6faa0f4c2ef3a63b3f0a7c6bc0a16f9be6cb03225850e4d5d4b22193b30"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="test-fixtures" data-pplx-source-anchor="true"></a>
# Fixtures de test

`tests/fixtures/` contient des **données simulées** déterministes, en forme d'API, pour la
[suite de tests](testing.md). Les entrées modélisent des structures de fils et de workflows représentatives ; leurs produits rendus sont validés comme des instantanés de référence.

<a id="source-contract" data-pplx-source-anchor="true"></a>
## Contrat de source

<!-- audit:contract fixture-source=simulated -->

Le contenu actuel des fixtures est simulé :

- Les nouvelles fixtures ou les mises à jour doivent être construites comme des données simulées ; les contributeurs ne doivent pas les peupler en important `web_archive/`, des données de compte utilisateur, des réponses API en direct ou des archives privées.
- Les noms, identités, identifiants, invites, réponses, charges utiles de workflow, chemins et URL dans les fichiers validés sont des espaces réservés de test.
- Le JSON reflète les schémas de réponse et d'archive de production uniquement pour exercer le comportement de l'analyseur, du rendu, de l'état et des relations.
- Le dépôt ne valide pas de mappage inverse des espaces réservés vers des identifiants privés.

Les termes **fixture de mode complet** et **fixture de scénario réduit** décrivent la couverture de test et la forme des entrées, pas la provenance. Les deux sont des données simulées.

<a id="directory-contract" data-pplx-source-anchor="true"></a>
## Contrat de répertoire

Chaque répertoire de fixture contient des entrées simulées en forme de réponse brute et, lorsque la comparaison d'instantanés est nécessaire, une arborescence `golden/` :

| Chemin | Rôle |
|---|---|
| `raw_entries.json` | entrées de fil simulées dans la forme de réponse de production |
| `raw_blocks.json` | blocs de workflow simulés ; absents lorsque le mode n'a pas de réponse en bloc |
| `thread.json` | métadonnées de fil archivé simulées |
| `golden/conversation.md` + `golden/turns/turn_*.md` | produits générés à partir des entrées simulées et comparés octet par octet |

Les conventions déterministes actuelles incluent :

- des comptes fictifs `alice` / `bob`, des identités d'exemple, un espace BOT fictif et un `read_write_token` fictif fixe ;
- des identifiants dérivés d'uuid5 étiquetés avec `5cbeef00`, préservant les références croisées intentionnelles entre les enregistrements simulés ;
- des identifiants `toolu_` simulés de longueur fixe étiquetés avec `5crub0` ;
- des invites, titres, textes de workflow et chemins de fichiers génériques ; et
- des chaînes de requête d'URL signées supprimées.

Ces conventions rendent facile la détection de résidus accidentels spécifiques à l'environnement ; elles n'impliquent pas que les identifiants simulés ont été dérivés d'objets réels.

<a id="inventory" data-pplx-source-anchor="true"></a>
## Inventaire

<!-- audit:inventory fixture-directories -->

<a id="full-mode-fixtures" data-pplx-source-anchor="true"></a>
### Fixtures de mode complet

Ce sont des conversations simulées complètes pour chaque mode pris en charge :

| Fixture | Couverture |
|---|---|
| `search_demo` | recherche, un tour ; bloc de code R et code en ligne |
| `deep_research_demo` | recherche approfondie ; conversion de délimiteurs mathématiques de bout en bout |
| `computer_demo` | ordinateur, rendu de workflow en sept tours |
| `council_demo` | rendu de comité de modèle avec une charge utile imbriquée volumineuse |
| `study_demo` | rendu en mode étude |

<a id="reduced-scenario-fixtures" data-pplx-source-anchor="true"></a>
### Fixtures de scénario réduit

Ce sont des charges utiles simulées ciblées contenant uniquement les entrées et relations nécessaires à une régression. « Réduit » ne signifie pas extrait d'un fil réel.

| Fixture | Couverture |
|---|---|
| `scenario_computer_answer_fallback` | récupérer la réponse d'un bloc de workflow schématisé lorsque le chemin FINAL simple n'est pas disponible |
| `scenario_subagent_fallback` | rendre un titre de sous-agent et ses propres éléments lorsqu'aucune correspondance de contexte n'existe |
| `scenario_user_response` | rendu question/réponse `WORKFLOW_ITEM_USER_RESPONSE` |
| `scenario_subagent_stub` | fenêtre d'association de dix secondes pour un stub de résultat de sous-agent non ancré |
| `scenario_workflow_item_nested` | rendu de bloc réduit `WORKFLOW_ITEM_WORKFLOW` imbriqué |
| `scenario_limit_interrupted` | interruption de limite de dépenses, cascade d'attribution, placement en annexe et pas de double rendu |
| `scenario_canceled` | annotation `WORKFLOW_CANCELED` |

<!-- /audit:inventory fixture-directories -->

<a id="maintaining-fixtures" data-pplx-source-anchor="true"></a>
## Maintenance des fixtures

`tests/scrub_fixtures.py` normalise les données simulées, régénère les produits de référence via le rendu hors ligne de production et applique une barrière de résidus :

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **Régénération** — chaque fixture est rendue dans un répertoire temporaire via `pplx_export.commands.rerender_cmd.rerender` ; les incohérences de nombre de tours interrompent le processus.
- **Normalisation déterministe** — le texte des espaces réservés, les UUID, les valeurs `toolu_`, les jetons et les URL signées sont normalisés de manière idempotente.
- **Les entrées de sécurité ne sont pas une provenance** — le `tests/scrub_pairs.local.json` local optionnel et la configuration de compte au niveau utilisateur étendent uniquement les vérifications de remplacement et de résidus. Ils ne doivent pas être utilisés comme entrées pour construire des scénarios de fixture.
- **Mode vérification** — `--check` n'effectue aucune écriture et échoue en cas de résidus configurés, de chemins absolus locaux ou d'identifiants d'URL signée.

Exécutez l'outil de maintenance après avoir modifié le JSON d'entrée simulé ou la sortie du rendu, et exécutez `--check` avant de valider les modifications de fixture.

<a id="golden-snapshot-authority" data-pplx-source-anchor="true"></a>
## Autorité de l'instantané de référence

Le JSON simulé validé est l'autorité d'entrée. Le Markdown de référence est une sortie dérivée : il est régénéré à partir de ce JSON avec le chemin de re-rendu de production actuel, puis validé pour une comparaison de régression au niveau octet. Il ne doit pas être modifié comme une source de vérité indépendante.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Voir aussi

- [Tests](testing.md) — comment la suite consomme les fixtures
- [Architecture du système de test](testing-architecture.md) — couches de régression et garanties
- `tests/fixtures/README.md` — inventaire des fixtures local au dépôt
