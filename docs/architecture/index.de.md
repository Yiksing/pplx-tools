---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/index.md"
translation_source_sha256: "a64006f8b94ad04a3bc498468e674f3b8a22f27242c9bb7b8c5a9252019cc751"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="architecture-reading-map" data-pplx-source-anchor="true"></a>
# Architektur-Lesekarte

Referenz auf Mechanismenebene für pplx-Werkzeuge (`pplx-export` / `pplx-ask`):
Abhängigkeiten, Pipelines, Zustandsmaschinen, Datenverträge und Zuverlässigkeitsgrenzen.
Für aufgabenorientierte Nutzung beginnen Sie mit der [Benutzeranleitung](../guide/index.md).

!!! note "Umfang und Quelle der Wahrheit"

    Diese Seiten erklären die Architektur von `pplx_export/` für Agenten und
    Ingenieure, die das Projekt warten. Zeilenverweise verwenden `file.py:NN`,
    relativ zu `pplx_export/`. Die Beschreibungen wurden am 2026-07-23 gegen das Repository
    geprüft (`__version__ = "0.1.0"`, `pplx_export/__init__.py:31`); aktueller Code und Tests bleiben maßgeblich.

<a id="start-with-the-system-map" data-pplx-source-anchor="true"></a>
## Beginnen Sie mit der Systemkarte

- [Architekturübersicht](overview.md) — Schichten, Modulverantwortlichkeiten und
  der Import-Abhängigkeitsgraph.

<a id="follow-a-runtime-flow" data-pplx-source-anchor="true"></a>
## Folgen Sie einem Laufzeitablauf

- [Export-Pipeline](export-pipeline.md) — Abrufen, Rohantwort-Speicherung,
  Moduserkennung und Markdown-Rendering.
- [Sub-Agenten und Unterbrechungen](subagents-interruptions.md) — Payload-
  Zuordnung und Unterbrechungs-/Fortsetzungssemantik.
- [pplx-ask und Konten](ask-and-accounts.md) — Streaming-Abfragen und
  Multi-Konto-Cookie-Wechsel.

<a id="understand-data-and-reliability" data-pplx-source-anchor="true"></a>
## Verstehen Sie Daten und Zuverlässigkeit

- [Datenmodell und Verzeichnisvertrag](data-model.md) — Modelle, Schreib-
  grenzen und der On-Disk-Archivvertrag.
- [Ratenbegrenzung und Fehlerbehandlung](rate-limiting-errors.md) — Drosselung,
  Backoff, Endzustände und Fehlerweiterleitung.
- [Offline-Betrieb](offline-operations.md) — Neu-Rendering ohne Netzwerk,
  Beziehungsneuerstellung und lokale Wartungspipelines.

<a id="related-references" data-pplx-source-anchor="true"></a>
## Verwandte Referenzen

- [Web-API-Referenz](../reference/api/index.md) — beobachtete REST/GraphQL-Verträge,
  Antwortsemantik und Erkennungshinweise.
- [Wartungsanleitung](../development/index.md) — Testarchitektur, Beitrags-
  workflow und simulierte Fixture-Verträge.
