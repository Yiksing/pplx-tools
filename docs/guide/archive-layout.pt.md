---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/archive-layout.md"
translation_source_sha256: "6302a47c60b6c8703d36f420cee6c18017110fcbb6127926eedb5c77e3e1f8e2"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="archive-layout" data-pplx-source-anchor="true"></a>
# Layout do arquivo

Tudo o que o `pplx-export` baixa é colocado em uma única árvore de saída — `./web_archive/` por padrão
(substituível com `--out`). Esta página é um guia de leitura para essa árvore: o que cada diretório e arquivo
é, quais chaves o `thread.json` carrega e como a ferramenta mantém um diretório por thread quando uma
conversação continua por dias. Tudo é gerado pela ferramenta; a profundidade do mecanismo está em
[Modelo de dados e contrato de diretório](../architecture/data-model.md) e
[Pipeline de exportação](../architecture/export-pipeline.md).

<a id="the-output-tree" data-pplx-source-anchor="true"></a>
## A árvore de saída

```
web_archive/
├── alice/                                # one folder per account (author display name)
│   ├── search/                           # mode: search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # one directory per thread
│   │       ├── thread.json               # metadata + optional registries
│   │       ├── conversation.md           # compact read: per-turn Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # full read: complete work-process detail
│   │       │   └── ...
│   │       ├── sources.json              # thread-wide citations (deduped by url)
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research report (only when one exists)
│   │       ├── raw_entries.json          # plain API response, verbatim (always present)
│   │       ├── raw_blocks.json           # schematized API response (absent for search)
│   │       └── assets/
│   │           ├── assets_manifest.json  # versioned manifest
│   │           └── files/                # downloaded asset bodies
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # state files and indexes (see below)
├── relations/                            # edges.jsonl + graph.md (rebuilt by `pplx-export relations`)
├── crosscheck/                           # cross-validation reports (manual/review artifacts)
└── bob/ ...
```

<a id="the-thread-directory" data-pplx-source-anchor="true"></a>
## O diretório da thread

Cada thread recebe exatamente um diretório, calculado por `thread_dir_for` (`fs_writer.py:58-72`):

```
<account display name>/<mode>/<YYYY-MM-DD>_<title-slug>_<uuid8>/
```

| Componente | Origem | Notas |
|---|---|---|
| `<account display name>` | autor da thread, via `author_folder` → `_safe_folder` (`fs_writer.py:40-51`) | separadores de caminho e caracteres ilegais no Windows (`:*?"<>\|`) tornam-se `_`; `.`/`..` rejeitados (proteção de travessia de caminho para espaços compartilhados); todo o resto — incluindo espaços — é mantido |
| `<mode>` | `detect_mode` | um dos cinco modos; consulte [Modos de conversa](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` `lastUpdated` prefixo de data | a data da última atualização da plataforma, **não** a data de exportação — ela se move quando uma thread continuada é atualizada (veja migração abaixo) |
| `<title-slug>` | `slugify(title)` (`normalize.py:261-263`) | máximo 40 caracteres, caracteres não-palavra → `-`, vazio → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | primeiros 8 caracteres do UUID da thread — a âncora de identidade do diretório |

<a id="files-in-a-thread-directory" data-pplx-source-anchor="true"></a>
## Arquivos em um diretório de thread

<a id="threadjson-metadata-and-registries" data-pplx-source-anchor="true"></a>
### thread.json — metadados e registros

Escrito por `write_thread` (`fs_writer.py:224-253`). Chaves sempre presentes:

| Chave | Conteúdo |
|---|---|
| `web_uuid` | entryUUID da web — o UUID na URL da thread; a identidade da thread |
| `psc_uuid` | `context_uuid` da plataforma (anulável; do primeiro turno não vazio) — o ID duplo usado por índices de espaço |
| `url` | URL canônica da thread |
| `title` | título da thread |
| `mode` | modo detectado (`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | nome de exibição da conta do autor |
| `export_via` | nome de usuário da conta que realizou a exportação — importante para threads de espaço compartilhado exportadas por outra conta |
| `space` | `{"uuid", "title", "slug"}` ou `null` |
| `lastUpdated` | timestamp da última atualização da plataforma (contrato de comparação de máquina para sincronização incremental) |
| `threadAccess` | sinalizador de acesso da plataforma |
| `n_turns` | contagem de turnos |
| `n_sources` | contagem de citações em toda a thread |
| `metadata` | `thread_metadata` da resposta da API, literalmente |
| `report_info` | `{"title", "file_name", "url"}` ou `null` |
| `exported_at` | hora da exportação (UTC ISO 8601) |

Chaves opcionais — ausentes quando não há nada a registrar:

| Chave | Adicionada quando | Conteúdo |
|---|---|---|
| `interruptions` | qualquer fluxo de trabalho não concluído (`fs_writer.py:242-244`) | lista de `{location, kind, headline, status}`; consulte [Modos de conversa — Interrupções](modes.md#interruptions-non-completed-workflows) |
| `answer_variants` | uma variante de reescrita de resposta é detectada (`fs_writer.py:247-252`) | `side_by_side_metadata` restrito localizando campos; consulte [Modos de conversa — Variantes de reescrita de resposta](modes.md#answer-rewrite-variants-answer_variants) |
| `remote_deleted` | `pplx-export sync-deleted --online` confirma exclusão remota | timestamp de exclusão, escrito no local, idempotente (valor existente nunca sobrescrito; `sync_deleted_cmd.py:215-244`) — o arquivo local em si é mantido |

<a id="conversationmd-the-compact-read" data-pplx-source-anchor="true"></a>
### conversation.md — a leitura compacta

`render_conversation` (`render.py:641`): cabeçalho do título (modo / autor / turnos / contagem de citações),
em seguida, por turno, um par `### Query` + `### Answer` com respostas completas e, quando presente, o
apêndice de tarefa em segundo plano no final. Este é o arquivo a ser aberto primeiro; os processos
de trabalho por turno estão em `turns/`.

<a id="turnsturn_nnnnmd-the-full-read" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md — a leitura completa

`render_turn` (`render.py:596`): um arquivo por turno (`turn_0001.md` …), cada um com o processo
de trabalho completo — etapas, chamadas de ferramenta, execuções de subagente, tabelas, citações por turno. Quando a
contagem de turnos de uma thread diminui, arquivos `turn_*.md` obsoletos de numeração alta são excluídos, mas arquivos não tocados mantêm
seu mtime (`fs_writer.py:287-301`).

### sources.json / sources.md

Citações em toda a thread, deduplicadas por URL (`fs_writer.py:270-278`). `sources.json` é
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`; `sources.md` é a mesma
lista como uma lista de links Markdown numerada.

### report.md

O produto do relatório de pesquisa aprofundada, escrito apenas quando a thread contém um
(`fs_writer.py:308-316`): título do relatório, o nome do arquivo do produto original e, em seguida, o relatório completo
em Markdown.

<a id="raw_entriesjson-raw_blocksjson-raw-fidelity" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json — fidelidade bruta

As respostas da API, persistidas literalmente **antes** de qualquer análise (`fs_writer.py:257-266`):

- `raw_entries.json` — a resposta simples: `{"thread_metadata", "entries", "background_entries"}`.
  Sempre presente.
- `raw_blocks.json` — a resposta esquematizada, mesma forma. Ausente para threads `search`
  (sem busca de blocos); buscada para os outros quatro modos, e também como fallback quando todos os
  sinais de detecção de modo estão ausentes.

Esses dois arquivos são a âncora de fidelidade do arquivo: análise, renderização e registros podem
ser reconstruídos a partir deles offline, com zero rede. Consulte
[Operações offline](../architecture/offline-operations.md).

<a id="assets-products-and-their-manifest" data-pplx-source-anchor="true"></a>
### assets/ — produtos e seu manifesto

Produtos baixáveis (arquivos do modo Computer e quaisquer outros ativos listados pela API) são buscados
de URLs assinadas do CloudFront para `assets/files/`; a extensão é decidida no momento do download
a partir do caminho da URL, bytes mágicos de conteúdo ou tipo de ativo. `assets/assets_manifest.json`
(`fs_writer.py:320-330`) registra cada versão:

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` é sempre o **número total de versões** (Σ `len(versions)`), não o número de grupos
de arquivos — use `len(files)` para isso.

<a id="the-index-layer" data-pplx-source-anchor="true"></a>
## A camada index/

`web_archive/index/` contém estado e índices gerenciados pela ferramenta — não edite manualmente:

| Arquivo | Escrito por | Semântica |
|---|---|---|
| `library_<account>.json` | `pplx-export index` (`index_cmd.py:17-43`) | índice completo de threads da conta (GraphQL); entrada para índices de lote / agendamento / espaço |
| `batch_state.json` | `BatchState` (`state.py`) | checkpoint retomável: uuid → status (ok/error/expired/deleted) + lastUpdated; gravações atômicas; arquivos corrompidos com backup automático como `.corrupt-<ts>` |
| `.cookies.json` | cache de cookies (`common.py:111`, `common.py:150`) | cache de cookies com frescor de 12h com origem e e-mail da conta; escrito `0o600` e então substituído atomicamente (credenciais de sessão, legível apenas pelo proprietário) |
| `space_<slug>.json` | `pplx-export space-index` (`spaces_cmd.py:106-167`) | lista de threads por espaço, incluindo o mapeamento de ID duplo `context_uuid` |
| `space_meta.json` | `pplx-export spaces --fetch-meta` (`spaces_cmd.py:299-330`) | cache de proprietário/membro do espaço reutilizado em reconstruções |
| `credit_usage_<account>.json` | `pplx-export usage-backfill` (`usage_backfill_cmd.py:17`) | uso de crédito por thread (idempotente, retomável, liberado a cada 25 entradas) |
| `cron_snippet.txt` | `pplx-export schedule` (`scheduler.py:48-78`) | trecho de invocação cron (caminhos absolutos) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (`variant_log.py:76`) | registro central de variantes de reescrita de resposta, deduplicado por (thread, entry), idempotente |
| `logs/` | `--log-file` (`common.py:218-229`) | logs DEBUG completos |

<a id="the-spaces-layer" data-pplx-source-anchor="true"></a>
## A camada spaces/

`pplx-export spaces` agrega `index/library_*.json` em um índice de espaço (`spaces_cmd.py:259-389`):
um `<slug>.md` por espaço (contas participantes, cabeçalho proprietário/membro, tabela de threads,
backlinks de local de exportação) mais um registro `spaces.json`.

!!! note "Local de saída"
    `spaces/` é escrito relativo ao diretório de trabalho atual (`spaces_cmd.py:332`) — ele
    **não** segue `--out`. Não edite manualmente: a próxima reconstrução sobrescreve.

<a id="cross-day-continuation-directory-migration-by-uuid-identity" data-pplx-source-anchor="true"></a>
## Continuação entre dias: migração de diretório por identidade UUID

O nome do diretório incorpora a data `lastUpdated`, então, quando você continua uma thread em um dia posterior,
o cálculo ingênuo produz um diretório *novo*. O escritor impede duplicatas por identidade UUID
(`thread_dir_for`, `fs_writer.py:58-72`):

1. **Encontrar**: `find_thread_dirs` (`fs_writer.py:74-105`) pesquisa todo o arquivo em busca de
   diretórios terminando em `_<uuid8>` — entre contas e modos. Um candidato é aceito apenas
   se seu `thread.json` existir, for analisável e seu `web_uuid` corresponder exatamente; diretórios ausentes, corrompidos ou
   incompatíveis nunca são tocados (melhor pular uma migração do que mesclar incorretamente).
2. **Mesclar**: `_merge_into` (`fs_writer.py:107-178`) mescla o diretório antigo no novo —
   união de arquivos (nada exclusivo do diretório antigo é perdido); mesmo nome + mesmo conteúdo → pular;
   conflitos de mesmo nome **sempre mantêm o lado de destino** (o semanticamente mais novo), com cada
   conflito registrado. Cada arquivo copiado é verificado por sha256 antes que o diretório antigo seja excluído; qualquer
   falha deixa o diretório antigo intacto e as tentativas são idempotentes.
3. **Limpar duplicatas históricas**: `consolidate_uuid` (`fs_writer.py:180-209`) mescla
   diretórios de data duplicados de um UUID em todo o arquivo, mantendo aquele com o máximo
   `lastUpdated` — a proteção para duplicatas deixadas por versões mais antigas.

A mesma rigidez de UUID protege os backlinks do índice de espaço: diretórios candidatos com um
`thread.json` ausente/corrompido/incompatível nunca são vinculados.

<a id="hand-editable-vs-tool-managed" data-pplx-source-anchor="true"></a>
## Editável manualmente vs. gerenciado pela ferramenta

- **Gerenciado pela ferramenta (não edite manualmente)**: tudo dentro dos diretórios de thread, mais `index/`,
  `spaces/` e `relations/`. Se o conteúdo estiver errado, corrija a ferramenta e regenere — correções
  de renderização passam por `pplx-export re-render`, correções de dados pelo comando de backfill correspondente
  (consulte [Comandos de manutenção](maintenance-commands.md)) — para que cada artefato permaneça reproduzível
  a partir dos dados brutos.
- **Editável manualmente**: a documentação e os relatórios de revisão `web_archive/crosscheck/`.
  Uma exceção de nível de usuário: uma resposta alternativa resgatada manualmente pode ser registrada como
  `rewritten_answer_variant.md` dentro do diretório da thread — consulte
  [Modos de conversa — Variantes de reescrita de resposta](modes.md#answer-rewrite-variants-answer_variants).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Consulte também

- [Modos de conversa](modes.md) — os cinco modos e o que cada um produz
- [Sincronização incremental](incremental-sync.md) — como `lastUpdated` impulsiona reexportações
- [Comandos de manutenção](maintenance-commands.md) — re-renderização, backfills, sincronização de exclusão
- [Modelo de dados e contrato de diretório](../architecture/data-model.md) — as dataclasses subjacentes
- [Pipeline de exportação](../architecture/export-pipeline.md) — como esses arquivos são escritos
- [Operações offline](../architecture/offline-operations.md) — reconstruindo tudo a partir de `raw_*.json`
