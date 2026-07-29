---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/troubleshooting.md"
translation_source_sha256: "3feeb14ea77ad45275ccca583b2fbcbee34745db32dca749c70e0b7a77302623"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="troubleshooting" data-pplx-source-anchor="true"></a>
# Solução de problemas

Formato FAQ: cada entrada é **problema → causa → correção**. Para a referência completa de semântica de erros (códigos de status, estados terminais, disciplina de repetição), consulte [Respostas e erros](../reference/api/api-responses-errors.md) e [Limitação de taxa e erros](../architecture/rate-limiting-errors.md).

<a id="bare-requests-to-the-api-get-a-cloudflare-403" data-pplx-source-anchor="true"></a>
## Requisições diretas à API recebem um Cloudflare 403

**Problema**: um script `curl` / feito à mão contra endpoints REST `www.perplexity.ai` retorna 403 com uma página de desafio do Cloudflare — mesmo com cookies copiados do navegador — enquanto os mesmos endpoints funcionam através da ferramenta.

**Causa**: o Cloudflare está na frente do site, e `cf_clearance` / `__cf_bm` estão vinculados à impressão digital TLS do navegador. A impressão digital de um cliente simples não corresponde, então o desafio é acionado. A ferramenta funciona porque usa Python `urllib` com cookies importados do navegador e um `User-Agent` do Chrome desktop (`pplx_export/core/http/cookie_transport.py:29`). O Cloudflare também pode retornar 403 sob controle de taxa — nesse caso, a resposta carrega a mesma forma de desafio.

**Correção**:

- Não ignore o transporte da ferramenta; execute sua chamada através de `pplx-export` / `pplx-ask` em vez de scripts ad-hoc.
- Dentro da ferramenta, uma resposta 200 com um corpo não JSON (o intersticial do Cloudflare) é classificada como um erro de transporte, não dados (`pplx_export/core/http/cookie_transport.py:133`).
- Se 403s começarem a aparecer dentro da ferramenta, reduza a velocidade (consulte [Limitação de taxa](rate-limiting.md)) e atualize os cookies; um desafio persistente significa fazer login novamente no navegador.
- Lembre-se das duas faces do 403: um desafio de controle de risco do Cloudflare (desaparece quando você reduz a velocidade) versus um 403 de nível de API (cookie morto — gerado imediatamente sem backoff; consulte a próxima seção). A página de design mapeia o último ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

Contexto: [Autenticação da API](../reference/api/api-authentication.md).

<a id="401-errors-expired-cookies" data-pplx-source-anchor="true"></a>
## Erros 401 / cookies expirados

**Problema**: comandos falham com um erro de autenticação — `AuthTransportError: 鉴权失败 401` do `pplx-export`, ou `pplx-ask ask` saindo com uma dica HTTP 401/403 para atualizar o cookie.

**Causa**: o cookie de sessão expirou ou foi invalidado. `401`/`403` são tratados como falhas de autenticação e gerados imediatamente — sem backoff, porque o backoff não pode autocorrigir uma sessão morta (`pplx_export/core/http/cookie_transport.py:82`; `pplx_export/core/errors.py:68`). `batch` adicionalmente falha rapidamente após 3 falhas de autenticação consecutivas para que um cookie morto não queime toda a fila.

**Correção**:

1. Faça login novamente (ou reabra o site) no navegador para que os cookies de sessão sejam renovados.
2. Atualize o cache de cookies da ferramenta. O cache em `<out>/index/.cookies.json` é reutilizado dentro de uma janela de frescor de 12 horas (`pplx_export/core/cookies/cache.py:22`), então, após o novo login:
   - execute uma vez com `--cookies-from <browser>` para forçar uma importação nova do navegador, ou
   - exclua `<out>/index/.cookies.json` e deixe a próxima execução reimportar automaticamente.
3. Cada execução que valida com sucesso salva novamente o cache (`pplx_export/commands/common.py:150`), então as execuções do dia a dia permanecem atualizadas por conta própria.

Detalhes de configuração: [Primeiros passos](getting-started.md) · [Configuração](configuration.md).

<a id="linux-cookie-decryption" data-pplx-source-anchor="true"></a>
## Descriptografia de cookies no Linux

**Problema**: no Linux, a detecção automática (ou `--cookies-from chrome` & co.) não consegue ler o armazenamento de cookies do navegador, mesmo que o navegador esteja logado.

**Mecanismo**: navegadores da família Chromium no Linux criptografam o banco de dados de cookies com uma chave mantida no chaveiro do sistema operacional, lida em tempo de execução através da API Secret Service D-Bus. `browser_cookie3` fala D-Bus via `jeepney` Python puro — já instalado com a ferramenta no Linux, nada extra para configurar — e recai para a senha `peanuts` legada quando nenhum chaveiro responde, que só descriptografa cookies que o Chrome também escreveu sem um chaveiro. Quando o chaveiro existe, mas a própria consulta D-Bus falha no nível de transporte (por exemplo, um barramento de sessão rejeitando autenticação anônima), a própria cadeia de fallback de `browser_cookie3` nunca é acionada; a ferramenta detecta esse caso e tenta novamente uma vez com o chaveiro ignorado, usando a senha padrão do Chromium — a mesma chave que o Chromium usa quando nenhum chaveiro está disponível (`pplx_export/core/cookies/loaders.py:62-104`, conectado ao caminho de carga em `loaders.py:136-153`). O Firefox não precisa de nada disso: seu `cookies.sqlite` não é criptografado.

**A matriz**:

| Camada | Caso | O que acontece |
|---|---|---|
| Navegador | Firefox | Zero atrito — `cookies.sqlite` não é criptografado |
| Navegador | Chromium + chaveiro acessível | Funciona — a chave é obtida via Secret Service |
| Navegador | Chromium + sem chaveiro | Caminho `peanuts` — funciona apenas se o Chrome também escreveu sem um chaveiro |
| Navegador | Chromium + chaveiro inacessível (falha de nível D-Bus) | A ferramenta tenta novamente automaticamente com a senha padrão do Chromium — mesmo alcance que o caminho `peanuts` |
| Método de instalação | Pacote nativo | Detectado automaticamente (caminhos internos do browser_cookie3) |
| Método de instalação | snap / flatpak | Detectado automaticamente — o registro de perfil interno cobre perfis sob `~/snap/<name>/...` resp. `~/.var/app/<app-id>/...` (`pplx_export/core/cookies/profiles.py:37-67`) |
| Ambiente de desktop | GNOME | Geralmente funciona imediatamente (gnome-keyring) |
| Ambiente de desktop | KDE | Ative **Usar KWallet para a interface Secret Service** nas configurações do KWallet |
| Ambiente de desktop | Headless / mínimo | Sem barramento de sessão D-Bus → caminho `peanuts` |
| Família de distribuição | Debian / Ubuntu | Instale `libsecret-1-0` + `gnome-keyring` |
| Família de distribuição | Fedora / RHEL | Instale `libsecret` + `gnome-keyring`; instalações mínimas / servidor geralmente não têm chaveiro — a falha mais comum |
| Família de distribuição | Arch | Mesmo mecanismo, apenas os nomes dos pacotes diferem |

Instalações em sandbox não precisam de sinalizadores extras: o caminho nativo é verificado primeiro, depois os bancos de dados de cookies snap/flatpak do registro via um `cookie_file=` explícito (`pplx_export/core/cookies/loaders.py:155-168`).

**Cenário → canal recomendado**:

| Cenário | Canal recomendado |
|---|---|
| Firefox instalado | `--cookies-from firefox` — zero atrito |
| Desktop GNOME / KDE | A detecção automática funciona |
| Navegador snap / flatpak | Detecção automática — o registro cobre; caso contrário, `--cookies FILE` exportado via uma extensão do navegador |
| Servidor headless | `--cookies FILE` — o fallback universal; `--transport webbridge` como último recurso |

<a id="an-export-ran-under-the-wrong-account-multi-account" data-pplx-source-anchor="true"></a>
## Uma exportação foi executada sob a conta errada (várias contas)

**Problema**: threads arquivados foram buscados com a sessão da conta errada — por exemplo, uma execução `--account alice` puxou dados como `bob`, ou o arquivo mostra threads que não pertencem à conta pretendida.

**Causa**: com várias contas logadas no mesmo navegador, o token de sessão ativo (`__Secure-next-auth.session-token`) pode pertencer a uma conta diferente da que você segmentou. Se o `email` da conta alvo não estiver registrado na configuração do usuário, a ferramenta não consegue detectar isso e apenas registra um aviso.

**Como a ferramenta previne** (`pplx_export/commands/common.py:93`): na inicialização, o transporte chama `GET /api/auth/session` e compara o e-mail ativo com o registrado. Em caso de incompatibilidade, ele enumera automaticamente os cookies de sessão por conta do navegador (`__Secure-pplx.session.<user_id>`), substitui cada um no token ativo e testa a sessão até que o e-mail alvo corresponda (`pplx_export/commands/common.py:190`; `pplx_export/core/cookies/loaders.py:175`). Se nenhum token corresponder, o comando aborta com um erro claro — ele nunca prossegue silenciosamente como a conta errada.

**Correção**:

- Registre o `email` de cada conta sob `[accounts.<name>]` (consulte [Configuração](configuration.md)) e passe `--account` explicitamente.
- Verifique a linha de log de inicialização `[auth] cookie 来源 …，当前账户: …` — ela nomeia o e-mail da sessão ativa antes de qualquer coisa ser buscada.
- Para auditar um arquivo existente, o `thread.json` de cada thread carrega um campo `export_via` registrando qual conta realizou a exportação (`pplx_export/sites/perplexity/fs_writer.py:229`). `pplx-export sync-deleted` usa o mesmo campo para escolher a conta para verificação online.

Profundidade do mecanismo: [Autenticação da API](../reference/api/api-authentication.md) · [Ask e contas](../architecture/ask-and-accounts.md).

<a id="config-file-not-found-degraded-mode" data-pplx-source-anchor="true"></a>
## "Arquivo de configuração não encontrado" — modo degradado

**Problema**: um aviso de inicialização diz que nenhum arquivo de configuração de nível de usuário foi encontrado e o comando é executado em modo degradado; ou um `--account alice` explícito falha com um erro apontando para `config.example.toml`.

**Causa**: nenhum arquivo de configuração em nenhum dos três locais de pesquisa — `--config PATH`, a variável de ambiente `PPLX_EXPORT_CONFIG`, ou o padrão `~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). Dois casos relacionados, mas distintos: um **caminho de configuração explicitamente especificado** que não existe gera `ConfigError`; uma configuração corrompida (não analisável) sempre gera `ConfigError` — uma configuração quebrada nunca degrada silenciosamente.

**Efeitos do modo degradado**:

- O registro de contas está vazio, então a verificação de propriedade do cookie é ignorada com um aviso e os comandos são executados como a conta substituta `default` (`pplx_export/commands/common.py:51`). Um `--account` explícito resulta em erro.
- `pplx-ask ask` pula a movimentação automática para o espaço BOT (`moved_to_bot` permanece `false` no JSON de resultado) e a telemetria carrega um ID de usuário vazio; perguntar e arquivar funcionam normalmente.
- Os arquivos são colocados na pasta de conta substituta derivada do nome de usuário.

**Correção**: copie `config.example.toml` para `~/.config/pplx-export/config.toml`, preencha `[accounts.<name>]` (`display_name` / `email` / `user_id`), `[bot_space]` e `default_account` — consulte [Configuração](configuration.md).

## ENTRY_EXPIRED vs ENTRY_DELETED

**Problema**: exportar ou ressincronizar um thread relata `ENTRY_EXPIRED` ou `ENTRY_DELETED`, e o thread nunca pode ser buscado novamente.

**Causa**: ambos chegam como HTTP 400 de `GET /rest/thread/<uuid>` com códigos de erro diferentes, e ambos são terminais — o thread não existe mais na plataforma:

| Código | Significado | Mapeamento da ferramenta | Estado terminal |
|---|---|---|---|
| `ENTRY_EXPIRED` | A plataforma removeu o thread (~retenção de 3 meses) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | O thread foi excluído ativamente pelo usuário / lado remoto (o efeito downstream de `DELETE /rest/thread/delete_thread_by_entry_uuid`) | `EntryDeletedError`, uma subclasse de `EntryExpiredError` (`pplx_export/core/errors.py:30`) | `deleted` |

**O que significa para seu arquivo**:

- Nenhum dos estados é repetido — nem por sincronização incremental, nem com `--force`. A marca terminal vive em `<out>/index/batch_state.json`.
- Seu **arquivo local nunca é excluído ou movido** pela ferramenta — a cópia do repositório é o backup. O comando de exportação registra o estado terminal e sai normalmente (`pplx_export/commands/export_cmd.py:51`).
- Como a relação de subclasse é deliberada, caminhos de código que só conhecem `EntryExpiredError` ainda tratam `ENTRY_DELETED` como terminal; caminhos cientes (lote / exportação / sincronização de excluídos / backfill de modo de pesquisa) o classificam precisamente como `deleted`.
- Conclusão prática: exporte em tempo hábil. Após a remoção de ~3 meses, links de origem de artefato/relatório também expiram irrecuperavelmente.

Relacionado: [Sincronização incremental](incremental-sync.md) · [Respostas e erros](../reference/api/api-responses-errors.md).

<a id="assets-that-cannot-be-downloaded-toolu_-handles" data-pplx-source-anchor="true"></a>
## Ativos que não podem ser baixados (manipulação `toolu_`)

**Problema**: algumas entradas em `assets/assets_manifest.json` têm versões sinalizadas como `"no_download_channel": true`, e nenhum arquivo correspondente existe sob `assets/files/`.

**Causa**: identificadores de espaço de trabalho em nuvem com prefixo `toolu_` (DOC_FILE / CODE_FILE / UNKNOWN sem um formulário de URL) não têm canal de download da API: `GET /rest/assets/<asset_uuid>/data` retorna 404 `ASSET_NOT_FOUND` para eles, e `file-repository/download` rejeita identificadores `file:repo/...` (400). Esta é uma **fronteira de completude de arquivo conhecida**, não um bug na exportação. `pplx-export assets-backfill` marca essas versões como `no_download_channel` e as pula (`pplx_export/commands/assets_backfill_cmd.py:356`).

**Correção**:

- Nada para baixar hoje — o sinalizador é o registro deliberado da fronteira.
- O conteúdo geralmente sobrevive inline: o texto de extração de página do subagente e as cargas de etapa são preservados no JSON bruto do thread (`raw_entries.json` / `raw_blocks.json`) e no `turns/` renderizado — verifique lá primeiro.
- `file-repository/list-files` é rastreado como um possível caminho de resgate futuro; consulte [Roteiro de descoberta da API](../reference/api/api-discovery-roadmap.md).

Layout do manifesto: [Layout do arquivo](archive-layout.md).

<a id="command-seems-hung-long-silences" data-pplx-source-anchor="true"></a>
## Comando parece travado / longos silêncios

**Sintoma**: `index` / `batch` / `export` não imprime nada por vários minutos; um gerenciador de tarefas externo pode matá-lo como "tempo limite excedido".

**Causa**: quase sempre uma espera de backoff, não um travamento. Em erros 429 / 5xx / de rede, o transporte dorme entre as tentativas — até 300 s por espera (`pplx_export/core/throttle.py:38-50`). No nível DEBUG, a espera é explícita:

```
19:39:31 GET www.perplexity.ai/rest/thread/<uuid> 网络错误: Remote end closed connection without response
19:39:31 退避 200.9s（连续失败 2 次）
```

**Como saber**: execute com `-v` (ou `--log-file`) e procure pelas linhas de backoff; enquanto o processo estiver vivo, nenhuma intervenção é necessária. Interromper é seguro a qualquer momento — o estado é escrito atomicamente e a próxima execução repara a lacuna.

**Antipadrão**: envolver a CLI em um gerenciador de tarefas com um tempo limite rígido curto (tarefas de fundo do agente, wrappers de cron estilo `timeout(1)`) *enquanto* encadeia contas com `&&` — a cascata de backoff da primeira conta queima todo o tempo limite e a conta encadeada nunca é executada. Uma conta por invocação, orçamento generoso: consulte [Orçamento de tempo de execução para chamadores](rate-limiting.md#runtime-budget-for-callers).

<a id="where-are-the-logs" data-pplx-source-anchor="true"></a>
## Onde estão os logs?

**Console**: progresso em nível INFO por padrão; `-v` / `--verbose` alterna para DEBUG (rastreamento de requisição, decisões internas); avisos e erros são sempre mostrados.

**Arquivo**: passe `--log-file` para capturar o fluxo completo de DEBUG (`pplx_export/core/logging.py:45`):

- `--log-file` sem um valor vai para `<out>/index/logs/<cmd>-<timestamp>.log` (`pplx_export/commands/common.py:218`) — por exemplo, `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH` escreve no caminho fornecido.

**Outros arquivos de estado úteis para diagnóstico** (sob `<out>/index/`):

| Arquivo | Conteúdo |
|---|---|
| `.cookies.json` | Cache de cookies (frescor de 12 h; escrito atomicamente com 0o600 — é uma credencial equivalente a login, mantenha-o privado) |
| `batch_state.json` | Estado de exportação por thread, incluindo as marcas terminais `expired` / `deleted` |
| `answer_variants_log.jsonl` | Registro de variantes de reescrita de resposta |
| `library_*.json` | Instantâneos do índice da biblioteca por conta |

<a id="see-also" data-pplx-source-anchor="true"></a>
## Veja também

- [Primeiros passos](getting-started.md) — configuração inicial e importação de cookies
- [Configuração](configuration.md) — contas, espaço BOT, modo degradado
- [pplx-ask](pplx-ask.md) — a CLI de consulta interativa
- [pplx-export](pplx-export.md) — a CLI de arquivamento
- [Limitação de taxa](rate-limiting.md) — disciplina de ritmo e backoff
