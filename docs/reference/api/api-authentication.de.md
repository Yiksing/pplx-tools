---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-authentication.md"
translation_source_sha256: "dc9067f0d08c997245ee548a335fc762ad0cbe986661ba0ad7f976150131dd72"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="authentication-model" data-pplx-source-anchor="true"></a>
# Authentifizierungsmodell

> Diese Seite führt in den API-Referenzbereich ein – die durch Feldtests erprobte Dokumentation des pplx_export-Projekts zur privaten Web-API von Perplexity.
> Zielgruppe: Betreuer und Nutzer dieses Projekts. Alle Endpunkte wurden mittels WebBridge-Netzwerkerfassung + direkten cookie-authentifizierten Anfragen verifiziert (2026-07).
> **Jede Änderung oder Ergänzung des API-Wissens muss in diese Seiten eingepflegt werden** (explizite Benutzeranforderung).
> Letzte Aktualisierung: 2026-07-23
>
> Der Referenzbereich ist unterteilt in: **1. Authentifizierungsmodell** (diese Seite) · [2. GraphQL (persistierte Abfragen / APQ)](api-graphql.md) · [3. REST-Endpunkte (nach Zweck gruppiert)](api-rest-endpoints.md) · [4–5. Antwortstruktur & Fehlersemantik](api-responses-errors.md) · [6–8. TBD-Punkte, Endpunkt-Erkennung & Roadmap](api-discovery-roadmap.md) — für das umgebende Systemdesign siehe die [Architektur-Lesekarte](../../architecture/index.md).

---

<a id="authentication-model_1" data-pplx-source-anchor="true"></a>
## Authentifizierungsmodell

<a id="cookie-session" data-pplx-source-anchor="true"></a>
### Cookie-Sitzung
- Alle API-Anfragen benötigen nur das Browser-Sitzungs-Cookie (kein CSRF-Token erforderlich; sowohl GET als auch POST wurden mittels direkter Anfragen verifiziert).
- Wichtiges Cookie: `__Secure-next-auth.session-token` (Sitzungstoken des **aktuell aktiven Kontos**).
- Cloudflare ist vorgeschaltet: `cf_clearance`/`__cf_bm` sind an den Browser-TLS-Fingerabdruck gebunden – **reine curl-Anfragen erhalten 403**;
  das Tool funktioniert mit Python-urllib + aus dem Browser importierten Cookies (UA als Desktop-Chrome getarnt).

<a id="multi-account-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Multi-Konto (entdeckt am 2026-07-20)
- Wenn mehrere Konten im selben Browser angemeldet sind, besitzt jedes Konto sein eigenes `__Secure-pplx.session.<user_id>`-Cookie
  (Domain www.perplexity.ai; der Wert wird mit den Antworten fortgeschrieben).
- Der Wert von `__Secure-next-auth.session-token` = der Wert des konto-spezifischen Cookies des aktiven Kontos.
- **Kontowechsel im Web** = Navigation zu `https://www.perplexity.ai/?pplx_account=<user_id>`; der Server überschreibt das aktive Token.
- **Automatischer Wechsel auf Tool-Seite** (implementiert in pplx_export): die `__Secure-pplx.session.*`-Cookies des Browsers auflisten,
  `__Secure-next-auth.session-token` nacheinander ersetzen und `/api/auth/session` abfragen, bis die Ziel-E-Mail übereinstimmt.
- `GET /api/auth/linked-accounts` gibt `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]` zurück,
  gibt aber **die vollständige Kontoliste nur zurück, wenn das primäre Konto aktiv ist** (nur das aktuelle Konto, wenn ein nicht-primäres Konto aktiv ist) – daher verlässt sich das Tool nicht darauf.
- Beispiele registrierter Konten (die eigentliche Kontotabelle befindet sich in der benutzerspezifischen `config.toml`; hier werden Platzhalter gezeigt):
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa` (Max);
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb` (Pro, primär).
