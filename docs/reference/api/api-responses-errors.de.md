---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-responses-errors.md"
translation_source_sha256: "4a9de23e2a900f4922480decf1b89d417310b94ce8116649dd2b2dd5c77b6bde"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-response-structure-and-error-semantics" data-pplx-source-anchor="true"></a>
# API-Antwortstruktur und Fehlersemantik

*Teil der Perplexity Web-API-Referenz — vollständige Übersicht im [API-Index](index.md).*

<a id="response-structure-essentials-parsing-discipline" data-pplx-source-anchor="true"></a>
## Grundlagen der Antwortstruktur (Parsing-Disziplin)

- **Rohdaten in erfolgreichen Archiven erhalten**: `raw_entries.json` (einfach) und
  `raw_blocks.json` (schematisiert, falls abgerufen) werden zusammen mit den gerenderten
  Artefakten gespeichert; Parsing/Rendering kann offline wiederholt werden (`pplx-export re-render`)
  ohne erneuten Abruf.
- **Felder extraktion zentralisiert** in `sites/perplexity/parsers.py` (Schemaabweichungen erfordern nur eine Änderungsstelle).
- Moduserkennung (`normalize.detect_mode`; Entscheidungsbaum in [export-pipeline.md](../../architecture/export-pipeline.md)): Das Signal mit der höchsten Priorität ist das
  **`search_mode`**-Feld eines Eintrags (Zuordnung am Ende von [§3.9](api-rest-endpoints.md)); wenn alle Signale fehlschlagen, Fallback — Computer = URL
  `/computer/tasks/` oder metadata.mode=="4" oder Index-Modus ∈ {ASI,COMPUTER}; Council = ein
  COUNCIL_RESEARCH-Schritt existiert; Deep-Research = ein RESEARCH_ANSWER-Schritt existiert (inhaltsbasiert, nicht auf chinesischen Bezeichnungen beruhend);
  andernfalls Suche.
- Die Computer-Benutzeroberfläche klappt alles zusammen — **immer nach den API-Einträgen/Blöcken gehen**; niemals UI-Text als Inhaltsgrenze verwenden.
- Subagent-Dualkanal (entdeckt am 19.07.2026): Prompt in schematisiertem `workflow_payload.objective_chunks`;
  Schritte/Schlussfolgerung in einfachem `background_entries`; verknüpft über `workflow_payload.id` (`toolu_X`).
- `WORKFLOW_ITEM_SOURCES`-Elemente enthalten oft `text_payload`
  (Subagent-Seitenextraktionstext / Vergleichstabellen; 450 Vorkommen bibliotheksweit, 408 innerhalb von Hintergrund-verschachtelten Nutzdaten)
  zusätzlich zu `sources_payload.sources` (Linkliste);
  derselbe Inhalt erscheint sowohl im einfachen Hintergrund-Eintrag als `text` eingebettetes Schritt-JSON als auch in den schematisierten verschachtelten Nutzdaten —
  verankerte Subagenten, die über den einfachen Pfad gerendert werden, erhalten den Text bereits (bibliotheksweite Prüfung am 22.07.2026: 408/408 vorhanden, keiner fehlt).
- **`related_queries` / `related_query_items` (geklärt am 23.07.2026)**: Jeder Eintrag trägt
  **Nächste-Frage-Prompt-Empfehlungen** — Folgevorschläge, die die Plattform für eine abgeschlossene Antwort generiert; `related_queries` ist ein Array von Empfehlungstexten,
  `related_query_items` die strukturierten Elemente (uuid/upsell_type usw.). Forensische Schlussfolgerung: Die uuid eines Elements
  **ist keine Thread-uuid** (0/988 Übereinstimmungen mit bibliotheksweiten Thread-uuids), und Empfehlungstexte haben keine Überschneidung mit Abfragen anderer Threads —
  **derzeit nicht in Beziehungen zwischen Threads auflösbar**; die Hypothese "vorab zugewiesene Thread-uuids (bei Klick materialisiert)" bleibt unbestätigt.
  Die Daten werden im Archiv `raw_entries.json` natürlich erhalten (Treffer in über der Hälfte der Threads eines Archivbibliothek); keine zusätzliche Sammlungsaktion erforderlich;
  der Beziehungsgraph baut daraus keine Kanten.

<a id="error-and-risk-control-semantics" data-pplx-source-anchor="true"></a>
## Fehler- und Risikokontrollsemantik

| Symptom | Bedeutung / Behandlung |
|---|---|
| 403 (mit cf-Challenge-Seite) | Cloudflare-Block (TLS-Fingerabdruck / Ratenbegrenzung) — zurückziehen; urllib + Browser-Cookies lösen es im Allgemeinen nicht aus |
| 401 / API-Level 403 (keine cf-Challenge-Seite) | Sitzungscookie abgelaufen/ungültig — das Tool meldet sofort, kein Zurückziehen; Batch schlägt nach 3 aufeinanderfolgenden Authentifizierungsfehlern fehl (Cookie aktualisieren) |
| 429 | Ratenbegrenzung — exponentielles Zurückziehen (im Tool implementiert) |
| 5xx (500/502/503/504) | Vorübergehende Serverfehler (504 häufig ein Cloudflare-Timeout) — zurückziehen und wiederholen (im Tool implementiert) |
| ENTRY_EXPIRED | Von der Plattform gelöscht (~3 Monate) — endgültig, nicht wiederholen |
| ENTRY_DELETED | Vom Benutzer/Remote gelöscht (auch HTTP 400, anderer Code) — endgültig `deleted`, nicht wiederholen |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED` (HTTP 200) | Aktuelles Konto kann den Space nicht anzeigen — mit einem Konto wiederholen, das dies kann |
| `error_code: VIEW_THREAD_NOT_ALLOWED` (HTTP 403) | Aktuelles Konto kann den Thread nicht anzeigen (getestet am 23.07.2026: Sibling-Varianten-uuid-Sondierung; das Objekt existiert, ist aber nicht zugänglich, nicht "nicht vorhanden") |
| `status:"failed"` leere Daten | Gleiche Klasse (die get_collection-Fehlerform) |

**Ratenbegrenzungsdisziplin (Anti-Bann, explizite Benutzeranforderung)**: Zufällige 10–20 s zwischen Batch-Threads, keine Parallelität, 429/403-Zurückziehen, 5xx-Zurückziehen-Wiederholen;
Paginierung ≥3 s; schematisierter Neuabruf ≥4 s; Space-Metadatenabruf ≥3 s. Einzel-Thread-Export = 1–2 Anfragen ≈ einmaliges Öffnen der Seite.

<a id="interruption-semantics-observed-values-2026-07-22-classification-source-of-truth-parsersclassify_wf_status" data-pplx-source-anchor="true"></a>
### Unterbrechungssemantik — beobachtete Werte (22.07.2026; Klassifikationsquelle der Wahrheit: `parsers.classify_wf_status`)

Das `locked_reason`-Feld: erscheint in `thread_metadata` / `entries[]` / `background_entries[]`
(auf beiden Seiten, einfach und schematisiert). Einziger beobachteter Wert:

| locked_reason | Bedeutung | Beobachtete Verteilung |
|---|---|---|
| `spending_limit_exceeded` | Ausgabenlimit-Unterbrechung (Kontingent erschöpft; der Workflow stoppt am Unterbrechungspunkt) | genau ein Thread bibliotheksweit (Marker in sowohl raw_entries als auch raw_blocks) |

Workflow-Statusfeld (`workflow_block.status` und verschachteltes `workflow_payload.status` teilen dieselbe Aufzählung) beobachtete Werte:

| Status | Semantik | Render-Anmerkung (COMPLETED erhält keine) |
|---|---|---|
| `WORKFLOW_COMPLETED` | normaler Abschluss | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | wartet auf nächste Schritte; mit `locked_reason=spending_limit_exceeded` ist es eine **Ausgabenlimit-Unterbrechung** (Inhalt stoppt am Unterbrechungspunkt); ohne locked_reason, unterbrochen in Erwartung der Fortsetzung | `⏸ 限额中断（内容截至中断点）` (⏸ limit-unterbrochen — Inhalt stoppt am Unterbrechungspunkt) / `⏸ 中断待续` (⏸ unterbrochen, Fortsetzung ausstehend) |
| `WORKFLOW_CANCELED` | abgebrochen (Benutzer/Plattform-Abbruch) | `⛔ 已取消` (⛔ abgebrochen) |

- `WORKFLOW_CANCELED` 19 Mal beobachtet (16 Haupt- + 3 verschachtelte), in 7 Computer-Threads
  (a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff).
- Hinweis: Der Status der Haupt-Eintrags-Anker-Nutzlast kann nachhinken (Anker COMPLETED beobachtet, während der Hintergrund tatsächlich CANCELED war) —
  der wahre Status eines Subagenten ist der hintergrundseitige `workflow_block.status`.
- Unterbrochene Hintergrundaufgaben erzeugen keine subagent_result-Abschlussbenachrichtigung; nicht verbrauchte Hintergrund-Nutzlasten fallen auf den Thread-Anhang zurück
  (siehe "Attribution-Wasserfall" in [subagents-interruptions.md](../../architecture/subagents-interruptions.md)).
- Leere Antworten im Computermodus (doppelt verifiziert Juli 2026, nicht wiederherstellbar): Im Computermodus haben einige Turns eine
  leere Antwort, weil der Server einfach keine hat — ein API-Neuabruf gibt Daten zurück, die mit dem Archiv identisch sind, und
  das Erweitern der "N Schritte abgeschlossen"-Leiste der UI löst null Datenanfragen aus (reines clientseitiges Rendering; die UI und
  die API teilen eine Quelle), daher kann die API sie nicht wiederherstellen. Nur eine Teilmenge solcher Turns ist mit
  `locked_reason=spending_limit_exceeded` verknüpft; der Rest trägt keinen serverseitigen Marker.

<a id="side_by_side_metadata-answer-rewrite-variant-signal-settled-2026-07-23" data-pplx-source-anchor="true"></a>
### `side_by_side_metadata`: Antwort-Neuschreibungs-Variantensignal (geklärt am 23.07.2026)

Feldpfad: `entries[].side_by_side_metadata` (einfache `/rest/thread/<uuid>`-Antwort).
Wenn die Plattform mehrere Antwortversionen für dieselbe Abfrage generiert (A/B-Experiment oder Neuschreibung), ist dies die
einzige Spur, die im aktuell aktiven Eintrag hinterlassen wird — **der Text (Schritte/Zitate) der ersetzten Variante ist nicht in der Thread-API-Antwort enthalten** (realer Fall
b2d2632b: die Antwort hat nur 1 Eintrag, 1 FINAL; Variante 2 vollständig unsichtbar).

Beobachtete Schlüssel und Werte (Nachweis: b2d2632b roh; bibliotheksweiter Scan von 2442 Einträgen):

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| Schlüssel | Semantik (beobachtet/hypothetisch) |
|---|---|
| `sibling_uuid` | Zeigt auf die **Geschwister-Antwortvariante** derselben Abfrage (ein anderer Eintrags-/Kontextbezeichner). 7 Threads bibliotheksweit getroffen; **Online-Forensik (23.07.2026) bestätigt einen toten Link**: Beide Konten `GET /rest/thread/<sibling_uuid>` geben 403 `VIEW_THREAD_NOT_ALLOWED` zurück (nicht 404/ENTRY_EXPIRED — der Server erkennt es als existierendes, aber nicht anzeigbares Objekt), und das Öffnen von `/search/<sibling_uuid>` im Browser (Besitzerkonto) wird per SPA zurück zur Startseite umgeleitet — ersetzte Varianten können nicht über sibling_uuid wiederhergestellt werden |
| `selection_status` | `SELECTED` = die Antwort dieses Eintrags ist die zur Anzeige ausgewählte Version; Kontrollgruppeninstanzen sind alle `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | Experimentrolle. Die Kontrollgruppe trägt ein `[control]`-Präfix (6 Fälle bibliotheksweit: `[control]default-model-class:gpt41` usw.); der reale Fall hat kein Präfix (`override-default-model-class:qwen3_instruct-01f7f`, d. h. die Behandlungsgruppe eines Modell-Override-Experiments) |
| `experiment_override` | Experiment-Override-Parameter (z. B. `override-default-model-class: qwen3_instruct`); nur bei Behandlungsgruppeninstanzen beobachtet |
| `execution_log` | Als leeres Objekt beobachtet; Semantik unbekannt |

**Eingrenzungskriterien** (Unterscheidung von "echter Neuschreibung, die beide Versionen behält" von "routinemäßiger A/B-Kontrolle"):
`sibling_uuid` nicht leer UND (`selection_status` nicht leer und nicht `SELECTION_STATUS_UNSPECIFIED`,
ODER `experiment_role` ohne das `[control]`-Präfix) → **nur b2d2632b trifft zu** unter den 2442 Einträgen bibliotheksweit
(der einzige bestätigte reale Fall; Präzision/Recall sind beide 1 in dieser Bibliothek, aber n=1 kann nicht extrapoliert werden).

Tool-Verhalten: `parsers.collect_answer_variants` extrahiert Treffer; `adapter.get_thread`
protokolliert eine Warnung + schreibt `thread.json.answer_variants` (Schlüssel fehlt, wenn keine Treffer);
`re-render --thread-json` fügt hinzu/entfernt direkt (idempotent). Zeitnachweis: Der reale Fall des Eintrags `created→updated`
Delta beträgt 53,66 s (generiert um 17:13, dann neu geschrieben/ausgewählt), und die Neuschreibung hat das Thread-Level `lastUpdated` vorgerückt (ein inkrementeller Re-Export
kann einen Neuabruf auslösen, aber die neu abgerufene Antwort enthält immer noch nur die aktive Antwort; alte Varianten sind nicht wiederherstellbar).

**Erkennungsprotokoll und Handhabungsablauf (23.07.2026, `sites/perplexity/variant_log.py`)**:

- **Protokollmarker**: Jeder Treffer gibt eine einzelne WARNING-Zeile mit dem einheitlichen grep-fähigen Marker `ANSWER_VARIANT_DETECTED` aus,
  einschließlich aller Lokalisierungsfelder und Handhabungsanleitung, geformt wie:
  `ANSWER_VARIANT_DETECTED thread=<full uuid> uuid8=<8 chars> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | action: …`
  Der Online-Pfad (`adapter.get_thread`) gibt bei jedem tatsächlichen Abruftreffer aus; offline `re-render`
  **gibt nur aus, wenn registrierter Inhalt hinzugefügt/geändert wird** (idempotente Wiederholungen spammen nicht); `batch` gibt auch eine einzeilige
  Trefferanzahl-Erinnerung in der abschließenden Zusammenfassung aus (ohne das vorhandene Zusammenfassungsformat zu brechen).
- **Zentrales Register**: `<out>/index/answer_variants_log.jsonl` (**eine eingecheckte Datei**, nicht unter dem
  gitignorierten `logs/`) — ein JSON pro Zeile (detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role), dedupliziert nach (web_uuid, entry_uuid); wiederholte Exporte/Neu-Renderings hängen nicht endlos an;
  detected_at behält die Zeit des ersten Sehens.
- **Empfohlene Aktion bei Treffer**: Geschwister sind empirisch tote Links (siehe Tabelle oben); die alternative Antwort ist normalerweise
  **nicht über die API wiederherstellbar** — umgehend manuell bestätigen, ob die alternative Antwort noch erhältlich ist (Plattform-Konversationsseite / Benutzererinnerung / Screenshots); falls erhältlich,
  manuell als `rewritten_answer_variant.md`-Datei im Thread-Verzeichnis aufzeichnen; falls nicht, `thread.json.answer_variants` +
  das jsonl-Register dienen als endgültiger nachverfolgbarer Datensatz.
