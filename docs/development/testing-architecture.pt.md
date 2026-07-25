---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing-architecture.md"
translation_source_sha256: "ca93c1e43ccc41337097685ec6268f2d1f6a9997504b4a67683bce250b443b66"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing-architecture" data-pplx-source-anchor="true"></a>
# Arquitetura de teste

O sistema de teste do `pplx_export` é totalmente offline, usa dados simulados verificados no repositório e bloqueia o comportamento do renderizador por snapshots. Esta página descreve a arquitetura e as garantias; a lista atual de módulos pertence a [Testing](../development/testing.md), e os detalhes das fixtures pertencem a [Test fixtures](../development/fixtures.md).

A seção mantém sua numeração da [visão geral da arquitetura](../architecture/overview.md).

---

<a id="test-system" data-pplx-source-anchor="true"></a>
## Sistema de teste

Execute a suíte com `uv run pytest tests`. As contagens de teste são relatadas a partir da execução atual, em vez de tratadas como uma constante arquitetural.

<a id="layers" data-pplx-source-anchor="true"></a>
### Camadas

| Camada | Módulos representativos | Contrato |
|---|---|---|
| Comportamento de unidade puro | `test_units.py`, testes de credenciais/cookies/config | isolar funções, classes, validação e normalização com entradas simuladas |
| Semântica de componentes | testes de interrupção, fluxo de trabalho simulado, variante de resposta e relações | exercitar a cooperação entre código de análise, renderizador, estado e índice sem acesso à rede |
| Comportamento de comando/estado offline | testes de backfill, sincronização de exclusão, inicialização e regressões de revisão | executar caminhos de comando em diretórios temporários e transportes simulados |
| Snapshots de renderização | `test_render_snapshots.py` | passar JSON simulado em formato de API pelo caminho de re-renderização de produção e comparar todos os bytes Markdown com goldens confirmados |

Identificadores de revisão como N, V3, V4 e V5 são metadados de rastreabilidade entre essas camadas. Eles não definem uma arquitetura de tempo de execução separada, e sua relação com os módulos de teste não é necessariamente um-para-um.

<a id="snapshot-data-flow" data-pplx-source-anchor="true"></a>
### Fluxo de dados de snapshot

1. Uma fixture simulada fornece `raw_entries.json`, `raw_blocks.json` opcional e `thread.json`.
2. `tests/conftest.py::render_fixture` copia esses arquivos para `tmp_path`.
3. A fixture chama `commands.rerender_cmd.rerender`, o caminho de reconstrução offline de produção.
4. Novos arquivos `conversation.md` e `turns/turn_*.md` são comparados byte a byte com os produtos `golden/` confirmados.

Goldens são expectativas geradas, não uma fonte de dados independente. Qualquer alteração no renderizador que altere os bytes do artefato torna a suíte de snapshot vermelha até que a alteração seja revisada e os goldens sejam intencionalmente regenerados.

<a id="isolation-and-trust-boundaries" data-pplx-source-anchor="true"></a>
### Isolamento e limites de confiança

- **Origem da fixture** — todas as entradas de fixture confirmadas são dados simulados. Elas não são copiadas de contas ativas, respostas de API ativas, `web_archive/` ou arquivos privados.
- **Limite de rede** — os testes usam caminhos simulados e offline; as fixtures verificadas no repositório não exigem credenciais ou acesso à rede.
- **Limite de configuração** — a fixture de uso automático instala configuração de conta placeholder, de modo que o `~/.config` real do desenvolvedor não determina os resultados.
- **Limite de sistema de arquivos** — o comportamento de comando e migração é executado sob `tmp_path`; arquivos de usuário não são alvos de teste.
- **Limite de resíduo** — `tests/scrub_fixtures.py --check` rejeita strings específicas de ambiente configuradas, caminhos absolutos locais e credenciais de URL assinada sem modificar arquivos.

Juntos, asserções de unidade, semântica de componentes, testes de estado de comando e snapshots em nível de byte protegem tanto a lógica local quanto o contrato de re-renderização de ponta a ponta.
