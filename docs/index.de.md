---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/index.md"
translation_source_sha256: "7a016c35bbb11272395a246fd23c0c27be794585c5b1cda9fdc9c6181fe32e48"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# Perplexity CLI-Toolkit

<p class="homepage-scope-note" role="note">
  <strong>NICHT für Pay-as-you-go-API</strong>
</p>

Perplexity Konversationsarchiv & interaktives Abfrage-Toolkit (`pplx-export` / `pplx-ask`).

Es kommuniziert direkt mit der Perplexity REST/GraphQL-API unter Verwendung der eingeloggten Cookies Ihres Browsers und archiviert Konversationen – Schritte, Zitate, Deep-Research-Berichte, Computer-Mode-Assets und Sub-Agent-Workflows – als lokales Markdown + JSON. Erfolgreiche Exporte behalten die rohen API-Antworten zusammen mit den gerenderten Artefakten, sodass das Rendern jederzeit offline wiederholt werden kann.

<a id="introduction" data-pplx-source-anchor="true"></a>
## Einführung

Über die Archivierung historischer Konversationen hinaus zielt dieses Projekt hauptsächlich darauf ab, lokalen Agenten – näher an den Daten und oft mit mehr Rechenleistung – ein gewisses Maß an Perplexity Computer-Fähigkeiten zu geben. Indem sie auf Berichte zugreifen können, die von Perplexity Deep Research direkt in ihrem Arbeitsablauf erstellt wurden, können sie hochwertige Informationen nutzen, um Schlüsselparameter im Code präziser abzustimmen und gleichzeitig ein bestehendes Perplexity Max-Abonnement besser auszuschöpfen.

> Stand 20. Juli bot Perplexity keine offizielle CLI für Unix-ähnliche Umgebungen an. Am 23. Juli veröffentlichte Perplexity öffentlich das `pplx`-Tool, das im Computer-Mode verwendet wird, aber dieses Tool verwendet weiterhin Pay-as-you-go-Abrechnung.

Es ist kein vollständiger Ersatz für den Computer-Mode. Zwei Fähigkeiten bleiben unerreichbar:

- die Freiheit der Deep-Research-Funktion, ein beliebiges Modell auszuwählen;
- die Fähigkeit der Council-Funktion, tiefgehende Recherchen mit mehreren benutzerdefinierten Modellen durchzuführen, Berichte zu erstellen und diese nebeneinander zu vergleichen.

Das Verzeichnis [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context) enthält archivierte System-Prompts und Betriebsregeln, die helfen können, Teile des Computer-Workflows lokal zu approximieren, einschließlich der Deep-Research-Modellauswahl und der Sub-Agent-Modellauswahl.

<a id="features" data-pplx-source-anchor="true"></a>
## Funktionen

<a id="pplx-export-archive-your-library" data-pplx-source-anchor="true"></a>
### `pplx-export` – Ihre Bibliothek archivieren

- Bibliotheksindex und Bereichsindex
- Einzelthread-/Batch-Export mit inkrementellem Frühstopp + fortsetzbaren Prüfpunkten
- Asset-Nachfüllung und Guthaben-Nachfüllung
- Konversationsbeziehungsgraph
- Offline-Neu-Rendering (`re-render`, kein Netzwerk)
- Periodisch-inkrementeller Cron-Ausschnitt

<a id="pplx-ask-query-perplexity-from-the-shell" data-pplx-source-anchor="true"></a>
### `pplx-ask` – Perplexity von der Shell abfragen

- SSE-Streaming-Abfragen in vier Modi: Suche / Deep-Research / Council / Study
- Automatisches Verschieben in einen BOT-Bereich bei Abschluss, Lesebestätigungen
- Automatische Archivierung jedes erstellten Threads – entwickelt, damit andere Agenten es aufrufen können, um Echtzeitinformationen abzurufen

Artefaktgrenzen pro Modus (Zitate / Berichte / Assets / Sub-Agenten): siehe [Modi](guide/modes.md); Rendering-Treue-Prinzipien: siehe [Export-Pipeline](architecture/export-pipeline.md).

!!! note "Dokumentationsherkunft"

    Die meisten Seiten dieser MkDocs-Site wurden aus dem aktuellen Code und Tests generiert oder rekonstruiert. Einige Seiten enthalten auch Designkontext, Beobachtungen und Entscheidungen aus früheren Diskussionen mit Agenten. Wenn eine Dokumentationsaussage und die Implementierung voneinander abweichen, betrachten Sie den aktuellen Code und die Tests als Quelle der Wahrheit.

<a id="where-to-next" data-pplx-source-anchor="true"></a>
## Wie es weitergeht

- **Die Tools verwenden** – folgen Sie der aufgabenorientierten [Benutzeranleitung](guide/index.md).
- **Die Implementierung verstehen** – nutzen Sie die [Architektur-Lesekarte](architecture/index.md).
- **Mit der beobachteten Weboberfläche arbeiten** – konsultieren Sie die [Web-API-Referenz](reference/api/index.md).
- **Das Projekt sicher ändern** – folgen Sie der [Betreueranleitung](development/index.md).
