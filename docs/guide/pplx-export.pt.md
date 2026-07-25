---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/pplx-export.md"
translation_source_sha256: "6ef4d5b78ce748c1fd97d6d1dfaea40f0bdfd427f23a089b6110c2fb0e4f9c53"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` é a CLI de arquivamento: ela extrai índices de conversas do Perplexity, exporta threads para o arquivo local e mantém as visualizações derivadas (índice de espaço, snippet cron). Esta página cobre os subcomandos do lado de captura — `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule` — mais o comando de configuração única `init`. Os subcomandos de backfill/reparo estão em [maintenance-commands.md](maintenance-commands.md); a CLI de consulta é coberta em [pplx-ask.md](pplx-ask.md).

<a id="common-options" data-pplx-source-anchor="true"></a>
## Opções comuns

Todo subcomando aceita estas flags (definidas uma vez em `pplx_export/commands/common.py`):

| Flag | Significado | Padrão |
|---|---|---|
| `--account NAME` | Conta alvo. Quando o email do cookie não corresponde ao email registrado, os tokens de sessão do navegador por conta são enumerados para alternar automaticamente | `default_account` da configuração de nível de usuário |
| `--config PATH` | Arquivo de configuração de nível de usuário (registro de contas). Prioridade: `--config` > env `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | cadeia de busca padrão |
| `--site NAME` | Adaptador de site | `perplexity` |
| `--out DIR` | Raiz de saída do arquivo | `./web_archive` |
| `--cookies-from BROWSER` | Importar cookies de um navegador (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | Arquivo de cookie Netscape ou arquivo de cookie JSON | — |
| `--transport MODE` | `cookie` = requisições diretas com cookie; `webbridge` = buscar dentro do contexto da página do navegador | `cookie` |
| `-v`, `--verbose` | Saída DEBUG (rastros de requisição, decisões internas); repetível | desligado |
| `--log-file [PATH]` | Escrever o log completo no disco; sem valor, caminho automático `<out>/index/logs/<cmd>-<timestamp>.log` | desligado |

- `--cookies-from` / `--cookies` são mutuamente exclusivos com `--transport webbridge` — a ponte executa no contexto da página e já carrega os cookies do navegador.
- `pplx-export --version` imprime a versão do pacote e sai (apenas no nível superior, não é uma flag de subcomando).
- Registro de conta, fontes de cookie e alternância de múltiplas contas: [configuration.md](configuration.md). Onde tudo fica no disco: [archive-layout.md](archive-layout.md).

## init

Descobrir contas a partir de cookies do navegador e escrever a configuração de nível de usuário — a alternativa automática para copiar manualmente `config.example.toml` (veja [configuration.md](configuration.md)).

| Flag | Significado | Padrão |
|---|---|---|
| `--force` | Sobrescrever um arquivo de configuração existente | desligado (recusa sobrescrever) |
| `--create-bot-space [TITLE]` | Criar o espaço BOT via API quando nenhum título de espaço corresponde (uma operação de escrita na conta); um TÍTULO explícito orienta tanto a correspondência quanto a criação, caso contrário o título vem de `--bot-title`; sem esta flag `[bot_space]` é escrito vazio | desligado |
| `--bot-title TITLE` | Título do espaço usado tanto para corresponder a um espaço existente quanto para nomear um criado | `BOT` |
| *(opções comuns se aplicam)* | Flags de fonte de cookie escolhem onde as contas são descobertas; para `init` apenas, `--config` é o caminho de **escrita** (a carga estrita de configuração é pulada) | |

Comportamentos principais:

- Enumeração de tokens: cookies de sessão por conta (`__Secure-pplx.session.<uid>`) são coletados dos armazenamentos do navegador — ou, com `--cookies FILE`, escaneados do arquivo de cookie (uma exportação completa pode conter várias contas). Sem tokens enumeráveis, apenas a sessão ativa atual é sondada.
- Sonda de sessão: cada token é testado contra `GET /api/auth/session` para aprender o email/nome de exibição da conta; tokens que falham ou não retornam email são pulados com um aviso.
- Montagem do registro: cada chave de conta é derivada da parte local do email (colisões recebem sufixos `-2`/`-3`…); `default_account` é definido para a conta atualmente ativa, caso contrário a primeira descoberta.
- Espaço BOT: um espaço é correspondido por título exato (insensível a maiúsculas/minúsculas) via `list_user_collections`; quando nada corresponde, `--create-bot-space [TITLE]` o cria no local (um TÍTULO explícito substitui `--bot-title` tanto para correspondência quanto para criação), caso contrário `[bot_space]` é deixado vazio.
- O TOML é escrito atomicamente (arquivo temporário + renomear) com permissões 0600, e um arquivo existente nunca é sobrescrito sem `--force`. O comando termina com uma linha JSON de resumo: caminho da configuração, chaves de conta, conta padrão, uuid/slug do espaço BOT.
- `--transport webbridge` é rejeitado — o canal de contexto de página não pode enumerar tokens por conta.

```bash
pplx-export init                          # write the default ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --config /path/to/config.toml --force   # custom path, overwrite allowed
```

## index

Buscar a lista completa de conversas da conta (GraphQL) e escrever o índice mestre `index/library_<account>.json` — a linha de base contra a qual todo outro comando faz diff.

| Flag | Significado | Padrão |
|---|---|---|
| *(apenas opções comuns)* | | |

Comportamentos principais:

- Preserva o enriquecimento `search_mode` escrito por `search-mode-backfill`: linhas de índice não o carregam nativamente, então na atualização ele é mesclado de volta do índice antigo por `entryUUID`.
- Execute-o antes de `batch`, `sync-space` e `sync-deleted` — seus diffs são tão recentes quanto este índice.

```bash
pplx-export index --account alice
```

## space-index

Extrair a lista de conversas "Todas" de um espaço — incluindo threads compartilhadas por outros membros — para `index/space_<slug>.json`.

| Flag | Significado | Padrão |
|---|---|---|
| `SPACE_URL` (posicional) | URL da página do espaço | obrigatório |
| `--transport webbridge` | Usar o caminho legado de renderização do navegador em vez de REST | `cookie` (REST direto) |

Comportamentos principais:

- Caminho padrão é REST direto: `list_collection_threads` sobre o transporte de cookie com paginação por deslocamento; linhas incluem `context_uuid` e `answer_preview`.
- Com `--transport webbridge` ele recorre à rolagem da página do espaço renderizada e à raspagem das propriedades das linhas — um backup caso a estrutura REST mude.
- As linhas são escritas das mais recentes para as mais antigas por `lastUpdated`.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

Exportar uma única thread (URL ou UUID simples) para seu diretório de arquivo `<out>/<account-folder>/<mode>/<thread-dir>/`.

| Flag | Significado | Padrão |
|---|---|---|
| `THREAD` (posicional) | URL ou UUID da thread | obrigatório |
| `--force` | Reexportar mesmo quando `lastUpdated` não mudou | desligado |

Comportamentos principais:

- Se a cópia arquivada já estiver atualizada, a exportação é pulada sem escritas; `--force` substitui a verificação.
- `lastUpdated` é obtido do índice da biblioteca local quando a thread está listada lá (mesma semântica e formato que `batch`), recorrendo ao valor da plataforma caso contrário.
- Estados terminais são registrados graciosamente, sem traceback: `ENTRY_DELETED` marca `deleted` em `batch_state.json`, `ENTRY_EXPIRED` marca `expired` — o arquivo local existente é mantido intocado de qualquer forma.
- Uma exportação bem-sucedida escreve `ok` em `index/batch_state.json`, para que o plano incremental conte a thread como "exportada e inalterada".
- O que vai para o diretório da thread: [archive-layout.md](archive-layout.md); o pipeline de exportação em si: [../architecture/export-pipeline.md](../architecture/export-pipeline.md).

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

Exportar em massa as threads de uma conta — o driver diário, com parada antecipada incremental e pontos de verificação retomáveis.

| Flag | Significado | Padrão |
|---|---|---|
| `--force` | Reexportar todas as threads (estados terminais excluídos) | desligado |
| `--full` | Varredura completa: threads inalteradas ainda são puladas, mas sem parada antecipada | desligado |
| `--limit N` | Processar apenas as primeiras N linhas da lista (mais recentes primeiro) | todas |
| `--mode MODE` | Exportar apenas threads `search` / `deep-research` / `computer` / `council` / `study` | todos os modos |
| `--delay-min SEC` | Limite inferior do intervalo aleatório entre threads | `10` |
| `--delay-max SEC` | Limite superior do intervalo aleatório entre threads | `20` |

Comportamentos principais:

- Requer `index/library_<account>.json` — execute `index` primeiro.
- **Parada antecipada incremental** padrão: a lista é ordenada das mais recentes para as mais antigas e a sequência final de threads "exportadas e inalteradas" é cortada inteiramente; lacunas deixadas por execuções interrompidas (erro/nunca exportadas) ficam acima desse sufixo e ainda são reparadas. `--full` desabilita a parada antecipada (backstop periódico, ou quando lacunas no arquivo são suspeitas); `--force` reexporta tudo exceto estados terminais, que nunca são repetidos. Semântica completa: [incremental-sync.md](incremental-sync.md).
- Filtragem `--mode`: linhas que carregam `search_mode` (o campo autoritativo da plataforma enriquecido por `search-mode-backfill`) correspondem exatamente via `SEARCH_MODE_MAP` — nesse caminho `--mode search` não puxa mais threads de deep-research/council/study. Linhas sem `search_mode` recorrem a heurísticas do índice: `computer` = modo `COMPUTER`; `deep-research` = displayModel `pplx_alpha`; `council` = `pplx_agentic_research`; `study` = `pplx_study`; `search` = as linhas restantes de modo `SEARCH` (incluindo esses três tipos — filtre-os precisamente exportando os modos específicos separadamente).
- O estado é salvo em `index/batch_state.json` após cada thread — interrompa e execute novamente livremente.
- Falha rápida de autenticação: 3 respostas 401/403 consecutivas abortam a execução (um cookie expirado não pode se autocorrigir, e continuar falharia centenas de threads uma por uma).
- Ritmo: uma pausa aleatória `--delay-min`–`--delay-max` entre threads; 429/5xx são recuados pela camada de transporte. Detalhes: [rate-limiting.md](rate-limiting.md).
- Threads que atingem variantes de resposta reescritas são registradas em `index/answer_variants_log.jsonl` com um aviso para tratá-las manualmente o mais rápido possível (veja [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md)).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

Reconstruir o índice de visualização de espaço — uma página Markdown por espaço mais um registro `spaces.json` — a partir dos índices da biblioteca local.

| Flag | Significado | Padrão |
|---|---|---|
| `--fetch-meta` | Atualizar metadados de proprietário/membro antes de reconstruir | desligado |

Comportamentos principais:

- Sem `--fetch-meta` o comando é puramente local (zero rede): ele agrega threads por slug de espaço em todos os arquivos `library_*.json`, com estatísticas de contas participantes e backlinks para os diretórios de thread exportados.
- A saída vai para `./spaces/` relativo ao diretório de trabalho atual — execute-o a partir do diretório que contém `web_archive/` para que os backlinks nas páginas de espaço sejam resolvidos.
- `--fetch-meta` primeiro atualiza o cache de proprietário/membro de cada espaço via `get_collection` (1 requisição por espaço, intervalo de 3s) para `index/space_meta.json`; quando a conta atual não pode ver um espaço, uma conta que pode é tentada automaticamente (cookies alternam por conta própria).

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

Sincronizar o campo `space` de arquivos `thread.json` já arquivados com o índice atual — puramente local, zero rede.

| Flag | Significado | Padrão |
|---|---|---|
| *(apenas opções comuns; apenas `--out` importa)* | | |

Comportamentos principais:

- Pré-requisito: execute `index` primeiro — o `library_*.json` atualizado é a fonte da verdade para a propriedade atual do espaço.
- Compara slugs de espaço por thread e corrige `thread.json` no local em caso de divergência; as primeiras 30 alterações são registradas.
- Após qualquer alteração, o índice `spaces/` é reconstruído automaticamente junto.

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

Calcular o plano de exportação incremental desta rodada e escrever um snippet cron que o cron do sistema pode chamar diretamente.

| Flag | Significado | Padrão |
|---|---|---|
| *(apenas opções comuns)* | | |

Comportamentos principais:

- Busca um índice ao vivo e relata o plano como contagens total/novo/atualizado, usando a mesma função pura de parada antecipada (`plan_incremental`) que `batch` — veja [incremental-sync.md](incremental-sync.md).
- Escreve `<out>/index/cron_snippet.txt` contendo uma linha `17 3 * * *` da forma `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'` — os caminhos são absolutos e entre aspas porque o cwd e o PATH do cron são imprevisíveis. O caminho do executável é resolvido via `shutil.which`; quando isso falha, o snippet recai para o nome simples `pplx-export`.
- Execuções agendadas são apenas incrementais por design; execute `batch --full` manualmente como um backstop periódico.

```bash
pplx-export schedule --account alice
```
