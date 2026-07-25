---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/index.md"
translation_source_sha256: "ca4f72f6b2dd481ccfbaebc2b4a1c807271077753873ce318b60d94c60f54228"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-reference" data-pplx-source-anchor="true"></a>
# Referência da API Web

Comportamento observado de REST e GraphQL Perplexity usado por `pplx-export` e
`pplx-ask`.

!!! warning "Interface observada, não uma garantia de estabilidade"

    Estas páginas descrevem o comportamento que o projeto observou da aplicação
    web, respostas arquivadas, pacotes frontend e a implementação atual. Elas
    não são um contrato oficial da API Perplexity. Observações datadas
    devem ser revalidadas antes de alterar código voltado para rede.

<a id="reading-order" data-pplx-source-anchor="true"></a>
## Ordem de leitura

1. [Modelo de autenticação](api-authentication.md) — cookies de sessão, tokens,
   contas vinculadas e identidade.
2. [GraphQL](api-graphql.md) — consultas persistidas, identificadores APQ e
   operações em uso.
3. [Endpoints REST](api-rest-endpoints.md) — endpoints observados agrupados por
   finalidade.
4. [Respostas e semântica de erros](api-responses-errors.md) — formatos de resposta,
   regras de análise, estados terminais e comportamento de controle de risco.
5. [Métodos de descoberta e roteiro](api-discovery-roadmap.md) — como os endpoints
   são encontrados e quais incertezas permanecem.

<a id="related-implementation-documents" data-pplx-source-anchor="true"></a>
## Documentos de implementação relacionados

- [pplx-ask e contas](../../architecture/ask-and-accounts.md)
- [Limitação de taxa e tratamento de erros](../../architecture/rate-limiting-errors.md)
- [Solução de problemas](../../guide/troubleshooting.md)
