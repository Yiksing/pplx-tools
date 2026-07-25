---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/index.md"
translation_source_sha256: "ca4f72f6b2dd481ccfbaebc2b4a1c807271077753873ce318b60d94c60f54228"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-reference" data-pplx-source-anchor="true"></a>
# Web-API-Referenz

Beobachtetes Perplexity REST- und GraphQL-Verhalten, das von `pplx-export` und
`pplx-ask` verwendet wird.

!!! warning "Beobachtete Schnittstelle, keine Stabilitätsgarantie"

    Diese Seiten beschreiben das Verhalten, das das Projekt aus der Webanwendung,
    archivierten Antworten, Frontend-Bundles und der aktuellen Implementierung
    beobachtet hat. Sie stellen keinen offiziellen Perplexity-API-Vertrag dar. Datterte
    Beobachtungen sollten vor Änderungen an netzwerkorientiertem Code erneut validiert werden.

<a id="reading-order" data-pplx-source-anchor="true"></a>
## Lesereihenfolge

1. [Authentifizierungsmodell](api-authentication.md) — Sitzungscookies, Tokens,
   verknüpfte Konten und Identität.
2. [GraphQL](api-graphql.md) — persistierte Abfragen, APQ-Identifikatoren und
   verwendete Operationen.
3. [REST-Endpunkte](api-rest-endpoints.md) — beobachtete Endpunkte, gruppiert nach
   Zweck.
4. [Antworten und Fehlersemantik](api-responses-errors.md) — Antwortstrukturen,
   Parsing-Regeln, Endzustände und Risikokontrollverhalten.
5. [Erkennungsmethoden und Fahrplan](api-discovery-roadmap.md) — wie Endpunkte
   gefunden werden und welche Unsicherheiten bestehen.

<a id="related-implementation-documents" data-pplx-source-anchor="true"></a>
## Verwandte Implementierungsdokumente

- [pplx-ask und Konten](../../architecture/ask-and-accounts.md)
- [Ratenbegrenzung und Fehlerbehandlung](../../architecture/rate-limiting-errors.md)
- [Fehlerbehebung](../../guide/troubleshooting.md)
