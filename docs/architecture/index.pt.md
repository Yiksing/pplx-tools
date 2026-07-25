---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/index.md"
translation_source_sha256: "a64006f8b94ad04a3bc498468e674f3b8a22f27242c9bb7b8c5a9252019cc751"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="architecture-reading-map" data-pplx-source-anchor="true"></a>
# Mapa de leitura da arquitetura

Referência de mecanismo para ferramentas pplx (`pplx-export` / `pplx-ask`):
dependências, pipelines, máquinas de estado, contratos de dados e limites
de confiabilidade. Para uso orientado a tarefas, comece com o [Guia do usuário](../guide/index.md).

!!! note "Escopo e fonte da verdade"

    Estas páginas explicam a arquitetura do `pplx_export/` para agentes e
    engenheiros que mantêm o projeto. As referências de linha usam `file.py:NN`,
    relativas a `pplx_export/`. As descrições foram verificadas em relação ao
    repositório em 2026-07-23 (`__version__ = "0.1.0"`,
    `pplx_export/__init__.py:31`); o código e os testes atuais permanecem como autoridade.

<a id="start-with-the-system-map" data-pplx-source-anchor="true"></a>
## Comece pelo mapa do sistema

- [Visão geral da arquitetura](overview.md) — camadas, responsabilidades dos módulos e
  o grafo de dependências em nível de importação.

<a id="follow-a-runtime-flow" data-pplx-source-anchor="true"></a>
## Siga um fluxo de execução

- [Pipeline de exportação](export-pipeline.md) — busca, retenção de resposta bruta,
  detecção de modo e renderização Markdown.
- [Subagentes e interrupções](subagents-interruptions.md) — atribuição de
  payload e semântica de interrupção/retomada.
- [pplx-ask e contas](ask-and-accounts.md) — consultas em streaming e
  alternância de cookies entre múltiplas contas.

<a id="understand-data-and-reliability" data-pplx-source-anchor="true"></a>
## Entenda dados e confiabilidade

- [Modelo de dados e contrato de diretório](data-model.md) — modelos, limites
  de escrita e o contrato de arquivamento em disco.
- [Limitação de taxa e tratamento de erros](rate-limiting-errors.md) — limitação,
  backoff, estados terminais e roteamento de erros.
- [Operações offline](offline-operations.md) — re-renderização sem rede,
  reconstrução de relacionamentos e pipelines de manutenção local.

<a id="related-references" data-pplx-source-anchor="true"></a>
## Referências relacionadas

- [Referência da API Web](../reference/api/index.md) — contratos REST/GraphQL observados,
  semântica de resposta e notas de descoberta.
- [Guia do mantenedor](../development/index.md) — arquitetura de teste, fluxo de trabalho
  do contribuidor e contratos de fixtures simuladas.
