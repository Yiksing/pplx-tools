---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/index.md"
translation_source_sha256: "4687af317a6aa8c7f17c6b758463042f3f6fa6f00ba78bc0ec76464bc1bec69b"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="user-guide" data-pplx-source-anchor="true"></a>
# Guia do usuário

Documentação orientada a tarefas para instalar, configurar e operar
`pplx-export` e `pplx-ask`.

<a id="start-here" data-pplx-source-anchor="true"></a>
## Comece aqui

- [Introdução](getting-started.md) — instale os comandos, inicialize a
  configuração e execute a primeira exportação.
- [Configuração](configuration.md) — contas, fontes de cookies, diretórios de saída
  e configurações do espaço BOT.

<a id="command-reference" data-pplx-source-anchor="true"></a>
## Referência de comandos

- [pplx-export](pplx-export.md) — comandos de indexação, exportação e arquivamento em lote.
- [pplx-ask](pplx-ask.md) — consultas de pesquisa em streaming, pesquisa aprofundada, conselho e estudo.
- [Comandos de manutenção](maintenance-commands.md) — operações de re-renderização, preenchimento retroativo,
  relações e sincronização.

<a id="archives-and-synchronization" data-pplx-source-anchor="true"></a>
## Arquivos e sincronização

- [Estrutura do arquivo](archive-layout.md) — arquivos, índices, estado e respostas brutas
  retidas.
- [Modos de conversa](modes.md) — limites de artefato para cada modo suportado.
- [Sincronização incremental](incremental-sync.md) — parada antecipada, pontos de verificação e comportamento
  de retomada.

<a id="operations" data-pplx-source-anchor="true"></a>
## Operações

- [Limitação de taxa](rate-limiting.md) — cadência segura de requisições e agendamento.
- [Solução de problemas](troubleshooting.md) — falhas comuns e caminhos de recuperação.

Para detalhes de implementação, continue para o
[mapa de leitura da arquitetura](../architecture/index.md).
