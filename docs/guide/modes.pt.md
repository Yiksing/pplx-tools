---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/modes.md"
translation_source_sha256: "dda1cfaf9d60ef912d922e65babafb68ec80cd1cdf046d661960d0de47ab77ff"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="conversation-modes" data-pplx-source-anchor="true"></a>
# Modos de conversa

As conversas do Perplexity vêm em cinco modos: `search` / `deep-research` / `computer` /
`council` / `study`. O modo é detectado por thread durante a exportação; ele decide quais
respostas da API são buscadas, o que vai para o diretório da thread e qual
[caminho de arquivo](archive-layout.md) a thread recebe (`<account>/<mode>/…`). O modo detectado é
registrado em `thread.json` (chave `mode`) e usado pela filtragem `pplx-export batch --mode`.
O `pplx-ask` também pode *criar* novas threads em quatro dos cinco modos (todos exceto
`computer`) — veja [pplx-ask](pplx-ask.md).

<a id="the-five-modes-at-a-glance" data-pplx-source-anchor="true"></a>
## Os cinco modos de relance

| Modo | Nome na interface / modelo | Conteúdo do turno | Citações | Produtos | Blocos esquematizados buscados |
|---|---|---|---|---|---|
| `search` | "Best" (`pplx_pro`; labs `STUDIO`/`pplx_beta` também mapeia aqui) | Consulta + Resposta, etapas de texto | nível do turno + da thread `sources.*` | — | Não (`raw_blocks.json` ausente) |
| `deep-research` | "Deep research" (`pplx_alpha`, fixo, sem seletor) | etapas de pesquisa incl. `RESEARCH_ANSWER` | sim | `report.md` (relatório completo) | Sim |
| `computer` | Computer (`pplx_asi_opus`, `pplx_asi_opus_thinking`) | `workflow_block` completo: narração, chamadas de ferramenta, prompts/passos de subagente, citações por etapa | por etapa + turno + thread | arquivos versionados em `assets/` + execuções de subagente | Sim |
| `council` | model council (`pplx_agentic_research`; três modelos por padrão) | etapa `COUNCIL_RESEARCH`; fluxo de trabalho `LLM_COUNCIL` aninhado de cada modelo dobrado em `<details>` (rodadas de pesquisa, todas as fontes, resposta completa por modelo) | por modelo + agregado | respostas por modelo comparadas lado a lado | Sim |
| `study` | Study (`pplx_study`) | etapas/citações via blocos (verificado que também contém ativos) | sim | ativos quando presentes | Sim |

<a id="how-the-mode-is-decided" data-pplx-source-anchor="true"></a>
## Como o modo é decidido

A autoridade de detecção é o próprio campo da plataforma **`entry.search_mode`**
(`SEARCH_MODE_MAP`, `normalize.py:50-59`), coletado em todas as entradas
(`normalize.py:106-115`). Foi verificado em relação à configuração oficial do modelo
(`GET /rest/models/config/v2`): `default_models.search=pplx_pro` (interface "Best"),
`default_models.research=pplx_alpha` (interface "Deep research"), e os valores mapeiam um a um para
modos de conversa:

| Valor `search_mode` | Modo |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`, `STUDIO` | `search` |

Regras de conflito (`detect_mode`, `normalize.py:66-128`):

- **Mudança de modo dentro de uma thread** (entradas discordam): pegar o mais alto por especificidade —
  **computer > council > study > deep-research > search** (`_MODE_SPECIFICITY`,
  `normalize.py:63`) — e `log.warning`.
- **Conflito com sinais downstream** (nomes de etapa / `display_model`): `search_mode` vence,
  `log.warning` (`normalize.py:120-123`).
- **`search_mode` totalmente ausente** → a cadeia original: URL contém `/computer/tasks/` ou
  `metadata.mode == '4'` ou modo de índice ∈ `ASI`/`COMPUTER` → `computer`; uma etapa `COUNCIL_RESEARCH`
  → `council`; uma etapa `RESEARCH_ANSWER` → `deep-research`; sinal `display_model` redundante
  (`DISPLAY_MODEL_MODE`, `normalize.py:32-37`) vence em conflito; nada atinge →
  `search` por padrão.
- **Todos os sinais ausentes não concluem search**: o pipeline ainda busca os blocos esquematizados
  (`adapter.py:83-89`) para que uma deriva de campo da plataforma não possa descartar silenciosamente `raw_blocks.json`.

!!! note "Por que `pplx_alpha` não é uma pista de detecção"
    `pplx_alpha` é o modelo dedicado a RESEARCH — ele é o *alvo* que o classificador deve
    detectar, não evidência para detecção, portanto é deliberadamente excluído da tabela de mapeamento
    (comentário `normalize.py:15-31`).

A árvore de decisão completa com todos os ramos: [Pipeline de exportação — detecção de modo](../architecture/export-pipeline.md).

<a id="where-sub-agent-payloads-land" data-pplx-source-anchor="true"></a>
## Onde os payloads de subagente vão parar

As execuções de Computer/council geram fluxos de trabalho de subagente em segundo plano. Cada
`workflow_payload` em segundo plano é renderizado em **exatamente um lugar, nunca duas vezes**; no nível do usuário, os
três locais possíveis são:

1. **Ancorado — dentro do turno iniciador**: o turno que iniciou o subagente carrega um
   id de payload correspondente, então a execução é renderizada inline no processo de trabalho desse turno
   (`turns/turn_NNNN.md`), com prompt, etapas, resposta e fontes.
2. **Turno stub — seção "子代理工作" (Trabalho de subagente)**: um turno stub `subagent_result` dentro de uma
   janela de conclusão de 10 segundos absorve o payload; a resposta não é preenchida.
3. **Apêndice da thread — final de `conversation.md`**: tudo o que sobrou (execuções interrompidas
   não produzem notificação de conclusão, então os dois primeiros níveis necessariamente erram) é arquivado
   literalmente sob "## 后台任务（未归入轮次）" (Tarefas em segundo plano (não atribuídas a turnos)) — sem
   adivinhação de atribuição de tempo, qualquer status aceito.

Regras de correspondência, estruturas de dados e as garantias de consumo único:
[Subagentes e interrupções](../architecture/subagents-interruptions.md).

<a id="interruptions-non-completed-workflows" data-pplx-source-anchor="true"></a>
## Interrupções: fluxos de trabalho não CONCLUÍDOS

Fluxos de trabalho que não foram concluídos são anotados inline onde quer que sejam renderizados — em cabeçalhos
de processo de trabalho, cabeçalhos de subagente e resumos `<details>` aninhados. As três anotações
(`parsers.classify_wf_status`, `parsers.py:263-284`):

| Anotação | Condição | Significado |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` (interrompido por limite — o conteúdo para no ponto de interrupção) | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | limite de gastos esgotado; o fluxo de trabalho parou no meio da execução |
| `⏸ 中断待续` (interrompido, pendente de continuação) | `WORKFLOW_AWAITING_NEXT_STEPS` sem `locked_reason` | interrompido, pode ser continuado na plataforma |
| `⛔ 已取消` (cancelado) | `WORKFLOW_CANCELED` | cancelado pelo usuário ou pela plataforma |

- `COMPLETED` nunca é anotado (threads saudáveis recebem diff zero); valores de status futuros desconhecidos
  permanecem silenciosos.
- Cada caso anotado também é registrado em `thread.json.interruptions` como
  `{location, kind, headline, status}` — os locais se parecem com `turn_0007`,
  `turn_0011/subagent`, `turn_0024/subagent_stub`, `background_unassigned`
  (`parsers.py:535-583`; chave ausente em threads saudáveis).
- **Retomada não precisa de caso especial**: quando você continua uma thread interrompida na
  plataforma, seu `lastUpdated` muda, a próxima exportação incremental o busca novamente, e as
  anotações simplesmente desaparecem quando o fluxo de trabalho é concluído. Veja
  [Sincronização incremental](incremental-sync.md).

Valores de status observados e distribuição: [Respostas da API e erros](../reference/api/api-responses-errors.md);
máquina de estados: [Subagentes e interrupções](../architecture/subagents-interruptions.md).

<a id="answer-rewrite-variants-answer_variants" data-pplx-source-anchor="true"></a>
## Variantes de reescrita de resposta (answer_variants)

Quando a plataforma reescreve uma resposta (experimentos A/B), a variante substituída fica invisível na
API — apenas a resposta selecionada é retornada, enquanto o irmão perdedor deixa um rastro em
`entries[].side_by_side_metadata` e pode ser removido posteriormente (links de irmãos mortos confirmados:
403 `VIEW_THREAD_NOT_ALLOWED`). A ferramenta torna "uma reescrita ocorreu" observável:

- **Registro**: acertos com critérios restritos são escritos em `thread.json.answer_variants`
  (`fs_writer.py:247-252`; chave ausente sem acertos) e anexados ao registro central
  `index/answer_variants_log.jsonl`, desduplicados por (thread, entrada) e idempotentes
  (`variant_log.py:76`).
- **Alertas**: uma única linha WARNING pesquisável `ANSWER_VARIANT_DETECTED` com campos de localização
  completos (thread uuid/uuid8, entry_uuid, sibling_uuid, selection_status, experiment_role) em
  cada acerto online; `re-render` registra novamente offline e avisa apenas quando o conteúdo é adicionado ou
  alterado, para que reexecuções em toda a biblioteca permaneçam silenciosas; o resumo em lote anexa uma contagem de acertos ⚠.
- **Re-arquivamento manual**: variantes irmãs são empiricamente links mortos, então a resposta
  alternativa geralmente **não pode ser recuperada via API**. Em um acerto, confirme prontamente a resposta
  alternativa manualmente (interface da plataforma, seus próprios registros, capturas de tela); se você a obtiver, registre-a como
  `rewritten_answer_variant.md` dentro do diretório da thread. Caso contrário,
  `thread.json.answer_variants` mais o registro jsonl são o registro final rastreável.

Cadeia de detecção e novo registro offline: [Operações offline](../architecture/offline-operations.md);
semântica de campo e evidência de link morto: [Respostas da API e erros](../reference/api/api-responses-errors.md).

<a id="rendering-fidelity-principles" data-pplx-source-anchor="true"></a>
## Princípios de fidelidade de renderização

Independentemente do modo, a renderização segue o mesmo contrato de fidelidade:

- **Respostas completas, nunca truncadas** — o antigo limite `[:4000]` foi removido porque cortava
  frases no meio (`render.py:645-647`).
- **Tabelas nunca truncadas** — `WORKFLOW_ITEM_TABLE` renderiza cada linha e coluna, escapando
  `|` e quebras de linha em cabeçalhos e células para que a estrutura Markdown sobreviva
  (`render.py:211-243`).
- **Citações completas** — três canais de coleta (`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`), desduplicados por URL em `sources.*`; nada citado é descartado.
- **O JSON bruto da API é o limite de conteúdo** — tudo o que é renderizado vem de
  `raw_entries.json` / `raw_blocks.json`; o que a API não retorna (por exemplo, uma variante de resposta
  substituída) não pode ser renderizado e é exibido por meio de registros em vez de ser inventado.
- **Dobras da interface, o arquivo expande** — detalhes que a interface web oculta atrás de dobras e cliques
  (narração do fluxo de trabalho do Computer e E/S de ferramentas, execuções por modelo do council, etapas de subagente) são
  renderizados por completo; blocos `<details>` mantêm o esboço do documento legível sem perder
  informações (`render.py:46`, `render.py:404-413`).
- **Robustez estrutural** — cercas de código são dimensionadas para seu conteúdo (`_fence_for`,
  `render.py:28-43`) para que a saída da ferramenta contendo suas próprias cercas não possa inverter o pareamento, e
  os delimitadores LaTeX são normalizados para `$$` / `$` com segmentos de código protegidos
  (`normalize_math_delims`).

Como as respostas brutas retidas tornam tudo isso regenerável offline:
[Pipeline de exportação](../architecture/export-pipeline.md) e [Operações offline](../architecture/offline-operations.md).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Veja também

- [Layout do arquivo](archive-layout.md) — onde os arquivos de cada modo vão parar
- [pplx-ask](pplx-ask.md) — criando novas threads em cada modo
- [Sincronização incremental](incremental-sync.md) — buscando novamente threads continuadas
- [Pipeline de exportação](../architecture/export-pipeline.md) — árvore de decisão completa de detecção de modo
- [Subagentes e interrupções](../architecture/subagents-interruptions.md) — cascata de atribuição e máquina de estados
- [Respostas da API e erros](../reference/api/api-responses-errors.md) — valores de campo observados
