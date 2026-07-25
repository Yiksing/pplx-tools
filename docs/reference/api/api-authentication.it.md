---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-authentication.md"
translation_source_sha256: "dc9067f0d08c997245ee548a335fc762ad0cbe986661ba0ad7f976150131dd72"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="authentication-model" data-pplx-source-anchor="true"></a>
# Modello di autenticazione

> Questa pagina introduce l'area di riferimento API — il record collaudato sul campo del progetto pplx_export dell'API web privata di Perplexity.
> Destinatari: manutentori e utenti di questo progetto. Tutti gli endpoint sono stati verificati tramite cattura di rete WebBridge + richieste dirette autenticate con cookie (2026-07).
> **Qualsiasi modifica o aggiunta alla conoscenza dell'API deve essere sincronizzata in queste pagine** (requisito esplicito dell'utente).
> Ultimo aggiornamento: 2026-07-23
>
> L'area di riferimento è suddivisa in: **1. Modello di autenticazione** (questa pagina) · [2. GraphQL (query persistenti / APQ)](api-graphql.md) · [3. Endpoint REST (raggruppati per scopo)](api-rest-endpoints.md) · [4–5. Struttura delle risposte e semantica degli errori](api-responses-errors.md) · [6–8. Elementi TBD, scoperta degli endpoint e roadmap](api-discovery-roadmap.md) — per il design di sistema circostante, consultare la [mappa di lettura dell'architettura](../../architecture/index.md).

---

<a id="authentication-model_1" data-pplx-source-anchor="true"></a>
## Modello di autenticazione

<a id="cookie-session" data-pplx-source-anchor="true"></a>
### Sessione cookie
- Tutte le richieste API necessitano solo del cookie di sessione del browser (nessun token CSRF richiesto; sia GET che POST verificati funzionanti tramite richieste dirette).
- Cookie chiave: `__Secure-next-auth.session-token` (token di sessione dell'**account attualmente attivo**).
- Cloudflare è posizionato davanti: `cf_clearance`/`__cf_bm` sono legati all'impronta digitale TLS del browser — **le richieste curl nude ottengono 403**;
  lo strumento passa con Python urllib + cookie importati dal browser (UA mascherato come Chrome desktop).

<a id="multi-account-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Multi-account (scoperto il 2026-07-20)
- Quando più account sono loggati nello stesso browser, ogni account possiede il proprio cookie `__Secure-pplx.session.<user_id>`
  (dominio www.perplexity.ai; il valore avanza con le risposte).
- Il valore di `__Secure-next-auth.session-token` = il valore del cookie per account dell'account attivo.
- **Cambiare account sul web** = navigare a `https://www.perplexity.ai/?pplx_account=<user_id>`; il server riscrive il token attivo.
- **Cambio automatico lato strumento** (implementato in pplx_export): enumerare i cookie `__Secure-pplx.session.*` del browser,
  sostituire `__Secure-next-auth.session-token` con ciascuno a turno, e sondare `/api/auth/session` finché l'email target corrisponde.
- `GET /api/auth/linked-accounts` restituisce `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`,
  ma **restituisce l'elenco completo degli account solo mentre l'account primario è attivo** (solo l'account corrente quando un account non primario è attivo) — quindi lo strumento non si basa su di esso.
- Esempi di account registrati (la tabella reale degli account risiede in `config.toml` a livello utente; segnaposto mostrati qui):
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa` (Max);
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb` (Pro, primario).
