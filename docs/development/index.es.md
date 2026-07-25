---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/index.md"
translation_source_sha256: "fc5f2fa607251be85bdc126f3701791c17d7330461b2ab49402ea485fcc961b7"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintainer-guide" data-pplx-source-anchor="true"></a>
# Guía para mantenedores

Contratos y flujos de trabajo para cambiar pplx-tools sin debilitar la fidelidad del archivo ni el aislamiento de pruebas.

<a id="choose-the-right-document" data-pplx-source-anchor="true"></a>
## Elija el documento correcto

- [Arquitectura de pruebas](testing-architecture.md) — capas de prueba, límites de confianza y las garantías proporcionadas por las instantáneas sin conexión.
- [Prácticas de prueba](testing.md) — inventario de pruebas actual y flujo de trabajo del colaborador.
- [Fixtures e instantáneas](fixtures.md) — procedencia de datos simulados, convenciones de directorios, generación de datos de referencia y comprobaciones de residuos.

<a id="local-quality-loop" data-pplx-source-anchor="true"></a>
## Bucle de calidad local

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Las entradas de los fixtures son datos simulados deterministas. No se copian de cuentas reales, respuestas de API reales, `web_archive/` ni archivos privados.
