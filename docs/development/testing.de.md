---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing.md"
translation_source_sha256: "a552c25a28367f384140a2e5cc2e9fa2a8546034b668772f5df79133d4995648"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing" data-pplx-source-anchor="true"></a>
# Testen

Die Testsuite befindet sich in `tests/`, außerhalb des `pplx_export`-Pakets, und läuft
vollständig offline. Ihre API-förmigen Eingaben sind deterministische simulierte Daten, die unter
`tests/fixtures/` eingecheckt sind; Tests hängen nicht von Live-Diensten oder einer echten
Benutzerkonfiguration ab.

Diese Seite enthält das aktuelle Testmodul-Inventar und den Arbeitsablauf für Mitwirkende.
Informationen zum Regression-Design finden Sie unter
[Testsystemarchitektur](testing-architecture.md). Informationen zum Eingabedatenvertrag finden Sie unter [Test-Fixtures](fixtures.md).

<a id="running-the-tests" data-pplx-source-anchor="true"></a>
## Tests ausführen

```bash
uv run pytest tests
```

pytest ist eine deklarierte Entwicklungsabhängigkeit. Die Suite garantiert:

- **Kein Netzwerk** — simulierte Eingaben sind eingecheckt; netzwerkbezogene Pfade werden
  mit Fakes, `tmp_path` und `monkeypatch` abgedeckt.
- **Keine echte Benutzerkonfiguration** — vor dem Importieren eines Produktionsmoduls erstellt
  `tests/conftest.py` eine prozesslokale temporäre Konfiguration und überschreibt
  `PPLX_EXPORT_CONFIG`. Jeder Test erhält dann seine eigene Platzhalterkonfiguration
  `alice` / `bob` und stellt die prozesslokale Platzhalterkonfiguration
  danach wieder her. Subprozess-Regressionen stellen sicher, dass eine fehlende oder beschädigte
  Aufruferkonfiguration die Testsammlung nicht beeinträchtigen kann.
- **Schnelles Feedback** — am 25.07.2026 beobachtete das Projekt 435 Tests, die aus 32
  `test_*.py`-Modulen gesammelt wurden, und führte die vollständige Suite in etwa 13–25 Sekunden
  bei lokalen Verifikationsläufen aus.
  Die Zählungen sind ein datierter Repository-Snapshot und werden wachsen.

Nützliche Auswahlen:

| Befehl | Effekt |
|---|---|
| `uv run pytest tests` | vollständige Suite |
| `uv run pytest tests/test_units.py` | ein Modul |
| `uv run pytest tests -k snapshot` | Tests, deren Knoten-ID mit `snapshot` übereinstimmt |
| `uv run pytest tests -x -q` | beim ersten Fehler anhalten, leise Ausgabe |
| `uv run pytest --collect-only -q` | Anzahl der gesammelten Fälle aktualisieren |

<a id="current-module-inventory" data-pplx-source-anchor="true"></a>
## Aktuelles Modulinventar

Inventar, synchronisiert mit dem Repository am **27.07.2026**:

<!-- audit:inventory test-modules -->

| Funktionale Familie | Module | Zweck |
|---|---|---|
| Render-Snapshots | `test_render_snapshots.py` | Alle simulierten Vollmodus- und reduzierten Szenario-Fixtures neu rendern, dann die eingecheckten Produkte byteweise vergleichen |
| Kern- und gemeinsame Dienstprogramme | `test_units.py` | Zustand, Drosselung, Planung, Normalisierung, Asset-Benennung, Moduserkennung, sichere Pfade und übergreifende Regressionen |
| Dokumentationsverträge, Fähigkeiten und Lokalisierung | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | Repository-lokale Fähigkeitsverträge plus isolierte Miniatur-Repository-Tests für den schreibgeschützten Dokumentationsauditor und die maschinelle Übersetzungspipeline |
| Konfiguration, Authentifizierung und Bootstrap | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | Externe Konfigurationsisolierung, Cookie-Quellprofile, Anmeldeinformationsauswahl und Initialisierung |
| Rendering- und Workflow-Semantik | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | Workflow-Zuordnung, Unterbrechungszustände, Antwortvarianten, Audit-Logging und Beziehungskanten |
| Offline-Archiv- und Indexwartung | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | Anreicherung, Wiederaufnahme/Idempotenzverhalten, Kontenübergreifende Löscherkennung, Endzustände und die Offline-Zustandskonto-/Änderungsberichtsebenen |
| Review-Regressionen | 16 `test_fix_*.py`-Module, unten aufgeführt | Korrekturen, die aus Review-Ergebnissen abgeleitet wurden; Modulnamen behalten die Review-Herkunft bei |

<a id="review-regression-lineage" data-pplx-source-anchor="true"></a>
### Review-Regressions-Herkunft

Review-Identifikatoren erklären, warum eine Regression existiert; sie sind nicht die primäre
Architektur der Testsuite. Die Zuordnung ist bewusst viele-zu-viele: Ein Modul kann mehrere
Ergebnisse abdecken, und ein Ergebnis kann auch Fälle zu einem bestehenden thematischen Modul hinzufügen.

| Herkunft | Dedizierte Module |
|---|---|
| N-Review | `test_fix_n01_inline_assets.py`, `test_fix_n02_spaces_link.py`, `test_fix_n03_n12.py`, `test_fix_n04_cookies.py`, `test_fix_n05_n06_n09.py`, `test_fix_n07_usage_checkpoint.py`, `test_fix_n08_throttle_overflow.py`, `test_fix_n10_table_header.py`, `test_fix_n11_batch_total.py` |
| V3-Review | `test_fix_v301_nested_sources_text.py`, `test_fix_v305_export_products.py` |
| V4-Review | `test_fix_v401_thread_dir_migration.py`, `test_fix_v402_manifest_count.py`, `test_fix_v403_handle_assets_idempotency.py`, `test_fix_v405_ask_post_steps.py` |
| V5-Review | `test_fix_v5_review.py`, plus gezielte Ergänzungen zu bestehenden thematischen Modulen |
| V6-Review | `test_fix_v6_atomic_writes.py` |

<!-- /audit:inventory test-modules -->

Die Modul-Docstrings bleiben die maßgebliche Erklärung des alten Verhaltens, des korrigierten
Verhaltens und der Regressionsgrenze jedes Befunds.

<a id="how-snapshot-tests-reuse-the-production-re-render-path" data-pplx-source-anchor="true"></a>
## Wie Snapshot-Tests den Produktions-Neu-Render-Pfad wiederverwenden

Snapshot-Tests implementieren keinen parallelen Renderer:

1. `render_fixture` in `tests/conftest.py` kopiert die simulierten
   `raw_entries.json`, optionales `raw_blocks.json` und `thread.json` eines Fixtures in ein
   temporäres Verzeichnis.
2. Es ruft `pplx_export.commands.rerender_cmd.rerender` auf, dieselbe Funktion,
   die von `pplx-export re-render` verwendet wird.
3. Die `rendered`-Fixture-Factory gibt die frische Ausgabe und das eingecheckte
   `golden/`-Verzeichnis des Fixtures zurück.
4. Tests vergleichen `conversation.md` und jedes `turns/turn_*.md` byteweise.

Inhaltsinvarianten ergänzen die Byte-Gleichheit: Antworten dürfen nicht auf den leeren
`(无)`-Platzhalter kollabieren, und Dict-Repr-Überreste wie `{'type': ...` dürfen nicht
in gerenderten Text gelangen.

<a id="adding-a-test" data-pplx-source-anchor="true"></a>
## Hinzufügen eines Tests

- **Vorhandene Logik** — fügen Sie einen Test zum passenden thematischen Modul hinzu. Verwenden Sie
  `tmp_path`, Fakes und `monkeypatch`; greifen Sie niemals auf das Netzwerk oder echtes
  `~/.config` zu.
- **Fehlerregression** — bevorzugen Sie das passende thematische Modul. Erstellen Sie ein
  `test_fix_<lineage>_<slug>.py`-Modul, wenn das Beibehalten der Review-Herkunft die Rückverfolgbarkeit
  wesentlich verbessert; gehen Sie nicht von einem Modul pro Befund aus.
- **Render-Regression** — fügen Sie ein simuliertes Fixture hinzu oder reduzieren Sie es, regenerieren Sie seine
  goldenen Produkte mit dem Wartungswerkzeug, und registrieren Sie es dann in
  `test_render_snapshots.py` oder fügen Sie szenariospezifische Assertions hinzu.

Folgen Sie dem benachbarten Stil: Typannotationen,
`from __future__ import annotations` und zweisprachige Modul-Docstrings.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Siehe auch

- [Test-Fixtures](fixtures.md) — simulierte Eingaben, goldene Produkte und der
  Wartungsvertrag
- [Testsystemarchitektur](testing-architecture.md) — Testebenen
  und Regressionsgarantien
- [Offline-Operationen](../architecture/offline-operations.md) — der Produktions-
  Neu-Render-Pfad, der von Snapshot-Tests verwendet wird
