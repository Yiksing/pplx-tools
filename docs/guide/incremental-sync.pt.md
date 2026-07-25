---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/incremental-sync.md"
translation_source_sha256: "35868edfb3e8e914afd9afa1b00370bffb9f8a50ca374691229f41d51ffa9b64"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="incremental-sync" data-pplx-source-anchor="true"></a>
# Sincronização Incremental

`pplx-export batch` é projetado para ser executado com frequência: cada execução exporta apenas o que é novo ou
modificado, corrige lacunas deixadas por execuções interrompidas e nunca retoca threads que a
plataforma já aposentou. A única fonte da verdade para "o que foi exportado" é `index/batch_state.json` (`BatchState`,
`pplx_export/core/state.py:63`), atualizada após cada thread — não há
cópia sombra separada.

<a id="prerequisites-and-basic-usage" data-pplx-source-anchor="true"></a>
## Pré-requisitos e uso básico

```bash
pplx-export index --account alice   # refresh index/library_alice.json first
pplx-export batch --account alice   # incremental export (early stop, resumable)
```

`batch` se recusa a executar sem o índice
(`pplx_export/commands/batch_cmd.py:79-81`). `--limit N` e `--mode <mode>`
filtram as linhas do índice antes do planejamento; linhas sem `entryUUID` são ignoradas
com um aviso em vez de interromper a execução (`batch_cmd.py:95-100`).

<a id="how-the-incremental-plan-works" data-pplx-source-anchor="true"></a>
## Como o plano incremental funciona

1. **Ordenar.** As linhas do índice são ordenadas por `lastUpdated`, da mais recente para a mais antiga
   (`batch_cmd.py:89`). Conversas novas e antigas retomadas (cujo
   `lastUpdated` as moveu para cima) ficam ambas no topo — essa ordenação é
   o que torna a parada antecipada segura.
2. **Classificar.** `plan_incremental`
   (`pplx_export/hooks/incremental.py:36-87`) — uma função pura compartilhada por
   `batch` e `schedule` — atribui a cada linha exatamente uma ação:

   | ação | condição | o que o lote faz |
   |---|---|---|
   | `new` | uuid nunca visto em `batch_state` | exportar |
   | `updated` | `lastUpdated` difere do valor registrado, ou `--force` | reexportar |
   | `done` | status `ok` e `lastUpdated` inalterados | pular |
   | `expired` | a plataforma retornou `ENTRY_EXPIRED` em uma tentativa anterior | pular — terminal, nunca repetido |
   | `deleted` | `sync-deleted` confirmou uma exclusão remota | pular — terminal, nunca repetido |

3. **Parada antecipada.** Por padrão (nem `--full` nem `--force`), a sequência
   final mais longa de entradas terminais (`done` / `expired` / `deleted`) é cortada
   por completo e contada como `n_stopped` (`incremental.py:83-87`). Como a
   lista está ordenada da mais recente para a mais antiga, tudo abaixo de uma entrada inalterada é necessariamente
   mais antigo e também inalterado — escanear mais só consumiria tempo.

   ```mermaid
   flowchart TD
       IDX["library index rows<br/>sorted by lastUpdated, newest first"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → export"]
       PLAN --> UPD["updated → re-export"]
       PLAN --> DONE["done → skip"]
       PLAN --> TERM["expired / deleted → skip (terminal)"]
       DONE --> STOP["early stop:<br/>trailing terminal run trimmed"]
       TERM --> STOP
   ```

4. **Executar.** Cada thread exportada é marcada imediatamente (`mark_ok` /
   `mark_error` / `mark_expired` / `mark_deleted`) e o arquivo de estado é salvo
   após cada item (`batch_cmd.py:154-201`); um `KeyboardInterrupt` também salva
   antes de propagar (`batch_cmd.py:158-161`). As gravações são atômicas — arquivo temporário
   mais `os.replace` (`state.py:145-152`) — portanto, uma execução interrompida nunca deixa
   JSON truncado.

<a id="gap-healing-after-interrupted-runs" data-pplx-source-anchor="true"></a>
## Correção de lacunas após execuções interrompidas

A parada antecipada nunca enterra uma lacuna. Threads que falharam (status `error`) ou nunca
foram alcançadas ficam **acima** do sufixo terminal, então a próxima execução as replaneja
como `updated` / `new` e as exporta antes que o ponto de parada antecipada seja atingido
(`incremental.py:12-14`, `batch_cmd.py:206-208`). Combinado com salvamentos de estado
por item, uma execução em lote pode ser interrompida em qualquer ponto e simplesmente reexecutada.

Se `batch_state.json` em si estiver corrompido, ele não é zerado silenciosamente: o
original é renomeado para `batch_state.json.corrupt-<timestamp>` para que os estados terminais
registrados não sejam perdidos e repetidos desnecessariamente (`state.py:68-81`).

<a id="-full-and-force" data-pplx-source-anchor="true"></a>
## `--full` e `--force`

| flag | efeito | estados terminais | quando usar |
|---|---|---|---|
| *(padrão)* | parada antecipada sobre a sequência terminal final | ignorados | toda execução regular / agendada |
| `--full` | varredura completa, sem parada antecipada; threads inalteradas ainda são ignoradas como `done` | ignorados | backstop periódico, ou quando houver suspeita de lacunas no arquivo |
| `--force` | reexportar tudo, mesmo threads inalteradas | ainda excluídos — nunca repetidos | após correções no pipeline que precisam reobter dados brutos |

Estados terminais são excluídos de `--force` por design: repetir uma thread expirada ou
excluída remotamente só desperdiça requisições e orçamento de backoff
(`batch_cmd.py:120-127`).

Veja também [`status`](maintenance-commands.md#status): um relatório sem rede do
estado da conta e o plano de mudança calculado com a mesma semântica `plan_incremental`
(`new`/`updated`/contagem de parada antecipada).

A comparação `lastUpdated` normaliza zeros à direita na
parte de segundos fracionários (`.18033Z` é igual a `.180330Z`; `state.py:23-55`),
porque a plataforma ocasionalmente os remove — uma comparação exata de strings
julgaria erroneamente como "modificado" e causaria exportações duplicadas.

<a id="terminal-states-expired-and-deleted" data-pplx-source-anchor="true"></a>
## Estados terminais: `expired` e `deleted`

| | `expired` | `deleted` |
|---|---|---|
| significado | a plataforma removeu a thread (~janela de retenção de 3 meses); a tentativa de exportação retornou `ENTRY_EXPIRED` | exclusão pelo usuário/remota, confirmada por `sync-deleted` |
| registrado por | `batch` em si (`mark_expired`, `state.py:131-134`) | `pplx-export sync-deleted --online` (`mark_deleted`, `state.py:136-143`) |
| repetido? | nunca — nem mesmo com `--force` | nunca — nem mesmo com `--force` |
| evidência | a resposta `ENTRY_EXPIRED` | campo `note`: ausência no índice + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted-confirming-remote-deletions" data-pplx-source-anchor="true"></a>
### sync-deleted: confirmando exclusões remotas

```bash
pplx-export sync-deleted --account alice            # offline dry-run: list candidates only
pplx-export sync-deleted --account alice --online   # confirm each candidate online
```

1. **Candidatos (offline, sem rede).** Qualquer thread com status `ok` em
   `batch_state` que esteja faltando na união `entryUUID` de **todos** os
   índices de conta `index/library_*.json` é um candidato suspeito de exclusão
   remota (`pplx_export/commands/sync_deleted_cmd.py:148-212`). A união
   entre contas é necessária: uma thread pertencente a `bob` mas exportada por `alice`
   através de um espaço compartilhado nunca aparece no índice de `alice` — um
   diff de conta única geraria falsos positivos para todo esse conjunto. Quando nenhum índice
   utilizável existe, todos os candidatos são ignorados com segurança e o motivo é registrado.
2. **Simulação por padrão.** Sem `--online`, o comando apenas lista
   candidatos — sem rede, sem alterações de arquivo.
3. **Confirmação `--online`.** Cada candidato é verificado com
   `GET /rest/thread/<uuid>`, usando a conta `export_via` do candidato de
   `thread.json` (o cookie alterna automaticamente):

   | resultado | desfecho |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | confirmado: `batch_state` marca terminal `deleted` (o `note` registra o motivo), e cada `thread.json` dessa thread recebe um timestamp `remote_deleted` no lugar |
   | thread ainda existe | falso positivo: relatado como está (o índice pode não estar totalmente atualizado — reexecute `index` e verifique novamente), nada mudou |
   | 5xx / erro de rede | nenhuma alteração de estado; o candidato é deixado para a próxima rodada |
   | 3 401/403 consecutivos | aborto rápido — um cookie expirado não pode se curar sozinho, e continuar marcaria erroneamente threads ativas (`sync_deleted_cmd.py:333-337`) |

   Marcas confirmadas são persistidas por item, portanto uma execução `--online` interrompida
   não perde nada e reexecuções são idempotentes (`sync_deleted_cmd.py:254-256`).

<a id="the-tombstone-principle" data-pplx-source-anchor="true"></a>
## O princípio do túmulo

!!! warning "Arquivos locais nunca são excluídos"
    Este arquivo é o backup de registro para as conversas exportadas.
    `sync-deleted` apenas *identifica e marca* (túmulo): ele **nunca exclui
    ou move nenhum arquivo de arquivo**. A confirmação altera exatamente duas coisas — o
    status `batch_state` e uma chave de marcador em `thread.json`:

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    O carimbo é idempotente: uma chave `remote_deleted` existente não é
    reescrita nem sobrescrita (`sync_deleted_cmd.py:215-244`).

<a id="idempotence-and-offline-re-render" data-pplx-source-anchor="true"></a>
## Idempotência e re-renderização offline

- Reexecutar `batch` contra um índice inalterado não exporta nada: cada linha
  classifica como `done` e a execução para no ponto de parada antecipada. As gravações de estado
  são atômicas, as marcas são por thread, e exclusões reconfirmadas nunca duplicam
  o carimbo `remote_deleted`.
- O arquivo mantém os payloads brutos da API (`raw_entries.json` /
  `raw_blocks.json`), para que os arquivos renderizados possam ser regenerados a qualquer momento
  sem acesso à rede:

  ```bash
  pplx-export re-render                 # rebuild conversation.md + turns/ everywhere
  pplx-export re-render --dry-run       # only list the thread directories
  pplx-export re-render --thread-json   # also sync interruptions / answer_variants keys
  ```

  `re-render` reanalisa o JSON bruto com o renderizador atual
  (`pplx_export/commands/rerender_cmd.py:105-190`): `conversation.md` e
  `turns/turn_*.md` são reescritos, arquivos de turno obsoletos numerados acima da contagem
  atual de turnos são removidos, e fontes, ativos, `report.md` e `thread.json`
  são deixados intactos. É assim que correções no renderizador são aplicadas em todo o
  arquivo sem uma única requisição.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Veja também

- [pplx-export.md](pplx-export.md) — referência completa do comando `batch` (`--mode`, `--limit`, atrasos)
- [maintenance-commands.md](maintenance-commands.md) — `sync-deleted`, `re-render` e os comandos de backfill
- [archive-layout.md](archive-layout.md) — onde `batch_state.json` e `thread.json` residem
- [rate-limiting.md](rate-limiting.md) — ritmo entre threads, backoff, fail-fast de autenticação
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) — o pipeline de exportação completo
- [../architecture/offline-operations.md](../architecture/offline-operations.md) — o pipeline de reconstrução offline em profundidade
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — taxonomia de erros e tratamento de estados terminais
