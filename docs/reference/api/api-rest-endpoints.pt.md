---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-rest-endpoints.md"
translation_source_sha256: "f1eb76feaffc48d910b988b54e4bcfcaa8b52a65502495399536392e4da7d146"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-rest-endpoints" data-pplx-source-anchor="true"></a>
# Referência da API: Endpoints REST

<a id="rest-endpoints-grouped-by-purpose" data-pplx-source-anchor="true"></a>
## Endpoints REST (agrupados por propósito)

Convenção: `?version=2.18&source=default` é a string de consulta comum (obrigatória na maioria dos endpoints).

<a id="thread-content-main-export-path" data-pplx-source-anchor="true"></a>
### Conteúdo do thread (caminho de exportação principal)
| Endpoint | Notas |
|---|---|
| `GET /rest/thread/<uuid>` | **Resposta simples**: `entries[]` (por turno; `text` contém todos os textos das etapas), `background_entries[]` (**fluxos completos de subagentes**), `thread_metadata`. Suporta paginação `?cursor=` (`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **Resposta esquematizada**: `entries[].blocks[]` (`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`), incluindo prompts de subagentes (`workflow_payload.objective_chunks`), URLs assinados de ativos, conteúdos de arquivos. Casos de uso em `rest.py:SCHEMATIZED_USE_CASES` (workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | Lista de threads recentes (barra lateral inicial; inclui o campo `unread`) |
| **`POST /rest/thread/mark_viewed`** | **Confirmação de leitura (descoberta em 2026-07-21)**: corpo `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`; não lido é alterado imediatamente. O frontend chama este endpoint quando um thread é aberto a partir da barra lateral. Nota: o evento de análise "thread viewed" **não altera** o estado de não lido (descartado por testes repetidos) |
| `GET /rest/thread/<uuid>/members` | **Membros de compartilhamento do thread** (testado): `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | Retorna `{"will_request_org_join": bool, "org_display_name": str|null}` — relacionado a ingresso em organização, **não relacionado à semântica de threadAccess** (descartado por testes) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | Presentes em análise estática; GET direto testado 400 (formato de parâmetro a determinar) |

<a id="asset-metadata-discovered-2026-07-20-lifesaver-for-expired-assets" data-pplx-source-anchor="true"></a>
### Metadados de ativos (descoberto em 2026-07-20, **salva-vidas para ativos expirados**)

- **`GET /rest/assets/<asset_uuid>/data`** → metadados completos do ativo (testado 200):
  - `asset_data.<type>.url` e `asset_data.download_info[].url`: **URLs assinados CloudFront atualizados** —
    se o URL assinado original expirou no momento do arquivamento, o endereço de download pode ser reobtido com o asset_uuid
    (desde que a plataforma não tenha removido o ativo);
  - também retorna `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    (cadeia de consulta reversa ativo → thread);
  - campos como `signed_url: null`, `read_write_token`, `allow_remix`.
- **Limites de aplicabilidade (testados)**: UUIDs de ativos reais funcionam; **handles de espaço de trabalho em nuvem com prefixo `toolu_` (DOC_FILE/CODE_FILE
  sem formato de URL) retornam 404 ASSET_NOT_FOUND**; `file-repository/download` requer um URL real e não aceita
  handles `file:repo/...` (400 falha ao analisar). Nenhum canal de download de API existe ainda para ativos do tipo toolu.
- Relacionados: `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access` (presentes em análise estática, não testados).
- Implementado: a ferramenta fornece `pplx-export assets-backfill` (extração inline + atualização online via este endpoint; veja a nota de ferramentas implementadas em [§4](api-responses-errors.md)).

- **ENTRY_EXPIRED**: threads/artefatos com mais de ~3 meses são removidos pela plataforma; as requisições retornam um corpo de erro específico — a ferramenta os marca como terminais e não tenta novamente.
- **Exclusão de thread (2026-07-23 WebBridge + pesquisa de chunk, testado)**:
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, corpo `{entry_uuid, read_write_token}`,
  sucesso `200 {"status":"success"}`; exclusão repetida é idempotente, ainda 200; excluir um uuid inexistente → 404 `THREAD_NOT_FOUND`;
  **aquisição de `read_write_token` (verificado na prática no mesmo dia)**: o primeiro `entries[].read_write_token` não vazio
  na resposta `GET /rest/thread/<uuid>` funciona (10/10 exclusões bem-sucedidas em threads ativos);
  **operações de escrita devem ir para o domínio www** (o domínio raiz retorna 301 para DELETE). Nenhuma mutação GraphQL, nenhum endpoint de exclusão em lote
  (a exclusão em lote da interface é um loop por item no frontend). A exclusão é destruição no nível do thread, irrecuperável; o thread desaparece automaticamente de seus espaços
  (não é necessário `batch_remove_collection_threads` primeiro).
  Opção suave: `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (corpo `{context_uuids:[...]}`; apenas análise estática, não testado).
- **ENTRY_DELETED**: após um thread ser excluído, `GET /rest/thread/<uuid>` retorna HTTP 400 `ENTRY_DELETED`
  (mesmo 400 que ENTRY_EXPIRED, mas um código diferente) — a ferramenta mapeia para `EntryDeletedError`
  (subclasse de `EntryExpiredError`); batch_state marca o estado terminal `deleted`.
- Cada entrada de turno carrega `context_uuid` (= o UUID `past_session_contexts` da plataforma — a chave para o mapeamento do namespace de ID duplo).

<a id="spaces-collections" data-pplx-source-anchor="true"></a>
### Espaços (coleções)
| Endpoint | Notas |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **Metadados do espaço**: `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. Valores de permissão observados: 4=proprietário, 2=pode editar. Quando a conta atual não tem acesso de visualização: `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` (HTTP ainda 200) |
| `POST /rest/collections/create_collection` | **Criar espaço** (2026-07-21 captura WebBridge, testado): corpo `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → retorna a coleção completa (uuid/slug/url/user_permission=4). O espaço BOT foi criado desta forma |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **Lista de threads do espaço (requisição direta de cookie; pode substituir o índice de espaço baseado no navegador)**: a resposta é um array; cada item tem `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview`, etc. **Paginação: `&offset=N` (20 por página)**; `has_next_page` está em cada item; `total_threads` lê alto (inclui sub-threads de computador; observado 99 vs 27 de nível superior) |
| `POST /rest/collections/batch_move_threads` | **Mover threads para um espaço** (testado com sucesso): corpo `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}` — **use context_uuid, não entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | Remover em lote de um espaço (corpo `{items:[{collection_uuid,...}]}`; não testado) |
| `GET /rest/collections/list_user_collections` | **Lista de espaços da conta atual** (testado, 16 itens): cada um tem `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page`, etc. — mais rica que list_recent |
| `GET /rest/collections/list_recent` | Espaços recentes da conta atual (`title/uuid/emoji/is_pinned/link`; testado, 5 itens) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | Informações de solicitação de acesso ao espaço (não testado) |
| `GET /rest/collections/<uuid>/join-requests` | Solicitações de ingresso (não explorado) |
| `GET /rest/spaces/<uuid>/tasks` | Retorna `{"tasks":[]}` — observado vazio; suspeita-se serem tarefas agendadas/de computador do espaço, não uma lista de threads |
| `GET /rest/spaces/<uuid>/recurring_tasks` | Tarefas recorrentes (não testado) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | Threads fixados/agendados do espaço (chamados no carregamento da página; não explorado) |

- **Ramificação entre contas (branch_of; conhecimento verificado pelo usuário em 2026-07-23)**: um thread compartilhado por meio de um espaço pode ser
  "continuado" por outra conta de membro em um thread ramificado que é **visível apenas para, e continuado por, essa conta** — após o thread da conta A ser compartilhado por meio de um espaço,
  B pode continuá-lo em uma ramificação privada de B. O arquivo ainda não tem instância; arestas de relações não estão implementadas por enquanto; os campos de sinalização de API do thread ramificado
  (ponteiro pai / marcador de ramificação) serão verificados e registrados quando a primeira instância aparecer.

<a id="account-session" data-pplx-source-anchor="true"></a>
### Conta / sessão
| Endpoint | Notas |
|---|---|
| `GET /api/auth/session` | `{user:{email,...}}` da sessão atual — usado para verificação de conta e sondagem de troca automática |
| `GET /api/auth/linked-accounts` | Veja [§1.2](api-authentication.md) (lista completa apenas enquanto a conta primária está ativa) |
| `GET /rest/user/info`, `/rest/user/settings` | Perfil / configurações do usuário (não explorado) |

<a id="credit-usage-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Uso de crédito (descoberto em 2026-07-20)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → uso de crédito por thread (testado 200):
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **Nota**: `thread_id` espera o **context_uuid** (psc_uuid); passar entryUUID resulta em 403
  `thread_usage_forbidden` ("Thread does not belong to the current user" — na verdade um formato de id errado).
- Fontes de context_uuid: `list_collection_threads` (o índice REST de espaço já cobre 27/27),
  o campo `context_uuid` da entrada do thread (arquivado como `psc_uuid` em thread.json).
- Apenas threads da conta atual podem ser consultados (entre contas → 403) — raspagem de múltiplas contas precisa de troca automática por conta.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`: versão de lista; testado vazio em ambas as contas
  (suspeita-se ser apenas para faturamento de organização; a determinar).
- Outros endpoints de faturamento (`/rest/billing/credits/balance`, etc.) no [apêndice §7](api-discovery-roadmap.md); não explorados.

<a id="official-export-backend-of-the-page-export-button-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Exportação oficial (backend do botão "Exportar" da página; descoberto em 2026-07-20)

- **`POST /rest/thread/export`**, corpo: `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<name>"}`
- Resposta: `{"file_content_64": "<base64>", "filename": "..."}`
- Formatos testados: **`md`** (markdown oficial com um cabeçalho de logotipo `<img>`), **`pdf`** (binário PDF ~880KB),
  **`docx`** (PK zip ~350KB) — todos HTTP 200. Outros valores de formato não testados.
- **Limite de conteúdo (verificado)**: retorna markdown **do thread inteiro** (consulta + resumo da resposta + citações de nota de rodapé `[^1_N]`),
  **sem o corpo RESEARCH_REPORT** — o relatório de pesquisa profunda em si só pode ser obtido por meio de seu URL assinado (§3.7);
  ou seja, a cadeia de URL assinado report.md atual **é a fonte oficial do relatório** (mesma fonte do download do painel de artefatos da página); não é necessário mudar para este endpoint.
- Valor: o markdown oficial no nível do thread pode servir como fonte de validação cruzada no nível da conversa (notas de rodapé de citação oficialmente renderizadas/formato).

<a id="asset-report-download" data-pplx-source-anchor="true"></a>
### Download de ativos / relatórios
- **URLs assinados CloudFront** na resposta esquematizada (`d2z0o16i8xm8ak.cloudfront.net`): download direto via urllib,
  sem necessidade de cookie/auth; arquivos com várias versões numerados na ordem `created_at`.
- Fonte alternativa de relatório de pesquisa: o URL S3 da etapa RESEARCH_ANSWER (`ppl-ai-file-upload.s3.amazonaws.com`, **expira**);
  segunda alternativa: extração por renderização de página (KaTeX `<annotation>`).
- **Remoção de ~3 meses**: links de fonte de artefato/relatório expiram irrecuperavelmente — as exportações devem ser feitas em tempo hábil.

<a id="other-observed-endpoints-page-load-not-explored" data-pplx-source-anchor="true"></a>
### Outros endpoints observados (carregamento de página; não explorados)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates` (SSE), `/api/version`.

<a id="message-submission-and-telemetry-2026-07-20-webbridge-cdp" data-pplx-source-anchor="true"></a>
### Envio de mensagem e telemetria (2026-07-20 WebBridge + CDP)

<a id="submission-endpoint-post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### Endpoint de envio: `POST /rest/sse/perplexity_ask`
- Amostras completas de corpo de requisição (exemplos sintéticos) em `docs/perplexity-api-samples/`:
  - `ask_envelope_deep_research.json` — turno de acompanhamento de pesquisa profunda (2026-07-20; 39 params + query_str):
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + a cadeia de continuação `last_backend_uuid`
  - `ask_envelope_search.json` — pesquisa padrão, nova conversa a partir da página inicial (2026-07-21; 35 params + query_str):
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json` — conselho de modelos, nova conversa a partir da página inicial (2026-07-21; 36 params + query_str):
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- Campos principais (turno de acompanhamento de pesquisa profunda, testado):
  - `mode: "copilot"` (pesquisa profunda); `model_preference: "pplx_alpha"`
  - **Cadeia de continuação**: `last_backend_uuid` (uuid do backend do turno anterior) + `query_source: "followup"`
  - `frontend_uuid` (novo uuid para este turno), `read_write_token`, `target_collection_uuid` (espaço contentor),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`** (milissegundos desde a primeira tecla até o envio — telemetria comportamental enviada com o envio)
  - `use_schematized_api: true`, `supported_block_use_cases` (lista completa de blocos, correspondendo à §3.1 esquematizada),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- A resposta é um stream SSE (o frontend o consome com fetch-event-source `getReader()` — o módulo do aplicativo congela a referência de fetch na inicialização,
  **hooks de fetch/XHR anexados à página são ineficazes**; e **corpos de resposta de streaming não são retidos pelo navegador** (`Network.getResponseBody` retorna
  No data found) — a captura só é possível via CDP `Network.getRequestPostData` (corpo da requisição disponível)).
- O estado final do stream é exatamente as entradas/blocos de `/rest/thread/<uuid>` (mesmos dados, entregues incrementalmente) —
  a ferramenta de exportação não precisa ler o stream; ela obtém o estado final diretamente.

<a id="telemetry-post-resteventanalytics-batched-high-frequency" data-pplx-source-anchor="true"></a>
#### Telemetria: `POST /rest/event/analytics` (em lote, alta frequência)
Eventos observados (com essentials de event_data):
| event_name | Campos principais | Notas |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | evento de visualização de página — **não altera o estado de não lido** (descartado por testes; a confirmação de leitura real é `POST /rest/thread/mark_viewed`, veja §3.1) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs` (**milissegundos de permanência de leitura para aquele turno**), `userId`, `isPro`, `deviceInfo` (concorrência/tela/profundidade de cor) | telemetria de duração de leitura (não altera o estado de não lido, descartado por testes) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | ação de envio |
| `query first llm token` | `startLLMTokenElapsed` (latência do primeiro token), `queryStr` completo | telemetria de desempenho |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, `queryStr` completo | confirmação de sucesso |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | interação com seletor de modelo do conselho |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | visualização do painel direito |
- Campos comuns de evento: `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info` (hardwareConcurrency/tela/profundidade de cor/arquitetura), `isBrowserExtension`, `web_platform`.
- **Nota**: um evento observado carregava um `userId` pertencente à **outra conta** (o uid pertencia à conta A enquanto a sessão já era da conta B) —
  o id de perfil do SDK de telemetria tem atraso de cache; não julgue a conta atual pelo userId da telemetria.
- Há também relatórios de alta frequência do datadog RUM (`browser-intake-datadoghq.com/api/v2/rum`) (rolagem/mouse/desempenho; conteúdo não analisado).

<a id="mode-and-model-selection-2026-07-21-tested-on-a-paid-account" data-pplx-source-anchor="true"></a>
#### Seleção de modo e modelo (2026-07-21, testado em uma conta paga)
- **`GET /rest/models/config/v2` = tabela de modelos autoritativa**: `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`, `agentic_research_compare_models` (padrão do conselho três modelos).
  `pplx-ask models` chama este endpoint.
  - Correspondência oficial (testada): **search = `pplx_pro` (nome na interface "Best"), research = `pplx_alpha`
    (nome na interface "Deep research")**.
  - Lista de modelos selecionáveis na interface do modo search (sem Deep research): Best (pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **O campo `mode` é sempre `"copilot"` — não é um discriminador de modo** (mesmo para search / deep research / model council).
- A discriminação está em **`model_preference`**:
  - Search: `pplx_pro` (ou o id de modelo selecionado pelo usuário, ex. `experimental`=Sonar 2, `gpt56_sol`…)
  - Deep research: `pplx_alpha` (**sem seletor de modelo na interface**, fixo)
  - **Model council**: `pplx_agentic_research` + **`compare_model_preferences: [<2-3 models>]`**
    (padrão observado `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`;
    a interface é **seleção única por slot**, reduzindo para 2 modelos no acompanhamento).
  - Step-by-step study: `pplx_study`; Computer: a família `pplx_asi*`.
- O seletor de modelo da área de composição ("model ⌄") e o seletor "N models ⌄" do conselho mapeiam para os campos acima;
  o evento de telemetria `ask input model selector opened` carrega `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels` (threads de pesquisa profunda anteriores tinham `searchMode: "research"`).
- Nova conversa: `query_source: "home"`, sem `last_backend_uuid`, tem `frontend_context_uuid`;
  continuação: `query_source: "followup"` + cadeia `last_backend_uuid`.

<a id="entrysearch_mode-the-authoritative-record-of-conversation-mode-settled-2026-07-22" data-pplx-source-anchor="true"></a>
#### entry.search_mode: o registro autoritativo do modo de conversa (estabelecido em 2026-07-22)
**Cada entrada** de `/rest/thread/<uuid>` carrega `search_mode`, o registro autoritativo da plataforma do modo de conversa daquele turno
(o sinal de detecção de modo de maior prioridade, `normalize.SEARCH_MODE_MAP`):

| search_mode | Significado (Interface/Modelo) | Modo do arquivo |
|---|---|---|
| `SEARCH` | pesquisa normal (default_models.search=pplx_pro "Best" e modelos selecionáveis na interface) | search |
| `STUDIO` | sessão labs (pplx_beta); a interface agrupa sob search | search |
| `RESEARCH` | Deep research (default_models.research=pplx_alpha; interface fixa, sem seletor) | deep-research |
| `AGENTIC_RESEARCH` | model council (pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | step-by-step study (pplx_study) | study |
| `ASI` | Computer (pplx_asi*) | computer |

- Levantamento de valores em todo o arquivo: todos os seis valores têm instâncias no arquivo real; SEARCH e RESEARCH dominam,
  STUDIO em seguida, ASI / STUDY / AGENTIC_RESEARCH raros.
- **pplx_alpha ⟺ RESEARCH comprovação cruzada**: 100+ entradas SEARCH da plataforma + threads pplx_alpha no arquivo são 100%
  `search_mode=RESEARCH`; 100+ threads puros pplx_pro são todos `search_mode=SEARCH` —
  a estatística antiga "pplx_alpha é um modelo comumente usado para pesquisa simples" era na verdade amostras de erro de classificação e não se sustenta.
- Múltiplos valores podem aparecer dentro de um thread (troca de modo, ex. uma mistura observada SEARCH+RESEARCH): a detecção pega o mais alto por especificidade
  computer>council>study>deep-research>search.

<a id="model-council-output-structure-and-expansion-behavior" data-pplx-source-anchor="true"></a>
#### Estrutura de saída do conselho de modelos e comportamento de expansão
- Saída de turno único = N blocos específicos de modelo "Council: <model name>" (cada um com consultas de recuperação/fontes/resposta) + uma parte de síntese:
  **Where Models Agree** (matriz de consenso, por Descoberta comparação de três modelos ✓ + Evidência),
  **Where Models Disagree** (tabela de discordância, posição de cada modelo + razões para divergência),
  **Unique Discoveries** (descobertas únicas de cada modelo), seguidas por recomendações de perguntas relacionadas — **tudo entregue no mesmo stream SSE**.
- Comportamento de expansão (incluindo expansão **durante a geração**): linhas expansíveis carregam um chevron ">" (linhas de etapa / linhas "Sources" / linhas Council);
  clicar expande — **renderização pura do lado do cliente, zero requisições de conteúdo**: das 1208 requisições desta sessão, 921 eram ativos estáticos de favicon/fonte;
  a expansão em si só dispara carregamentos de favicon e /api/version. Expandir durante o streaming não perturba a entrega contínua.
- Latência do primeiro token observada ~204s (três modelos gerando em paralelo, marcadamente maior que modelo único); contagem de fontes observada 236.
- Essenciais de automação da área de composição (Lexical): o texto deve ser injetado via CDP `Input.insertText` (após execCommand/fill,
  o estado interno do Lexical dessincroniza e Enter falha); o envio pode usar CDP Enter ou clicar no botão com aria-label="提交" ("Submit")
  (o modo council tem uma seta de envio explícita).

<a id="behavior-when-continuing-a-historical-conversation-tested-2026-07-20" data-pplx-source-anchor="true"></a>
#### Comportamento ao continuar uma conversa histórica (testado em 2026-07-20)
1. Carregar página do thread → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. Enviar acompanhamento → `rate-limit/status` → `sse/perplexity_ask` (com a cadeia `last_backend_uuid`) → análises de alta frequência.
3. Durante a geração → o stream SSE renderiza incrementalmente; após a conclusão, outro lote de análises (incluindo duração de leitura `thread entry exited`).
4. Turnos de acompanhamento de pesquisa profunda também produzem estruturas de relatório (este turno completou 5 etapas).
