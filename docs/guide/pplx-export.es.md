---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/pplx-export.md"
translation_source_sha256: "09f79a39d95641d1816d529b4471c245bb60e11c49266417504b27a495c90231"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` es la CLI archivadora: extrae índices de conversaciones de Perplexity, exporta hilos al archivo local y mantiene las vistas derivadas (índice de espacios, fragmento cron). Esta página cubre los subcomandos de captura — `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule` — además del comando de configuración única `init`. Los subcomandos de relleno/reparación se encuentran en [maintenance-commands.md](maintenance-commands.md); la CLI de consulta se cubre en [pplx-ask.md](pplx-ask.md).

<a id="common-options" data-pplx-source-anchor="true"></a>
## Opciones comunes

Cada subcomando acepta estas banderas (definidas una vez en `pplx_export/commands/common.py`):

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| `--account NAME` | Cuenta objetivo. Cuando el correo electrónico de la cookie no coincide con el correo registrado, se enumeran los tokens de sesión del navegador por cuenta para cambiar automáticamente | `default_account` de la configuración de nivel de usuario |
| `--config PATH` | Archivo de configuración de nivel de usuario (registro de cuentas). Prioridad: `--config` > env `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | cadena de búsqueda predeterminada |
| `--skip-auth-check` | Omitir la sonda de sesión de atribución de cuenta al inicio y confiar en el inicio de sesión actual, evitando una larga espera de inicio en una red deficiente; `batch` ejecuta una verificación de cuenta diferida si se acumulan errores — consulte [Configuration](configuration.md) | desactivado |
| `--site NAME` | Adaptador de sitio | `perplexity` |
| `--out DIR` | Raíz de salida del archivo | `--out` > config `archive_root` > `./web_archive` |
| `--cookies-from BROWSER` | Importar cookies desde un navegador (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | Archivo de cookies Netscape o archivo de cookies JSON | — |
| `--transport MODE` | `cookie` = solicitudes directas con cookies; `webbridge` = obtener dentro del contexto de la página del navegador | `cookie` |
| `-v`, `--verbose` | Salida DEBUG (trazas de solicitud, decisiones internas); repetible | desactivado |
| `--log-file [PATH]` | Escribir el registro completo en disco; sin valor, ruta automática `<out>/index/logs/<cmd>-<timestamp>.log` | desactivado |

- `--cookies-from` / `--cookies` son mutuamente excluyentes con `--transport webbridge` — el puente se ejecuta en el contexto de la página y ya lleva las cookies del navegador.
- `pplx-export --version` imprime la versión del paquete y sale (solo a nivel superior, no es una bandera de subcomando).
- Registro de cuentas, fuentes de cookies y cambio entre múltiples cuentas: [configuration.md](configuration.md). Dónde se almacena todo en disco: [archive-layout.md](archive-layout.md).

## init

Descubrir cuentas a partir de cookies del navegador y escribir la configuración de nivel de usuario — la alternativa automática a copiar manualmente `config.example.toml` (consulte [configuration.md](configuration.md)).

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| `--force` | Sobrescribir un archivo de configuración existente | desactivado (se niega a sobrescribir) |
| `--create-bot-space [TITLE]` | Crear el espacio BOT a través de la API cuando ningún título de espacio coincide (una operación de escritura en la cuenta); un TITLE explícito impulsa tanto la coincidencia como la creación, de lo contrario el título proviene de `--bot-title`; sin esta bandera `[bot_space]` se escribe vacío | desactivado |
| `--bot-title TITLE` | Título del espacio utilizado tanto para coincidir con un espacio existente como para nombrar uno creado | `BOT` |
| *(se aplican opciones comunes)* | Las banderas de fuente de cookies eligen dónde se descubren las cuentas; solo para `init`, `--config` es la ruta de **escritura** (la carga de configuración estricta se omite) | |

Comportamientos clave:

- Enumeración de tokens: las cookies de sesión por cuenta (`__Secure-pplx.session.<uid>`) se recopilan de los almacenes del navegador — o, con `--cookies FILE`, se escanean desde el archivo de cookies (una exportación completa puede contener varias cuentas). Sin tokens enumerables, solo se sondea la sesión activa actual.
- Sonda de sesión: cada token se prueba contra `GET /api/auth/session` para conocer el correo electrónico / nombre para mostrar de la cuenta; los tokens que fallan o no devuelven un correo electrónico se omiten con una advertencia.
- Ensamblaje del registro: cada clave de cuenta se deriva de la parte local del correo electrónico (las colisiones obtienen sufijos `-2`/`-3`…); `default_account` se establece en la cuenta actualmente activa, de lo contrario en la primera descubierta.
- Espacio BOT: se busca un espacio por título exacto (sin distinción de mayúsculas/minúsculas) a través de `list_user_collections`; cuando no hay coincidencia, `--create-bot-space [TITLE]` lo crea en el acto (un TITLE explícito anula `--bot-title` tanto para la coincidencia como para la creación), de lo contrario `[bot_space]` se deja vacío.
- El TOML se escribe atómicamente (archivo temporal + renombrar) con permisos 0600, y un archivo existente nunca se sobrescribe sin `--force`. El comando termina con una línea JSON de resumen: ruta de configuración, claves de cuenta, cuenta predeterminada, uuid/slug del espacio BOT.
- Siembra de modelos (mejor esfuerzo): después de escribir la configuración, `init` obtiene `models/config/v2` y siembra la tabla `[models]` administrada por la máquina para que una configuración nueva ya tenga los valores predeterminados/catálogo de modelos actuales; en caso de fallo, se omite con una advertencia (actualizar más tarde con `pplx-ask models --refresh`). Consulte [Configuration](configuration.md).
- `--transport webbridge` es rechazado — el canal de contexto de página no puede enumerar tokens por cuenta.

```bash
pplx-export init                          # write the default ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --config /path/to/config.toml --force   # custom path, overwrite allowed
```

## index

Actualizar el índice de la lista de conversaciones de la cuenta `index/library_<account>.json` — la línea base contra la que todos los demás comandos comparan.

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| `--full` | Paginar toda la biblioteca y reescribir el índice; restablece el contador incremental | incremental |

Comportamientos clave:

- **Incremental por defecto.** Pagina primero las más recientes y se detiene una vez que una página completa (`_STOP_RUN`) de filas consecutivas ya es conocida y sin cambios, luego fusiona el encabezado obtenido con el índice existente — las filas más antiguas se transfieren textualmente (sin pérdida). La primera ejecución, o cualquier ejecución sin índice existente, es un barrido completo.
- **`--full`** pagina todo y reescribe el índice; úselo como interfaz de reconciliación periódica.
- **Punto ciego de la ruta incremental:** las *eliminaciones* y *cambios de espacio* remotos de hilos antiguos nunca aparecen en el encabezado obtenido, por lo que no se observan. La autoridad de eliminación permanece con `sync-deleted --online`. El documento de índice rastrea `incremental_runs_since_full`; después de suficientes ejecuciones incrementales, le advierte que ejecute `--full` (y `sync-deleted --online`).
- Preserva el enriquecimiento `search_mode` escrito por `search-mode-backfill`, fusionado de nuevo por `entryUUID`.
- Ejecútelo antes de `batch`, `sync-space` y `sync-deleted` — sus diferencias son tan recientes como este índice.

```bash
pplx-export index --account alice          # incremental refresh
pplx-export index --account alice --full   # full sweep + reconciliation front-end
```

## sync

Entrada de conveniencia de alta frecuencia: **`index` incremental + `batch` incremental**, centrado solo en conversaciones.

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| `--full` | Reconciliación completa: barrido completo de `index` + `batch` (y ejecuta los pasos de eliminación/espacio a continuación) | desactivado |
| `--check-deleted` | También ejecutar `sync-deleted --online` para verificar y marcar hilos eliminados remotamente | desactivado |
| `--refresh-spaces` | También reconstruir `spaces --fetch-meta` y ejecutar `sync-space` | desactivado |
| `--limit N` / `--mode X` / `--delay-min` / `--delay-max` | Se pasan a la fase `batch` | — |

Comportamientos clave:

- La ejecución predeterminada obtiene solo conversaciones nuevas/actualizadas y **omite la detección de eliminación y la actualización de espacio** — la forma más económica para sincronizaciones frecuentes.
- La reconciliación de eliminación/espacio es optativa (`--check-deleted` / `--refresh-spaces`) o agrupada por `--full`. El contador `index` (`incremental_runs_since_full`) es el respaldo: le recuerda cuándo una reconciliación `--full` está vencida.

```bash
pplx-export sync --account alice                     # conversations only (fast)
pplx-export sync --account alice --full              # periodic full reconciliation
pplx-export sync --account alice --check-deleted     # also mark remote deletions
```

## space-index

Extraer la lista de conversaciones "Todo" de un espacio — incluidos los hilos compartidos por otros miembros — en `index/space_<slug>.json`.

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| `SPACE_URL` (posicional) | URL de la página del espacio | requerido |
| `--transport webbridge` | Usar la ruta heredada de renderizado del navegador en lugar de REST | `cookie` (REST directo) |

Comportamientos clave:

- La ruta predeterminada es REST directo: `list_collection_threads` sobre el transporte de cookies con paginación por desplazamiento; las filas incluyen `context_uuid` y `answer_preview`.
- Con `--transport webbridge` recurre a desplazar la página del espacio renderizada y extraer las propiedades de las filas — un respaldo en caso de que la estructura REST cambie.
- Las filas se escriben primero las más recientes mediante `lastUpdated`.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

Exportar un solo hilo (URL o UUID simple) a su directorio de archivo `<out>/<account-folder>/<mode>/<thread-dir>/`.

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| `THREAD` (posicional) | URL del hilo o UUID | requerido |
| `--force` | Reexportar incluso cuando `lastUpdated` no ha cambiado | desactivado |

Comportamientos clave:

- Si la copia archivada ya está actualizada, la exportación se omite sin escrituras; `--force` anula la verificación.
- `lastUpdated` se toma del índice de la biblioteca local cuando el hilo está listado allí (misma semántica y formato que `batch`), recurriendo al valor de la plataforma en caso contrario.
- Los estados terminales se registran correctamente, sin un traceback: `ENTRY_DELETED` marca `deleted` en `batch_state.json`, `ENTRY_EXPIRED` marca `expired` — el archivo local existente se mantiene intacto en cualquier caso.
- Una exportación exitosa escribe `ok` en `index/batch_state.json`, por lo que el plan incremental cuenta el hilo como "exportado y sin cambios".
- Qué se almacena en el directorio del hilo: [archive-layout.md](archive-layout.md); el propio pipeline de exportación: [../architecture/export-pipeline.md](../architecture/export-pipeline.md).

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

Exportar en masa los hilos de una cuenta — el controlador diario, con parada temprana incremental y puntos de control reanudables.

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| `--force` | Reexportar todos los hilos (estados terminales excluidos) | desactivado |
| `--full` | Escaneo completo: los hilos sin cambios aún se omiten, pero sin parada temprana | desactivado |
| `--limit N` | Procesar solo las primeras N filas de la lista (más recientes primero) | todas |
| `--mode MODE` | Exportar solo hilos `search` / `deep-research` / `computer` / `council` / `study` | todos los modos |
| `--delay-min SEC` | Límite inferior del intervalo aleatorio entre hilos | `10` |
| `--delay-max SEC` | Límite superior del intervalo aleatorio entre hilos | `20` |

Comportamientos clave:

- Requiere `index/library_<account>.json` — ejecute `index` primero.
- **Parada temprana incremental** predeterminada: la lista se ordena primero las más recientes y la ejecución final de hilos "exportados y sin cambios" se recorta por completo; los huecos dejados por ejecuciones interrumpidas (error/nunca exportados) se encuentran por encima de ese sufijo y aún se reparan. `--full` deshabilita la parada temprana (respaldo periódico, o cuando se sospechan huecos en el archivo); `--force` reexporta todo excepto los estados terminales, que nunca se reintentan. Semántica completa: [incremental-sync.md](incremental-sync.md).
- Filtrado `--mode`: las filas que llevan `search_mode` (el campo autoritativo de la plataforma enriquecido por `search-mode-backfill`) coinciden exactamente a través de `SEARCH_MODE_MAP` — en esa ruta `--mode search` ya no incluye hilos de deep-research/council/study. Las filas sin `search_mode` recurren a heurísticas del índice: `computer` = modo `COMPUTER`; `deep-research` = displayModel `pplx_alpha`; `council` = `pplx_agentic_research`; `study` = `pplx_study`; `search` = las filas restantes de modo-`SEARCH` (incluyendo esos tres tipos — fíltrelos con precisión exportando los modos específicos por separado).
- El estado se guarda en `index/batch_state.json` después de cada hilo — interrumpa y vuelva a ejecutar libremente.
- Falla rápida de autenticación: 3 respuestas 401/403 consecutivas abortan la ejecución (una cookie caducada no puede autocorregirse, y seguir girando fallaría cientos de hilos uno por uno).
- Ritmo: una pausa aleatoria de `--delay-min`–`--delay-max` entre hilos; 429/5xx se retroceden por la capa de transporte. Detalles: [rate-limiting.md](rate-limiting.md).
- Los hilos que alcanzan variantes de respuesta reescritas se registran en `index/answer_variants_log.jsonl` con una advertencia para manejarlos manualmente lo antes posible (consulte [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md)).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

Reconstruir el índice de vista de espacios — una página Markdown por espacio más un registro `spaces.json` — a partir de los índices de la biblioteca local.

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| `--fetch-meta` | Actualizar metadatos de propietario/miembro antes de reconstruir | desactivado |

Comportamientos clave:

- Sin `--fetch-meta` el comando es puramente local (cero red): agrega hilos por slug de espacio en todos los archivos `library_*.json`, con estadísticas de cuentas participantes y enlaces de retroceso a los directorios de hilos exportados.
- La salida va a `./spaces/` relativo al directorio de trabajo actual — ejecútelo desde el directorio que contiene `web_archive/` para que los enlaces de retroceso en las páginas de espacio se resuelvan.
- `--fetch-meta` primero actualiza la caché de propietario/miembro de cada espacio a través de `get_collection` (1 solicitud por espacio, intervalo de 3s) en `index/space_meta.json`; cuando la cuenta actual no puede ver un espacio, se reintenta automáticamente una cuenta que pueda (las cookies cambian por sí solas).

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

Sincronizar el campo `space` de los archivos `thread.json` ya archivados con el índice actual — puramente local, cero red.

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| *(solo opciones comunes; solo `--out` importa)* | | |

Comportamientos clave:

- Requisito previo: ejecute `index` primero — el `library_*.json` actualizado es la fuente de verdad para la propiedad actual del espacio.
- Compara slugs de espacio por hilo y parchea `thread.json` en su lugar en caso de divergencia; los primeros 30 cambios se registran.
- Después de cualquier cambio, el índice `spaces/` se reconstruye automáticamente junto con él.

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

Calcular el plan de exportación incremental de esta ronda y escribir un fragmento cron que el cron del sistema pueda llamar directamente.

| Bandeja | Significado | Valor predeterminado |
|---|---|---|
| *(solo opciones comunes)* | | |

Comportamientos clave:

- Obtiene un índice en vivo e informa el plan como conteos total/nuevo/actualizado, usando la misma función pura de parada temprana (`plan_incremental`) que `batch` — consulte [incremental-sync.md](incremental-sync.md).
- Escribe `<out>/index/cron_snippet.txt` que contiene una línea `17 3 * * *` de la forma `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'` — las rutas son absolutas y están entre comillas porque el cwd y PATH de cron son impredecibles. La ruta del ejecutable se resuelve a través de `shutil.which`; cuando eso falla, el fragmento recurre al nombre simple `pplx-export`.
- Las ejecuciones programadas son solo incrementales por diseño; ejecute `batch --full` manualmente como respaldo periódico.

```bash
pplx-export schedule --account alice
```
