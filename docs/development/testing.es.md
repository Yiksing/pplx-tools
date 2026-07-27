---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing.md"
translation_source_sha256: "a552c25a28367f384140a2e5cc2e9fa2a8546034b668772f5df79133d4995648"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing" data-pplx-source-anchor="true"></a>
# Pruebas

El conjunto de pruebas reside en `tests/`, fuera del paquete `pplx_export`, y se ejecuta completamente sin conexión. Sus entradas con forma de API son datos simulados deterministas confirmados bajo `tests/fixtures/`; las pruebas no dependen de servicios en vivo ni de una configuración real a nivel de usuario.

Esta página contiene el inventario actual de módulos de prueba y el flujo de trabajo del colaborador. Para el diseño de regresiones, consulte [Arquitectura del sistema de pruebas](testing-architecture.md). Para el contrato de datos de entrada, consulte [Accesorios de prueba](fixtures.md).

<a id="running-the-tests" data-pplx-source-anchor="true"></a>
## Ejecución de las pruebas

```bash
uv run pytest tests
```

pytest es una dependencia de desarrollo declarada. El conjunto garantiza:

- **Sin red** — las entradas simuladas están verificadas; las rutas que interactúan con la red están cubiertas con simulaciones, `tmp_path` y `monkeypatch`.
- **Sin configuración real de usuario** — antes de importar cualquier módulo de producción, `tests/conftest.py` crea una configuración temporal local al proceso y anula `PPLX_EXPORT_CONFIG`. Cada prueba recibe entonces su propia configuración `alice` / `bob` y restaura la configuración temporal local al proceso después. Las regresiones de subprocesos verifican que una configuración faltante o dañada del llamador no pueda romper la recolección de pruebas.
- **Retroalimentación rápida** — al 2026-07-25 el proyecto observó 435 pruebas recolectadas de 32 módulos `test_*.py` y ejecutó el conjunto completo en aproximadamente 13–25 segundos en ejecuciones de verificación local. Los conteos son una instantánea del repositorio fechada y crecerán.

Selecciones útiles:

| Comando | Efecto |
|---|---|
| `uv run pytest tests` | conjunto completo |
| `uv run pytest tests/test_units.py` | un módulo |
| `uv run pytest tests -k snapshot` | pruebas cuyo id de nodo coincide con `snapshot` |
| `uv run pytest tests -x -q` | detenerse en el primer fallo, salida silenciosa |
| `uv run pytest --collect-only -q` | actualizar el conteo de casos recolectados |

<a id="current-module-inventory" data-pplx-source-anchor="true"></a>
## Inventario actual de módulos

Inventario sincronizado con el repositorio el **2026-07-27**:

<!-- audit:inventory test-modules -->

| Familia funcional | Módulos | Propósito |
|---|---|---|
| Instantáneas de renderizado | `test_render_snapshots.py` | re-renderizar todos los accesorios simulados de modo completo y escenario reducido, luego comparar los productos confirmados byte por byte |
| Utilidades centrales y compartidas | `test_units.py` | estado, limitación, planificación, normalización, nombres de activos, detección de modo, rutas seguras y regresiones transversales |
| Contratos de documentación, habilidades y localización | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | contratos de habilidades locales al repositorio más pruebas aisladas de repositorio en miniatura para el auditor de documentación de solo lectura y el pipeline de traducción automática |
| Configuración, autenticación e inicialización | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | aislamiento de configuración externa, perfiles de fuente de cookies, selección de credenciales e inicialización |
| Semántica de renderizado y flujo de trabajo | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | atribución de flujo de trabajo, estados de interrupción, variantes de respuesta, registro de auditoría y aristas de relación |
| Mantenimiento de archivo e índice sin conexión | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | enriquecimiento, comportamiento de reanudación/idempotencia, detección de eliminación entre cuentas, estados terminales y los niveles de informe de cambio/cuenta de estado sin conexión |
| Regresiones de revisión | 16 módulos `test_fix_*.py` listados abajo | correcciones derivadas de hallazgos de revisión; los nombres de los módulos conservan el linaje de revisión |

<a id="review-regression-lineage" data-pplx-source-anchor="true"></a>
### Linaje de regresiones de revisión

Los identificadores de revisión explican por qué existe una regresión; no son la arquitectura principal del conjunto de pruebas. El mapeo es deliberadamente muchos a muchos: un módulo puede cubrir varios hallazgos, y un hallazgo también puede agregar casos a un módulo temático existente.

| Linaje | Módulos dedicados |
|---|---|
| Revisión N | `test_fix_n01_inline_assets.py`, `test_fix_n02_spaces_link.py`, `test_fix_n03_n12.py`, `test_fix_n04_cookies.py`, `test_fix_n05_n06_n09.py`, `test_fix_n07_usage_checkpoint.py`, `test_fix_n08_throttle_overflow.py`, `test_fix_n10_table_header.py`, `test_fix_n11_batch_total.py` |
| Revisión V3 | `test_fix_v301_nested_sources_text.py`, `test_fix_v305_export_products.py` |
| Revisión V4 | `test_fix_v401_thread_dir_migration.py`, `test_fix_v402_manifest_count.py`, `test_fix_v403_handle_assets_idempotency.py`, `test_fix_v405_ask_post_steps.py` |
| Revisión V5 | `test_fix_v5_review.py`, más adiciones enfocadas a módulos temáticos existentes |
| Revisión V6 | `test_fix_v6_atomic_writes.py` |

<!-- /audit:inventory test-modules -->

Los docstrings de los módulos siguen siendo la explicación autorizada del comportamiento anterior de cada hallazgo, el comportamiento corregido y el límite de regresión.

<a id="how-snapshot-tests-reuse-the-production-re-render-path" data-pplx-source-anchor="true"></a>
## Cómo las pruebas de instantáneas reutilizan la ruta de re-renderizado de producción

Las pruebas de instantáneas no implementan un renderizador paralelo:

1. `render_fixture` en `tests/conftest.py` copia el `raw_entries.json` simulado de un accesorio, el `raw_blocks.json` opcional y `thread.json` en un directorio temporal.
2. Llama a `pplx_export.commands.rerender_cmd.rerender`, la misma función utilizada por `pplx-export re-render`.
3. La fábrica de accesorios `rendered` devuelve la salida nueva y el directorio `golden/` confirmado del accesorio.
4. Las pruebas comparan `conversation.md` y cada `turns/turn_*.md` byte por byte.

Los invariantes de contenido complementan la igualdad de bytes: las respuestas no deben colapsar al marcador de posición `(无)` vacío, y los residuos de representación de dict como `{'type': ...` no deben filtrarse al texto renderizado.

<a id="adding-a-test" data-pplx-source-anchor="true"></a>
## Agregar una prueba

- **Lógica existente** — agregue una prueba al módulo temático correspondiente. Use `tmp_path`, simulaciones y `monkeypatch`; nunca acceda a la red ni a `~/.config` real.
- **Regresión de error** — prefiera el módulo temático correspondiente. Cree un módulo `test_fix_<lineage>_<slug>.py` cuando conservar el linaje de revisión mejore materialmente la trazabilidad; no asuma un módulo por hallazgo.
- **Regresión de renderizado** — agregue o reduzca un accesorio simulado, regenere sus productos de referencia con la herramienta de mantenimiento, luego regístrelo en `test_render_snapshots.py` o agregue aserciones específicas del escenario.

Siga el estilo vecino: anotaciones de tipo, `from __future__ import annotations` y docstrings de módulo bilingües.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Véase también

- [Accesorios de prueba](fixtures.md) — entradas simuladas, productos de referencia y el contrato de mantenimiento
- [Arquitectura del sistema de pruebas](testing-architecture.md) — capas de prueba y garantías de regresión
- [Operaciones sin conexión](../architecture/offline-operations.md) — la ruta de re-renderizado de producción utilizada por las pruebas de instantáneas
