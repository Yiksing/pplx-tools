---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing-architecture.md"
translation_source_sha256: "ca93c1e43ccc41337097685ec6268f2d1f6a9997504b4a67683bce250b443b66"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing-architecture" data-pplx-source-anchor="true"></a>
# Arquitectura de pruebas

El sistema de pruebas de `pplx_export` es completamente offline, utiliza datos simulados verificados y bloquea el comportamiento del renderizador mediante instantáneas. Esta página describe la arquitectura y las garantías; la lista actual de módulos pertenece a [Testing](../development/testing.md), y los detalles de los fixtures pertenecen a [Test fixtures](../development/fixtures.md).

La sección mantiene su numeración de la [visión general de la arquitectura](../architecture/overview.md).

---

<a id="test-system" data-pplx-source-anchor="true"></a>
## Sistema de pruebas

Ejecute el conjunto con `uv run pytest tests`. Los recuentos de pruebas se informan desde la ejecución actual, no se tratan como una constante arquitectónica.

<a id="layers" data-pplx-source-anchor="true"></a>
### Capas

| Capa | Módulos representativos | Contrato |
|---|---|---|
| Comportamiento de unidad pura | `test_units.py`, pruebas de credenciales/cookies/configuración | aislar funciones, clases, validación y normalización con entradas simuladas |
| Semántica de componentes | pruebas de interrupción, flujo de trabajo stub, variante de respuesta y relaciones | ejercitar la cooperación entre el analizador, el renderizador, el estado y el código de índice sin acceso a la red |
| Comportamiento de comando/estado offline | pruebas de relleno, sincronización de eliminación, inicialización y regresiones de revisión | ejecutar rutas de comando contra directorios temporales y transportes falsos |
| Instantáneas de renderizado | `test_render_snapshots.py` | pasar JSON con forma de API simulada a través de la ruta de re-renderizado de producción y comparar todos los bytes de Markdown con los golden confirmados |

Los identificadores de revisión como N, V3, V4 y V5 son metadatos de trazabilidad a través de estas capas. No definen una arquitectura de tiempo de ejecución separada, y su relación con los módulos de prueba no es necesariamente uno a uno.

<a id="snapshot-data-flow" data-pplx-source-anchor="true"></a>
### Flujo de datos de instantáneas

1. Un fixture simulado proporciona `raw_entries.json`, `raw_blocks.json` opcional y `thread.json`.
2. `tests/conftest.py::render_fixture` copia esos archivos en `tmp_path`.
3. El fixture llama a `commands.rerender_cmd.rerender`, la ruta de reconstrucción offline de producción.
4. Los archivos nuevos de `conversation.md` y `turns/turn_*.md` se comparan byte por byte con los productos golden confirmados `golden/`.

Los golden son expectativas generadas, no una fuente de datos independiente. Cualquier cambio en el renderizador que altere los bytes del artefacto hará que el conjunto de instantáneas falle hasta que se revise el cambio y los golden se regeneren intencionalmente.

<a id="isolation-and-trust-boundaries" data-pplx-source-anchor="true"></a>
### Límites de aislamiento y confianza

- **Origen del fixture** — todas las entradas de fixture confirmadas son datos simulados. No se copian de cuentas reales, respuestas de API reales, `web_archive/` o archivos privados.
- **Límite de red** — las pruebas utilizan rutas falsas y offline; los fixtures confirmados no requieren credenciales ni acceso a la red.
- **Límite de configuración** — el fixture de uso automático instala una configuración de cuenta de marcador de posición, por lo que el `~/.config` real de un desarrollador no determina los resultados.
- **Límite del sistema de archivos** — el comportamiento de comandos y migraciones se ejecuta bajo `tmp_path`; los archivos de usuario no son objetivos de prueba.
- **Límite de residuos** — `tests/scrub_fixtures.py --check` rechaza cadenas específicas del entorno configuradas, rutas absolutas locales y credenciales de URL firmadas sin modificar archivos.

En conjunto, las aserciones de unidad, la semántica de componentes, las pruebas de estado de comando y las instantáneas a nivel de byte protegen tanto la lógica local como el contrato de re-renderizado de extremo a extremo.
