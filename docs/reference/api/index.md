# Web API reference

Observed Perplexity REST and GraphQL behavior used by `pplx-export` and
`pplx-ask`.

!!! warning "Observed interface, not a stability guarantee"

    These pages describe behavior the project observed from the web
    application, archived responses, frontend bundles, and the current
    implementation. They are not an official Perplexity API contract. Dated
    observations should be revalidated before changing network-facing code.

## Reading order

1. [Authentication model](api-authentication.md) — session cookies, tokens,
   linked accounts, and identity.
2. [GraphQL](api-graphql.md) — persisted queries, APQ identifiers, and
   operations in use.
3. [REST endpoints](api-rest-endpoints.md) — observed endpoints grouped by
   purpose.
4. [Responses and error semantics](api-responses-errors.md) — response shapes,
   parsing rules, terminal states, and risk-control behavior.
5. [Discovery methods and roadmap](api-discovery-roadmap.md) — how endpoints
   are found and which uncertainties remain.

## Related implementation documents

- [pplx-ask and accounts](../../architecture/ask-and-accounts.md)
- [Rate limiting and error handling](../../architecture/rate-limiting-errors.md)
- [Troubleshooting](../../guide/troubleshooting.md)
