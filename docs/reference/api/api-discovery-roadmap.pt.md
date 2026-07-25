---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-discovery-roadmap.md"
translation_source_sha256: "60c675dcc583c059cd489ea085f9c2923f9447f7bbafb0a7ac991fee9f8add08"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="endpoint-discovery-and-improvement-roadmap" data-pplx-source-anchor="true"></a>
# Roteiro de Descoberta e Melhoria de Endpoints

*Parte da referência da API web Perplexity — mapa completo no [índice da API](index.md).*

<a id="known-unexplored-tbd-items" data-pplx-source-anchor="true"></a>
## Itens conhecidos não explorados / TBD

- Campo de ordenação `list_collection_threads` e semântica exata de `total_threads`
  (instantâneo de conta ativa em julho de 2026: relatados 99 vs 27 itens de nível superior).
- Espectro completo de valores `threadAccess`/`access`/`user_permission` (amostra
  observada em julho de 2026: threadAccess 5 normal, 1 com 🔒; collection access 1;
  permission 4 owner / 2 can edit; dados de assets também carregam thread_access).
- Formatos de parâmetros corretos para `list_ask_threads`, `list_scheduled_computer_tasks` (GET direto retorna 400).
- Estruturas de resposta de `collections/*/request-access-info`, `spaces/<uuid>/recurring_tasks`, `assets/<id>/members`.
- Por que as operações GraphQL do painel não estão registradas (PERSISTED_QUERY_NOT_FOUND): divergência de versão ou bloqueio de contexto;
  quando necessário, reextrair com hashes ativos a partir da captura de rede.
- Divisão de trabalho entre `frontend_uuid` vs `uuid` vs `context_uuid` em threads de computador.
- Campos de sinal da API de threads de ramificação compartilhadas entre contas (branch_of)
  (ponteiro pai / marcador de ramificação) — mecanismo confirmado (final de
  [§3.3](api-rest-endpoints.md)); nenhuma instância arquivada em 23 de julho de 2026;
  verificar e registrar quando a primeira aparecer.

<a id="endpoint-discovery-method-frontend-bundle-static-analysis-zero-api-cost-established-2026-07-20" data-pplx-source-anchor="true"></a>
## Método de descoberta de endpoints: análise estática do bundle do frontend (custo zero de API; estabelecido em 20 de julho de 2026)

Descobertos **147 endpoints `/rest/`** em uma passada; o método é reutilizável (reexecutar após reformulações do frontend):

1. O ponto de entrada de carregamento de página `_spa/assets/index.html-*.js` referencia `bootstrap-*.js` (o runtime contém todos os mapeamentos de chunks);
2. Extrair 682 nomes de chunks (padrão `<name>-<hash8>.js`) do bootstrap; filtrar os relacionados à API pelo nome
   (client/api/thread/collection/space/computer…);
3. Baixar diretamente do CDN público `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js`
   (nenhum cookie necessário); módulos hub: `platform-core-*` (cliente da API), `spa-shell-*`, `spa-metadata-*`;
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` produz a lista de endpoints (147);
5. Os chunks também revelam formas de chamada (ex.: `format:'md'` e `file_content_64` da exportação).
6. Sourcemaps também existem: `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (não explorado).

<a id="appendix-147-endpoints-grouped-by-category-archive-relevance-marked" data-pplx-source-anchor="true"></a>
### Apêndice: 147 endpoints agrupados por categoria (relevância para arquivamento marcada)

- **thread**: `/rest/thread/{entry_uuid_or_slug}`, `/rest/thread/export`★, `/rest/thread/{uuid}/members`,
  `/rest/thread/list_recent`, `/rest/thread/list_ask_threads`, `/rest/thread/list_pinned_ask_threads`,
  `/rest/thread/list_scheduled_computer_tasks`, `/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★: veja a tabela completa na [§3.3](api-rest-endpoints.md) (incl. batch_move/batch_remove, list_user_collections, request-access-info,
  recurring_tasks, pins/threads, scheduled_threads)
- **assets**★: `/rest/assets/{asset_id}/data`, `/rest/assets/{asset_id}/members`,
  `/rest/assets/{asset_id}/published-access`, `/rest/assets/sites/{site_id}/publish-info`
- **analytics**: `/rest/analytics/computer/usage`, `/rest/analytics/computer/usage/members`
  (ambos 403 NOT_ORG_MEMBER — apenas contas organizacionais)
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
- **verticais** (irrelevantes para arquivamento): `/rest/finance/*`, `/rest/sports/*`, `/rest/travel/hotels/{slug}`,
  `/rest/health-assistant/*`, `/rest/article/{uuid_or_slug}`
- **misc**: `/rest/pins`, `/rest/rate-limit/(all|status)`, `/rest/notifications/web-push/*`,
  `/rest/attribution/*`, `/rest/homepage-widgets/upsell`, `/rest/ntp/upsell/`, `/rest/sidebar/upsell/`,
  `/rest/incentives/comet-activation`, `/rest/connector-service/usage`

(★ = diretamente relevante para arquivamento)

<a id="endpoint-tool-capability-status-and-roadmap" data-pplx-source-anchor="true"></a>
## Status de endpoint → capacidade da ferramenta e roteiro

O status de implementação abaixo foi sincronizado com o código atual e o conjunto
 de testes em **24 de julho de 2026**. As evidências da API mantêm a data e o escopo da observação
 ao vivo original ou da análise estática; esta sincronização da documentação não reexaminou
 endpoints privados. As contagens de conta/arquivo são instantâneos, não garantias
 de toda a plataforma.

Significados dos status:

- **Implementado** — um caminho atual da CLI ou de produção usa o endpoint para a
  capacidade declarada.
- **Parcial** — o endpoint está em uso, mas a capacidade downstream no
  roteiro permanece incompleta.
- **Testado, não integrado** — o comportamento da API ao vivo foi observado, mas nenhum
  caminho da ferramenta o consome.
- **Planejado** — existem evidências, mas a implementação não foi iniciada.
- **Bloqueado** — um bloqueador upstream ou de protocolo conhecido impede a implementação.
- **Fechado** — as evidências refutaram o uso proposto ou o colocaram fora do escopo.

<a id="capability-status-matrix" data-pplx-source-anchor="true"></a>
### Matriz de status de capacidade

| Endpoint / operação | Base de verificação | Integração atual | Status | Lacuna restante |
|---|---|---|---|---|
| `collections/get_collection` | observação ao vivo + código atual | `spaces --fetch-meta` constrói o índice de proprietário/membro do espaço | **Implementado** | — |
| `collections/list_collection_threads` | observação ao vivo + código atual | `space-index` usa REST por padrão com mapeamento de ID duplo context_uuid; WebBridge é fallback | **Implementado** | Ordem de classificação e semântica exata de `total_threads` permanecem TBD |
| `assets/<uuid>/data` | testado ao vivo em 20/07/2026 + código atual | `assets-backfill --online` atualiza URLs assinados para UUIDs de assets reais | **Implementado** | Handles de espaço de trabalho em nuvem `toolu_` estão fora da cobertura deste endpoint |
| `LibraryThreadsRelayQuery` e consulta de paginação | APQ capturado + código atual | `index`/`batch` fornecem indexação completa e parada antecipada incremental | **Implementado** | Consultas de filtro de modo do painel permanecem bloqueadas separadamente |
| `collections/list_user_collections` | observado ao vivo em julho de 2026 + código atual | `init` usa uma correspondência exata de título para descobrir o espaço BOT | **Parcial** | Construir um registro de espaço de conta autoritativo para descoberta de novos espaços e reconstrução de `spaces` |
| `credits/thread-usage` | testado ao vivo em 20/07/2026 + código atual | `usage-backfill` escreve `index/credit_usage_<account>.json` | **Parcial** | Decidir se enriquece `thread.json` e/ou linhas do índice da biblioteca sem duplicar autoridade |
| `models/config/v2` | testado ao vivo em 21/07/2026 + código atual | `pplx-ask models` lista modelos/padrões; constantes de normalização são verificadas contra ele | **Parcial** | Persistir metadados estáveis de exibição de modelo em registros de arquivo/índice se útil |
| `POST /rest/thread/export` | md/pdf/docx testado ao vivo em 20/07/2026 | nenhuma integração com CLI | **Testado, não integrado** | Arquivamento em vários formatos e reconciliação de Markdown oficial |
| `rate-limit/status` | observação de carregamento de página; semântica de resposta inexplorada | nenhum | **Planejado** | Validar semântica antes de usar para limitação adaptativa |
| `file-repository/list-files` | apenas análise estática do frontend | nenhum | **Planejado** | Validar se pode enumerar/resgatar handles `toolu_`; um instantâneo de arquivo de julho de 2026 registrou 270 handles sem um canal de download |
| `pins`, `tasks/{id}` | análise estática do frontend / observações de carregamento de página | nenhum | **Planejado** | Enriquecimento de estado e duração de tarefa de computador |
| `thread/<uuid>/members` | testado ao vivo em julho de 2026 | nenhum | **Planejado** | Arestas de compartilhamento em nível de thread para o grafo de relações |
| GraphQL do painel `threadGroup` + filtros de modo | chamadas diretas retornaram `PERSISTED_QUERY_NOT_FOUND` | nenhum | **Bloqueado** | Recuperar hashes de consulta persistida ao vivo ou estabelecer o contexto necessário |
| `related_queries` / `sse/related-queries` | investigações forenses em todo o arquivo encerradas em 23/07/2026 | deliberadamente não produz arestas de relação | **Fechado** | Reabrir apenas se novas evidências estabelecerem identidade de thread resolvível |

<a id="active-roadmap" data-pplx-source-anchor="true"></a>
### Roteiro ativo

<a id="p0-official-export-integration" data-pplx-source-anchor="true"></a>
#### P0 — Integração de exportação oficial

- **Arquivamento em vários formatos**: opcionalmente reter produtos PDF/DOCX retornados por
  `POST /rest/thread/export`.
- **Reconciliação de renderizador**: comparar o Markdown oficial de thread inteira com
  `conversation.md` como um sinal de regressão independente.

<a id="p1-space-discovery" data-pplx-source-anchor="true"></a>
#### P1 — Descoberta de espaços

- Promover `list_user_collections` de pesquisa por título BOT para um registro de espaço
  autoritativo e com escopo de conta, usado para descoberta de novos espaços e reconstrução
  de `spaces`.

<a id="p2-metadata-risk-control-and-asset-rescue" data-pplx-source-anchor="true"></a>
#### P2 — Metadados, controle de risco e resgate de assets

- Decidir e documentar o limite de autoridade para uso de crédito: manter o
  `credit_usage_<account>.json` dedicado, ou também enriquecer `thread.json` /
  linhas da biblioteca.
- Adicionar metadados de exibição de modelo, estado de pin, duração de tarefa de computador e relações
  de compartilhamento de thread apenas onde a semântica do endpoint for estável.
- Validar `rate-limit/status` antes de projetar limitação adaptativa.
- Testar `file-repository/list-files` como um possível caminho de resgate de `toolu_` antes de
  adicionar qualquer mutação no arquivo.

<a id="p3-blocked-discovery" data-pplx-source-anchor="true"></a>
#### P3 — Descoberta bloqueada

- Recapturar os hashes de consulta persistida do GraphQL do painel apenas se a indexação
  incremental por modo se tornar valiosa o suficiente para justificar o custo
  de manutenção.

<a id="closed-decisions-not-adopted" data-pplx-source-anchor="true"></a>
### Decisões fechadas / não adotadas

- **Exportação oficial como fonte de relatório**: refutada. O endpoint retorna
  Markdown de thread inteira sem o corpo do relatório; a cadeia de URL assinada permanece
  a fonte oficial para `report.md` ([§3.6](api-rest-endpoints.md)).
- **Relações de `related_queries`**: refutado em 23/07/2026. UUIDs de itens não são
  UUIDs de thread e os textos de recomendação não foram resolvidos para consultas arquivadas;
  nenhuma aresta de relação é construída ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)`: observado como apenas para organizações
  (`403 NOT_ORG_MEMBER`) para as contas testadas.
- `thread/request-access-info`: testado como relacionado a ingresso em organização, não um
  sinal de `threadAccess`.
- Verticais de faturamento/Stripe/empresas e finanças/esportes permanecem fora do
  escopo da ferramenta de arquivo.

---

*Este documento complementa [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md) (arquitetura da ferramenta) e [overview.md](../../architecture/overview.md) (design do sistema).*
