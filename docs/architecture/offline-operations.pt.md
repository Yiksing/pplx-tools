---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/offline-operations.md"
translation_source_sha256: "c813dedc53caddaa170728bac2152dadca3175bb204ddb9e0cdbca72d7907763"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="offline-operations" data-pplx-source-anchor="true"></a>
# Operações offline

O lado sem rede do `pplx_export`: regeneração offline a partir de JSON bruto, o pipeline de reconstrução de relações, backfills de enriquecimento de índice, a máquina de estado de exclusão remota e a cadeia de detecção de answer_variants. As seções mantêm sua numeração original da [visão geral da arquitetura](overview.md).

---

<a id="offline-regeneration-re-render" data-pplx-source-anchor="true"></a>
## Regeneração offline (re-render)

Após correções na camada de renderização, regenerar todos os artefatos a partir de JSON bruto **sem rede**, de forma idempotente.
Implementação: `commands/rerender_cmd.py` (single-thread `rerender` rerender_cmd.py:105-190;
lote `cmd_rerender` rerender_cmd.py:193-212).

```mermaid
flowchart TD
    IN[("&lt;out&gt;/*/*/*/raw_entries.json<br/>glob all thread directories (rerender_cmd.py:199)")] --> CHK{"raw_entries.json exists?"}
    CHK -->|"no"| SKIP["skip (counted as skipped)"]
    CHK -->|"yes"| P1["parse_turn per entry (parsers.py:173)<br/>sort by created_us, re-number index<br/>(rerender_cmd.py:57-60)"]
    P1 --> P2["Conversation rebuilt<br/>metadata = thread_metadata (rerender_cmd.py:65-70)<br/>conv._plain = doc"]
    P2 --> P3{"raw_blocks.json exists?"}
    P3 -->|"yes"| P4["conv._blocks loaded (rerender_cmd.py:91)<br/>PerplexityAdapter(None).sub_agents builds sub_map<br/>(None-transport pure data assembly, rerender_cmd.py:84-88, 138)"]
    P3 -->|"no"| P5["sub_map = {}"]
    P4 --> P6{"mode in computer/council?"}
    P6 -->|"yes"| P7["attach_workflow_blocks (rerender_cmd.py:93)<br/>attach_stub_workflows (rerender_cmd.py:97)<br/>collect_unconsumed_background (rerender_cmd.py:101)"]
    P6 -->|"no"| P8
    P5 --> P8["render_conversation → conversation.md<br/>render_turn × N → turns/turn_NNNN.md<br/>(rerender_cmd.py:170, 189)"]
    P7 --> P8
    P8 --> TJ{"--thread-json?"}
    TJ -->|"no"| OUT(("done: other files untouched"))
    TJ -->|"yes"| TJ1["collect_interruptions(conv, sub_map) (rerender_cmd.py:150)<br/>answer_variants rebuilt with load_archived's same implementation (rerender_cmd.py:83)"]
    TJ1 --> TJ2{"compare the two keys<br/>interruptions / answer_variants<br/>against existing thread.json"}
    TJ2 -->|"content changed"| TJ3["add/remove the two keys in place, then write; all other fields kept as-is (round-trip indent=1)<br/>(rerender_cmd.py:141-169)<br/>warn + append jsonl registration when variants are added/changed<br/>(rerender_cmd.py:163-166, see §18)"]
    TJ2 -->|"no change"| TJ4["no write — avoids library-wide mtime/diff noise"]
```

Disciplina:

- **Sem rede**: `PerplexityAdapter(None)` reutiliza apenas métodos de montagem de dados puros; nenhum método online (get_thread etc.) é chamado.
- **Idempotente**: artefatos dependem apenas de bruto + renderizador; reexecuções são byte-idênticas (garantido pelos testes de regressão de snapshot, [§13](../development/testing-architecture.md)).
- **Outros arquivos intactos**: fontes, report.md, assets permanecem como estão; thread.json não é alterado por padrão — com `--thread-json` apenas as duas chaves interruptions / answer_variants são adicionadas ou removidas.
- `--dry-run` apenas lista diretórios sem escrever arquivos (rerender_cmd.py:204-206); `--limit N` pega os primeiros N.

---

<a id="relations-offline-rebuild-pipeline" data-pplx-source-anchor="true"></a>
## Pipeline de reconstrução offline de relações

`cmd_relations` (misc_cmd.py:16) reconstrói o grafo de relações de conversas em toda a biblioteca a partir de dados brutos arquivados **sem rede**: reutiliza o pipeline de reconstrução offline do re-render `load_archived_conversation` (rerender_cmd.py:34) para restaurar cada Conversation (análise/ordenação/numeração de turnos, anexação _plain/_blocks), preenche `conv.sub_agents` em nível de conversa via `adapter.sub_agents` thread por thread (misc_cmd.py:70-73; o pipeline de exportação não preenche este campo, models.py:178-182); o fallback de resposta do computador (`wf_block_answer`) preenche `turn.answer` nesta camada, ampliando a superfície de varredura de referências (misc_cmd.py:74-79). Threads sem dados brutos degradam para um shell thread.json + conversation.md (apenas arestas same_space / bare-uuid podem ser detectadas, misc_cmd.py:61-66).

```mermaid
flowchart LR
    RAW["web_archive/*/*/*/raw_entries.json<br/>+ raw_blocks.json"] --> LA["load_archived_conversation<br/>(rerender_cmd.py:34, zero network)"]
    LA --> SUB["adapter.sub_agents → conv.sub_agents<br/>(misc_cmd.py:70-73)"]
    LA --> FB["wf_block_answer backfills turn.answer<br/>(misc_cmd.py:74-79)"]
    SUB --> BE["build_edges (relations.py:200)"]
    FB --> BE
    BE --> SS["same_space: same space<br/>dst = space:&lt;slug&gt;"]
    BE --> SP["same_prompt: first-query normalized equality<br/>(normalize_query, relations.py:111)<br/>in-cluster chaining by created_us (not cliques)<br/>query_source distinguishes scheduled-task reruns<br/>from manual resends (parsers.py:209-215)"]
    BE --> RF["references: answer text / citation URLs<br/>referencing other archived threads (incl. bare uuids)"]
    BE --> SA["subagent_of: main thread → subagent run<br/>dst = toolu_X run id (not a thread uuid)<br/>archived subagent threads recorded in evidence"]
    SS --> OUT[("web_archive/relations/<br/>edges.jsonl + graph.md")]
    SP --> OUT
    RF --> OUT
    SA --> OUT
```

Disciplina de decisão (2026-07-23): o mecanismo `branch_of` está confirmado, mas não possui instância no arquivo — nenhuma aresta construída; `related_query` não pode ser analisado a partir de dados existentes — nenhuma aresta construída também: é melhor perder uma aresta do que construir uma suposta.
Escala observada: 772 arestas / 21 clusters em todo o arquivo (same_space 559 / subagent_of 154 / same_prompt 49 / references 10).

---

<a id="search-mode-backfill-index-search_mode-enrichment" data-pplx-source-anchor="true"></a>
## search-mode-backfill (enriquecimento search_mode do índice)

`cmd_search_mode_backfill` (search_mode_backfill_cmd.py:81) enriquece o campo autoritativo da plataforma `search_mode` em `index/library_<account>.json`: **bruto local primeiro** (para threads arquivados, extraído de `entries[].search_mode` do raw_entries.json, zero rede); apenas threads sem bruto local recorrem a uma busca online de thread. A escrita mescla e preserva campos de índice existentes (semântica de atualização: chaves de enriquecimento sobrescrevem, todo o resto mantido), idempotente e retomável, com `--limit` para subconjuntos.
Linhas de índice enriquecidas tornam o filtro `--mode` do lote autoritativo:
`index_row_matches_mode` (batch_cmd.py:46) julga pelo search_mode do índice primeiro (SEARCH_MODE_MAP, normalize.py:50), recorrendo a heurísticas apenas quando ausente.

---

<a id="sync-deleted-remote-deletion-state-machine" data-pplx-source-anchor="true"></a>
## sync-deleted máquina de estado de exclusão remota

`cmd_sync_deleted` (sync_deleted_cmd.py:262) identifica threads "excluídos pelo usuário/remotamente no lado da plataforma" e registra um estado terminal, junto com expirados. A determinação de candidatos é uma **diferença de uniões de todos os índices de conta**: um thread arquivado ok conta como candidato apenas quando desapareceu de **todos** os arquivos `index/library_*.json` (um thread export_via entre contas aparece apenas no índice de seu proprietário, então uma diferença de conta única geraria falso positivo; find_candidates, sync_deleted_cmd.py:148); índices ausentes/ilegíveis são ignorados com segurança, com o motivo registrado. O dry-run offline padrão apenas lista candidatos (sem rede, sem alterações de arquivo); `--online` verifica thread por thread com GET: `ENTRY_DELETED` / `ENTRY_EXPIRED` / 404 → exclusão confirmada, `state.mark_deleted` (state.py:136) + um thread.json tombstone (mark_thread_json_remote_deleted, sync_deleted_cmd.py:215).

```mermaid
stateDiagram-v2
    [*] --> ok : archived (batch_state = ok)
    ok --> candidate : gone from the union of all account indexes<br/>(find_candidates, sync_deleted_cmd.py:148)
    candidate --> skipped : index missing/unreadable<br/>safely skipped, reason recorded
    candidate --> listed : offline dry-run lists only<br/>(no network, no file changes)
    listed --> deleted : --online verifies one by one<br/>ENTRY_DELETED / ENTRY_EXPIRED / 404<br/>(_confirm_deleted, sync_deleted_cmd.py:247)
    deleted --> [*] : terminal mark_deleted (state.py:136) + thread.json tombstone<br/>plan_incremental trims it like expired<br/>(incremental.py:74-75, 84)
```

Camadas de tipo de erro: `EntryDeletedError` herda de `EntryExpiredError` (a verificação de 400 com corpo contendo ENTRY_DELETED vem antes de ENTRY_EXPIRED, cookie_transport.py:93-98); o lote deve capturar a subclasse antes da classe pai (batch_cmd.py:163-174 antes de 175-183), ou excluído seria registrado incorretamente como expirado. A API de exclusão em si:
`DELETE /rest/thread/delete_thread_by_entry_uuid`
(read_write_token retirado do primeiro `entries[].read_write_token` não vazio;
verificado na prática 10/10 exclusões bem-sucedidas em threads de teste criados por si e threads do espaço BOT).

---

<a id="the-answer_variants-answer-rewrite-variant-detection-chain" data-pplx-source-anchor="true"></a>
## A cadeia de detecção de variantes answer_variants (reescrita de resposta)

Variantes substituídas nos "experimentos de reescrita de resposta / A-B" da plataforma são invisíveis no lado da API — a resposta selecionada é visível, enquanto o irmão perdedor deixa apenas um rastro em `entries[].side_by_side_metadata`, e pode ser removido pela plataforma (links de irmãos mortos são comprovados: 403 VIEW_THREAD_NOT_ALLOWED + um redirecionamento SPA para a página inicial; veja [a referência da API §5.2](../reference/api/api-responses-errors.md)). A cadeia de detecção torna "uma reescrita ocorreu" observável e rastreável:

```mermaid
flowchart LR
    E["entries[].side_by_side_metadata<br/>narrowed criteria"] --> CAV["parsers.collect_answer_variants<br/>(parsers.py:589)"]
    CAV --> AD["adapter.get_thread warns on online hits<br/>(adapter.py:141-147)"]
    CAV --> RR["re-render offline rebuild<br/>warns only on additions/changes (rerender_cmd.py:163-166)"]
    AD --> LOG["variant_log.warn_detections (variant_log.py:65)<br/>single WARNING line ANSWER_VARIANT_DETECTED (variant_log.py:45)<br/>full locating fields + handling guidance, grep-able"]
    RR --> LOG
    AD --> TJ["thread.json.answer_variants registration<br/>(fs_writer.py:247-252)"]
    RR --> TJ
    TJ --> JSONL[("index/answer_variants_log.jsonl<br/>append_registry (variant_log.py:76)<br/>dedup by (web_uuid, entry_uuid), idempotent")]
    LOG --> B["batch summary surfaces ⚠ hit-thread count<br/>(batch_cmd.py:214-223)"]
    JSONL --> B
```

- **Critérios restritos**: apenas os sinais autoritativos de side_by_side_metadata são aceitos; campos de localização completos são registrados (full thread uuid + uuid8, title, entry_uuid, sibling_uuid, selection_status, experiment_role) além de orientação de tratamento; o formato está em `format_detection` (variant_log.py:53).
- **Idempotente**: o jsonl deduplica por (web_uuid, entry_uuid); registros duplicados dos caminhos online (source=online) e offline (source=offline) não produzem linhas duplicadas; re-render avisa apenas quando o conteúdo da variante muda, então reexecuções em toda a biblioteca não geram spam.
- **Fluxo de tratamento**: em um acerto, confirme manualmente a resposta alternativa o mais rápido possível e registre-a (a alternativa pode ser removida pela plataforma e não pode ser recuperada via API); o fluxo completo está em [a referência da API §5.2](../reference/api/api-responses-errors.md).
