---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/modes.md"
translation_source_sha256: "dda1cfaf9d60ef912d922e65babafb68ec80cd1cdf046d661960d0de47ab77ff"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="conversation-modes" data-pplx-source-anchor="true"></a>
# Gesprächsmodi

Perplexity-Gespräche gibt es in fünf Modi: `search` / `deep-research` / `computer` /
`council` / `study`. Der Modus wird pro Thread während des Exports erkannt; er bestimmt, welche
API-Antworten abgerufen werden, was im Thread-Verzeichnis landet und welchen
[Archivpfad](archive-layout.md) der Thread erhält (`<account>/<mode>/…`). Der erkannte Modus wird
in `thread.json` (`mode`-Schlüssel) aufgezeichnet und von der `pplx-export batch --mode`-Filterung verwendet.
`pplx-ask` kann auch *neue* Threads in vier der fünf Modi erstellen (alle außer
`computer`) – siehe [pplx-ask](pplx-ask.md).

<a id="the-five-modes-at-a-glance" data-pplx-source-anchor="true"></a>
## Die fünf Modi auf einen Blick

| Modus | UI-Name / Modell | Inhalt der Runde | Zitate | Produkte | Schematisierte Blöcke abgerufen |
|---|---|---|---|---|---|
| `search` | "Best" (`pplx_pro`; Labs `STUDIO`/`pplx_beta` wird ebenfalls hierhin abgebildet) | Abfrage + Antwort, Textschritte | auf Rundenebene + threadweit `sources.*` | — | Nein (`raw_blocks.json` fehlt) |
| `deep-research` | "Deep research" (`pplx_alpha`, fest, kein Auswahlfeld) | Forschungsschritte inkl. `RESEARCH_ANSWER` | ja | `report.md` (vollständiger Bericht) | Ja |
| `computer` | Computer (`pplx_asi_opus`, `pplx_asi_opus_thinking`) | vollständiger `workflow_block`: Erzählung, Tool-Aufrufe, Sub-Agent-Prompts/Schritte, Zitate pro Schritt | pro Schritt + Runde + Thread | versionierte Dateien in `assets/` + Sub-Agent-Ausführungen | Ja |
| `council` | Model Council (`pplx_agentic_research`; standardmäßig drei Modelle) | `COUNCIL_RESEARCH`-Schritt; der verschachtelte `LLM_COUNCIL`-Workflow jedes Modells in `<details>` eingefaltet (Suchrunden, alle Quellen, vollständige Antwort pro Modell) | pro Modell + aggregiert | Antworten pro Modell nebeneinander verglichen | Ja |
| `study` | Study (`pplx_study`) | Schritte/Zitate über Blöcke (verifiziert, dass sie auch Assets enthalten) | ja | Assets, falls vorhanden | Ja |

<a id="how-the-mode-is-decided" data-pplx-source-anchor="true"></a>
## Wie der Modus bestimmt wird

Die Erkennungsautorität ist das plattformeigene Feld **`entry.search_mode`**
(`SEARCH_MODE_MAP`, `normalize.py:50-59`), das über alle Einträge gesammelt wird
(`normalize.py:106-115`). Es wurde gegen die offizielle Modellkonfiguration verifiziert
(`GET /rest/models/config/v2`): `default_models.search=pplx_pro` (UI "Best"),
`default_models.research=pplx_alpha` (UI "Deep research"), und die Werte bilden eins zu eins auf
Gesprächsmodi ab:

| `search_mode`-Wert | Modus |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`, `STUDIO` | `search` |

Konfliktregeln (`detect_mode`, `normalize.py:66-128`):

- **Moduswechsel innerhalb eines Threads** (Einträge widersprechen sich): nimm den höchsten nach Spezifität –
  **computer > council > study > deep-research > search** (`_MODE_SPECIFICITY`,
  `normalize.py:63`) – und `log.warning`.
- **Konflikt mit nachgelagerten Signalen** (Schrittnamen / `display_model`): `search_mode` gewinnt,
  `log.warning` (`normalize.py:120-123`).
- **`search_mode` vollständig abwesend** → die ursprüngliche Kette: URL enthält `/computer/tasks/` oder
  `metadata.mode == '4'` oder Index-Modus ∈ `ASI`/`COMPUTER` → `computer`; ein `COUNCIL_RESEARCH`-
  Schritt → `council`; ein `RESEARCH_ANSWER`-Schritt → `deep-research`; redundantes `display_model`-
  Signal (`DISPLAY_MODEL_MODE`, `normalize.py:32-37`) gewinnt bei Konflikt; nichts trifft zu →
  `search` standardmäßig.
- **Alle Signale fehlen, bedeutet nicht search**: Die Pipeline ruft trotzdem die schematisierten
  Blöcke ab (`adapter.py:83-89`), sodass eine Drift des Plattformfelds nicht stillschweigend `raw_blocks.json` fallen lässt.

!!! note "Warum `pplx_alpha` kein Erkennungshinweis ist"
    `pplx_alpha` ist das RESEARCH-gewidmete Modell – es ist das *Ziel*, das der Klassifikator erkennen muss,
    kein Beleg für die Erkennung, daher wird es bewusst aus der Zuordnungstabelle ausgeschlossen
    (`normalize.py:15-31`-Kommentar).

Der vollständige Entscheidungsbaum mit allen Verzweigungen: [Export-Pipeline – Moduserkennung](../architecture/export-pipeline.md).

<a id="where-sub-agent-payloads-land" data-pplx-source-anchor="true"></a>
## Wo Sub-Agent-Nutzlasten landen

Computer-/Council-Ausführungen starten Hintergrund-Sub-Agent-Workflows. Jeder Hintergrund-
`workflow_payload` wird an **genau einer Stelle, niemals zweimal** gerendert; auf Benutzerebene sind die
drei möglichen Landeplätze:

1. **Verankert – innerhalb der initiierenden Runde**: Die Runde, die den Sub-Agent gestartet hat, trägt eine
   passende Nutzlast-ID, sodass die Ausführung inline im Arbeitsprozess dieser Runde gerendert wird
   (`turns/turn_NNNN.md`), mit Prompt, Schritten, Antwort und Quellen.
2. **Platzhalter-Runde – Abschnitt "子代理工作" (Subagent work)**: Eine `subagent_result`-Platzhalter-Runde innerhalb eines
   10-Sekunden-Abschlussfensters absorbiert die Nutzlast; die Antwort wird nicht nachgetragen.
3. **Thread-Anhang – Ende von `conversation.md`**: Alles Übrige (unterbrochene Ausführungen
   erzeugen keine Abschlussbenachrichtigung, daher werden die ersten beiden Ebenen zwangsläufig verfehlt) wird
   wörtlich unter "## 后台任务（未归入轮次）" (Hintergrundaufgaben (nicht Runden zugeordnet)) archiviert – keine
   Zeitzuordnungsvermutung, jeder Status akzeptiert.

Zuordnungsregeln, Datenstrukturen und die Garantie des einmaligen Verbrauchs:
[Sub-Agents & Unterbrechungen](../architecture/subagents-interruptions.md).

<a id="interruptions-non-completed-workflows" data-pplx-source-anchor="true"></a>
## Unterbrechungen: Nicht-COMPLETED-Workflows

Workflows, die nicht abgeschlossen wurden, werden inline annotiert, wo immer sie gerendert werden – in Arbeitsprozess-
Überschriften, Sub-Agent-Überschriften und verschachtelten `<details>`-Zusammenfassungen. Die drei Annotationen
(`parsers.classify_wf_status`, `parsers.py:263-284`):

| Annotation | Bedingung | Bedeutung |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` (limit-unterbrochen – Inhalt stoppt an der Unterbrechungsstelle) | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | Ausgabenlimit erschöpft; der Workflow wurde mitten in der Ausführung angehalten |
| `⏸ 中断待续` (unterbrochen, Fortsetzung ausstehend) | `WORKFLOW_AWAITING_NEXT_STEPS` ohne `locked_reason` | unterbrochen, kann auf der Plattform fortgesetzt werden |
| `⛔ 已取消` (abgebrochen) | `WORKFLOW_CANCELED` | vom Benutzer oder der Plattform abgebrochen |

- `COMPLETED` wird nie annotiert (gesunde Threads erhalten keine Differenz); unbekannte zukünftige Statuswerte
  bleiben still.
- Jeder annotierte Fall wird auch in `thread.json.interruptions` als
  `{location, kind, headline, status}` registriert – Orte sehen aus wie `turn_0007`,
  `turn_0011/subagent`, `turn_0024/subagent_stub`, `background_unassigned`
  (`parsers.py:535-583`; Schlüssel fehlt bei gesunden Threads).
- **Wiederaufnahme benötigt keinen Sonderfall**: Wenn Sie einen unterbrochenen Thread auf der
  Plattform fortsetzen, ändert sich sein `lastUpdated`, der nächste inkrementelle Export ruft ihn erneut ab, und die
  Annotationen verschwinden einfach, sobald der Workflow abgeschlossen ist. Siehe
  [Inkrementelle Synchronisation](incremental-sync.md).

Beobachtete Statuswerte und Verteilung: [API-Antworten & Fehler](../reference/api/api-responses-errors.md);
Zustandsautomat: [Sub-Agents & Unterbrechungen](../architecture/subagents-interruptions.md).

<a id="answer-rewrite-variants-answer_variants" data-pplx-source-anchor="true"></a>
## Antwort-Neuschreibungsvarianten (answer_variants)

Wenn die Plattform eine Antwort neu schreibt (A/B-Experimente), ist die ersetzte Variante in der
API unsichtbar – nur die ausgewählte Antwort wird zurückgegeben, während das verlierende Geschwister eine Spur in
`entries[].side_by_side_metadata` hinterlässt und später gelöscht werden kann (tote Geschwisterlinks bestätigt:
403 `VIEW_THREAD_NOT_ALLOWED`). Das Tool macht "eine Neuschreibung fand statt" beobachtbar:

- **Registrierung**: Treffer mit eingeschränkten Kriterien werden in `thread.json.answer_variants` geschrieben
  (`fs_writer.py:247-252`; Schlüssel fehlt ohne Treffer) und an das zentrale Register
  `index/answer_variants_log.jsonl` angehängt, dedupliziert nach (Thread, Eintrag) und idempotent
  (`variant_log.py:76`).
- **Warnungen**: Eine einzelne grep-fähige WARNING-Zeile `ANSWER_VARIANT_DETECTED` mit vollständigen Lokalisierungs-
  feldern (Thread-UUID/UUID8, entry_uuid, sibling_uuid, selection_status, experiment_role) bei
  jedem Online-Treffer; `re-render` registriert offline erneut und warnt nur, wenn Inhalt hinzugefügt oder
  geändert wird, sodass bibliotheksweite Wiederholungen ruhig bleiben; die Batch-Zusammenfassung hängt eine ⚠-Trefferanzahl an.
- **Manuelle Neuarchivierung**: Geschwistervarianten sind empirisch tote Links, daher kann die alternative Antwort
  normalerweise **nicht über die API wiederhergestellt werden**. Bei einem Treffer bestätigen Sie die alternative Antwort
  umgehend von Hand (Plattform-UI, eigene Aufzeichnungen, Screenshots); wenn Sie sie erhalten, zeichnen Sie sie als
  `rewritten_answer_variant.md` im Thread-Verzeichnis auf. Wenn nicht,
  `thread.json.answer_variants` plus das jsonl-Register sind der endgültig nachverfolgbare Datensatz.

Erkennungskette und erneute Offline-Registrierung: [Offline-Operationen](../architecture/offline-operations.md);
Feldsemantik und Nachweise für tote Links: [API-Antworten & Fehler](../reference/api/api-responses-errors.md).

<a id="rendering-fidelity-principles" data-pplx-source-anchor="true"></a>
## Grundsätze der Rendering-Treue

Unabhängig vom Modus folgt das Rendering demselben Treuevertrag:

- **Antworten vollständig, niemals abgeschnitten** – die alte `[:4000]`-Begrenzung wurde entfernt, weil sie
  Sätze mitten im Satz abschnitt (`render.py:645-647`).
- **Tabellen niemals abgeschnitten** – `WORKFLOW_ITEM_TABLE` rendert jede Zeile und Spalte, maskiert
  `|` und Zeilenumbrüche in Überschriften und Zellen, sodass die Markdown-Struktur überlebt
  (`render.py:211-243`).
- **Vollständige Zitate** – drei Sammelkanäle (`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`), dedupliziert nach URL in `sources.*`; nichts Zitiertes wird fallengelassen.
- **Das rohe API-JSON ist die Inhaltsgrenze** – alles Gerenderte stammt aus
  `raw_entries.json` / `raw_blocks.json`; was die API nicht zurückgibt (z. B. eine ersetzte Antwort-
  variante), kann nicht gerendert werden und wird stattdessen durch Register sichtbar gemacht, anstatt erfunden zu werden.
- **UI-Falten, das Archiv erweitert** – Details, die die Weboberfläche hinter Falten und Klicks verbirgt
  (Computer-Workflow-Erzählung und Tool-E/A, Council-pro-Modell-Ausführungen, Sub-Agent-Schritte) werden
  vollständig gerendert; `<details>`-Blöcke halten die Dokumentgliederung lesbar, ohne Informationen zu verlieren
  (`render.py:46`, `render.py:404-413`).
- **Strukturelle Robustheit** – Code-Blöcke werden an ihren Inhalt angepasst (`_fence_for`,
  `render.py:28-43`), sodass Tool-Ausgaben, die eigene Code-Blöcke enthalten, die Paarung nicht umkehren können, und
  LaTeX-Trennzeichen werden auf `$$` / `$` normalisiert, wobei Code-Segmente geschützt werden
  (`normalize_math_delims`).

Wie beibehaltene rohe Antworten all dies offline regenerierbar machen:
[Export-Pipeline](../architecture/export-pipeline.md) und [Offline-Operationen](../architecture/offline-operations.md).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Siehe auch

- [Archiv-Layout](archive-layout.md) – wo die Dateien jedes Modus landen
- [pplx-ask](pplx-ask.md) – Erstellen neuer Threads in jedem Modus
- [Inkrementelle Synchronisation](incremental-sync.md) – erneutes Abrufen fortgesetzter Threads
- [Export-Pipeline](../architecture/export-pipeline.md) – vollständiger Entscheidungsbaum zur Moduserkennung
- [Sub-Agents & Unterbrechungen](../architecture/subagents-interruptions.md) – Zuordnungswasserfall und Zustandsautomat
- [API-Antworten & Fehler](../reference/api/api-responses-errors.md) – beobachtete Feldwerte
