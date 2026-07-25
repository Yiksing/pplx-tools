---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/index.md"
translation_source_sha256: "fc5f2fa607251be85bdc126f3701791c17d7330461b2ab49402ea485fcc961b7"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintainer-guide" data-pplx-source-anchor="true"></a>
# Leitfaden für Maintainer

Verträge und Workflows für die Änderung von pplx-Tools, ohne die Archivtreue oder Testisolierung zu beeinträchtigen.

<a id="choose-the-right-document" data-pplx-source-anchor="true"></a>
## Das richtige Dokument auswählen

- [Testarchitektur](testing-architecture.md) — Testebenen, Vertrauensgrenzen und die Garantien, die durch Offline-Snapshots bereitgestellt werden.
- [Testpraktiken](testing.md) — aktuelles Testinventar und Mitwirkenden-Workflow.
- [Fixtures und Snapshots](fixtures.md) — Herkunft simulierter Daten, Verzeichniskonventionen, Golden-Generierung und Rückstandsprüfungen.

<a id="local-quality-loop" data-pplx-source-anchor="true"></a>
## Lokale Qualitätsschleife

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Fixture-Eingaben sind deterministische simulierte Daten. Sie werden nicht von Live-Konten, Live-API-Antworten, `web_archive/` oder privaten Archiven kopiert.
