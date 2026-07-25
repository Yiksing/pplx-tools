---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/maintenance-commands.md"
translation_source_sha256: "550aca319a6386123658e8d54ede5367bc97765c9a11710e20f1ed1f2854f617"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintenance-commands" data-pplx-source-anchor="true"></a>
# Wartungsbefehle

`pplx-export`-Wartungsunterbefehle halten ein vorhandenes Archiv gesund: Seiten nach Renderer-Korrekturen neu rendern, Assets/Nutzungs-/Modusmetadaten nachträglich befüllen, remote gelöschte Threads als gelöscht markieren und den Beziehungsgraphen neu aufbauen. Die meisten sind offline-first; ihre Online-Phasen folgen derselben Taktungsdisziplin wie `batch` (siehe [rate-limiting.md](rate-limiting.md)). Alle akzeptieren die [gemeinsamen Optionen](pplx-export.md) (`--account`, `--out`, `--cookies-from`, `--transport`, …).

- Prinzip der lokalen Archivaufbewahrung: Kein Wartungsbefehl löscht oder verschiebt jemals archivierte Thread-Inhalte – das Archiv ist die Sicherung.
- Die Offline-Befehle (`re-render`, `relations`, `sync-space`, `spaces` ohne `--fetch-meta` und die Standardphasen unten) benötigen überhaupt keinen Transport; siehe [../architecture/offline-operations.md](../architecture/offline-operations.md).

## re-render

`conversation.md` und `turns/` aus dem archivierten rohen JSON (`raw_entries.json` / `raw_blocks.json`) nach Renderer-Korrekturen neu generieren – kein Netzwerk, und jede andere Datei bleibt unberührt.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--limit N` | Nur die ersten N Thread-Verzeichnisse verarbeiten | alle |
| `--dry-run` | Die zu verarbeitenden Verzeichnisse auflisten, nichts schreiben | aus |
| `--thread-json` | Auch die Schlüssel `interruptions` und `answer_variants` in `thread.json` an Ort und Stelle hinzufügen/entfernen | aus |

Wichtige Verhaltensweisen:

- Baut Züge offline mit derselben Pipeline wie der Export neu auf: Parsen, Sortieren nach `created_us`, Zitationsdeduplizierung und – für Computer/Council – Workflow-Blöcke, Sub-Agent-Zuordnung und den Anhang für nicht verbrauchte Hintergründe.
- Nur `conversation.md` und `turns/turn_*.md` werden (neu) geschrieben; `sources*`, `assets/`, `report.md` und `thread.json` bleiben unverändert. Veraltete `turn_*.md`-Dateien, deren Nummer über der aktuellen Zuganzahl liegt, werden gelöscht – sonst nichts, sodass unveränderte Dateien ihre mtime behalten.
- `--thread-json` schreibt nur, wenn sich der Inhalt tatsächlich ändert; neu hinzugefügte/geänderte `answer_variants` lösen eine `ANSWER_VARIANT_DETECTED`-Warnung aus und werden an `index/answer_variants_log.jsonl` angehängt (idempotente Wiederholungen spammen nicht).
- Thread-Verzeichnisse ohne `raw_entries.json` werden übersprungen und gezählt.

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

Behebt Assets, die ohne signierte URL archiviert wurden – drei gestaffelte Abhilfemaßnahmen: erneutes Abrufen fehlender Blöcke, Offline-Inline-Extraktion und optionales Online-Refresh.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--fetch-blocks` | Zuerst fehlende `raw_blocks.json` und deren signierte URL-Assets erneut abrufen (online) | aus |
| `--online` | Online-Refresh fehlender/veralteter Assets aktivieren | aus (nur Offline-Inline-Extraktion, null Anfragen) |
| `--limit N` | Nur die ersten N Thread-Verzeichnisse verarbeiten | alle |

Wichtige Verhaltensweisen:

- Standardphase (offline, null Anfragen): Extrahiert Inline-Assets (`ASSET_DIFF` / `CODE_ASSET`) aus `raw_blocks.json` in `assets/files/*.md` und registriert Cloud-Workspace-Handle-Arten (`DOC_FILE` / `CODE_FILE` / `UNKNOWN` – noch kein Download-Kanal) in `assets/assets_manifest.json`. Idempotent: bekannte Datensätze werden nach UUID, dann file_handle dedupliziert; Dateien mit mehreren Versionen und gleichem Namen erhalten einen kurzen UUID-Suffix, sodass Wiederholungen nicht kollidieren.
- `--fetch-blocks` (online): Fehlende `raw_blocks.json` für Deep-Research/Computer/Council/Study-Threads sowie deren herunterladbare Assets erneut abrufen; Threads werden nach Kontoverzeichnissen gruppiert mit einem lazy erstellten Adapter pro Konto (Cookies wechseln automatisch), 3s zwischen Threads.
- `--online`: Für Manifest-Versionen, deren `downloaded_to` fehlt/veraltet ist, eine frische signierte URL über `/rest/assets/<uuid>/data` abrufen (API-Aufrufe seriell, 3s Abstand), dann vom CDN erneut herunterladen (6 gleichzeitige Threads, keine Verzögerung – CDN, nicht API). Ein 404 `ASSET_NOT_FOUND` setzt das terminale Flag `asset_expired`; ein kontenübergreifender 403 wird einmalig mit dem Konto wiederholt, das das Archivverzeichnis besitzt.
- Das Manifest `count` wird bei jedem Rückschreiben als Gesamtzahl der Versionen neu berechnet.

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

Füllt die Nutzung pro Thread (`credits/thread-usage`) für alle archivierten Threads des Kontos in `index/credit_usage_<account>.json` nachträglich ein.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--limit N` | Nur die ersten N Threads verarbeiten | alle |

Wichtige Verhaltensweisen:

- Ein GET pro archiviertem Thread (`thread_id` = die `psc_uuid` des Threads), 3s Abstand; idempotent – bereits in der Ausgabedatei vorhandene Threads werden übersprungen.
- Ein 403 (`thread_usage_forbidden`, d.h. ein kontenübergreifender Thread) wird als `error` aufgezeichnet und nie wiederholt; andere Fehler werden für den nächsten Lauf belassen. Der Fortschritt wird alle 25 verarbeiteten Threads gespeichert.
- Mehrere Konten: Einmal pro Konto mit `--account` ausführen – die Cookies wechseln zwischen den Läufen automatisch.

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

Füllt das plattformautoritative Feld `search_mode` in jede Zeile von `index/library_<account>.json` nachträglich ein, sodass `batch --mode` exakt filtern kann, anstatt auf Heuristiken angewiesen zu sein.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--limit N` | Nur die ersten N ausstehenden Zeilen verarbeiten | alle |
| `--offline` | Nur lokale Extraktion – Zeilen ohne lokale Rohdaten warten auf die nächste Runde, kein Online-Fallback | aus |
| `--delay-min SEC` | Untere Grenze des zufälligen Intervalls zwischen Online-Fallback-Threads | `10` |
| `--delay-max SEC` | Obere Grenze des zufälligen Intervalls zwischen Online-Fallback-Threads | `20` |

Wichtige Verhaltensweisen:

- Speichert den rohen Plattformwert (`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…); ein Thread mit mehreren Werten behält den spezifischsten gemäß computer > council > study > deep-research > search.
- Local-first: Archivierte Threads werden aus `raw_entries.json` ohne Netzwerk aufgelöst – ein vollständig lokaler Lauf baut nicht einmal einen Transport auf (nicht einmal einen Session-Probe).
- Online-Fallback nur für Zeilen ohne lokale Rohdaten: `GET /rest/thread/<uuid>` mit einem zufälligen Intervall von 10–20s; Zeilen im terminalen Zustand `expired` werden übersprungen und aufgezeichnet; Threads, die online neu als abgelaufen/gelöscht gefunden werden, werden in `batch_state.json` markiert, um zukünftige Anfragen zu sparen.
- Idempotent und fortsetzbar: Zeilen, die bereits `search_mode` haben, werden übersprungen, der Fortschritt wird alle 25 Zeilen gespeichert, und spätere `index`-Aktualisierungen bewahren die Anreicherung (zurückgeführt durch `entryUUID`).

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

Identifiziert Threads, die aus der entfernten Bibliothek verschwunden sind (vom Benutzer oder der Plattform gelöscht), und markiert sie als gelöscht – es löscht oder verschiebt niemals eine Archivdatei.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--online` | Jeden Kandidaten online überprüfen | aus (Offline-Trockenlauf: nur Kandidaten auflisten) |
| `--limit N` | Nur die ersten N Kandidaten verarbeiten | alle |
| `--delay-min SEC` | Untere Grenze des zufälligen Intervalls zwischen Kandidaten | `10` |
| `--delay-max SEC` | Obere Grenze des zufälligen Intervalls zwischen Kandidaten | `20` |

Wichtige Verhaltensweisen:

- Die Kandidatenerkennung erfolgt offline und kontenübergreifend: Ein Thread mit `batch_state`-Status `ok`, der in der `entryUUID`-Vereinigung **aller** `index/library_*.json`-Dateien fehlt, wird zum Kandidaten – jeder einzelne Index, der ihn enthält, zählt als lebendig, sodass Threads, die kontenübergreifend über gemeinsame Bereiche exportiert wurden, nicht fälschlich positiv sind. Wenn kein brauchbarer Index existiert, wird alles sicher mit einem Hinweis übersprungen, zuerst `index` auszuführen.
- Standard ist ein Offline-Trockenlauf: Er listet Kandidaten und sichere Überspringungsgründe auf – null Netzwerk, null Schreibvorgänge.
- `--online` überprüft jeden Kandidaten mit `GET /rest/thread/<uuid>` unter dem in `thread.json` `export_via` aufgezeichneten Konto (Cookies wechseln automatisch pro Kandidat).
- Bestätigt durch `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 → `batch_state` markiert den terminalen Zustand `deleted` (gleiche Semantik wie `expired`: nie wiederholt, `--force` exportiert nicht erneut; siehe [incremental-sync.md](incremental-sync.md)) und jede der `thread.json`-Dateien des Threads erhält einen `remote_deleted`-Zeitstempel an Ort und Stelle (idempotent – ein vorhandener Schlüssel bleibt erhalten).
- Thread existiert noch → falsch positiv: wird wie besehen gemeldet mit einem Hinweis, `index` erneut auszuführen, nichts geändert. Transportfehler warten auf die nächste Runde; 3 aufeinanderfolgende Authentifizierungsfehler brechen den Lauf ab, bevor etwas falsch markiert wird.

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

Der erste Lauf listet Kandidaten auf (Offline-Trockenlauf); der zweite überprüft sie online und markiert die bestätigten als gelöscht.

## status

Gibt den Archivzustand des Kontos und den inkrementellen Änderungsplan aus – null Netzwerk, schreibgeschützt. Es beantwortet „Wie sieht das Archiv gerade aus und was würde der nächste `batch`-Lauf tun“, ohne das Netzwerk zu berühren.

| Flag | Bedeutung | Standard |
|---|---|---|
| `--account X` | Nur über ein Konto berichten | alle Konten, die eine `index/library_*.json`-Datei haben |
| `--json` | Vollständiger maschinenlesbarer Bericht auf stdout (ignoriert Ausführlichkeit) | aus (menschliche Logzeilen) |

Wichtige Verhaltensweisen:

- Datenquellen sind rein lokal: `index/library_*.json` (pro-Konto-Indexzeilen) und `index/batch_state.json` (die einzige Quelle für Exportzustände). Die Änderungsklassifizierung verwendet dieselbe `plan_incremental`-Reinfunktion wie `batch`/`schedule`, sodass die Semantik von `new`/`updated`/`done`/`expired`/`deleted` identisch mit dem ist, was `batch` berechnen würde.
- Die Standard-INFO-Ausgabe gibt eine Zusammenfassungszeile pro Konto aus (Indexanzahl + Aktualität, `ok/expired/deleted/error`-Zustandszählungen, `new/updated`-Änderungszählungen und die Frühstoppzahl) plus eine globale `batch_state`-Kontenzeile (z.B. `559 ok + 13 expired + 12 deleted`).
- Detailstufen folgen dem standardmäßigen Ausführlichkeits-Flag: `-v` fügt die Titel von `new`/`updated`/`error`-Threads hinzu (erste Zeile, auf 60 Zeichen gekürzt); `-vv` fügt `done`/`expired`/`deleted`-Threads mit `lastUpdated`/`exported_at` hinzu; `-vvv` gibt alles ungekürzt mit Index-`mode`/`search_mode`-Feldern und der zustandsnur-Liste aus (Datensätze, die in `batch_state` vorhanden sind, aber im Index jedes Kontos fehlen – Kandidaten für Remote-Löschung, die mit [sync-deleted](#sync-deleted) abgeglichen werden müssen).
- Schutzmaßnahmen: Eine fehlende `index/` oder fehlende Bibliotheksdatei beendet das Programm mit einem Fehler, der auf `pplx-export index` verweist; eine fehlende `batch_state.json` wird als leerer Zustand behandelt (alles zählt als `new`). Es ist keine Benutzerkonfiguration erforderlich – Konten werden aus den Bibliotheksdateinamen aufgezählt.
- `--json` gibt den vollständigen Bericht (Konten, Änderungen, Threads, zustandsnur, Summen) als einzeiliges JSON auf stdout aus – derselbe Vertragsstil wie `pplx-ask`.

```bash
pplx-export status                 # summary for every account
pplx-export status -vv             # five-state thread details
pplx-export status --account alice --json
```

## relations

Baut den Konversationsbeziehungsgraphen aus den exportierten Threads neu auf → `relations/edges.jsonl` plus eine menschenlesbare `relations/graph.md` unter dem Archivstammverzeichnis.

| Flag | Bedeutung | Standard |
|---|---|---|
| *(nur gemeinsame Optionen; nur `--out` ist relevant)* | | |

Wichtige Verhaltensweisen:

- Rein offline, null Netzwerk, schreibgeschützt gegenüber dem Archiv: Es verwendet die Offline-Neubau-Pipeline von re-render (`raw_entries.json` / `raw_blocks.json`), sodass `sub_agents`, `query_source` und Zitationssignale alle für die Kantenerkennung verfügbar sind.
- Threads ohne Rohdaten degradieren zu einer `thread.json` + `conversation.md`-Hülle – nur `same_space`- und Bare-UUID-Referenzkanten können für sie ausgelöst werden.

```bash
pplx-export relations
```

## debug-js

Führt ein JavaScript-Snippet im aktuellen Browser-Seitenkontext über den lokalen WebBridge-Daemon (`127.0.0.1:10086`) aus und gibt das Ergebnis als JSON aus – eine Debugging-Notluke.

| Flag | Bedeutung | Standard |
|---|---|---|
| `JS代码` (positional) | JavaScript-Code, der im Seitenkontext ausgewertet werden soll (das wörtliche argparse-Metavar) | erforderlich |

Wichtige Verhaltensweisen:

- Erfordert, dass der WebBridge-Daemon erreichbar ist und die Ziel-Perplexity-Seite im Browser geöffnet ist; das Snippet läuft mit der eigenen Session der Seite.
- Das ausgegebene JSON wird auf 5000 Zeichen gekürzt.

```bash
pplx-export debug-js 'document.title'
```
