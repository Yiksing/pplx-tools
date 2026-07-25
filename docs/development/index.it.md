---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/index.md"
translation_source_sha256: "fc5f2fa607251be85bdc126f3701791c17d7330461b2ab49402ea485fcc961b7"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintainer-guide" data-pplx-source-anchor="true"></a>
# Guida per i manutentori

Contratti e flussi di lavoro per modificare gli strumenti pplx senza compromettere la fedeltà dell'archivio o l'isolamento dei test.

<a id="choose-the-right-document" data-pplx-source-anchor="true"></a>
## Scegli il documento giusto

- [Architettura dei test](testing-architecture.md) — livelli di test, confini di fiducia e le garanzie fornite dagli snapshot offline.
- [Pratiche di test](testing.md) — inventario attuale dei test e flusso di lavoro per i contributori.
- [Fixture e snapshot](fixtures.md) — provenienza dei dati simulati, convenzioni di directory, generazione golden e controlli dei residui.

<a id="local-quality-loop" data-pplx-source-anchor="true"></a>
## Ciclo di qualità locale

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Gli input delle fixture sono dati simulati deterministici. Non sono copiati da account live, risposte API live, `web_archive/` o archivi privati.
