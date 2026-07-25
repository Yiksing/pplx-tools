---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/fixtures.md"
translation_source_sha256: "72f6f6faa0f4c2ef3a63b3f0a7c6bc0a16f9be6cb03225850e4d5d4b22193b30"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# Test-Fixtures

`tests/fixtures/` enthält deterministische, API-förmige **simulierte Daten** für die
[Test-Suite](testing.md). Die Eingaben modellieren repräsentative Thread- und Workflow-
Strukturen; ihre gerenderten Produkte werden als goldene Schnappschüsse festgeschrieben.

<a id="source-contract" data-pplx-source-anchor="true"></a>
## Quellvertrag

<!-- audit:contract fixture-source=simulated -->

Der aktuell festgeschriebene Fixture-Inhalt ist simuliert:

- Neue oder aktualisierte Fixtures müssen als simulierte Daten konstruiert werden; Mitwirkende
  dürfen sie nicht durch Import von `web_archive/`, Benutzerkontodaten, Live-
  API-Antworten oder privaten Archiven befüllen.
- Namen, Identitäten, Kennungen, Eingabeaufforderungen, Antworten, Workloads, Pfade
  und URLs in den festgeschriebenen Dateien sind Platzhalter für Tests.
- Das JSON spiegelt Produktionsantwort- und Archivschemata nur wider, um das Verhalten von
  Parser, Renderer, Zustand und Beziehung zu testen.
- Das Repository enthält keine Rückwärtszuordnung von Platzhaltern zu
  privaten Kennungen.

Die Begriffe **Full-Mode-Fixture** und **Reduced-Scenario-Fixture** beschreiben die Testabdeckung
und Eingabeform, nicht die Herkunft. Beide sind simulierte Daten.

<a id="directory-contract" data-pplx-source-anchor="true"></a>
## Verzeichnisvertrag

Jedes Fixture-Verzeichnis enthält simulierte rohantwortförmige Eingaben und,
wo ein Schnappschussvergleich erforderlich ist, einen `golden/`-Baum:

| Pfad | Rolle |
|---|---|
| `raw_entries.json` | simulierte Thread-Einträge in der Produktionsantwortform |
| `raw_blocks.json` | simulierte Workflow-Blöcke; fehlend, wenn der Modus keine Blockantwort hat |
| `thread.json` | simulierte Metadaten archivierter Threads |
| `golden/conversation.md` + `golden/turns/turn_*.md` | aus den simulierten Eingaben generierte Produkte, byteweise verglichen |

Die aktuellen deterministischen Konventionen umfassen:

- Platzhalterkonten `alice` / `bob`, Beispielidentitäten, einen Platzhalter-BOT-
  Bereich und eine feste Platzhalter-`read_write_token`;
- uuid5-abgeleitete Kennungen, gekennzeichnet mit `5cbeef00`, die absichtliche
  Querverweise zwischen simulierten Datensätzen bewahren;
- feste Länge simulierte `toolu_`-Kennungen, gekennzeichnet mit `5crub0`;
- generische Eingabeaufforderungen, Titel, Workflow-Text und Dateipfade; und
- signierte URL-Abfragezeichenfolgen entfernt.

Diese Konventionen machen versehentliche umgebungsspezifische Rückstände leicht erkennbar;
sie implizieren nicht, dass die simulierten Kennungen von Live-Objekten abgeleitet wurden.

<a id="inventory" data-pplx-source-anchor="true"></a>
## Bestandsaufnahme

<!-- audit:inventory fixture-directories -->

### Full-Mode-Fixtures

Dies sind vollständige simulierte Gespräche für jeden unterstützten Modus:

| Fixture | Abdeckung |
|---|---|
| `search_demo` | Suche, eine Runde; R-Code-Fence und Inline-Code |
| `deep_research_demo` | Deep Research; End-to-End-Mathematik-Begrenzer-Konvertierung |
| `computer_demo` | Computer, sieben Runden Workflow-Rendering |
| `council_demo` | Council-Modellausschuss-Rendering mit einer großen verschachtelten Nutzlast |
| `study_demo` | Study-Mode-Rendering |

### Reduced-Scenario-Fixtures

Dies sind fokussierte simulierte Nutzlasten, die nur die Einträge und
Beziehungen enthalten, die für eine Regression benötigt werden. „Reduced“ bedeutet nicht aus einem echten Thread extrahiert.

| Fixture | Abdeckung |
|---|---|
| `scenario_computer_answer_fallback` | die Antwort aus einem schematisierten Workflow-Block wiederherstellen, wenn der einfache FINAL-Pfad nicht verfügbar ist |
| `scenario_subagent_fallback` | eine Unter-Agent-Überschrift und ihre eigenen Elemente rendern, wenn keine Hintergrundübereinstimmung existiert |
| `scenario_user_response` | `WORKFLOW_ITEM_USER_RESPONSE` Frage/Antwort-Rendering |
| `scenario_subagent_stub` | Zehn-Sekunden-Assoziationsfenster für einen unverankerten Unteragent-Ergebnis-Stub |
| `scenario_workflow_item_nested` | verschachteltes `WORKFLOW_ITEM_WORKFLOW`-zusammengeklapptes Block-Rendering |
| `scenario_limit_interrupted` | Ausgabenlimit-Unterbrechung, Attributions-Wasserfall, Anhang-Platzierung und kein Doppel-Rendering |
| `scenario_canceled` | `WORKFLOW_CANCELED`-Annotation |

<!-- /audit:inventory fixture-directories -->

<a id="maintaining-fixtures" data-pplx-source-anchor="true"></a>
## Fixtures warten

`tests/scrub_fixtures.py` normalisiert die simulierten Daten, regeneriert goldene
Produkte durch den Produktions-Offline-Renderer und erzwingt eine Rückstandsprüfung:

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **Regeneration** — jedes Fixture wird in einem temporären Verzeichnis durch
  `pplx_export.commands.rerender_cmd.rerender` gerendert; Abweichungen bei der Rundenanzahl brechen ab.
- **Deterministische Normalisierung** — Platzhaltertext, UUIDs, `toolu_`-Werte,
  Token und signierte URLs werden idempotent normalisiert.
- **Sicherheitseingaben sind keine Herkunft** — die optionale lokale
  `tests/scrub_pairs.local.json` und benutzerkontenbezogene Konfiguration erweitern nur
  Ersetzungs- und Rückstandsprüfungen. Sie dürfen nicht als Eingaben zur
  Konstruktion von Fixture-Szenarien verwendet werden.
- **Prüfmodus** — `--check` führt keine Schreibvorgänge durch und schlägt bei konfiguriertem Rückstand,
  lokalen absoluten Pfaden oder signierten URL-Anmeldeinformationen fehl.

Führen Sie das Wartungswerkzeug nach Änderungen an simulierten Eingabe-JSONs oder Renderer-Ausgaben aus
und führen Sie `--check` vor dem Festschreiben von Fixture-Änderungen aus.

<a id="golden-snapshot-authority" data-pplx-source-anchor="true"></a>
## Goldene Schnappschuss-Autorität

Festgeschriebenes simuliertes JSON ist die Eingabeautorität. Goldenes Markdown ist abgeleitete
Ausgabe: Es wird aus diesem JSON mit dem aktuellen Produktions-Neu-Render-Pfad
regeneriert und dann für den Byte-Level-Regressionsvergleich festgeschrieben. Es darf nicht
als unabhängige Wahrheitsquelle bearbeitet werden.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Siehe auch

- [Testen](testing.md) — wie die Suite die Fixtures verwendet
- [Test-Systemarchitektur](testing-architecture.md) — Regressions-
  Ebenen und Garantien
- `tests/fixtures/README.md` — Repository-lokale Fixture-Bestandsaufnahme
