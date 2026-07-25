---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/index.md"
translation_source_sha256: "fc5f2fa607251be85bdc126f3701791c17d7330461b2ab49402ea485fcc961b7"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintainer-guide" data-pplx-source-anchor="true"></a>
# Guia do mantenedor

Contratos e fluxos de trabalho para alterar as ferramentas pplx sem enfraquecer a fidelidade do arquivo ou o isolamento de teste.

<a id="choose-the-right-document" data-pplx-source-anchor="true"></a>
## Escolha o documento correto

- [Arquitetura de teste](testing-architecture.md) — camadas de teste, limites de confiança e as garantias fornecidas por snapshots offline.
- [Práticas de teste](testing.md) — inventário de teste atual e fluxo de trabalho do contribuidor.
- [Fixtures e snapshots](fixtures.md) — proveniência de dados simulados, convenções de diretório, geração dourada e verificações de resíduos.

<a id="local-quality-loop" data-pplx-source-anchor="true"></a>
## Ciclo de qualidade local

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

As entradas de fixture são dados simulados determinísticos. Eles não são copiados de contas reais, respostas de API reais, `web_archive/` ou arquivos privados.
