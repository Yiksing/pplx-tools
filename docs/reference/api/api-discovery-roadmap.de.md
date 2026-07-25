---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-discovery-roadmap.md"
translation_source_sha256: "60c675dcc583c059cd489ea085f9c2923f9447f7bbafb0a7ac991fee9f8add08"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="endpoint-discovery-and-improvement-roadmap" data-pplx-source-anchor="true"></a>
# Endpunkt-Erkennung und Verbesserungs-Roadmap

*Teil der Perplexity-Web-API-Referenz – vollständige Karte im [API-Index](index.md).*

<a id="known-unexplored-tbd-items" data-pplx-source-anchor="true"></a>
## Bekannte unerforschte / offene Punkte

- `list_collection_threads`-Sortierfeld und genaue `total_threads`-Semantik
  (2026-07 Live-Konto-Snapshot: gemeldet 99 vs. 27 Elemente der obersten Ebene).
- Volles Spektrum der `threadAccess`/`access`/`user_permission`-Werte (2026-07
  beobachtete Stichprobe: threadAccess 5 normal, 1 mit 🔒; collection access 1;
  permission 4 owner / 2 can edit; assets data enthält auch thread_access).
- Korrekte Parameterformen für `list_ask_threads`, `list_scheduled_computer_tasks` (direkter GET 400).
- Antwortstrukturen von `collections/*/request-access-info`, `spaces/<uuid>/recurring_tasks`, `assets/<id>/members`.
- Warum die Dashboard-GraphQL-Operationen nicht registriert sind (PERSISTED_QUERY_NOT_FOUND): Versionsabweichung oder Kontext-Gating;
  bei Bedarf erneut mit Live-Hashes aus dem Netzwerk-Mitschnitt extrahieren.
- Aufgabenverteilung zwischen `frontend_uuid` vs. `uuid` vs. `context_uuid` in Computer-Threads.
- API-Signalfelder von kontenübergreifenden Space-verzweigten Threads (branch_of)
  (Parent-Zeiger / Branch-Marker) – Mechanismus bestätigt (Ende von
  [§3.3](api-rest-endpoints.md)); kein archiviertes Exemplar zum 2026-07-23;
  überprüfen und aufzeichnen, wenn das erste erscheint.

<a id="endpoint-discovery-method-frontend-bundle-static-analysis-zero-api-cost-established-2026-07-20" data-pplx-source-anchor="true"></a>
## Endpunkt-Erkennungsmethode: Statische Analyse des Frontend-Bundles (null API-Kosten; etabliert 2026-07-20)

**147 `/rest/`-Endpunkte** in einem Durchgang entdeckt; die Methode ist wiederverwendbar (erneut ausführen nach Frontend-Überarbeitungen):

1. Der Seitenlade-Einstiegspunkt `_spa/assets/index.html-*.js` referenziert `bootstrap-*.js` (die Laufzeit enthält alle Chunk-Zuordnungen);
2. 682 Chunk-Dateinamen extrahieren (`<name>-<hash8>.js`-Muster) aus dem Bootstrap; API-bezogene nach Namen filtern
   (client/api/thread/collection/space/computer…);
3. Direkt vom öffentlichen CDN `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js` herunterladen
   (kein Cookie erforderlich); Hub-Module: `platform-core-*` (API-Client), `spa-shell-*`, `spa-metadata-*`;
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` liefert die Endpunktliste (147);
5. Chunks geben auch Aufrufstrukturen preis (z. B. Export's `format:'md'` und `file_content_64`).
6. Sourcemaps existieren ebenfalls: `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (nicht untersucht).

<a id="appendix-147-endpoints-grouped-by-category-archive-relevance-marked" data-pplx-source-anchor="true"></a>
### Anhang: 147 Endpunkte gruppiert nach Kategorie (Archivrelevanz markiert)

- **thread**: `/rest/thread/{entry_uuid_or_slug}`, `/rest/thread/export`★, `/rest/thread/{uuid}/members`,
  `/rest/thread/list_recent`, `/rest/thread/list_ask_threads`, `/rest/thread/list_pinned_ask_threads`,
  `/rest/thread/list_scheduled_computer_tasks`, `/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★: siehe vollständige Tabelle in [§3.3](api-rest-endpoints.md) (inkl. batch_move/batch_remove, list_user_collections, request-access-info,
  recurring_tasks, pins/threads, scheduled_threads)
- **assets**★: `/rest/assets/{asset_id}/data`, `/rest/assets/{asset_id}/members`,
  `/rest/assets/{asset_id}/published-access`, `/rest/assets/sites/{site_id}/publish-info`
- **analytics**: `/rest/analytics/computer/usage`, `/rest/analytics/computer/usage/members`
  (beide 403 NOT_ORG_MEMBER — nur Organisationskonten)
- **models/skills**: `/rest/models/config(/v2)`, `/rest/skills`, `/rest/skills/selectable`,
  `/rest/skills/grants`, `/rest/skills/submissions(/source)`
- **files/uploads**: `/rest/file-repository/*` (list/download/get-file-upload-urls/delete-files…),
  `/rest/files/list(/list-infinite/list-errors)`, `/rest/uploads/(batch_)create_upload_url(s)`,
  `/rest/connectors/attachments/upload`
- **tasks/computer**: `/rest/tasks/`, `/rest/tasks/{task_id}`, `/rest/tasks/shortcuts/mentions`,
  `/rest/tasks/shortcuts/paste/{copy_token}`, `/rest/computer/asset`, `/rest/computer/menu`,
  `/rest/computer/onboarding_cards`
- **user/auth**: `/rest/user/settings`, `/rest/user/get_user_ai_profile`, `/rest/user/promotions`,
  `/rest/user/site-instructions`, `/rest/auth/get_special_profile`, `/rest/visitor/*`
- **billing/stripe**: `/rest/billing/*` (credits/paypal/subscription…), `/rest/stripe/*`
- **enterprise/org**: `/rest/enterprise/*`, `/rest/organizations/{id}/credit-limits*`,
  `/rest/pplx-api/v2/enterprise-api-org`
- **sse**: `/rest/sse/attachment_processing/subscribe`, `/rest/sse/index_files`,
  `/rest/sse/perplexity_terminate`, `/rest/sse/related-queries/{entry_uuid}`
- **verticals** (für Archivierung irrelevant): `/rest/finance/*`, `/rest/sports/*`, `/rest/travel/hotels/{slug}`,
  `/rest/health-assistant/*`, `/rest/article/{uuid_or_slug}`
- **misc**: `/rest/pins`, `/rest/rate-limit/(all|status)`, `/rest/notifications/web-push/*`,
  `/rest/attribution/*`, `/rest/homepage-widgets/upsell`, `/rest/ntp/upsell/`, `/rest/sidebar/upsell/`,
  `/rest/incentives/comet-activation`, `/rest/connector-service/usage`

(★ = direkt relevant für Archivierung)

<a id="endpoint-tool-capability-status-and-roadmap" data-pplx-source-anchor="true"></a>
## Endpunkt → Werkzeugfähigkeit: Status und Roadmap

Der Implementierungsstatus unten wurde mit dem aktuellen Code und der Test-Suite
am **2026-07-24** synchronisiert. API-Nachweise behalten das Datum und den Umfang der
ursprünglichen Live-Beobachtung oder statischen Analyse; diese Dokumentationssynchronisation hat keine privaten Endpunkte erneut getestet. Konto-/Archivzahlen sind Schnappschüsse, keine plattformweiten Garantien.

Statusbedeutungen:

- **Implemented** — ein aktueller CLI- oder Produktionspfad verwendet den Endpunkt für die
  genannte Fähigkeit.
- **Partial** — der Endpunkt wird verwendet, aber die nachgelagerte Fähigkeit in der
  Roadmap bleibt unvollständig.
- **Tested, not integrated** — das Live-API-Verhalten wurde beobachtet, aber kein Werkzeugpfad
  verbraucht es.
- **Planned** — Nachweise existieren, aber die Implementierung hat noch nicht begonnen.
- **Blocked** — ein bekannter vorgelagerter oder Protokoll-Blocker verhindert die Implementierung.
- **Closed** — Nachweise haben die vorgeschlagene Verwendung widerlegt oder als nicht im Rahmen liegend eingestuft.

<a id="capability-status-matrix" data-pplx-source-anchor="true"></a>
### Fähigkeitsstatus-Matrix

| Endpunkt / Operation | Verifikationsbasis | Aktuelle Integration | Status | Verbleibende Lücke |
|---|---|---|---|---|
| `collections/get_collection` | Live-Beobachtung + aktueller Code | `spaces --fetch-meta` erstellt den Space-Besitzer/Mitglieder-Index | **Implemented** | — |
| `collections/list_collection_threads` | Live-Beobachtung + aktueller Code | `space-index` verwendet standardmäßig REST mit context_uuid-Dual-ID-Mapping; WebBridge ist Fallback | **Implemented** | Sortierreihenfolge und genaue `total_threads`-Semantik bleiben offen |
| `assets/<uuid>/data` | Live-getestet 2026-07-20 + aktueller Code | `assets-backfill --online` aktualisiert signierte URLs für echte Asset-UUIDs | **Implemented** | `toolu_`-Cloud-Workspace-Handles liegen außerhalb der Abdeckung dieses Endpunkts |
| `LibraryThreadsRelayQuery` und Paginierungsabfrage | erfasster APQ + aktueller Code | `index`/`batch` bieten vollständige Indizierung und inkrementellen Frühstopp | **Implemented** | Dashboard-Modusfilter-Abfragen bleiben separat blockiert |
| `collections/list_user_collections` | Live-beobachtet 2026-07 + aktueller Code | `init` verwendet eine exakte Titelübereinstimmung, um den BOT-Space zu entdecken | **Partial** | Erstellen eines autoritativen Konto-Space-Registers für die Entdeckung neuer Spaces und den `spaces`-Wiederaufbau |
| `credits/thread-usage` | Live-getestet 2026-07-20 + aktueller Code | `usage-backfill` schreibt `index/credit_usage_<account>.json` | **Partial** | Entscheiden, ob `thread.json` und/oder Bibliotheksindexzeilen angereichert werden sollen, ohne Autorität zu duplizieren |
| `models/config/v2` | Live-getestet 2026-07-21 + aktueller Code | `pplx-ask models` listet Modelle/Standardeinstellungen; Normalisierungskonstanten werden damit abgeglichen | **Partial** | Stabile Modellanzeige-Metadaten in Archiv-/Indexdatensätzen persistieren, falls nützlich |
| `POST /rest/thread/export` | md/pdf/docx live-getestet 2026-07-20 | keine CLI-Integration | **Tested, not integrated** | Multi-Format-Archivierung und offizielle Markdown-Abstimmung |
| `rate-limit/status` | Seitenlade-Beobachtung; Antwortsemantik unerforscht | keine | **Planned** | Semantik validieren, bevor es für adaptives Drosseln verwendet wird |
| `file-repository/list-files` | nur Frontend-Statikanalyse | keine | **Planned** | Validieren, ob es `toolu_`-Handles aufzählen/retten kann; ein 2026-07-Archiv-Snapshot verzeichnete 270 Handles ohne Download-Kanal |
| `pins`, `tasks/{id}` | Frontend-Statikanalyse / Seitenlade-Beobachtungen | keine | **Planned** | Pin-Status und Computer-Task-Dauer-Anreicherung |
| `thread/<uuid>/members` | Live-getestet 2026-07 | keine | **Planned** | Thread-Level-Sharing-Kanten für den Beziehungsgraphen |
| Dashboard GraphQL `threadGroup` + Modusfilter | direkte Aufrufe gaben `PERSISTED_QUERY_NOT_FOUND` zurück | keine | **Blocked** | Live-Persisted-Query-Hashes wiederherstellen oder den erforderlichen Kontext herstellen |
| `related_queries` / `sse/related-queries` | archivweite Forensik abgeschlossen 2026-07-23 | erzeugt bewusst keine Beziehungskanten | **Closed** | Nur wieder öffnen, wenn neue Nachweise eine auflösbare Thread-Identität etablieren |

<a id="active-roadmap" data-pplx-source-anchor="true"></a>
### Aktive Roadmap

<a id="p0-official-export-integration" data-pplx-source-anchor="true"></a>
#### P0 — Offizielle Export-Integration

- **Multi-Format-Archivierung**: optional PDF/DOCX-Produkte beibehalten, die von
  `POST /rest/thread/export` zurückgegeben werden.
- **Renderer-Abstimmung**: offizielles gesamten-Thread-Markdown mit
  `conversation.md` als unabhängiges Regressionssignal vergleichen.

<a id="p1-space-discovery" data-pplx-source-anchor="true"></a>
#### P1 — Space-Erkennung

- `list_user_collections` von BOT-Titel-Nachschlagewerk zu einem autoritativen,
  kontenbasierten Space-Register befördern, das für die Entdeckung neuer Spaces und den `spaces`-Wiederaufbau verwendet wird.

<a id="p2-metadata-risk-control-and-asset-rescue" data-pplx-source-anchor="true"></a>
#### P2 — Metadaten, Risikokontrolle und Asset-Rettung

- Autoritätsgrenze für die Guthabenverwendung entscheiden und dokumentieren: dediziertes
  `credit_usage_<account>.json` beibehalten oder auch `thread.json` /
  Bibliothekszeilen anreichern.
- Modellanzeige-Metadaten, Pin-Status, Computer-Task-Dauer und Thread-Sharing-Beziehungen
  nur hinzufügen, wo die Endpunktsemantik stabil ist.
- `rate-limit/status` validieren, bevor adaptives Drosseln entworfen wird.
- `file-repository/list-files` als möglichen `toolu_`-Rettungspfad testen, bevor
  eine Archiv-Mutation hinzugefügt wird.

<a id="p3-blocked-discovery" data-pplx-source-anchor="true"></a>
#### P3 — Blockierte Erkennung

- Dashboard-GraphQL-Persisted-Query-Hashes nur dann erneut erfassen, wenn die
  modusweise inkrementelle Indizierung wertvoll genug ist, um die Wartungskosten
  zu rechtfertigen.

<a id="closed-decisions-not-adopted" data-pplx-source-anchor="true"></a>
### Abgeschlossene Entscheidungen / nicht übernommen

- **Offizieller Export als Berichtsquelle**: widerlegt. Der Endpunkt gibt
  gesamten-Thread-Markdown ohne den Berichtstext zurück; die signierte-URL-Kette bleibt
  die offizielle Quelle für `report.md` ([§3.6](api-rest-endpoints.md)).
- **Beziehungen aus `related_queries`**: widerlegt 2026-07-23. Element-UUIDs sind keine
  Thread-UUIDs und Empfehlungstexte lösten sich nicht in archivierte Abfragen auf;
  es werden keine Beziehungskanten erstellt ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)`: beobachtet als organisationsbeschränkt
  (`403 NOT_ORG_MEMBER`) für die getesteten Konten.
- `thread/request-access-info`: getestet als organisationsbeitrittsbezogen, kein
  `threadAccess`-Signal.
- Billing/Stripe/Enterprise- und Finanz-/Sport-Verticals bleiben außerhalb des
  Anwendungsbereichs des Archivierungswerkzeugs.

---

*Dieses Dokument ergänzt [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md) (Werkzeugarchitektur) und [overview.md](../../architecture/overview.md) (Systemdesign).*
