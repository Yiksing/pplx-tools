---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/maintenance-commands.md"
translation_source_sha256: "550aca319a6386123658e8d54ede5367bc97765c9a11710e20f1ed1f2854f617"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintenance-commands" data-pplx-source-anchor="true"></a>
# Comandos de mantenimiento

Los subcomandos de mantenimiento de `pplx-export` mantienen un archivo existente en buen estado: re-renderizan páginas tras correcciones del renderizador, rellenan activos/uso de créditos/metadatos de modo, marcan como eliminados hilos remotos y reconstruyen el grafo de relaciones. La mayoría son offline-first; sus fases en línea siguen la misma disciplina de ritmo que `batch` (consulte [rate-limiting.md](rate-limiting.md)). Todos aceptan las [opciones comunes](pplx-export.md) (`--account`, `--out`, `--cookies-from`, `--transport`, …).

- Principio de retención del archivo local: ningún comando de mantenimiento elimina o mueve contenido de hilos archivados; el archivo es la copia de seguridad.
- Los comandos fuera de línea (`re-render`, `relations`, `sync-space`, `spaces` sin `--fetch-meta`, y las fases predeterminadas a continuación) no necesitan transporte en absoluto; consulte [../architecture/offline-operations.md](../architecture/offline-operations.md).

## re-render

Regenera `conversation.md` y `turns/` a partir del JSON sin procesar archivado (`raw_entries.json` / `raw_blocks.json`) tras correcciones del renderizador: cero red, y todos los demás archivos quedan intactos.

| Indicador | Significado | Predeterminado |
|---|---|---|
| `--limit N` | Procesa solo los primeros N directorios de hilos | todos |
| `--dry-run` | Lista los directorios que se procesarían, no escribe nada | desactivado |
| `--thread-json` | También agrega/elimina las claves `interruptions` y `answer_variants` en `thread.json` en el lugar | desactivado |

Comportamientos clave:

- Reconstruye turnos fuera de línea con el mismo pipeline que la exportación: análisis, ordenación por `created_us`, deduplicación de citas y — para computer/council — bloques de flujo de trabajo, mapeo de subagentes y el apéndice de fondo no consumido.
- Solo se (re)escriben `conversation.md` y `turns/turn_*.md`; `sources*`, `assets/`, `report.md` y `thread.json` permanecen como están. Los archivos `turn_*.md` obsoletos numerados por encima del recuento de turnos actual se eliminan; nada más, por lo que los archivos sin cambios conservan su mtime.
- `--thread-json` escribe solo cuando el contenido realmente cambia; los `answer_variants` recién agregados/cambiados generan una advertencia `ANSWER_VARIANT_DETECTED` y se agregan a `index/answer_variants_log.jsonl` (las reejecuciones idempotentes no saturan).
- Los directorios de hilos sin `raw_entries.json` se omiten y se cuentan.

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

Remedia activos que se archivaron sin una URL firmada: tres remedios escalonados: recuperación de bloques faltantes, extracción en línea fuera de línea y actualización opcional en línea.

| Indicador | Significado | Predeterminado |
|---|---|---|
| `--fetch-blocks` | Primero recupera los `raw_blocks.json` faltantes y sus activos de URL firmada (en línea) | desactivado |
| `--online` | Habilita la actualización en línea de activos faltantes/obsoletos | desactivado (solo extracción en línea fuera de línea, cero solicitudes) |
| `--limit N` | Procesa solo los primeros N directorios de hilos | todos |

Comportamientos clave:

- Fase predeterminada (fuera de línea, cero solicitudes): extrae activos en línea (`ASSET_DIFF` / `CODE_ASSET`) de `raw_blocks.json` a `assets/files/*.md`, y registra tipos de identificadores de espacio de trabajo en la nube (`DOC_FILE` / `CODE_FILE` / `UNKNOWN` — aún sin canal de descarga) en `assets/assets_manifest.json`. Idempotente: los registros conocidos se deduplican por uuid, luego por file_handle; los archivos del mismo nombre con varias versiones obtienen un sufijo corto de uuid para que las reejecuciones no colisionen.
- `--fetch-blocks` (en línea): recupera los `raw_blocks.json` faltantes para hilos deep-research/computer/council/study más sus activos descargables; los hilos se agrupan por carpeta de cuenta con un adaptador creado perezosamente por cuenta (las cookies cambian automáticamente), 3s entre hilos.
- `--online`: para versiones de manifiesto cuyo `downloaded_to` falta/está obsoleto, obtiene una URL firmada nueva mediante `/rest/assets/<uuid>/data` (llamadas API en serie, con 3s de diferencia), luego vuelve a descargar desde la CDN (6 hilos concurrentes, sin demora — CDN, no API). Un `ASSET_NOT_FOUND` 404 establece el indicador terminal `asset_expired`; un 403 entre cuentas se reintenta una vez con la cuenta propietaria de la carpeta de archivo.
- El `count` del manifiesto se recalcula como el número total de versiones en cada escritura.

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

Rellena el uso de créditos por hilo (`credits/thread-usage`) para todos los hilos archivados de la cuenta en `index/credit_usage_<account>.json`.

| Indicador | Significado | Predeterminado |
|---|---|---|
| `--limit N` | Procesa solo los primeros N hilos | todos |

Comportamientos clave:

- Un GET por hilo archivado (`thread_id` = el `psc_uuid` del hilo), con 3s de diferencia; idempotente — los hilos ya presentes en el archivo de salida se omiten.
- Un 403 (`thread_usage_forbidden`, es decir, un hilo entre cuentas) se registra como `error` y nunca se reintenta; otros fallos se dejan para la siguiente ejecución. El progreso se guarda cada 25 hilos procesados.
- Multi-cuenta: ejecutar una vez por cuenta con `--account` — las cookies cambian automáticamente entre ejecuciones.

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

Rellena el campo `search_mode` autoritativo de la plataforma en cada fila de `index/library_<account>.json`, para que `batch --mode` pueda filtrar exactamente en lugar de depender de heurísticas.

| Indicador | Significado | Predeterminado |
|---|---|---|
| `--limit N` | Procesa solo las primeras N filas pendientes | todas |
| `--offline` | Solo extracción local — las filas sin datos sin procesar locales esperan la siguiente ronda, sin respaldo en línea | desactivado |
| `--delay-min SEC` | Límite inferior del intervalo aleatorio entre hilos de respaldo en línea | `10` |
| `--delay-max SEC` | Límite superior del intervalo aleatorio entre hilos de respaldo en línea | `20` |

Comportamientos clave:

- Almacena el valor sin procesar de la plataforma (`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…); un hilo que lleva múltiples valores conserva el más específico según computer > council > study > deep-research > search.
- Local-first: los hilos archivados se resuelven desde `raw_entries.json` con cero red — una ejecución completamente local nunca construye un transporte (ni siquiera una sonda de sesión).
- Respaldo en línea solo para filas sin datos sin procesar locales: `GET /rest/thread/<uuid>` con un intervalo aleatorio de 10–20s; las filas en estado terminal `expired` se omiten y registran; los hilos encontrados recién expirados/eliminados en línea se marcan en `batch_state.json` para ahorrar solicitudes futuras.
- Idempotente y reanudable: las filas que ya tienen `search_mode` se omiten, el progreso se guarda cada 25 filas, y las actualizaciones `index` posteriores preservan el enriquecimiento (fusionado de nuevo por `entryUUID`).

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

Identifica hilos que desaparecieron de la biblioteca remota (eliminados por el usuario o la plataforma) y los marca como eliminados — nunca elimina ni mueve ningún archivo de archivo.

| Indicador | Significado | Predeterminado |
|---|---|---|
| `--online` | Verifica cada candidato en línea | desactivado (simulación fuera de línea: solo lista candidatos) |
| `--limit N` | Procesa solo los primeros N candidatos | todos |
| `--delay-min SEC` | Límite inferior del intervalo aleatorio entre candidatos | `10` |
| `--delay-max SEC` | Límite superior del intervalo aleatorio entre candidatos | `20` |

Comportamientos clave:

- La detección de candidatos es fuera de línea y entre cuentas: un hilo con estado `batch_state` `ok` que falta en la unión `entryUUID` de **todos** los archivos `index/library_*.json` se convierte en candidato — cualquier índice individual que lo contenga cuenta como vivo, por lo que los hilos exportados entre cuentas a través de espacios compartidos no son falsos positivos. Cuando no existe un índice utilizable, todo se omite de forma segura con una sugerencia para ejecutar `index` primero.
- El valor predeterminado es una simulación fuera de línea: lista candidatos y razones de omisión segura — cero red, cero escrituras.
- `--online` verifica cada candidato con `GET /rest/thread/<uuid>` bajo la cuenta registrada en `thread.json` `export_via` (las cookies cambian automáticamente por candidato).
- Confirmado por `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 → `batch_state` marca el estado terminal `deleted` (misma semántica que `expired`: nunca reintentado, `--force` no reexporta; consulte [incremental-sync.md](incremental-sync.md)) y cada uno de los archivos `thread.json` del hilo obtiene una marca de tiempo `remote_deleted` en el lugar (idempotente — una clave existente se conserva).
- El hilo aún existe → falso positivo: se informa tal cual con una sugerencia para reejecutar `index`, nada cambió. Los errores de transporte retroceden a la siguiente ronda; 3 fallos de autenticación consecutivos abortan la ejecución antes de que algo se marque incorrectamente.

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

La primera ejecución lista candidatos (simulación fuera de línea); la segunda los verifica en línea y marca los confirmados.

## status

Imprime el estado de la cuenta de archivo y el plan de cambios incrementales — cero red, solo lectura. Responde "¿cómo se ve el archivo ahora mismo y qué haría la próxima ejecución de `batch`?" sin tocar la red.

| Indicador | Significado | Predeterminado |
|---|---|---|
| `--account X` | Informa sobre una sola cuenta | todas las cuentas que tienen un archivo `index/library_*.json` |
| `--json` | Informe completo legible por máquina en stdout (ignora la verbosidad) | desactivado (líneas de registro humano) |

Comportamientos clave:

- Las fuentes de datos son puramente locales: `index/library_*.json` (filas de índice por cuenta) y `index/batch_state.json` (la única fuente de estados de exportación). La clasificación de cambios reutiliza la misma función pura `plan_incremental` que `batch`/`schedule`, por lo que las semánticas de `new`/`updated`/`done`/`expired`/`deleted` son idénticas a lo que `batch` calcularía.
- La salida INFO predeterminada imprime una línea de resumen por cuenta (recuento de índice + frescura, recuentos de estado `ok/expired/deleted/error`, recuentos de cambios `new/updated` y el número de parada temprana) más una línea de cuenta `batch_state` global (por ejemplo, `559 ok + 13 expired + 12 deleted`).
- Los niveles de detalle siguen el indicador de verbosidad estándar: `-v` agrega los títulos de los hilos `new`/`updated`/`error` (primera línea, truncada a 60 caracteres); `-vv` agrega hilos `done`/`expired`/`deleted` con `lastUpdated`/`exported_at`; `-vvv` imprime todo sin truncar con campos de índice `mode`/`search_mode` y la lista solo de estado (registros presentes en `batch_state` pero faltantes en el índice de cada cuenta — candidatos de eliminación remota para reconciliar con [sync-deleted](#sync-deleted)).
- Barreras de protección: un `index/` faltante o un archivo de biblioteca faltante sale con un error señalando a `pplx-export index`; un `batch_state.json` faltante se trata como un estado vacío (todo cuenta como `new`). No se requiere configuración a nivel de usuario: las cuentas se enumeran a partir de los nombres de los archivos de biblioteca.
- `--json` emite el informe completo (cuentas, cambios, hilos, solo estado, totales) como un JSON de una sola línea en stdout — el mismo estilo de contrato que `pplx-ask`.

```bash
pplx-export status                 # summary for every account
pplx-export status -vv             # five-state thread details
pplx-export status --account alice --json
```

## relations

Reconstruye el grafo de relaciones de conversación a partir de los hilos exportados → `relations/edges.jsonl` más un `relations/graph.md` legible por humanos bajo la raíz del archivo.

| Indicador | Significado | Predeterminado |
|---|---|---|
| *(solo opciones comunes; solo `--out` importa)* | | |

Comportamientos clave:

- Puramente fuera de línea, cero red, solo lectura contra el archivo: reutiliza el pipeline de reconstrucción fuera de línea de re-render (`raw_entries.json` / `raw_blocks.json`), por lo que `sub_agents`, `query_source` y las señales de citas están disponibles para la detección de bordes.
- Los hilos sin datos sin procesar se degradan a un caparazón `thread.json` + `conversation.md` — solo los bordes de referencia `same_space` y uuid simple pueden activarse para ellos.

```bash
pplx-export relations
```

## debug-js

Ejecuta un fragmento de JavaScript en el contexto de la página del navegador actual a través del daemon WebBridge local (`127.0.0.1:10086`) e imprime el resultado como JSON — una puerta de escape de depuración.

| Indicador | Significado | Predeterminado |
|---|---|---|
| `JS代码` (posicional) | Código JavaScript para evaluar en el contexto de la página (el metavar argparse literal) | requerido |

Comportamientos clave:

- Requiere que el daemon WebBridge sea accesible y que la página Perplexity de destino esté abierta en el navegador; el fragmento se ejecuta con la propia sesión de la página.
- El JSON impreso se trunca a 5000 caracteres.

```bash
pplx-export debug-js 'document.title'
```
