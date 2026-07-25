---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/archive-layout.md"
translation_source_sha256: "6302a47c60b6c8703d36f420cee6c18017110fcbb6127926eedb5c77e3e1f8e2"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="archive-layout" data-pplx-source-anchor="true"></a>
# Diseño del archivo

Todo lo que `pplx-export` descarga termina en un único árbol de salida — `./web_archive/` por defecto
(anular con `--out`). Esta página es una guía de lectura de ese árbol: qué es cada directorio y archivo,
qué claves lleva `thread.json` y cómo la herramienta mantiene un directorio por hilo cuando una
conversación continúa a lo largo de varios días. Todo es generado por la herramienta; la profundidad del mecanismo reside en
[Modelo de datos y contrato de directorio](../architecture/data-model.md) y
[Pipeline de exportación](../architecture/export-pipeline.md).

<a id="the-output-tree" data-pplx-source-anchor="true"></a>
## El árbol de salida

```
web_archive/
├── alice/                                # one folder per account (author display name)
│   ├── search/                           # mode: search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # one directory per thread
│   │       ├── thread.json               # metadata + optional registries
│   │       ├── conversation.md           # compact read: per-turn Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # full read: complete work-process detail
│   │       │   └── ...
│   │       ├── sources.json              # thread-wide citations (deduped by url)
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research report (only when one exists)
│   │       ├── raw_entries.json          # plain API response, verbatim (always present)
│   │       ├── raw_blocks.json           # schematized API response (absent for search)
│   │       └── assets/
│   │           ├── assets_manifest.json  # versioned manifest
│   │           └── files/                # downloaded asset bodies
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # state files and indexes (see below)
├── relations/                            # edges.jsonl + graph.md (rebuilt by `pplx-export relations`)
├── crosscheck/                           # cross-validation reports (manual/review artifacts)
└── bob/ ...
```

<a id="the-thread-directory" data-pplx-source-anchor="true"></a>
## El directorio del hilo

Cada hilo recibe exactamente un directorio, calculado por `thread_dir_for` (`fs_writer.py:58-72`):

```
<account display name>/<mode>/<YYYY-MM-DD>_<title-slug>_<uuid8>/
```

| Componente | Fuente | Notas |
|---|---|---|
| `<account display name>` | autor del hilo, mediante `author_folder` → `_safe_folder` (`fs_writer.py:40-51`) | los separadores de ruta y caracteres ilegales en Windows (`:*?"<>\|`) se convierten en `_`; `.`/`..` rechazados (protección de recorrido de ruta para espacios compartidos); todo lo demás — incluidos espacios — se conserva |
| `<mode>` | `detect_mode` | uno de los cinco modos; consulte [Modos de conversación](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` `lastUpdated` prefijo de fecha | la fecha de última actualización de la plataforma, **no** la fecha de exportación — se mueve cuando se actualiza un hilo continuado (ver migración abajo) |
| `<title-slug>` | `slugify(title)` (`normalize.py:261-263`) | máximo 40 caracteres, caracteres no alfabéticos → `-`, vacío → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | primeros 8 caracteres del UUID del hilo — el ancla de identidad del directorio |

<a id="files-in-a-thread-directory" data-pplx-source-anchor="true"></a>
## Archivos en un directorio de hilo

<a id="threadjson-metadata-and-registries" data-pplx-source-anchor="true"></a>
### thread.json — metadatos y registros

Escrito por `write_thread` (`fs_writer.py:224-253`). Claves siempre presentes:

| Clave | Contenido |
|---|---|
| `web_uuid` | entryUUID web — el UUID en la URL del hilo; la identidad del hilo |
| `psc_uuid` | `context_uuid` de la plataforma (nullable; del primer turno no vacío) — el ID dual usado por los índices de espacio |
| `url` | URL canónica del hilo |
| `title` | título del hilo |
| `mode` | modo detectado (`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | nombre para mostrar de la cuenta del autor |
| `export_via` | nombre de usuario de la cuenta que realizó la exportación — importante para hilos de espacio compartido exportados a través de otra cuenta |
| `space` | `{"uuid", "title", "slug"}` o `null` |
| `lastUpdated` | marca de tiempo de última actualización de la plataforma (contrato de comparación automática para sincronización incremental) |
| `threadAccess` | indicador de acceso de la plataforma |
| `n_turns` | recuento de turnos |
| `n_sources` | recuento de citas a nivel de hilo |
| `metadata` | `thread_metadata` de la respuesta de la API, textual |
| `report_info` | `{"title", "file_name", "url"}` o `null` |
| `exported_at` | hora de exportación (UTC ISO 8601) |

Claves opcionales — ausentes cuando no hay nada que registrar:

| Clave | Añadida cuando | Contenido |
|---|---|---|
| `interruptions` | cualquier flujo de trabajo no completado (`fs_writer.py:242-244`) | lista de `{location, kind, headline, status}`; consulte [Modos de conversación — Interrupciones](modes.md#interruptions-non-completed-workflows) |
| `answer_variants` | se detecta una variante de reescritura de respuesta (`fs_writer.py:247-252`) | `side_by_side_metadata` reducido que localiza campos; consulte [Modos de conversación — Variantes de reescritura de respuesta](modes.md#answer-rewrite-variants-answer_variants) |
| `remote_deleted` | `pplx-export sync-deleted --online` confirma eliminación remota | marca de tiempo de tumba, escrita en el lugar, idempotente (el valor existente nunca se sobrescribe; `sync_deleted_cmd.py:215-244`) — el archivo local en sí se conserva |

<a id="conversationmd-the-compact-read" data-pplx-source-anchor="true"></a>
### conversation.md — la lectura compacta

`render_conversation` (`render.py:641`): encabezado de título (modo / autor / turnos / recuento de citas),
luego por turno un par `### Query` + `### Answer` con respuestas completas y, cuando está presente, el
apéndice de tareas en segundo plano a nivel de hilo al final. Este es el archivo que se debe abrir primero; los procesos
de trabajo por turno están en `turns/`.

<a id="turnsturn_nnnnmd-the-full-read" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md — la lectura completa

`render_turn` (`render.py:596`): un archivo por turno (`turn_0001.md` …), cada uno con el proceso de trabajo
completo — pasos, llamadas a herramientas, ejecuciones de subagentes, tablas, citas por turno. Cuando el recuento de turnos
de un hilo se reduce, los archivos `turn_*.md` obsoletos de números altos se eliminan, pero los archivos no tocados
conservan su mtime (`fs_writer.py:287-301`).

### sources.json / sources.md

Citas a nivel de hilo, deduplicadas por URL (`fs_writer.py:270-278`). `sources.json` es
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`; `sources.md` es la misma
lista como una lista de enlaces Markdown numerada.

### report.md

El producto del informe de investigación profunda, escrito solo cuando el hilo lleva uno
(`fs_writer.py:308-316`): título del informe, el nombre de archivo del producto original, luego el informe completo
en Markdown.

<a id="raw_entriesjson-raw_blocksjson-raw-fidelity" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json — fidelidad sin procesar

Las respuestas de la API, conservadas textualmente **antes** de cualquier análisis (`fs_writer.py:257-266`):

- `raw_entries.json` — la respuesta simple: `{"thread_metadata", "entries", "background_entries"}`.
  Siempre presente.
- `raw_blocks.json` — la respuesta esquematizada, misma forma. Ausente para hilos `search`
  (sin recuperación de bloques); recuperada para los otros cuatro modos, y también como alternativa cuando cada
  señal de detección de modo falta.

Estos dos archivos son el ancla de fidelidad del archivo: el análisis, la representación y los registros pueden
reconstruirse a partir de ellos sin conexión, con cero red. Consulte
[Operaciones sin conexión](../architecture/offline-operations.md).

<a id="assets-products-and-their-manifest" data-pplx-source-anchor="true"></a>
### assets/ — productos y su manifiesto

Los productos descargables (archivos de modo Computer y cualquier otro activo que la API enumere) se obtienen
de URL firmadas de CloudFront en `assets/files/`; la extensión se decide en el momento de la descarga
a partir de la ruta URL, bytes mágicos de contenido o tipo de activo. `assets/assets_manifest.json`
(`fs_writer.py:320-330`) registra cada versión:

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` es siempre el **número total de versiones** (Σ `len(versions)`), no el número de grupos de archivos
— use `len(files)` para eso.

<a id="the-index-layer" data-pplx-source-anchor="true"></a>
## La capa index/

`web_archive/index/` contiene el estado administrado por la herramienta e índices — no editar manualmente:

| Archivo | Escrito por | Semántica |
|---|---|---|
| `library_<account>.json` | `pplx-export index` (`index_cmd.py:17-43`) | índice completo de hilos de la cuenta (GraphQL); entrada para lotes / programación / índices de espacio |
| `batch_state.json` | `BatchState` (`state.py`) | punto de control reanudable: uuid → estado (ok/error/expired/deleted) + lastUpdated; escrituras atómicas; archivos corruptos respaldados automáticamente como `.corrupt-<ts>` |
| `.cookies.json` | caché de cookies (`common.py:111`, `common.py:150`) | caché de cookies con frescura de 12h con fuente y correo electrónico de la cuenta; escrito `0o600` luego reemplazado atómicamente (credenciales de sesión, solo legible por el propietario) |
| `space_<slug>.json` | `pplx-export space-index` (`spaces_cmd.py:106-167`) | lista de hilos por espacio, incluyendo la asignación de ID dual `context_uuid` |
| `space_meta.json` | `pplx-export spaces --fetch-meta` (`spaces_cmd.py:299-330`) | caché de propietario/miembro del espacio reutilizado en reconstrucciones |
| `credit_usage_<account>.json` | `pplx-export usage-backfill` (`usage_backfill_cmd.py:17`) | uso de crédito por hilo (idempotente, reanudable, vaciado cada 25 entradas) |
| `cron_snippet.txt` | `pplx-export schedule` (`scheduler.py:48-78`) | fragmento de invocación cron (rutas absolutas) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (`variant_log.py:76`) | registro central de variantes de reescritura de respuesta, deduplicado por (hilo, entrada), idempotente |
| `logs/` | `--log-file` (`common.py:218-229`) | registros DEBUG completos |

<a id="the-spaces-layer" data-pplx-source-anchor="true"></a>
## La capa spaces/

`pplx-export spaces` agrega `index/library_*.json` en un índice de espacio (`spaces_cmd.py:259-389`):
un `<slug>.md` por espacio (cuentas participantes, encabezado de propietario/miembro, tabla de hilos,
backlinks de ubicación de exportación) más un registro `spaces.json`.

!!! nota "Ubicación de salida"
    `spaces/` se escribe en relación con el directorio de trabajo actual (`spaces_cmd.py:332`) — no
    sigue a `--out`. No editar manualmente: la próxima reconstrucción lo sobrescribe.

<a id="cross-day-continuation-directory-migration-by-uuid-identity" data-pplx-source-anchor="true"></a>
## Continuación entre días: migración de directorio por identidad UUID

El nombre del directorio incorpora la fecha `lastUpdated`, por lo que cuando continúa un hilo en un día posterior,
el cálculo ingenuo produce un directorio *nuevo*. El escritor evita duplicados por identidad UUID
(`thread_dir_for`, `fs_writer.py:58-72`):

1. **Buscar**: `find_thread_dirs` (`fs_writer.py:74-105`) busca en todo el archivo
   directorios que terminan en `_<uuid8>` — entre cuentas y modos. Un candidato se acepta solo
   si su `thread.json` existe, se analiza y su `web_uuid` coincide exactamente; los directorios faltantes, corruptos o
   no coincidentes nunca se tocan (es mejor omitir una migración que fusionar incorrectamente).
2. **Fusionar**: `_merge_into` (`fs_writer.py:107-178`) fusiona el directorio antiguo en el nuevo —
   unión de archivos (nada único del directorio antiguo se pierde); mismo nombre + mismo contenido → omitir;
   conflictos de mismo nombre **siempre mantienen el lado de destino** (el semánticamente más nuevo), con cada
   conflicto registrado. Cada archivo copiado se verifica con sha256 antes de eliminar el directorio antiguo; cualquier
   fallo deja el directorio antiguo intacto y los reintentos son idempotentes.
3. **Limpiar duplicados históricos**: `consolidate_uuid` (`fs_writer.py:180-209`) fusiona
   directorios de fecha duplicados de un UUID en todo el archivo, manteniendo el que tiene el máximo
   `lastUpdated` — la red de seguridad para duplicados dejados por versiones anteriores.

La misma estrictez de UUID protege los backlinks del índice de espacio: los directorios candidatos con un
`thread.json` faltante/corrupto/no coincidente nunca se vinculan.

<a id="hand-editable-vs-tool-managed" data-pplx-source-anchor="true"></a>
## Editable manualmente vs. administrado por la herramienta

- **Administrado por la herramienta (no editar manualmente)**: todo dentro de los directorios de hilo, más `index/`,
  `spaces/` y `relations/`. Si el contenido es incorrecto, corrija la herramienta y regenere — las correcciones
  de representación pasan por `pplx-export re-render`, las correcciones de datos a través del comando de relleno correspondiente
  (consulte [Comandos de mantenimiento](maintenance-commands.md)) — para que cada artefacto siga siendo reproducible
  a partir de los datos sin procesar.
- **Editable manualmente**: la documentación y los informes de revisión `web_archive/crosscheck/`.
  Una excepción a nivel de usuario: una respuesta alternativa rescatada manualmente puede registrarse como
  `rewritten_answer_variant.md` dentro del directorio del hilo — consulte
  [Modos de conversación — Variantes de reescritura de respuesta](modes.md#answer-rewrite-variants-answer_variants).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Véase también

- [Modos de conversación](modes.md) — los cinco modos y lo que produce cada uno
- [Sincronización incremental](incremental-sync.md) — cómo `lastUpdated` impulsa las reexportaciones
- [Comandos de mantenimiento](maintenance-commands.md) — rerenderizado, rellenos, sincronización de eliminados
- [Modelo de datos y contrato de directorio](../architecture/data-model.md) — las dataclasses subyacentes
- [Pipeline de exportación](../architecture/export-pipeline.md) — cómo se escriben estos archivos
- [Operaciones sin conexión](../architecture/offline-operations.md) — reconstruir todo desde `raw_*.json`
