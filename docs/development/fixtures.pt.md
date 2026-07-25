---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/fixtures.md"
translation_source_sha256: "72f6f6faa0f4c2ef3a63b3f0a7c6bc0a16f9be6cb03225850e4d5d4b22193b30"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="test-fixtures" data-pplx-source-anchor="true"></a>
# Fixtures de teste

`tests/fixtures/` contém **dados simulados** determinísticos e em formato de API para o
[conjunto de testes](testing.md). As entradas modelam estruturas representativas de thread e workflow;
seus produtos renderizados são confirmados como snapshots dourados.

<a id="source-contract" data-pplx-source-anchor="true"></a>
## Contrato de origem

<!-- audit:contract fixture-source=simulated -->

O conteúdo atual do fixture confirmado é simulado:

- Novos fixtures ou atualizações devem ser construídos como dados simulados; contribuidores
  não devem populá-los importando `web_archive/`, dados de conta de usuário, respostas
  de API ao vivo ou arquivos privados.
- Nomes, identidades, identificadores, prompts, respostas, payloads de workflow, caminhos
  e URLs nos arquivos confirmados são placeholders de teste.
- O JSON espelha os esquemas de resposta e arquivo de produção apenas para exercitar
  o comportamento do parser, renderizador, estado e relacionamento.
- O repositório não confirma um mapeamento reverso de placeholders para
  identificadores privados.

Os termos **fixture de modo completo** e **fixture de cenário reduzido** descrevem
cobertura de teste e formato de entrada, não proveniência. Ambos são dados simulados.

<a id="directory-contract" data-pplx-source-anchor="true"></a>
## Contrato de diretório

Cada diretório de fixture contém entradas simuladas no formato de resposta bruta e,
onde a comparação de snapshot é necessária, uma árvore `golden/`:

| Caminho | Função |
|---|---|
| `raw_entries.json` | entradas de thread simuladas no formato de resposta de produção |
| `raw_blocks.json` | blocos de workflow simulados; ausente quando o modo não tem resposta de bloco |
| `thread.json` | metadados de thread arquivada simulados |
| `golden/conversation.md` + `golden/turns/turn_*.md` | produtos gerados a partir das entradas simuladas e comparados byte a byte |

As convenções determinísticas atuais incluem:

- contas placeholder `alice` / `bob`, identidades de exemplo, um espaço BOT placeholder
  e um `read_write_token` placeholder fixo;
- identificadores derivados de uuid5 marcados com `5cbeef00`, preservando referências
  cruzadas intencionais entre registros simulados;
- identificadores `toolu_` simulados de comprimento fixo marcados com `5crub0`;
- prompts, títulos, texto de workflow e caminhos de arquivo genéricos; e
- strings de consulta de URL assinada removidas.

Essas convenções tornam fácil detectar resíduos acidentais específicos de ambiente;
elas não implicam que os identificadores simulados foram derivados de objetos
reais.

<a id="inventory" data-pplx-source-anchor="true"></a>
## Inventário

<!-- audit:inventory fixture-directories -->

<a id="full-mode-fixtures" data-pplx-source-anchor="true"></a>
### Fixtures de modo completo

Estas são conversas simuladas completas para cada modo suportado:

| Fixture | Cobertura |
|---|---|
| `search_demo` | pesquisa, um turno; bloco de código R e código inline |
| `deep_research_demo` | pesquisa aprofundada; conversão de delimitadores matemáticos ponta a ponta |
| `computer_demo` | computador, renderização de workflow de sete turnos |
| `council_demo` | renderização de comitê de modelo de conselho com um payload aninhado grande |
| `study_demo` | renderização de modo de estudo |

<a id="reduced-scenario-fixtures" data-pplx-source-anchor="true"></a>
### Fixtures de cenário reduzido

Estes são payloads simulados focados contendo apenas as entradas e
relacionamentos necessários para uma regressão. “Reduzido” não significa extraído de uma
thread real.

| Fixture | Cobertura |
|---|---|
| `scenario_computer_answer_fallback` | recuperar a resposta de um bloco de workflow esquematizado quando o caminho FINAL simples não está disponível |
| `scenario_subagent_fallback` | renderizar um título de subagente e seus próprios itens quando não existe correspondência de fundo |
| `scenario_user_response` | renderização de pergunta/resposta `WORKFLOW_ITEM_USER_RESPONSE` |
| `scenario_subagent_stub` | janela de associação de dez segundos para um stub de resultado de subagente não ancorado |
| `scenario_workflow_item_nested` | renderização de bloco recolhido `WORKFLOW_ITEM_WORKFLOW` aninhado |
| `scenario_limit_interrupted` | interrupção de limite de gastos, cascata de atribuição, posicionamento de apêndice e sem dupla renderização |
| `scenario_canceled` | anotação `WORKFLOW_CANCELED` |

<!-- /audit:inventory fixture-directories -->

<a id="maintaining-fixtures" data-pplx-source-anchor="true"></a>
## Manutenção de fixtures

`tests/scrub_fixtures.py` normaliza os dados simulados, regenera produtos
dourados através do renderizador offline de produção e impõe uma verificação de resíduo:

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **Regeneração** — cada fixture é renderizado em um diretório temporário através
  de `pplx_export.commands.rerender_cmd.rerender`; incompatibilidades de contagem de turnos abortam.
- **Normalização determinística** — texto placeholder, UUIDs, valores `toolu_`,
  tokens e URLs assinadas são normalizados idempotentemente.
- **Entradas de segurança não são proveniência** — a configuração opcional local
  `tests/scrub_pairs.local.json` e de conta de usuário apenas
  estendem verificações de substituição e resíduo. Elas não devem ser usadas como entradas
  para construir cenários de fixture.
- **Modo de verificação** — `--check` não realiza gravações e falha em resíduo configurado,
  caminhos absolutos locais ou credenciais de URL assinada.

Execute a ferramenta de manutenção após alterar o JSON de entrada simulado ou a saída do renderizador,
e execute `--check` antes de confirmar alterações de fixture.

<a id="golden-snapshot-authority" data-pplx-source-anchor="true"></a>
## Autoridade do snapshot dourado

O JSON simulado confirmado é a autoridade de entrada. O Markdown dourado é saída
derivada: é regenerado a partir desse JSON com o caminho de re-renderização de produção atual
e então confirmado para comparação de regressão em nível de byte. Não deve ser
editado como uma fonte de verdade independente.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Veja também

- [Testes](testing.md) — como o conjunto consome os fixtures
- [Arquitetura do sistema de teste](testing-architecture.md) — camadas
  de regressão e garantias
- `tests/fixtures/README.md` — inventário de fixtures local do repositório
