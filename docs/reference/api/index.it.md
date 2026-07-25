---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/index.md"
translation_source_sha256: "ca4f72f6b2dd481ccfbaebc2b4a1c807271077753873ce318b60d94c60f54228"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-reference" data-pplx-source-anchor="true"></a>
# Riferimento API Web

Comportamento REST e GraphQL osservato di Perplexity utilizzato da `pplx-export` e
`pplx-ask`.

!!! warning "Interfaccia osservata, non una garanzia di stabilità"

    Queste pagine descrivono il comportamento che il progetto ha osservato dall'applicazione
    web, dalle risposte archiviate, dai bundle frontend e dall'implementazione
    corrente. Non costituiscono un contratto API ufficiale di Perplexity. Le osservazioni
    datate dovrebbero essere rivalidate prima di modificare il codice che interagisce con la rete.

<a id="reading-order" data-pplx-source-anchor="true"></a>
## Ordine di lettura

1. [Modello di autenticazione](api-authentication.md) — cookie di sessione, token,
   account collegati e identità.
2. [GraphQL](api-graphql.md) — query persistenti, identificatori APQ e
   operazioni in uso.
3. [Endpoint REST](api-rest-endpoints.md) — endpoint osservati raggruppati per
   scopo.
4. [Risposte e semantica degli errori](api-responses-errors.md) — forme delle risposte,
   regole di parsing, stati terminali e comportamento di controllo del rischio.
5. [Metodi di scoperta e roadmap](api-discovery-roadmap.md) — come vengono trovati
   gli endpoint e quali incertezze rimangono.

<a id="related-implementation-documents" data-pplx-source-anchor="true"></a>
## Documenti di implementazione correlati

- [pplx-ask e account](../../architecture/ask-and-accounts.md)
- [Limitazione della frequenza e gestione degli errori](../../architecture/rate-limiting-errors.md)
- [Risoluzione dei problemi](../../guide/troubleshooting.md)
