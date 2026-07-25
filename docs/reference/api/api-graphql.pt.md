---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-graphql.md"
translation_source_sha256: "3963e26d58d8dc1ad0835fe715357592295f31dd7c3b7c3f1ca67854fa3c98a0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-graphql" data-pplx-source-anchor="true"></a>
# Referência da API: GraphQL

<a id="graphql-persisted-queries-apq" data-pplx-source-anchor="true"></a>
## GraphQL (consultas persistentes / APQ)

- **Endpoint**: `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **Forma**: consulta persistente — o corpo carrega operationName + variáveis + um hash sha256 (nenhum texto de consulta necessário).
- Implementação: `pplx_export/sites/perplexity/graphql.py`.

<a id="librarythreadsrelayquery-list-first-page" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery (listar primeira página)
- sha256: `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- Variáveis: `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- Caminho da resposta: `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- Campos do nó (usados pelo adaptador): `name(title)`, `entryId(entryUUID)`, `slug(href)`, `mode`, `displayModel.modelID`,
  `updatedAt(lastUpdated)`, `status`, `space{spaceUuid,title,slug}`
- **Contrato do lado do arquivo (2026-07-22 V5-01)**: o `lastUpdated` de `web_archive/**/thread.json` é sempre igual a este campo
  (escrito em disco com precisão ISO completa, verbatim); a comparação de idempotência de exportação em lote/única (`is_unchanged`) é baseada nele,
  não mais no formato de apresentação da camada de renderização (`YYYY-MM-DD HH:MM UTC`).
- **Enriquecimento do lado do arquivo (2026-07-23)**: a chave `search_mode` das linhas de índice (`index/library_*.json`) é um
  campo de enriquecimento do lado do arquivo — o nó desta consulta não contém search_mode; ele é preenchido por `pplx-export search-mode-backfill`
  a partir de dados no nível do thread (`entries[].search_mode` de `GET /rest/thread/<uuid>`) (primeiro raw local,
  fallback online); a atualização `index` mescla e preserva por entryUUID. A filtragem `batch --mode` prefere o mapeamento autoritativo deste campo.

<a id="libraryrecentthreadspaginationquery-pagination" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery (paginação)
- sha256: `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- Variáveis: variáveis da primeira página + `{cursor, count}` (**os nomes das variáveis são cursor/count, não after/first**)
- Mesma estrutura de resposta acima. Quando `hasNextPage` é verdadeiro mas `endCursor` está vazio, pare (caso contrário, a mesma página se repete).

<a id="computer-dashboard-operation-group-extracted-from-route-chunk-2026-07-20-not-registered-on-the-server" data-pplx-source-anchor="true"></a>
### Grupo de operações do painel do Computer (extraído do chunk de rota 2026-07-20, **não registrado no servidor**)

O chunk `ComputerDashboardPage-*.js` incorpora textos completos de consultas Relay + ids persistentes (método de extração em [§7](api-discovery-roadmap.md)).
Essenciais estruturais: `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— ou seja, uma lista de threads filtrada por threadGroup + mode; o nó contém `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`.

| operação | id persistente (primeiros 16 caracteres) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (assinatura WebSocket) |

**Testado**: chamar `/rest/perplexity_ask/graphql` com esses ids retorna `PERSISTED_QUERY_NOT_FOUND`
(não registrado na implantação atual — diferença de versão ou contexto do painel necessário; os textos completos das consultas e ids são mantidos nas notas de exploração `/tmp`;
se necessário, envie o texto da consulta diretamente ou reextraia do bundle ativo).

<a id="notes" data-pplx-source-anchor="true"></a>
### Notas
- Nenhuma chamada graphql observada na página de espaço web ou página inicial (todas passam por /rest); graphql é confirmado para a lista /library e o painel do Computer.
- Os hashes sha256 podem mudar com as versões do frontend; o modo de falha é `PERSISTED_QUERY_NOT_FOUND` — então reextraia da captura de rede do navegador
  (ferramenta WebBridge `network` filtrando `perplexity_ask/graphql`), ou reextraia do bundle ativo ([§7](api-discovery-roadmap.md)).

<a id="extracted-dashboard-connection-keys-relay-cache-keys-for-debugging" data-pplx-source-anchor="true"></a>
### Chaves de conexão do painel extraídas (chaves de cache Relay, para depuração)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
