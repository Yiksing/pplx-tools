---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/index.md"
translation_source_sha256: "fc5f2fa607251be85bdc126f3701791c17d7330461b2ab49402ea485fcc961b7"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintainer-guide" data-pplx-source-anchor="true"></a>
# Guide du mainteneur

Contrats et workflows pour modifier les outils pplx sans compromettre la fidélité des archives ni l'isolation des tests.

<a id="choose-the-right-document" data-pplx-source-anchor="true"></a>
## Choisir le bon document

- [Architecture de test](testing-architecture.md) — couches de test, limites de confiance et garanties offertes par les instantanés hors ligne.
- [Pratiques de test](testing.md) — inventaire actuel des tests et workflow du contributeur.
- [Fixtures et instantanés](fixtures.md) — provenance des données simulées, conventions de répertoire, génération de références et vérifications des résidus.

<a id="local-quality-loop" data-pplx-source-anchor="true"></a>
## Boucle de qualité locale

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Les entrées des fixtures sont des données simulées déterministes. Elles ne sont pas copiées à partir de comptes réels, de réponses d'API réelles, de `web_archive/` ou d'archives privées.
