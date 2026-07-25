---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/incremental-sync.md"
translation_source_sha256: "35868edfb3e8e914afd9afa1b00370bffb9f8a50ca374691229f41d51ffa9b64"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="incremental-sync" data-pplx-source-anchor="true"></a>
# Sincronización incremental

`pplx-export batch` está diseñado para ejecutarse con frecuencia: cada ejecución exporta solo lo que es nuevo o ha cambiado, sana las brechas dejadas por ejecuciones interrumpidas y nunca retoca hilos que la plataforma ya ha retirado. La única fuente de verdad sobre "lo que se ha exportado" es `index/batch_state.json` (`BatchState`, `pplx_export/core/state.py:63`), actualizado después de cada hilo — no existe una copia sombra separada.

<a id="prerequisites-and-basic-usage" data-pplx-source-anchor="true"></a>
## Requisitos previos y uso básico

```bash
pplx-export index --account alice   # refresh index/library_alice.json first
pplx-export batch --account alice   # incremental export (early stop, resumable)
```

`batch` se niega a ejecutarse sin el índice (`pplx_export/commands/batch_cmd.py:79-81`). `--limit N` y `--mode <mode>` filtran las filas del índice antes de planificar; las filas que carecen de `entryUUID` se omiten con una advertencia en lugar de bloquear la ejecución (`batch_cmd.py:95-100`).

<a id="how-the-incremental-plan-works" data-pplx-source-anchor="true"></a>
## Cómo funciona el plan incremental

1. **Ordenar.** Las filas del índice se ordenan por `lastUpdated`, las más recientes primero (`batch_cmd.py:89`). Las conversaciones nuevas y las reanudadas (cuyo `lastUpdated` las movió hacia arriba) están ambas en la parte superior — este orden es lo que hace seguro detenerse temprano.
2. **Clasificar.** `plan_incremental` (`pplx_export/hooks/incremental.py:36-87`) — una función pura compartida por `batch` y `schedule` — asigna a cada fila exactamente una acción:

   | acción | condición | qué hace el lote |
   |---|---|---|
   | `new` | uuid nunca visto en `batch_state` | exportar |
   | `updated` | `lastUpdated` difiere del valor registrado, o `--force` | reexportar |
   | `done` | estado `ok` y `lastUpdated` sin cambios | omitir |
   | `expired` | la plataforma devolvió `ENTRY_EXPIRED` en un intento anterior | omitir — terminal, nunca reintentar |
   | `deleted` | `sync-deleted` confirmó una eliminación remota | omitir — terminal, nunca reintentar |

3. **Detención temprana.** Por defecto (ni `--full` ni `--force`), la ejecución más larga de entradas terminales (`done` / `expired` / `deleted`) se recorta por completo y se cuenta como `n_stopped` (`incremental.py:83-87`). Debido a que la lista está ordenada de más reciente a más antigua, todo lo que está debajo de una entrada sin cambios es necesariamente más antiguo y también sin cambios — escanear más allá solo consumiría tiempo.

   ```mermaid
   flowchart TD
       IDX["library index rows<br/>sorted by lastUpdated, newest first"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → export"]
       PLAN --> UPD["updated → re-export"]
       PLAN --> DONE["done → skip"]
       PLAN --> TERM["expired / deleted → skip (terminal)"]
       DONE --> STOP["early stop:<br/>trailing terminal run trimmed"]
       TERM --> STOP
   ```

4. **Ejecutar.** Cada hilo exportado se marca inmediatamente (`mark_ok` / `mark_error` / `mark_expired` / `mark_deleted`) y el archivo de estado se guarda después de cada elemento (`batch_cmd.py:154-201`); un `KeyboardInterrupt` también guarda antes de propagar (`batch_cmd.py:158-161`). Las escrituras son atómicas — archivo temporal más `os.replace` (`state.py:145-152`) — por lo que una ejecución interrumpida nunca deja JSON truncado.

<a id="gap-healing-after-interrupted-runs" data-pplx-source-anchor="true"></a>
## Curación de brechas después de ejecuciones interrumpidas

La detención temprana nunca entierra una brecha. Los hilos que fallaron (estado `error`) o nunca se alcanzaron están **por encima** del sufijo terminal, por lo que la siguiente ejecución los replanifica como `updated` / `new` y los exporta antes de alcanzar el punto de detención temprana (`incremental.py:12-14`, `batch_cmd.py:206-208`). Combinado con guardados de estado por elemento, una ejecución por lotes puede interrumpirse en cualquier punto y simplemente reejecutarse.

Si `batch_state.json` en sí está corrupto, no se vacía en silencio: el original se renombra a `batch_state.json.corrupt-<timestamp>` para que los estados terminales registrados no se pierdan y se reintenten innecesariamente (`state.py:68-81`).

<a id="-full-and-force" data-pplx-source-anchor="true"></a>
## `--full` y `--force`

| indicador | efecto | estados terminales | cuándo usarlo |
|---|---|---|---|
| *(predeterminado)* | detención temprana sobre la ejecución terminal final | omitidos | cada ejecución regular / programada |
| `--full` | escaneo completo, sin detención temprana; los hilos sin cambios aún se omiten como `done` | omitidos | respaldo periódico, o cuando se sospechan brechas en el archivo |
| `--force` | reexportar todo, incluso hilos sin cambios | aún excluidos — nunca reintentados | después de correcciones en la tubería que deben volver a obtener datos sin procesar |

Los estados terminales se excluyen de `--force` por diseño: reintentar un hilo expirado o eliminado remotamente solo desperdicia solicitudes y presupuesto de retroceso (`batch_cmd.py:120-127`).

Véase también [`status`](maintenance-commands.md#status): un informe sin red del estado de la cuenta y el plan de cambios calculado con la misma semántica de `plan_incremental` (`new`/`updated`/recuento de detención temprana).

La comparación de `lastUpdated` normaliza los ceros finales en la parte de segundos fraccionarios (`.18033Z` es igual a `.180330Z`; `state.py:23-55`), porque la plataforma ocasionalmente los elimina — una comparación exacta de cadenas juzgaría erróneamente "cambiado" y causaría exportaciones duplicadas.

<a id="terminal-states-expired-and-deleted" data-pplx-source-anchor="true"></a>
## Estados terminales: `expired` y `deleted`

| | `expired` | `deleted` |
|---|---|---|
| significado | la plataforma eliminó el hilo (~ventana de retención de 3 meses); el intento de exportación devolvió `ENTRY_EXPIRED` | eliminación por usuario/remota, confirmada por `sync-deleted` |
| registrado por | `batch` mismo (`mark_expired`, `state.py:131-134`) | `pplx-export sync-deleted --online` (`mark_deleted`, `state.py:136-143`) |
| ¿reintentado? | nunca — ni siquiera con `--force` | nunca — ni siquiera con `--force` |
| evidencia | la respuesta de `ENTRY_EXPIRED` | campo `note`: ausencia en el índice + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted-confirming-remote-deletions" data-pplx-source-anchor="true"></a>
### sync-deleted: confirmando eliminaciones remotas

```bash
pplx-export sync-deleted --account alice            # offline dry-run: list candidates only
pplx-export sync-deleted --account alice --online   # confirm each candidate online
```

1. **Candidatos (sin conexión, cero red).** Cualquier hilo con estado `ok` en `batch_state` que falte en la unión `entryUUID` de **todos** los índices de cuenta de `index/library_*.json` es un candidato sospechoso de eliminación remota (`pplx_export/commands/sync_deleted_cmd.py:148-212`). La unión entre cuentas es necesaria: un hilo propiedad de `bob` pero exportado por `alice` a través de un espacio compartido nunca aparece en el índice propio de `alice` — una diferencia de una sola cuenta daría un falso positivo para todo ese conjunto. Cuando no existe ningún índice utilizable, cada candidato se omite de forma segura con la razón registrada.
2. **Simulación por defecto.** Sin `--online`, el comando solo lista candidatos — sin red, sin cambios de archivos.
3. **Confirmación `--online`.** Cada candidato se verifica con `GET /rest/thread/<uuid>`, utilizando la cuenta `export_via` del candidato desde `thread.json` (la cookie cambia automáticamente):

   | resultado | consecuencia |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | confirmado: `batch_state` marca terminal `deleted` (`note` registra la razón), y cada `thread.json` de ese hilo recibe una marca de tiempo `remote_deleted` en su lugar |
   | el hilo aún existe | falso positivo: se informa tal cual (el índice puede no estar completamente actualizado — reejecutar `index` y verificar de nuevo), nada cambió |
   | 5xx / error de red | sin cambio de estado; el candidato se deja para la siguiente ronda |
   | 3 401/403 consecutivos | aborto rápido — una cookie caducada no puede sanarse sola, y continuar marcaría erróneamente hilos activos (`sync_deleted_cmd.py:333-337`) |

   Las marcas confirmadas se persisten por elemento, por lo que una ejecución interrumpida de `--online` no pierde nada y las reejecuciones son idempotentes (`sync_deleted_cmd.py:254-256`).

<a id="the-tombstone-principle" data-pplx-source-anchor="true"></a>
## El principio de la lápida

!!! warning "Los archivos locales nunca se eliminan"
    Este archivo es la copia de seguridad de referencia de las conversaciones exportadas.
    `sync-deleted` solo *identifica y marca* (lápida): **nunca elimina ni mueve ningún archivo de archivo**. La confirmación cambia exactamente dos cosas — el estado de `batch_state` y una clave de marcador en `thread.json`:

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    El sello es idempotente: una clave `remote_deleted` existente no se reescribe ni sobrescribe (`sync_deleted_cmd.py:215-244`).

<a id="idempotence-and-offline-re-render" data-pplx-source-anchor="true"></a>
## Idempotencia y renderizado sin conexión

- Reejecutar `batch` contra un índice sin cambios no exporta nada: cada fila se clasifica como `done` y la ejecución se detiene en el punto de detención temprana. Las escrituras de estado son atómicas, las marcas son por hilo, y las eliminaciones reconfirmadas nunca duplican el sello `remote_deleted`.
- El archivo conserva las cargas útiles de la API sin procesar (`raw_entries.json` / `raw_blocks.json`), por lo que los archivos renderizados se pueden regenerar en cualquier momento sin acceso a la red:

  ```bash
  pplx-export re-render                 # rebuild conversation.md + turns/ everywhere
  pplx-export re-render --dry-run       # only list the thread directories
  pplx-export re-render --thread-json   # also sync interruptions / answer_variants keys
  ```

  `re-render` vuelve a analizar el JSON sin procesar con el renderizador actual (`pplx_export/commands/rerender_cmd.py:105-190`): `conversation.md` y `turns/turn_*.md` se reescriben, los archivos de turno obsoletos numerados por encima del recuento de turnos actual se eliminan, y las fuentes, activos, `report.md` y `thread.json` se dejan intactos. Así es como las correcciones del renderizador se implementan en todo el archivo sin una sola solicitud.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Véase también

- [pplx-export.md](pplx-export.md) — referencia completa del comando `batch` (`--mode`, `--limit`, retrasos)
- [maintenance-commands.md](maintenance-commands.md) — `sync-deleted`, `re-render` y los comandos de relleno
- [archive-layout.md](archive-layout.md) — dónde residen `batch_state.json` y `thread.json`
- [rate-limiting.md](rate-limiting.md) — ritmo entre hilos, retroceso, fallo rápido de autenticación
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) — la tubería de exportación completa
- [../architecture/offline-operations.md](../architecture/offline-operations.md) — la tubería de reconstrucción sin conexión en profundidad
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — taxonomía de errores y manejo de estados terminales
