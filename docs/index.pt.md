---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/index.md"
translation_source_sha256: "7a016c35bbb11272395a246fd23c0c27be794585c5b1cda9fdc9c6181fe32e48"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="perplexity-cli-toolkit" data-pplx-source-anchor="true"></a>
# Kit de ferramentas CLI Perplexity

<p class="homepage-scope-note" role="note">
  <strong>NÃO para API pré-paga</strong>
</p>

Perplexity kit de ferramentas de arquivo de conversas e consulta interativa (`pplx-export` / `pplx-ask`).

Ele se comunica diretamente com a API REST/GraphQL do Perplexity usando os cookies de sessão do seu navegador e arquiva conversas — etapas, citações, relatórios de pesquisa aprofundada, ativos do modo computador e fluxos de trabalho de subagentes — como Markdown + JSON local. Exportações bem-sucedidas retêm as respostas brutas da API junto com os artefatos renderizados, permitindo que a renderização seja executada novamente offline a qualquer momento.

<a id="introduction" data-pplx-source-anchor="true"></a>
## Introdução

Além de arquivar conversas históricas, este projeto visa principalmente dar a agentes locais — mais próximos dos dados e muitas vezes apoiados por mais poder computacional — uma medida das capacidades do Perplexity Computer. Ao permitir que eles acessem relatórios produzidos pelo Perplexity Deep Research diretamente em seu ciclo de trabalho, eles podem usar informações de alta qualidade para ajustar parâmetros-chave no código com mais precisão, enquanto fazem uso mais completo de uma assinatura Perplexity Max existente.

> Em 20 de julho, o Perplexity não oferecia uma CLI oficial para ambientes Unix-like. Em 23 de julho, o Perplexity lançou publicamente a ferramenta `pplx` usada no modo computador, mas essa ferramenta ainda usa faturamento pré-pago.

Não é uma substituição completa para o modo computador. Duas habilidades permanecem fora de alcance:

- a liberdade da habilidade Deep Research de escolher um modelo arbitrário;
- a capacidade da habilidade Council de executar pesquisa aprofundada com vários modelos especificados pelo usuário, produzir relatórios e compará-los lado a lado.

O diretório [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context) inclui prompts de sistema arquivados e regras operacionais que podem ajudar a aproximar partes do fluxo de trabalho do computador localmente, incluindo seleção de modo Deep Research e seleção de modelo de subagente.

<a id="features" data-pplx-source-anchor="true"></a>
## Recursos

<a id="pplx-export-archive-your-library" data-pplx-source-anchor="true"></a>
### `pplx-export` — arquive sua biblioteca

- Índice da biblioteca e índice de espaços
- Exportação de thread único / lote com parada antecipada incremental + pontos de verificação retomáveis
- Preenchimento de ativos e preenchimento de uso de crédito
- Grafo de relacionamento de conversas
- Re-renderização offline (`re-render`, zero rede)
- Trecho de cron incremental periódico

<a id="pplx-ask-query-perplexity-from-the-shell" data-pplx-source-anchor="true"></a>
### `pplx-ask` — consulte o Perplexity a partir do shell

- Consultas de streaming SSE em quatro modos: search / deep-research / council / study
- Movimento automático para um espaço BOT na conclusão, recibos de leitura
- Arquivamento automático de cada thread que cria — construído para que outros agentes possam chamá-lo para buscar informações em tempo real

Limites de artefatos por modo (citações / relatórios / ativos / subagentes): consulte [Modos](guide/modes.md); princípios de fidelidade de renderização: consulte [Pipeline de exportação](architecture/export-pipeline.md).

!!! note "Proveniência da documentação"

    A maioria das páginas neste site MkDocs foi gerada ou reconstruída a partir do código e testes atuais. Algumas páginas também retêm contexto de design, observações e decisões de discussões anteriores com agentes. Quando uma declaração da documentação e a implementação diferirem, trate o código e os testes atuais como a fonte da verdade.

<a id="where-to-next" data-pplx-source-anchor="true"></a>
## Para onde ir a seguir

- **Use as ferramentas** — siga o [Guia do usuário](guide/index.md) orientado a tarefas.
- **Entenda a implementação** — use o [Mapa de leitura da arquitetura](architecture/index.md).
- **Trabalhe com a interface web observada** — consulte a [Referência da API Web](reference/api/index.md).
- **Altere o projeto com segurança** — siga o [Guia do mantenedor](development/index.md).
