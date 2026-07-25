---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/rate-limiting.md"
translation_source_sha256: "0f94f3ddbb3a7ac5ea7eef4a48ecd5479e5a834d8fda263c700df5ada0de3350"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="rate-limiting" data-pplx-source-anchor="true"></a>
# Limitação de Taxa

Cada número na política de ritmo serve a um objetivo: o tráfego de arquivamento deve se parecer com navegação comum. Uma exportação de thread única custa 1–2 requisições — aproximadamente uma visualização de página — e execuções em lote distribuem essas requisições em intervalos aleatórios sem concorrência. Este é um requisito explícito de mitigação de risco (`pplx_export/core/throttle.py:1-2`), não um parâmetro de desempenho ajustável.

<a id="the-numbers" data-pplx-source-anchor="true"></a>
## Os números

| onde | ritmo | código |
|---|---|---|
| `batch`: entre threads | uniforme aleatório 10–20 s (`--delay-min` / `--delay-max`) | `pplx_export/cli.py:126-129`, `pplx_export/core/throttle.py:33-36` |
| `sync-deleted --online`: entre candidatos | uniforme aleatório 10–20 s | `pplx_export/cli.py:164-167`, `pplx_export/commands/sync_deleted_cmd.py:368-369` |
| `search-mode-backfill`: fallback online | uniforme aleatório 10–20 s | `pplx_export/cli.py:144-147` |
| paginação dentro de uma thread / listagem de espaço | ≥3 s entre páginas | `pplx_export/sites/perplexity/rest.py:39,56`, `pplx_export/sites/perplexity/adapter.py:285-309` |
| retroalimentação de blocos esquematizados (computer / deep-research / council / study) | ≥4 s de espera antes da segunda busca | `pplx_export/sites/perplexity/adapter.py:27-32,88` |
| `spaces --fetch-meta` | 3 s por espaço | `pplx_export/commands/spaces_cmd.py:328` |
| `usage-backfill` | 3 s por thread | `pplx_export/commands/usage_backfill_cmd.py:77` |
| `assets-backfill` fases online | 3 s por thread | `pplx_export/commands/assets_backfill_cmd.py:215,456` |
| downloads de ativos dentro de uma thread | 0,5 s | `pplx_export/sites/perplexity/assets.py:28,103` |
| `assets-backfill` fase CDN | 6 downloads paralelos, sem atraso | `pplx_export/commands/assets_backfill_cmd.py:460-475` |
| concorrência de API | nenhuma — nunca | — |

<a id="why-these-numbers" data-pplx-source-anchor="true"></a>
## Por que esses números

- **Exportação única = 1–2 requisições ≈ uma visualização de página.** Uma thread de busca custa uma `GET /rest/thread/<uuid>`; computer / deep-research / council / study adicionam exatamente uma busca de blocos esquematizados (`pplx_export/sites/perplexity/adapter.py:87-89`). Isso é aproximadamente o que um navegador faz quando você abre a página uma vez — o arquivamento não adiciona carga significativa além do uso normal.
- **Intervalo aleatório de 10–20 s, sem concorrência.** Ritmo de leitura humana, e a aleatoriedade evita timing perfeitamente metronômico. Requisições seriais mantêm a taxa abaixo do que a navegação comum já produz.
- **≥3 s para viradas de página.** Paginação dentro de uma thread longa imita o tempo de rolagem e leitura.
- **≥4 s antes da busca de blocos.** A re-busca esquematizada atingiria a API consecutivamente com a busca simples; a pausa imita o atraso antes de uma página pesada carregar sua carga completa.
- **0,5 s para downloads de ativos.** Pequenos arquivos estáticos, muito mais baratos que chamadas de API — mas ainda ritmados.
- **A fase CDN é a única relaxação.** Downloads de URL assinada atingem a rede de entrega de conteúdo, não a API Perplexity, então 6 conexões paralelas são aceitáveis ali e somente ali.

<a id="error-handling-and-backoff" data-pplx-source-anchor="true"></a>
## Tratamento de erros e backoff

Toda classificação ocorre em `CookieTransport._request` (`pplx_export/core/http/cookie_transport.py:63-126`); cada requisição recebe até `max_retries=3` tentativas (`cookie_transport.py:48`).

```mermaid
flowchart TD
    R{response} -->|"2xx"| OK["reset backoff counter"]
    R -->|"429"| BO["backoff + retry (≤3 attempts)"]
    R -->|"5xx / network error"| BO
    R -->|"401 / 403"| AF["raise immediately →<br/>abort after 3 consecutive"]
    R -->|"ENTRY_EXPIRED / ENTRY_DELETED"| TERM["terminal mark<br/>never retried"]
```

| resposta | classificação | tratamento |
|---|---|---|
| 2xx | sucesso | contador de backoff resetado (`cookie_transport.py:77`) — contagens nunca se acumulam entre requisições |
| 429 | limitado por taxa | backoff e repetição (`cookie_transport.py:86-92`) |
| 500 / 502 / 503 / 504 | erro de servidor transitório (504 é comumente um problema do Cloudflare) | backoff e repetição pelo menos uma vez antes de desistir (`cookie_transport.py:99-107`) |
| erro de rede | transitório | backoff e repetição (`cookie_transport.py:117-125`) |
| 401 / 403 | falha de autenticação | `AuthTransportError` levantado imediatamente — sem backoff (`cookie_transport.py:82-85`) |
| 400 + `ENTRY_EXPIRED` | remoção da plataforma | `EntryExpiredError` — terminal, nunca repetido (`cookie_transport.py:96-98`) |
| 400 + `ENTRY_DELETED` | exclusão por usuário/remoto | `EntryDeletedError` — terminal, nunca repetido (`cookie_transport.py:93-95`) |
| 404 / outros códigos | erro comum | sem repetição em nível de transporte; **nunca** mapeado para estado terminal (`cookie_transport.py:108-116`) |

**Fórmula de backoff** (`pplx_export/core/throttle.py:38-50`):
`delay_max × 3^N`, onde `N` é a contagem de falhas consecutivas (expoente limitado a 8), com jitter de ±20% contra sincronização, limitado a 300 s. Não há espera desnecessária após a última tentativa falha, e `throttle.reset()` limpa o contador no primeiro sucesso (`throttle.py:52`).

Por que cada regra existe:

- **Backoff 429** — o servidor explicitamente pediu para desacelerar; honre-o exponencialmente.
- **Repetição 5xx** — um problema de gateway único não deve falhar uma thread.
- **401/403 sem backoff** — esperar não pode curar um cookie morto.
- **`ENTRY_EXPIRED` sem repetição** — a remoção da plataforma (janela de ~3 meses) é permanente; repetir só queima requisições e orçamento de backoff.
- **404 nunca terminal** — uma thread criada por `pplx-ask` pode dar 404 transitoriamente logo após a criação (atraso de propagação); uma marca terminal enterraria uma thread viva que está apenas brevemente invisível.

<a id="auth-fail-fast" data-pplx-source-anchor="true"></a>
## Falha de autenticação rápida

A camada de lote conta falhas de autenticação consecutivas (`_AUTH_FAIL_FAST = 3`, `pplx_export/commands/batch_cmd.py:43`). Qualquer resposta que alcançou o servidor — incluindo `ENTRY_DELETED` / `ENTRY_EXPIRED` — prova que o cookie funciona e reseta o contador (`batch_cmd.py:170-182`). Três 401/403 consecutivos e a execução salva seu arquivo de estado, então aborta (`batch_cmd.py:190-194`): continuar com um cookie morto faria centenas de threads falharem cada uma uma vez — horas perdidas. `sync-deleted` aplica a mesma disciplina (`pplx_export/commands/sync_deleted_cmd.py:111,333-337`). A correção é atualizar o cookie e reexecutar; tudo já exportado é pulado.

`batch` e o transporte compartilham uma instância `Throttle` (`pplx_export/cli.py:280-282`, `batch_cmd.py:101-105`), então a contagem de backoff nunca se divide entre camadas — e a instância compartilhada sobrevive à troca automática de conta.

<a id="scheduling-periodic-sync" data-pplx-source-anchor="true"></a>
## Agendamento de sincronização periódica

`pplx-export schedule` calcula o plano incremental atual (contagens de novos/atualizados) e escreve um trecho de cron para `<out>/index/cron_snippet.txt` (`pplx_export/commands/misc_cmd.py:86-96`, `pplx_export/hooks/scheduler.py:48-77`):

```bash
pplx-export schedule --account alice
```

```cron
17 3 * * * cd '<out-parent>' && '/abs/path/to/pplx-export' batch --account 'alice' --out '<out>'
```

- Execuções periódicas são **apenas incrementais** (parada antecipada) — sem re-buscas completas (`scheduler.py:4-9`).
- O trecho usa caminhos absolutos e entre aspas porque o diretório de trabalho do cron e `PATH` são imprevisíveis (`scheduler.py:63-75`).
- Instale-o com `crontab -e` e ajuste o horário a gosto; distribua múltiplas contas em intervalos diferentes.
- Opcional: adicione uma varredura manual semanal ou mensal com `pplx-export batch --account alice --full` (veja [incremental-sync.md](incremental-sync.md)).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Veja também

- [incremental-sync.md](incremental-sync.md) — o que cada execução agendada realmente exporta
- [pplx-export.md](pplx-export.md) — `--delay-min` / `--delay-max` e as outras opções de comando
- [troubleshooting.md](troubleshooting.md) — o que fazer após uma abortagem rápida por falha de autenticação
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — a taxonomia completa de erros
- [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) — semântica de erros do lado da plataforma (`ENTRY_EXPIRED`, `ENTRY_DELETED`, Cloudflare)
- [../reference/api/api-authentication.md](../reference/api/api-authentication.md) — cookies e troca de múltiplas contas
