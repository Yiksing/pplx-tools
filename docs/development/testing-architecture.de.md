---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing-architecture.md"
translation_source_sha256: "ca93c1e43ccc41337097685ec6268f2d1f6a9997504b4a67683bce250b443b66"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing-architecture" data-pplx-source-anchor="true"></a>
# Testarchitektur

Das `pplx_export`-Testsystem ist vollständig offline, verwendet eingecheckte simulierte Daten
und sperrt das Renderer-Verhalten mittels Snapshots. Diese Seite beschreibt die Architektur und
Garantien; die aktuelle Modulliste gehört in
[Testing](../development/testing.md), und Fixture-Details gehören in
[Test-Fixtures](../development/fixtures.md).

Der Abschnitt behält seine Nummerierung aus dem
[Architekturüberblick](../architecture/overview.md).

---

<a id="test-system" data-pplx-source-anchor="true"></a>
## Testsystem

Führen Sie die Suite mit `uv run pytest tests` aus. Testzahlen werden aus dem
aktuellen Lauf gemeldet und nicht als architektonische Konstante behandelt.

<a id="layers" data-pplx-source-anchor="true"></a>
### Ebenen

| Ebene | Repräsentative Module | Vertrag |
|---|---|---|
| Reines Unit-Verhalten | `test_units.py`, Credential-/Cookie-/Config-Tests | Funktionen, Klassen, Validierung und Normalisierung mit simulierten Eingaben isolieren |
| Komponentensemantik | Interruptions-, Stub-Workflow-, Answer-Variant- und Relations-Tests | Zusammenarbeit von Parser, Renderer, State und Index-Code ohne Netzwerkzugriff testen |
| Offline-Befehls-/Zustandsverhalten | Backfill-, Löschsynchronisations-, Initialisierungs- und Review-Regressionen | Befehlspfade mit temporären Verzeichnissen und gefälschten Transports ausführen |
| Render-Snapshots | `test_render_snapshots.py` | Simulierte API-förmige JSON durch den Produktions-Render-Pfad leiten und alle Markdown-Bytes mit festgelegten Goldens vergleichen |

Überprüfungsbezeichner wie N, V3, V4 und V5 sind Rückverfolgbarkeitsmetadaten über
diese Ebenen hinweg. Sie definieren keine separate Laufzeitarchitektur, und ihre
Beziehung zu Testmodulen ist nicht notwendigerweise eins-zu-eins.

<a id="snapshot-data-flow" data-pplx-source-anchor="true"></a>
### Snapshot-Datenfluss

1. Ein simuliertes Fixture liefert `raw_entries.json`, optional
   `raw_blocks.json` und `thread.json`.
2. `tests/conftest.py::render_fixture` kopiert diese Dateien in `tmp_path`.
3. Das Fixture ruft `commands.rerender_cmd.rerender` auf, den Produktions-Offline-
   Rekonstruktionspfad.
4. Neue `conversation.md`- und `turns/turn_*.md`-Dateien werden
   byteweise mit den festgelegten `golden/`-Produkten verglichen.

Goldens sind generierte Erwartungen, keine unabhängige Datenquelle. Jede
Renderer-Änderung, die Artefakt-Bytes verändert, färbt die Snapshot-Suite rot, bis
die Änderung überprüft und die Goldens absichtlich neu generiert werden.

<a id="isolation-and-trust-boundaries" data-pplx-source-anchor="true"></a>
### Isolation und Vertrauensgrenzen

- **Fixture-Ursprung** — alle festgelegten Fixture-Eingaben sind simulierte Daten. Sie
  werden nicht von Live-Konten, Live-API-Antworten, `web_archive/` oder
  privaten Archiven kopiert.
- **Netzwerkgrenze** — Tests verwenden Fakes und Offline-Pfade; eingecheckte Fixtures
  erfordern keine Anmeldeinformationen oder Netzwerkzugriff.
- **Konfigurationsgrenze** — das Autouse-Fixture installiert Platzhalter-Kontokonfiguration,
  sodass die echten `~/.config` eines Entwicklers die Ergebnisse nicht bestimmen.
- **Dateisystemgrenze** — Befehls- und Migrationsverhalten läuft unter
  `tmp_path`; Benutzerarchive sind keine Testziele.
- **Rückstandsgrenze** — `tests/scrub_fixtures.py --check` lehnt konfigurierte
  umgebungsspezifische Zeichenfolgen, lokale absolute Pfade und signierte URL-
  Anmeldeinformationen ab, ohne Dateien zu ändern.

Zusammen schützen Unit-Assertions, Komponentensemantik, Befehlszustandstests und
Byte-Level-Snapshots sowohl die lokale Logik als auch den End-to-End-Render-
Vertrag.
