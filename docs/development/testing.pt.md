---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing.md"
translation_source_sha256: "a552c25a28367f384140a2e5cc2e9fa2a8546034b668772f5df79133d4995648"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing" data-pplx-source-anchor="true"></a>
# Testes

A suíte de testes reside em `tests/`, fora do pacote `pplx_export`, e é executada
completamente offline. Suas entradas em formato de API são dados simulados determinísticos confirmados
em `tests/fixtures/`; os testes não dependem de serviços ativos ou de uma configuração
real em nível de usuário.

Esta página contém o inventário atual dos módulos de teste e o fluxo de trabalho do contribuidor.
Para o design de regressão, consulte
[Arquitetura do sistema de teste](testing-architecture.md). Para o contrato
de dados de entrada, consulte [Fixtures de teste](fixtures.md).

<a id="running-the-tests" data-pplx-source-anchor="true"></a>
## Executando os testes

```bash
uv run pytest tests
```

pytest é uma dependência de desenvolvimento declarada. A suíte garante:

- **Zero rede** — entradas simuladas são verificadas; caminhos voltados para rede são
  cobertos com fakes, `tmp_path` e `monkeypatch`.
- **Nenhuma configuração real de usuário** — antes de importar qualquer módulo de produção,
  `tests/conftest.py` cria uma configuração temporária local ao processo e substitui
  `PPLX_EXPORT_CONFIG`. Cada teste então recebe sua própria configuração placeholder
  `alice` / `bob` e restaura o placeholder local ao processo
  depois. Regressões de subprocesso verificam que uma configuração ausente ou quebrada do
  chamador não pode quebrar a coleta de testes.
- **Feedback rápido** — em 2026-07-25 o projeto observou 435 testes coletados
  de 32 módulos `test_*.py` e executou a suíte completa em aproximadamente 13–25 segundos
  em execuções de verificação local.
  As contagens são um instantâneo datado do repositório e crescerão.

Seleções úteis:

| Comando | Efeito |
|---|---|
| `uv run pytest tests` | suíte completa |
| `uv run pytest tests/test_units.py` | um módulo |
| `uv run pytest tests -k snapshot` | testes cujo id do nó corresponde a `snapshot` |
| `uv run pytest tests -x -q` | parar na primeira falha, saída silenciosa |
| `uv run pytest --collect-only -q` | atualizar a contagem de casos coletados |

<a id="current-module-inventory" data-pplx-source-anchor="true"></a>
## Inventário atual de módulos

Inventário sincronizado com o repositório em **2026-07-27**:

<!-- audit:inventory test-modules -->

| Família funcional | Módulos | Propósito |
|---|---|---|
| Snapshots de renderização | `test_render_snapshots.py` | re-renderizar todas as fixtures simuladas de modo completo e cenário reduzido, depois comparar produtos confirmados byte a byte |
| Utilitários principais e compartilhados | `test_units.py` | estado, limitação, planejamento, normalização, nomeação de ativos, detecção de modo, caminhos seguros e regressões transversais |
| Contratos de documentação, habilidades e localização | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | contratos de habilidades locais ao repositório mais testes isolados de mini-repositório para o auditor de documentação somente leitura e pipeline de tradução automática |
| Configuração, autenticação e inicialização | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | isolamento de configuração externa, perfis de fonte de cookie, seleção de credenciais e inicialização |
| Semântica de renderização e fluxo de trabalho | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | atribuição de fluxo de trabalho, estados de interrupção, variantes de resposta, registro de auditoria e arestas de relação |
| Manutenção de arquivo offline e índice | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | enriquecimento, comportamento de retomada/idempotência, detecção de exclusão entre contas, estados terminais e os níveis de relatório de conta/alteração de estado offline |
| Regressões de revisão | 16 módulos `test_fix_*.py` listados abaixo | correções derivadas de achados de revisão; nomes de módulos retêm linhagem de revisão |

<a id="review-regression-lineage" data-pplx-source-anchor="true"></a>
### Linhagem de regressão de revisão

Identificadores de revisão explicam por que uma regressão existe; eles não são a
arquitetura primária da suíte de teste. O mapeamento é deliberadamente muitos-para-muitos: um
módulo pode cobrir vários achados, e um achado também pode adicionar casos a um
módulo temático existente.

| Linhagem | Módulos dedicados |
|---|---|
| Revisão N | `test_fix_n01_inline_assets.py`, `test_fix_n02_spaces_link.py`, `test_fix_n03_n12.py`, `test_fix_n04_cookies.py`, `test_fix_n05_n06_n09.py`, `test_fix_n07_usage_checkpoint.py`, `test_fix_n08_throttle_overflow.py`, `test_fix_n10_table_header.py`, `test_fix_n11_batch_total.py` |
| Revisão V3 | `test_fix_v301_nested_sources_text.py`, `test_fix_v305_export_products.py` |
| Revisão V4 | `test_fix_v401_thread_dir_migration.py`, `test_fix_v402_manifest_count.py`, `test_fix_v403_handle_assets_idempotency.py`, `test_fix_v405_ask_post_steps.py` |
| Revisão V5 | `test_fix_v5_review.py`, mais adições focadas a módulos temáticos existentes |
| Revisão V6 | `test_fix_v6_atomic_writes.py` |

<!-- /audit:inventory test-modules -->

Os docstrings dos módulos permanecem a explicação autoritativa do comportamento antigo de cada achado,
comportamento corrigido e limite de regressão.

<a id="how-snapshot-tests-reuse-the-production-re-render-path" data-pplx-source-anchor="true"></a>
## Como os testes de snapshot reutilizam o caminho de re-renderização de produção

Testes de snapshot não implementam um renderizador paralelo:

1. `render_fixture` em `tests/conftest.py` copia o `raw_entries.json` simulado de uma fixture,
   `raw_blocks.json` opcional e `thread.json` para um
   diretório temporário.
2. Ele chama `pplx_export.commands.rerender_cmd.rerender`, a mesma função
   usada por `pplx-export re-render`.
3. A fábrica de fixtures `rendered` retorna a saída nova e o diretório `golden/`
   confirmado da fixture.
4. Testes comparam `conversation.md` e cada `turns/turn_*.md` byte a byte.

Invariantes de conteúdo complementam a igualdade de bytes: respostas não devem colapsar para o
placeholder vazio `(无)`, e resíduos de representação de dicionário como `{'type': ...` não devem
vazar para o texto renderizado.

<a id="adding-a-test" data-pplx-source-anchor="true"></a>
## Adicionando um teste

- **Lógica existente** — adicione um teste ao módulo temático correspondente. Use
  `tmp_path`, fakes e `monkeypatch`; nunca acesse a rede ou `~/.config`
  real.
- **Regressão de bug** — prefira o módulo temático correspondente. Crie um
  módulo `test_fix_<lineage>_<slug>.py` quando reter a linhagem de revisão melhorar materialmente
  a rastreabilidade; não assuma um módulo por achado.
- **Regressão de renderização** — adicione ou reduza uma fixture simulada, regenere seus
  produtos dourados com a ferramenta de manutenção, depois registre-a em
  `test_render_snapshots.py` ou adicione asserções específicas de cenário.

Siga o estilo vizinho: anotações de tipo,
`from __future__ import annotations` e docstrings de módulo bilíngues.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Veja também

- [Fixtures de teste](fixtures.md) — entradas simuladas, produtos dourados e o
  contrato de manutenção
- [Arquitetura do sistema de teste](testing-architecture.md) — camadas de teste
  e garantias de regressão
- [Operações offline](../architecture/offline-operations.md) — o caminho de re-renderização
  de produção usado por testes de snapshot
