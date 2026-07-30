---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "0c5f1be9b103913deee332caa4397a3dc356027148beac491834f6791f3b73db"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="configuration" data-pplx-source-anchor="true"></a>
# Configuração

pplx-export mantém seus dados de identidade — o registro de contas (nomes de exibição, e-mails de login, IDs de usuário) e o espaço BOT — em um arquivo TOML no nível do usuário que fica fora do repositório. Esta página cobre onde esse arquivo reside, todos os campos que ele aceita, o que acontece quando está ausente e como o registro gerencia o tratamento de cookies de múltiplas contas.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## Por que a configuração fica fora do repositório

O registro de contas e o espaço BOT são dados pessoais e **nunca são commitados** no repositório (`pplx_export/config.py:7-12`). O repositório fornece apenas um modelo de placeholder, `config.example.toml`; seus valores reais vão para uma cópia privada. Todo o resto que a ferramenta precisa — o domínio do site, URLs da API, a raiz de arquivamento padrão — é uma constante de código (`pplx_export/config.py:50-58`), não configuração do usuário.

O TOML carrega apenas dados de identidade. A origem dos cookies e a seleção de transporte são flags de CLI por invocação, não campos de configuração — veja [Flags de CLI, não campos de configuração](#cli-flags-not-config-fields) abaixo.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## Localização e prioridade de carregamento

`configure()` (`pplx_export/config.py:113`) resolve o caminho da configuração com esta precedência (`pplx_export/config.py:95-110`):

| Prioridade | Origem | Conta como explícito |
|---|---|---|
| 1 | Flag CLI `--config PATH` | sim |
| 2 | Variável de ambiente `PPLX_EXPORT_CONFIG` | sim |
| 3 | `~/.config/pplx-export/config.toml` (caminho padrão) | não |

"Explícito" importa para o comportamento de erro quando o arquivo está ausente — veja [modo degradado](#missing-config-degraded-mode). Ambas as entradas de CLI recarregam a configuração em modo estrito após o parsing de argumentos (`pplx_export/cli.py:223`, `pplx_export/ask_cli.py:278`); o carregamento no momento da importação (`pplx_export/config.py:174-179`) é tolerante a falhas, então importar o pacote nunca falha por arquivo ausente.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## Criando sua configuração

!!! tip "Alternativa automática"
    `pplx-export init` pode gerar este arquivo automaticamente — ele descobre as contas logadas a partir dos cookies do seu navegador e escreve o TOML com permissões 0600. Veja [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

Em seguida, edite a cópia. O modelo usa placeholders puros — copie a estrutura, substitua cada valor:

```toml
# Default account used when --account is not given (a key of [accounts.<name>] below)
default_account = "alice"

# Account registry: key = account username (the username in thread URLs / library)
[accounts.alice]
# Full display name: used for archive directory naming (web_archive/<display name>/…)
display_name = "Alice Example"
# Login email: verifies cookie ownership
email = "alice@example.com"
# Account uid (required for thread-viewed telemetry)
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT space: where threads created by pplx-ask are collected after completion
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

Estilo do placeholder: `alice`/`bob` são nomes de usuário fictícios, e-mails usam `example.com` e UUIDs usam a forma `00000000-0000-4000-8000-…` de todos zeros. No seu arquivo real, a chave da tabela **deve ser o nome de usuário real da conta** como aparece nas URLs de tópicos e na sua biblioteca.

!!! warning "Mantenha privado"
    A configuração real contém dados pessoais (e-mails, IDs de usuário). A permissão recomendada é `0o600`; nunca a commite em nenhum repositório git (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## Referência de campos

<a id="top-level" data-pplx-source-anchor="true"></a>
### Nível superior

| Campo | Tipo | Significado |
|---|---|---|
| `default_account` | string | Chave de uma tabela `[accounts.<name>]`, usada quando `--account` não é fornecido (`pplx_export/commands/common.py:84-85`). Vazio/ausente = modo degradado. |
| `archive_root` | string | Opcional. Raiz de saída de arquivamento usada como fallback de `--out`, para que comandos diários possam omitir `--out`. Precedência: `--out` > `archive_root` > `./web_archive` (`pplx_export/config.py`, carregado em `ARCHIVE_ROOT`; resolvido em `cli.py` / `ask_cli.py`). `~` é expandido. |
| `[models]` (tabela) | tabela | **Gerenciado automaticamente, não escrito à mão.** Catálogo de modelos atualizável escrito por `pplx-ask models --refresh` e semeado por `pplx-export init`; ele substitui a linha de base fixa em `pplx_export/sites/perplexity/platform.py`. Chaves: `last_refreshed` (UTC), `source_version`, `auto_refresh` (bool), `mode_defaults`, `council_defaults`, `search_models` e um `[models.catalog]` completo (`id → {label, provider, mode}`). Requisições o leem (com a linha de base `platform.py` como fallback); um TTL de 7 dias imprime um lembrete de atualização, ou atualiza automaticamente quando `auto_refresh = true`. A escrita de ida e volta preserva suas outras tabelas e comentários (via a dependência de tempo de execução `tomlkit`) e permanece `0600`. |

### `[accounts.<name>]`

Uma tabela por conta; `<name>` é o nome de usuário da conta. O registro carrega em três dicionários chaveados por nome de usuário: `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Campo | Tipo | Obrigatório | Significado |
|---|---|---|---|
| `display_name` | string | não | Nome de exibição completo, usado para nomeação de diretórios de arquivamento (`web_archive/<display name>/…`); recai para o nome de usuário quando omitido. Veja [Layout de arquivamento](archive-layout.md). |
| `email` | string | recomendado | E-mail de login. O transporte verifica a propriedade do cookie contra ele, prevenindo "uma exportação para a conta B carregando a sessão da conta A" (`pplx_export/config.py:69-72`). Em caso de incompatibilidade, a ferramenta enumera tokens de sessão por conta no navegador e alterna automaticamente — veja [Modelo de cookie de múltiplas contas](#multi-account-cookie-model). |
| `user_id` | string | para telemetria `pplx-ask` | UID da conta, necessário para telemetria de tópicos visualizados (`pplx_export/config.py:73-75`). Leia de `GET /api/auth/linked-accounts`, que retorna `user_id` / `email` / `display_name` de cada conta logada — veja [Autenticação da API](../reference/api/api-authentication.md). |

### `[bot_space]`

O espaço BOT é o ponto de coleta para tópicos criados por `pplx-ask` após sua conclusão (`pplx_export/config.py:76-79`). Crie o espaço em si com `pplx-ask space-create` (veja [pplx-ask](pplx-ask.md)), depois registre-o aqui.

| Campo | Tipo | Significado |
|---|---|---|
| `uuid` | string | UUID do espaço. `pplx-ask` move tópicos concluídos para cá (`pplx_export/ask_cli.py:156-158`); quando vazio, a etapa de movimentação é pulada. |
| `slug` | string | O slug da URL do espaço. Carregado em `BOT_SPACE_SLUG` (`pplx_export/config.py:79`); a CLI de tempo de execução não o lê — a ferramenta de manutenção de fixtures o consome, construindo um par de substituição de identidade a partir dele (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### Flags de CLI, não campos de configuração

O TOML não tem configurações de transporte ou cookie. Elas são escolhidas por invocação:

| Aspecto | Onde é definido |
|---|---|
| Caminho do arquivo de configuração | `--config PATH`, ou `PPLX_EXPORT_CONFIG` |
| Origem do cookie | `--cookies-from BROWSER` / `--cookies FILE` |
| Transporte | `--transport cookie\|webbridge` (apenas `pplx-export`; padrão `cookie`) |
| Pular verificação de conta na inicialização | `--skip-auth-check` (ambas as entradas) — veja [Modelo de cookie de múltiplas contas](#multi-account-cookie-model) |

Veja [pplx-export](pplx-export.md) para a referência completa de flags.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## Configuração ausente: modo degradado

Quando nada é carregado, os registros no nível do módulo permanecem vazios e `LOADED_CONFIG_PATH` é `None` (`pplx_export/config.py:83-85`). Comportamento por cenário (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`):

| Cenário | Comportamento |
|---|---|
| Nenhuma configuração no caminho padrão, `--account` não fornecido | Modo degradado: um aviso é registrado e os comandos executam com uma conta placeholder (`username='default'`); a verificação de propriedade de e-mail é pulada. Comandos offline do dia a dia não são afetados (`pplx_export/commands/common.py:86-90`). |
| Nenhuma configuração, `--account` explícito | `SystemExit` nomeando a ordem de busca e apontando para `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| Configuração carregada, `--account` não registrado | `SystemExit` nomeando o arquivo carregado, pedindo para adicionar `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| Caminho explícito (`--config` / variável de ambiente) não existe | `ConfigError` em modo estrito (`pplx_export/config.py:140-146`). |
| Arquivo existe mas falha ao fazer parsing | Sempre `ConfigError` — uma configuração corrompida não deve degradar silenciosamente (`pplx_export/config.py:147-150`). |
| `--account` omitido, configuração carregada | `default_account` é usado (`pplx_export/commands/common.py:84-85`). |

O que "comandos offline" cobrem e como execuções degradadas interagem com o arquivamento é detalhado em [Operações offline](../architecture/offline-operations.md).

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## Modelo de cookie de múltiplas contas

Com várias contas logadas no mesmo navegador, o armazenamento contém um cookie de sessão **por conta**, e o campo `email` da configuração informa à ferramenta qual delas é necessária:

- Cada conta logada tem um cookie `__Secure-pplx.session.<uid>` (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`); o sufixo `<uid>` é o `user_id` da conta.
- A conta **ativa** é aquela cujo token está atualmente em `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). Alternar contas = escrever o valor do cookie por conta da conta alvo nesse cookie — sem necessidade de interface do navegador (`pplx_export/core/cookies/loaders.py:180-187`).
- Na inicialização, o transporte consulta `GET https://www.perplexity.ai/api/auth/session` e compara o e-mail retornado com `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- Em caso de incompatibilidade, `_try_switch_account` (`pplx_export/commands/common.py:190-215`) enumera cada token de conta no navegador via `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`, preferindo entradas no subdomínio `www.`), tenta cada um em `__Secure-next-auth.session-token` e reconstrói o transporte na primeira correspondência.
- Se nenhum token corresponder, o comando termina exibindo ambos os e-mails e pedindo que você faça login da conta alvo no navegador primeiro (`pplx_export/commands/common.py:142-145`) — veja [Solução de problemas](troubleshooting.md).
- Uma conta sem `email` registrado prossegue sem verificação, com um aviso pedindo que você confirme o login no navegador por conta própria (`pplx_export/commands/common.py:146-149`).

Para o fluxo completo de alternância e a semântica do endpoint de sessão, veja [Ask e contas](../architecture/ask-and-accounts.md) e [Autenticação da API](../reference/api/api-authentication.md).

**Pulando a verificação (`--skip-auth-check`).** A consulta de sessão na inicialização acima
troca alguns segundos — às vezes minutos em uma rede ruim — pela proteção de
propriedade "conta B usada como conta A". Quando você sabe que o navegador está
logado na conta correta, `--skip-auth-check` (compartilhado por `pplx-export` e `pplx-ask`) pula
essa consulta completamente e vai direto ao trabalho (`pplx_export/commands/common.py`,
`make_transport`):

- Sem `GET /api/auth/session` na inicialização, então uma rede instável não produz mais
  uma longa espera silenciosa (agora com heartbeat) antes da primeira requisição real.
- A ferramenta confia em qualquer conta que esteja logada no momento; a verificação
  antecipada de propriedade de e-mail e a alternância automática de múltiplas contas acima não são executadas.
- **Rede de segurança adiada**: em `batch`, uma vez que erros genéricos de exportação se acumulam
  (três falhas), uma verificação de conta única é executada e avisa o que encontrou —
  o cookie expirou, a conta não corresponde ao alvo, ou a conta está
  ok (então os erros são de rede / limite de taxa, não de autenticação)
  (`pplx_export/commands/common.py`, `report_account_status`;
  `pplx_export/commands/batch_cmd.py`).
- **Compensação**: a verificação adiada detecta um cookie expirado, mas não
  pode detectar uma conta *errada-mas-válida* que exporta sem erro — com
  `--skip-auth-check` você assume a responsabilidade de que a conta logada é a
  pretendida.

Use para execuções rápidas e não supervisionadas em um login conhecido; omita quando você confia
na proteção de propriedade antecipada ou na alternância automática de contas.

<a id="cookie-cache" data-pplx-source-anchor="true"></a>
## Cache de cookies

Após validação bem-sucedida, os cookies resolvidos são armazenados em cache para que execuções posteriores pulem o navegador:

| Propriedade | Valor |
|---|---|
| Caminho | `<archive root>/index/.cookies.json` — segue `--out` (`pplx_export/commands/common.py:111`) |
| Frescor | 12 horas (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`); um cache obsoleto ou corrompido é tratado como ausente |
| Conteúdo | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Escrita | Atômica: arquivo temporário criado com modo `0o600`, depois `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Coberto por `.gitignore` (`**/index/.cookies.json`) |

Ordem de resolução de cookies (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`): `--cookies-from` explícito → arquivo `--cookies` explícito → cache fresco → detectar navegadores automaticamente (edge → chrome → firefox → safari). O cache é atualizado após cada validação de conta bem-sucedida (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## Protegendo seus arquivos

- `chmod 600` seu `config.toml` — ele contém dados pessoais (e-mails, IDs de usuário).
- O cache de cookies já é escrito com modo `0o600` pela ferramenta; cookies de sessão são credenciais equivalentes a login.
- Se você criar manualmente um arquivo de cookie para `--cookies`, aplique `chmod 600` a ele também.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## Quando a autenticação falha

Cookies expirados, uma conta que a alternância automática não encontra, erros de permissão do chaveiro do navegador e outras falhas de autenticação são cobertos em [Solução de problemas](troubleshooting.md).
