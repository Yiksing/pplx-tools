---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/maintenance-commands.md"
translation_source_sha256: "550aca319a6386123658e8d54ede5367bc97765c9a11710e20f1ed1f2854f617"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintenance-commands" data-pplx-source-anchor="true"></a>
# Comandos de manutenção

Os subcomandos de manutenção do `pplx-export` mantêm um arquivo existente saudável: re-renderizar páginas após correções no renderizador, preencher retroativamente ativos/uso de crédito/metadados de modo, marcar threads excluídas remotamente e reconstruir o grafo de relações. A maioria é offline-first; suas fases online seguem a mesma disciplina de ritmo que `batch` (veja [rate-limiting.md](rate-limiting.md)). Todos aceitam as [opções comuns](pplx-export.md) (`--account`, `--out`, `--cookies-from`, `--transport`, …).

- Princípio de retenção do arquivo local: nenhum comando de manutenção exclui ou move conteúdo de thread arquivado — o arquivo é o backup.
- Os comandos offline (`re-render`, `relations`, `sync-space`, `spaces` sem `--fetch-meta`, e as fases padrão abaixo) não precisam de transporte algum; veja [../architecture/offline-operations.md](../architecture/offline-operations.md).

## re-render

Regenerar `conversation.md` e `turns/` a partir do JSON bruto arquivado (`raw_entries.json` / `raw_blocks.json`) após correções no renderizador — zero rede, e todos os outros arquivos permanecem intocados.

| Bandeira | Significado | Padrão |
|---|---|---|
| `--limit N` | Processar apenas os primeiros N diretórios de thread | todos |
| `--dry-run` | Listar os diretórios que seriam processados, não escrever nada | desligado |
| `--thread-json` | Também adicionar/remover as chaves `interruptions` e `answer_variants` em `thread.json` no local | desligado |

Comportamentos principais:

- Reconstrói turnos offline com o mesmo pipeline da exportação: análise, ordenação por `created_us`, dedup de citações e — para computer/council — blocos de fluxo de trabalho, mapeamento de subagentes e o apêndice de background não consumido.
- Apenas `conversation.md` e `turns/turn_*.md` são (re)escritos; `sources*`, `assets/`, `report.md` e `thread.json` permanecem como estão. Arquivos `turn_*.md` obsoletos numerados acima da contagem atual de turnos são excluídos — nada mais, então arquivos inalterados mantêm seu mtime.
- `--thread-json` escreve apenas quando o conteúdo realmente muda; `answer_variants` recém-adicionados/alterados geram um aviso `ANSWER_VARIANT_DETECTED` e são anexados a `index/answer_variants_log.jsonl` (reexecuções idempotentes não geram spam).
- Diretórios de thread sem `raw_entries.json` são pulados e contados.

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

Remediar ativos que foram arquivados sem uma URL assinada — três remediações em estágios: reobter blocos faltantes, extração inline offline e atualização online opcional.

| Bandeira | Significado | Padrão |
|---|---|---|
| `--fetch-blocks` | Primeiro reobter `raw_blocks.json` faltantes e seus ativos de URL assinada (online) | desligado |
| `--online` | Habilitar a atualização online de ativos faltantes/obsoletos | desligado (apenas extração inline offline, zero requisições) |
| `--limit N` | Processar apenas os primeiros N diretórios de thread | todos |

Comportamentos principais:

- Fase padrão (offline, zero requisições): extrair ativos inline (`ASSET_DIFF` / `CODE_ASSET`) de `raw_blocks.json` para `assets/files/*.md`, e registrar tipos de handle de workspace em nuvem (`DOC_FILE` / `CODE_FILE` / `UNKNOWN` — ainda sem canal de download) em `assets/assets_manifest.json`. Idempotente: registros conhecidos são deduplicados por uuid, depois file_handle; arquivos com mesmo nome e múltiplas versões recebem um sufixo curto de uuid para que reexecuções não colidam.
- `--fetch-blocks` (online): reobter `raw_blocks.json` faltantes para threads deep-research/computer/council/study mais seus ativos baixáveis; threads são agrupados por pasta de conta com um adaptador construído preguiçosamente por conta (cookies alternam automaticamente), 3s entre threads.
- `--online`: para versões de manifesto cujo `downloaded_to` está faltante/obsoleto, buscar uma nova URL assinada via `/rest/assets/<uuid>/data` (chamadas de API em série, com 3s de intervalo), então baixar novamente da CDN (6 threads concorrentes, sem atraso — CDN, não API). Um `ASSET_NOT_FOUND` 404 define a bandeira terminal `asset_expired`; um 403 entre contas é repetido uma vez com a conta que possui a pasta do arquivo.
- O `count` do manifesto é recalculado como o número total de versões a cada gravação.

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

Preencher retroativamente o uso de crédito por thread (`credits/thread-usage`) para todas as threads arquivadas da conta em `index/credit_usage_<account>.json`.

| Bandeira | Significado | Padrão |
|---|---|---|
| `--limit N` | Processar apenas as primeiras N threads | todas |

Comportamentos principais:

- Um GET por thread arquivada (`thread_id` = o `psc_uuid` da thread), com 3s de intervalo; idempotente — threads já presentes no arquivo de saída são puladas.
- Um 403 (`thread_usage_forbidden`, i.e., uma thread entre contas) é registrado como `error` e nunca repetido; outras falhas são deixadas para a próxima execução. O progresso é salvo a cada 25 threads processadas.
- Multi-conta: execute uma vez por conta com `--account` — os cookies alternam automaticamente entre execuções.

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

Preencher retroativamente o campo `search_mode` autoritativo da plataforma em cada linha de `index/library_<account>.json`, para que `batch --mode` possa filtrar exatamente em vez de depender de heurísticas.

| Bandeira | Significado | Padrão |
|---|---|---|
| `--limit N` | Processar apenas as primeiras N linhas pendentes | todas |
| `--offline` | Apenas extração local — linhas sem dados brutos locais aguardam a próxima rodada, sem fallback online | desligado |
| `--delay-min SEC` | Limite inferior do intervalo aleatório entre threads de fallback online | `10` |
| `--delay-max SEC` | Limite superior do intervalo aleatório entre threads de fallback online | `20` |

Comportamentos principais:

- Armazena o valor bruto da plataforma (`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…); uma thread com múltiplos valores mantém o mais específico por computer > council > study > deep-research > search.
- Local-first: threads arquivadas resolvem de `raw_entries.json` com zero rede — uma execução totalmente local nunca constrói um transporte (nem mesmo uma sonda de sessão).
- Fallback online apenas para linhas sem dados brutos locais: `GET /rest/thread/<uuid>` com um intervalo aleatório de 10–20s; linhas em estado terminal `expired` são puladas e registradas; threads recém-encontradas como expiradas/excluídas online são marcadas em `batch_state.json` para poupar requisições futuras.
- Idempotente e retomável: linhas que já possuem `search_mode` são puladas, o progresso é salvo a cada 25 linhas, e atualizações `index` posteriores preservam o enriquecimento (mesclado de volta por `entryUUID`).

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

Identificar threads que desapareceram da biblioteca remota (excluídas pelo usuário ou pela plataforma) e marcá-las como tombstone — nunca exclui ou move nenhum arquivo do arquivo.

| Bandeira | Significado | Padrão |
|---|---|---|
| `--online` | Verificar cada candidato online | desligado (dry-run offline: listar candidatos apenas) |
| `--limit N` | Processar apenas os primeiros N candidatos | todos |
| `--delay-min SEC` | Limite inferior do intervalo aleatório entre candidatos | `10` |
| `--delay-max SEC` | Limite superior do intervalo aleatório entre candidatos | `20` |

Comportamentos principais:

- A detecção de candidatos é offline e entre contas: uma thread com status `batch_state` `ok` que está faltando na união `entryUUID` de **todos** os arquivos `index/library_*.json` torna-se candidata — qualquer índice único que a contenha conta como viva, então threads exportadas entre contas via espaços compartilhados não são falsos positivos. Quando nenhum índice utilizável existe, tudo é pulado com segurança com uma dica para executar `index` primeiro.
- O padrão é um dry-run offline: lista candidatos e razões de pulo seguro — zero rede, zero gravações.
- `--online` verifica cada candidato com `GET /rest/thread/<uuid>` sob a conta registrada em `thread.json` `export_via` (cookies alternam automaticamente por candidato).
- Confirmado por `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 → `batch_state` marca o estado terminal `deleted` (mesma semântica que `expired`: nunca repetido, `--force` não reexporta; veja [incremental-sync.md](incremental-sync.md)) e cada um dos arquivos `thread.json` da thread recebe um timestamp `remote_deleted` no local (idempotente — uma chave existente é mantida).
- Thread ainda existe → falso positivo: relatado como está com uma dica para reexecutar `index`, nada alterado. Erros de transporte recuam para a próxima rodada; 3 falhas de autenticação consecutivas abortam a execução antes que algo seja marcado incorretamente.

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

A primeira execução lista candidatos (dry-run offline); a segunda os verifica online e marca os confirmados como tombstone.

## status

Imprimir o estado da conta do arquivo e o plano de mudança incremental — zero rede, somente leitura. Responde "como está o arquivo agora e o que a próxima execução de `batch` faria" sem tocar na rede.

| Bandeira | Significado | Padrão |
|---|---|---|
| `--account X` | Relatar apenas uma conta | todas as contas que possuem um arquivo `index/library_*.json` |
| `--json` | Relatório completo legível por máquina no stdout (ignora verbosidade) | desligado (linhas de log humanas) |

Comportamentos principais:

- Fontes de dados são puramente locais: `index/library_*.json` (linhas de índice por conta) e `index/batch_state.json` (a única fonte de estados de exportação). A classificação de mudanças reutiliza a mesma função pura `plan_incremental` que `batch`/`schedule`, então as semânticas de `new`/`updated`/`done`/`expired`/`deleted` são idênticas ao que `batch` calcularia.
- A saída INFO padrão imprime uma linha de resumo por conta (contagem de índice + frescor, contagens de estado `ok/expired/deleted/error`, contagens de mudança `new/updated` e o número de parada antecipada) mais uma linha de conta `batch_state` global (ex.: `559 ok + 13 expired + 12 deleted`).
- Os níveis de detalhe seguem a bandeira de verbosidade padrão: `-v` adiciona os títulos das threads `new`/`updated`/`error` (primeira linha, truncada a 60 caracteres); `-vv` adiciona threads `done`/`expired`/`deleted` com `lastUpdated`/`exported_at`; `-vvv` imprime tudo sem truncamento com campos de índice `mode`/`search_mode` e a lista somente de estado (registros presentes em `batch_state` mas ausentes de cada índice de conta — candidatos a exclusão remota para reconciliar com [sync-deleted](#sync-deleted)).
- Salvaguardas: um `index/` ausente ou arquivo de biblioteca ausente sai com um erro apontando para `pplx-export index`; um `batch_state.json` ausente é tratado como um estado vazio (tudo conta como `new`). Nenhuma configuração de nível de usuário é necessária — as contas são enumeradas a partir dos nomes dos arquivos de biblioteca.
- `--json` emite o relatório completo (contas, mudanças, threads, somente estado, totais) como um JSON de linha única no stdout — o mesmo estilo de contrato que `pplx-ask`.

```bash
pplx-export status                 # summary for every account
pplx-export status -vv             # five-state thread details
pplx-export status --account alice --json
```

## relations

Reconstruir o grafo de relações de conversa a partir das threads exportadas → `relations/edges.jsonl` mais um `relations/graph.md` legível por humanos sob a raiz do arquivo.

| Bandeira | Significado | Padrão |
|---|---|---|
| *(apenas opções comuns; apenas `--out` importa)* | | |

Comportamentos principais:

- Puramente offline, zero rede, somente leitura contra o arquivo: reutiliza o pipeline de reconstrução offline do re-render (`raw_entries.json` / `raw_blocks.json`), então `sub_agents`, `query_source` e sinais de citação estão todos disponíveis para detecção de arestas.
- Threads sem dados brutos degradam para um shell `thread.json` + `conversation.md` — apenas arestas de referência `same_space` e uuid simples podem disparar para elas.

```bash
pplx-export relations
```

## debug-js

Executar um trecho de JavaScript no contexto da página atual do navegador via o daemon WebBridge local (`127.0.0.1:10086`) e imprimir o resultado como JSON — uma escotilha de depuração.

| Bandeira | Significado | Padrão |
|---|---|---|
| `JS代码` (posicional) | Código JavaScript para avaliar no contexto da página (o metavar literal do argparse) | obrigatório |

Comportamentos principais:

- Requer que o daemon WebBridge esteja acessível e que a página Perplexity alvo esteja aberta no navegador; o trecho executa com a própria sessão da página.
- O JSON impresso é truncado em 5000 caracteres.

```bash
pplx-export debug-js 'document.title'
```
