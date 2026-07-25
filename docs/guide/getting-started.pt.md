---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/getting-started.md"
translation_source_sha256: "d98ba1f32b1e75bff7b3d51ef17e833417ecaf283996152cfa3342455b6eca7a"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="getting-started" data-pplx-source-anchor="true"></a>
# Primeiros passos

De um checkout novo a um primeiro arquivo local: instale os dois comandos, crie a
configuração de nível de usuário, escolha um canal de cookies e percorra uma primeira exportação.

<a id="requirements" data-pplx-source-anchor="true"></a>
## Requisitos

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — usado para instalar as ferramentas e executar o conjunto de testes
- **Um navegador de desktop conectado ao Perplexity** — as ferramentas reutilizam seus cookies de sessão;
  nenhum token é armazenado na configuração

A descriptografia de cookies usa `browser_cookie3`. A detecção automática cobre Edge, Chrome, Firefox e
Safari; Brave, Chromium, Opera e Vivaldi funcionam via `--cookies-from`.

<a id="install" data-pplx-source-anchor="true"></a>
## Instalar

Não é necessário clonar — instale diretamente da URL git:

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

A partir de um clone local (raiz do repositório):

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

Isso instala dois comandos: `pplx-export` (arquivamento) e `pplx-ask` (consultas
interativas). Verifique:

```bash
pplx-export --version
pplx-export --help           # overview with examples; each subcommand has its own --help
pplx-ask --help
```

`uvx --from . pplx-export` executa um comando único sem instalar.

<a id="create-the-user-level-config" data-pplx-source-anchor="true"></a>
## Criar a configuração de nível de usuário

O registro da conta (nome de exibição / e-mail / user_id) e o espaço BOT são dados
pessoais e **não são commitados no repositório**; eles residem em um arquivo TOML externo.
Modelo: `config.example.toml` na raiz do repositório.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

1. Crie o diretório de configuração.
2. Copie o modelo para o caminho padrão.
3. `chmod 600` — o arquivo contém dados pessoais; mantenha-o apenas para o proprietário.
4. Preencha `[accounts.<name>]` — a chave é o nome de usuário da conta (como aparece em
   URLs de tópicos / na biblioteca); defina `display_name`, `email`, `user_id` e escolha um
   `default_account`.
5. Preencha `[bot_space]` — onde os tópicos criados por `pplx-ask` são coletados após a
   conclusão (um espaço real pode ser criado com `pplx-ask space-create`).

**Alternativa automática:** `pplx-export init` deriva este arquivo para você — ele
enumera os cookies de sessão por conta no seu navegador, consulta
`/api/auth/session` para o e-mail / nome de exibição de cada token, define
`default_account` como a conta ativa no momento, corresponde o espaço BOT pelo
título e escreve o TOML atomicamente com permissões 0600 (um arquivo existente
só é sobrescrito com `--force`).

```bash
pplx-export init                     # discover accounts, write the default config path
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --bot-title TITLE   # match/create a different space title (default BOT)
pplx-export init --config /path/to/config.toml   # write to a custom path
```

Flags: `--force` sobrescreve uma configuração existente; `--create-bot-space [TITLE]`
cria o espaço via API quando nenhum título corresponde (uma operação de escrita na
conta; um TÍTULO explícito orienta tanto a correspondência quanto a criação); `--bot-title TITLE`
é usado tanto para correspondência quanto para criação. Observe que para
`init` — ao contrário de todos os outros comandos — `--config` é o caminho de **escrita**, não
o caminho de carregamento. Detalhes completos: [pplx-export → init](pplx-export.md#init).

A referência completa dos campos está em [Configuração](configuration.md).

**Prioridade de carregamento** (maior primeiro):

| # | Origem |
|---|--------|
| 1 | `--config PATH` |
| 2 | Variável de ambiente `PPLX_EXPORT_CONFIG` |
| 3 | `~/.config/pplx-export/config.toml` (padrão) |

!!! note "Quando a configuração está ausente"
    Comandos sem `--account` executam em modo degradado — a verificação de propriedade do e-mail é
    ignorada com um aviso (comandos offline não são afetados); um `--account` explícito
    gera um erro apontando para `config.example.toml`. Quando `--account` é omitido,
    `default_account` da configuração é usado.

<a id="choose-a-cookie-channel" data-pplx-source-anchor="true"></a>
## Escolher um canal de cookies

As credenciais vêm dos cookies de sessão do Perplexity conectado no seu navegador local, lidos
via `browser_cookie3` — incluindo enumeração de tokens de múltiplas contas e alternância
automática. Quatro canais:

| Canal | Como | Notas |
|---------|-----|-------|
| Detecção automática (padrão) | sem flag | cache fresco de 12 h primeiro, depois armazenamentos do navegador na ordem edge→chrome→firefox→safari |
| Navegador nomeado | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| Arquivo de cookies | `--cookies /path/to/cookies.txt` | Arquivo de cookies Netscape ou JSON exportado |
| WebBridge | `--transport webbridge` | busca no contexto da página — o canal de fallback, usado apenas quando explicitamente solicitado |

No Linux, instalações de navegadores snap e flatpak também são detectadas automaticamente — seus caminhos
de perfil são cobertos pelo registro integrado. A matriz completa do Linux (keyring, ambientes de
desktop, pacotes de distribuição):
[Solução de problemas → Descriptografia de cookies no Linux](troubleshooting.md#linux-cookie-decryption).

```bash
pplx-export export <thread_url>                                 # default: auto-detect browser store
pplx-export export <thread_url> --cookies-from edge             # import from a specific browser
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # use a cookie file
pplx-export export <thread_url> --transport webbridge           # WebBridge page context (explicit fallback)
```

Após obter os cookies, a ferramenta chama `/api/auth/session` e imprime o e-mail da conta
atual para que você possa confirmar que a conta correta está em uso — cuidado se `--account`
discordar da conta do cookie. O design de transporte/credenciais é abordado em
[Ask e contas](../architecture/ask-and-accounts.md).

<a id="first-run" data-pplx-source-anchor="true"></a>
## Primeira execução

```bash
pplx-export index --account alice     # fetch the library index
pplx-export export <thread_url>       # export a single thread
pplx-export batch --account alice     # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run       # offline re-render, zero network
```

1. **`index`** busca o índice da biblioteca da conta — o ponto de entrada no qual `batch` e
   os outros comandos de toda a conta se baseiam.
2. **`export`** arquiva um tópico de ponta a ponta: ele retém as respostas brutas da API
   (`raw_*.json`) junto com Markdown para que a renderização possa ser reproduzida offline.
3. **`batch`** varre toda a biblioteca. Ele para cedo quando tudo o que resta já está
   arquivado (parada antecipada incremental), escreve pontos de verificação retomáveis e aceita
   `--full` para uma varredura completa. Detalhes: [Sincronização incremental](incremental-sync.md).
4. **`re-render --dry-run`** prova o caminho offline: ele regenera `conversation.md`
   + `turns/` a partir de arquivos brutos locais com zero rede. Use `--dry-run` para escrever os
   resultados. Veja [Operações offline](../architecture/offline-operations.md).

Depois que isso funcionar, `pplx-ask ask "<prompt>"` executa uma consulta em streaming e arquiva o
tópico resultante automaticamente — veja [pplx-ask](pplx-ask.md).

<a id="where-archives-land" data-pplx-source-anchor="true"></a>
## Onde os arquivos são salvos

Os arquivos são salvos em `./web_archive/` por padrão (substitua com `--out`): um
diretório por tópico.

| Caminho | Conteúdo |
|------|---------|
| `conversation.md`, `turns/` | conversa renderizada |
| `thread.json` | metadados do tópico + registro de interrupções |
| `sources.md` / `sources.json` | citações |
| `report.md` | relatório de deep-research / council / study |
| `assets/` | ativos baixados (modo computador) |
| `raw_*.json` | respostas brutas da API retidas — arquivos bem-sucedidos podem ser re-renderizados offline sem nova busca |

O contrato completo do diretório: [Layout do arquivo](archive-layout.md).

<a id="next-steps" data-pplx-source-anchor="true"></a>
## Próximos passos

- Algo deu errado? → [Solução de problemas](troubleshooting.md)
- Referência comando por comando → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [Comandos de manutenção](maintenance-commands.md)
- Os cinco modos de conversa → [Modos](modes.md)
