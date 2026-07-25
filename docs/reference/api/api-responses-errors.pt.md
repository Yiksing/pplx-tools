---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-responses-errors.md"
translation_source_sha256: "4a9de23e2a900f4922480decf1b89d417310b94ce8116649dd2b2dd5c77b6bde"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-response-structure-and-error-semantics" data-pplx-source-anchor="true"></a>
# Estrutura da Resposta da API e Semântica de Erros

*Parte da referência da API web da Perplexity — mapa completo no [índice da API](index.md).*

<a id="response-structure-essentials-parsing-discipline" data-pplx-source-anchor="true"></a>
## Fundamentos da estrutura da resposta (disciplina de análise)

- **Dados brutos retidos em arquivos bem-sucedidos**: `raw_entries.json` (simples) e
  `raw_blocks.json` (esquematizado, quando obtido) são armazenados junto com os artefatos
  renderizados; a análise/renderização pode ser reexecutada offline (`pplx-export re-render`)
  sem nova obtenção.
- **Extração de campos centralizada** em `sites/perplexity/parsers.py` (deriva de esquema precisa apenas de um local alterado).
- Detecção de modo (`normalize.detect_mode`; árvore de decisão em [export-pipeline.md](../../architecture/export-pipeline.md)): o sinal de maior prioridade é o
  campo **`search_mode`** de qualquer entrada (mapeamento no final de [§3.9](api-rest-endpoints.md)); quando todos os sinais falham, recorre-se — computador = URL
  `/computer/tasks/` ou metadata.mode=="4" ou modo do índice ∈ {ASI,COMPUTER}; council = existe uma
  etapa COUNCIL_RESEARCH; deep-research = existe uma etapa RESEARCH_ANSWER (baseado no conteúdo, sem depender de rótulos chineses);
  caso contrário, pesquisa.
- A interface do computador colapsa tudo — **sempre siga as entradas/blocos da API**; nunca use o texto da interface como limite de conteúdo.
- Canal duplo de subagente (descoberto em 2026-07-19): prompt no `workflow_payload.objective_chunks` esquematizado;
  etapas/conclusão no `background_entries` simples; vinculados via `workflow_payload.id` (`toolu_X`).
- Itens `WORKFLOW_ITEM_SOURCES` frequentemente carregam `text_payload`
  (texto de extração de página do subagente / tabelas de comparação; 450 ocorrências na biblioteca, 408 dentro de payloads aninhados de fundo)
  além de `sources_payload.sources` (lista de links);
  o mesmo conteúdo aparece tanto no JSON de etapa incorporado `text` da entrada de fundo simples quanto no payload aninhado esquematizado —
  subagentes ancorados renderizados pelo caminho simples já preservam o texto (verificação em toda a biblioteca em 2026-07-22: 408/408 presentes, nenhum ausente).
- **`related_queries` / `related_query_items` (resolvido em 2026-07-23)**: cada entrada carrega
  **recomendações de prompt para próxima pergunta** — sugestões de acompanhamento que a plataforma gera para uma resposta concluída; `related_queries` é um array de textos de recomendação,
  `related_query_items` os itens estruturados (uuid/upsell_type, etc.). Conclusão forense: o uuid de um item
  **não é um uuid de thread** (0/988 correspondências cruzadas com uuids de thread da biblioteca), e os textos de recomendação têm sobreposição zero com consultas de outras threads —
  **não resolvível em relações entre threads por enquanto**; a hipótese de "uuids de thread pré-alocados (materializados ao clicar)" permanece não verificada.
  Os dados são naturalmente preservados no arquivo `raw_entries.json` (ocorrências em mais da metade das threads de uma biblioteca de arquivo); nenhuma ação extra de coleta necessária;
  o grafo de relações não constrói arestas a partir disso.

<a id="error-and-risk-control-semantics" data-pplx-source-anchor="true"></a>
## Semântica de erros e controle de risco

| Sintoma | Significado / tratamento |
|---|---|
| 403 (com página de desafio cf) | Bloqueio do Cloudflare (impressão digital TLS / controle de taxa) — recuar; urllib + cookies de navegador geralmente não o acionam |
| 401 / 403 no nível da API (sem página de desafio cf) | Cookie de sessão expirado/inválido — a ferramenta levanta imediatamente, sem recuo; lote falha rapidamente após 3 falhas de autenticação consecutivas (atualizar o cookie) |
| 429 | Limitação de taxa — recuo exponencial (implementado na ferramenta) |
| 5xx (500/502/503/504) | Erros de servidor transitórios (504 comumente um timeout do Cloudflare) — recuar e tentar novamente (implementado na ferramenta) |
| ENTRY_EXPIRED | Removido pela plataforma (~3 meses) — terminal, não tentar novamente |
| ENTRY_DELETED | Excluído pelo usuário/remoto (também HTTP 400, código diferente) — terminal `deleted`, não tentar novamente |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED` (HTTP 200) | A conta atual não pode visualizar o espaço — tentar novamente com uma conta que possa |
| `error_code: VIEW_THREAD_NOT_ALLOWED` (HTTP 403) | A conta atual não pode visualizar a thread (testado em 2026-07-23: sondagem de uuid variante irmão; o objeto existe mas está inacessível, não "inexistente") |
| `status:"failed"` dados vazios | Mesma classe (a forma de falha get_collection) |

**Disciplina de limite de taxa (anti-banimento, requisito explícito do usuário)**: aleatório 10–20s entre threads do lote, sem concorrência, recuo 429/403, recuo-retry 5xx;
paginação ≥3s; nova obtenção esquematizada ≥4s; obtenção de metadados do espaço ≥3s. Exportação de thread única = 1–2 requisições ≈ abrir a página uma vez.

<a id="interruption-semantics-observed-values-2026-07-22-classification-source-of-truth-parsersclassify_wf_status" data-pplx-source-anchor="true"></a>
### Semântica de interrupção — valores observados (2026-07-22; fonte da verdade da classificação: `parsers.classify_wf_status`)

O campo `locked_reason`: aparece em `thread_metadata` / `entries[]` / `background_entries[]`
(em ambos os lados simples e esquematizado). Único valor observado:

| locked_reason | Significado | Distribuição observada |
|---|---|---|
| `spending_limit_exceeded` | interrupção de limite de gastos (cota esgotada; o fluxo de trabalho para no ponto de interrupção) | exatamente uma thread em toda a biblioteca (marcadores em raw_entries e raw_blocks) |

Campo de status do fluxo de trabalho (`workflow_block.status` e `workflow_payload.status` aninhado compartilham o mesmo enum) valores observados:

| status | Semântica | Anotação de renderização (COMPLETED não recebe nenhuma) |
|---|---|---|
| `WORKFLOW_COMPLETED` | conclusão normal | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | aguardando próximas etapas; com `locked_reason=spending_limit_exceeded` é uma **interrupção de limite de gastos** (o conteúdo para no ponto de interrupção); sem locked_reason, interrompido pendente de continuação | `⏸ 限额中断（内容截至中断点）` (⏸ interrompido por limite — o conteúdo para no ponto de interrupção) / `⏸ 中断待续` (⏸ interrompido, pendente de continuação) |
| `WORKFLOW_CANCELED` | cancelado (aborto do usuário/plataforma) | `⛔ 已取消` (⛔ cancelado) |

- `WORKFLOW_CANCELED` observado 19 vezes (16 principais + 3 aninhados), em 7 threads de computador
  (a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff).
- Nota: o status do payload âncora da entrada principal pode estar atrasado (observado âncora COMPLETED enquanto o fundo estava na verdade CANCELED) —
  o status verdadeiro de um subagente é o `workflow_block.status` do lado do fundo.
- Tarefas de fundo interrompidas não produzem notificação de conclusão subagent_result; payloads de fundo não consumidos recaem no apêndice da thread
  (veja "cascata de atribuição" em [subagents-interruptions.md](../../architecture/subagents-interruptions.md)).
- Respostas vazias no modo computador (duplamente verificado em 2026-07, irrecuperável): no modo computador, alguns turnos têm uma
  resposta vazia porque o servidor simplesmente não tem nenhuma — uma nova obtenção da API retorna dados idênticos ao arquivo, e
  expandir a barra "N etapas concluídas" da interface aciona zero requisições de dados (renderização pura do lado do cliente; a interface e
  a API compartilham uma fonte), então a API não pode recuperá-las. Apenas um subconjunto de tais turnos está vinculado a
  `locked_reason=spending_limit_exceeded`; os restantes não carregam marcador do lado do servidor.

<a id="side_by_side_metadata-answer-rewrite-variant-signal-settled-2026-07-23" data-pplx-source-anchor="true"></a>
### `side_by_side_metadata`: sinal de variante de reescrita de resposta (resolvido em 2026-07-23)

Caminho do campo: `entries[].side_by_side_metadata` (resposta `/rest/thread/<uuid>` simples).
Quando a plataforma gera múltiplas versões de resposta para a mesma consulta (experimento A/B ou reescrita), este é o
único traço deixado na entrada atualmente ativa — **o corpo da variante substituída (texto/etapas/citações) não está na resposta da API da thread** (caso real
b2d2632b: a resposta tem apenas 1 entrada, 1 FINAL; variante 2 completamente invisível).

Chaves e valores observados (evidência: b2d2632b bruto; varredura em toda a biblioteca de 2442 entradas):

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| Chave | Semântica (observada/hipotetizada) |
|---|---|
| `sibling_uuid` | Aponta para a **variante de resposta irmã** da mesma consulta (outro identificador de entrada/contexto). 7 threads atingidas em toda a biblioteca; **forense online (2026-07-23) confirma um link morto**: ambas as contas `GET /rest/thread/<sibling_uuid>` retornam 403 `VIEW_THREAD_NOT_ALLOWED` (não 404/ENTRY_EXPIRED — o servidor o reconhece como um objeto existente mas não visualizável), e abrir `/search/<sibling_uuid>` no navegador (conta proprietária) é redirecionado pelo SPA de volta para o início — variantes substituídas não podem ser recuperadas via sibling_uuid |
| `selection_status` | `SELECTED` = a resposta desta entrada é a versão escolhida para exibição; instâncias do grupo de controle são todas `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | Papel do experimento. O grupo de controle carrega um prefixo `[control]` (6 casos em toda a biblioteca: `[control]default-model-class:gpt41`, etc.); o caso real não tem prefixo (`override-default-model-class:qwen3_instruct-01f7f`, ou seja, o grupo de tratamento de um experimento de substituição de modelo) |
| `experiment_override` | Parâmetros de substituição do experimento (ex. `override-default-model-class: qwen3_instruct`); observado apenas em instâncias do grupo de tratamento |
| `execution_log` | Observado como um objeto vazio; semântica desconhecida |

**Critérios de estreitamento** (distinguindo "reescrita genuína mantendo ambas as versões" de "controle A/B rotineiro"):
`sibling_uuid` não vazio E (`selection_status` não vazio e não `SELECTION_STATUS_UNSPECIFIED`,
OU `experiment_role` sem o prefixo `[control]`) → **apenas b2d2632b atinge** entre as 2442 entradas em toda a biblioteca
(o único caso real confirmado; precisão/revocação são ambos 1 nesta biblioteca, mas n=1 não pode ser extrapolado).

Comportamento da ferramenta: `parsers.collect_answer_variants` extrai ocorrências; `adapter.get_thread`
registra um aviso + escreve `thread.json.answer_variants` (chave ausente quando não há ocorrências);
`re-render --thread-json` adiciona/remove no local (idempotente). Evidência de tempo: a entrada do caso real `created→updated`
delta é 53,66 s (gerada às 17:13, depois reescrita/selecionada), e a reescrita avançou o `lastUpdated` no nível da thread (uma reexportação incremental
pode acionar uma nova obtenção, mas a resposta reobtida ainda contém apenas a resposta ativa; variantes antigas são irrecuperáveis).

**Log de detecção e fluxo de tratamento (2026-07-23, `sites/perplexity/variant_log.py`)**:

- **Marcador de log**: cada ocorrência emite uma única linha WARNING com o marcador greppable uniforme `ANSWER_VARIANT_DETECTED`,
  incluindo todos os campos de localização e orientação de tratamento, com formato:
  `ANSWER_VARIANT_DETECTED thread=<full uuid> uuid8=<8 chars> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | action: …`
  O caminho online (`adapter.get_thread`) gera saída em cada ocorrência de obtenção real; offline `re-render`
  **gera saída apenas quando o conteúdo registrado é adicionado/alterado** (reexecuções idempotentes não geram spam); `batch` também passa um lembrete de contagem de ocorrências de uma linha
  no resumo final (sem quebrar o formato de resumo existente).
- **Registro central**: `<out>/index/answer_variants_log.jsonl` (**um arquivo versionado**, não sob o
  `logs/` ignorado pelo git) — um JSON por linha (detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role), deduplicado por (web_uuid, entry_uuid); exportações/rerenderizações repetidas não anexam infinitamente;
  detected_at mantém o horário da primeira visualização.
- **Ação recomendada em ocorrência**: irmãos são empiricamente links mortos (veja a tabela acima); a resposta alternativa geralmente
  **não pode ser recuperada via API** — confirmar manualmente prontamente se a resposta alternativa ainda é obtível (conversa na plataforma / memória do usuário / capturas de tela); se obtível,
  registrá-la manualmente como um arquivo `rewritten_answer_variant.md` no diretório da thread; se não, `thread.json.answer_variants` +
  o registro jsonl serve como o registro final rastreável.
