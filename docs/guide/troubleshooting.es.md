---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/troubleshooting.md"
translation_source_sha256: "97f7bccfca0aa4546418bd68903cbd5b905aa5658d496da6ea06413b246bfd88"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="troubleshooting" data-pplx-source-anchor="true"></a>
# Solución de problemas

Formato de preguntas frecuentes: cada entrada es **problema → causa → solución**. Para la referencia completa de semántica de errores (códigos de estado, estados terminales, disciplina de reintentos), consulte [Respuestas y errores](../reference/api/api-responses-errors.md) y [Límite de velocidad y errores](../architecture/rate-limiting-errors.md).

<a id="bare-requests-to-the-api-get-a-cloudflare-403" data-pplx-source-anchor="true"></a>
## Solicitudes directas a la API obtienen un 403 de Cloudflare

**Problema**: un `curl` / script hecho a mano contra los endpoints REST de `www.perplexity.ai` devuelve 403 con una página de desafío de Cloudflare, incluso con cookies copiadas del navegador, mientras que los mismos endpoints funcionan a través de la herramienta.

**Causa**: Cloudflare está frente al sitio, y `cf_clearance` / `__cf_bm` están vinculados a la huella digital TLS del navegador. La huella digital de un cliente simple no coincide, por lo que se activa el desafío. La herramienta funciona porque usa Python `urllib` con cookies importadas del navegador y un `User-Agent` de Chrome de escritorio (`pplx_export/core/http/cookie_transport.py:29`). Cloudflare también puede devolver 403 bajo control de velocidad; en ese caso, la respuesta tiene la misma forma de desafío.

**Solución**:

- No evite el transporte de la herramienta; ejecute su llamada a través de `pplx-export` / `pplx-ask` en lugar de scripts ad-hoc.
- Dentro de la herramienta, una respuesta 200 con un cuerpo que no es JSON (la página intersticial de Cloudflare) se clasifica como un error de transporte, no como datos (`pplx_export/core/http/cookie_transport.py:133`).
- Si aparecen 403 dentro de la herramienta, reduzca la velocidad (consulte [Límite de velocidad](rate-limiting.md)) y actualice las cookies; un desafío persistente significa volver a iniciar sesión en el navegador.
- Tenga en cuenta las dos caras del 403: un desafío de control de riesgo de Cloudflare (se soluciona cuando reduce la velocidad) frente a un 403 a nivel de API (cookie muerta: se genera inmediatamente sin retroceso; consulte la siguiente sección). La página de diseño mapea esto último ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

Antecedentes: [Autenticación de API](../reference/api/api-authentication.md).

<a id="401-errors-expired-cookies" data-pplx-source-anchor="true"></a>
## Errores 401 / cookies caducadas

**Problema**: los comandos fallan con un error de autenticación: `AuthTransportError: 鉴权失败 401` de `pplx-export`, o `pplx-ask ask` sale con una sugerencia de HTTP 401/403 para actualizar la cookie.

**Causa**: la cookie de sesión ha caducado o ha sido invalidada. `401`/`403` se tratan como fallos de autenticación y se generan inmediatamente, sin retroceso, porque el retroceso no puede auto-reparar una sesión muerta (`pplx_export/core/http/cookie_transport.py:82`; `pplx_export/core/errors.py:68`). `batch` además falla rápidamente después de 3 fallos de autenticación consecutivos para que una cookie muerta no consuma toda la cola.

**Solución**:

1. Vuelva a iniciar sesión (o vuelva a abrir el sitio) en el navegador para que se renueven las cookies de sesión.
2. Actualice la caché de cookies de la herramienta. La caché en `<out>/index/.cookies.json` se reutiliza dentro de una ventana de frescura de 12 horas (`pplx_export/core/cookies/cache.py:22`), así que después de volver a iniciar sesión, ya sea:
   - ejecute una vez con `--cookies-from <browser>` para forzar una importación nueva del navegador, o
   - elimine `<out>/index/.cookies.json` y deje que la próxima ejecución lo reimporte automáticamente.
3. Cada ejecución que se valida correctamente vuelve a guardar la caché (`pplx_export/commands/common.py:150`), por lo que las ejecuciones diarias se mantienen frescas por sí solas.

Detalles de configuración: [Primeros pasos](getting-started.md) · [Configuración](configuration.md).

<a id="linux-cookie-decryption" data-pplx-source-anchor="true"></a>
## Descifrado de cookies en Linux

**Problema**: en Linux, la detección automática (o `--cookies-from chrome` y compañía) no puede leer el almacén de cookies del navegador incluso si el navegador ha iniciado sesión.

**Mecanismo**: los navegadores de la familia Chromium en Linux cifran la base de datos de cookies con una clave almacenada en el llavero del sistema operativo, leída en tiempo de ejecución a través de la API Secret Service D-Bus. `browser_cookie3` se comunica con D-Bus a través de `jeepney` en Python puro (ya instalado con la herramienta en Linux, no es necesario configurar nada adicional) y recurre a la contraseña heredada de `peanuts` cuando ningún llavero responde, lo que solo descifra cookies que Chrome también escribió sin un llavero. Cuando el llavero existe pero la búsqueda de D-Bus falla a nivel de transporte (por ejemplo, un bus de sesión que rechaza la autenticación anónima), la propia cadena de respaldo de `browser_cookie3` nunca se activa; la herramienta detecta ese caso y reintenta una vez omitiendo el llavero, usando la contraseña predeterminada de Chromium (la misma clave que Chromium usa cuando no hay llavero disponible) (`pplx_export/core/cookies/loaders.py:62-104`, conectado en la ruta de carga en `loaders.py:136-153`). Firefox no necesita nada de esto: su `cookies.sqlite` no está cifrado.

**La matriz**:

| Capa | Caso | Qué sucede |
|---|---|---|
| Navegador | Firefox | Sin fricción: `cookies.sqlite` no está cifrado |
| Navegador | Chromium + llavero accesible | Funciona: la clave se obtiene a través de Secret Service |
| Navegador | Chromium + sin llavero | Ruta `peanuts`: funciona solo si Chrome también escribió sin llavero |
| Navegador | Chromium + llavero inaccesible (fallo a nivel de D-Bus) | La herramienta reintenta automáticamente con la contraseña predeterminada de Chromium: mismo alcance que la ruta `peanuts` |
| Método de instalación | Paquete nativo | Detectado automáticamente (rutas integradas de browser_cookie3) |
| Método de instalación | snap / flatpak | Detectado automáticamente: el registro de perfiles integrado cubre los perfiles en `~/snap/<name>/...` resp. `~/.var/app/<app-id>/...` (`pplx_export/core/cookies/profiles.py:37-67`) |
| Entorno de escritorio | GNOME | Generalmente funciona de inmediato (gnome-keyring) |
| Entorno de escritorio | KDE | Active **Usar KWallet para la interfaz Secret Service** en la configuración de KWallet |
| Entorno de escritorio | Sin cabeza / mínimo | Sin bus de sesión D-Bus → ruta `peanuts` |
| Familia de distribución | Debian / Ubuntu | Instale `libsecret-1-0` + `gnome-keyring` |
| Familia de distribución | Fedora / RHEL | Instale `libsecret` + `gnome-keyring`; las instalaciones mínimas / de servidor a menudo carecen de un llavero por completo: el fallo más común |
| Familia de distribución | Arch | Mismo mecanismo, solo difieren los nombres de los paquetes |

Las instalaciones en entornos aislados no necesitan banderas adicionales: primero se sondea la ruta nativa, luego las bases de datos de cookies snap/flatpak del registro a través de un `cookie_file=` explícito (`pplx_export/core/cookies/loaders.py:155-168`).

**Escenario → canal recomendado**:

| Escenario | Canal recomendado |
|---|---|
| Firefox instalado | `--cookies-from firefox`: sin fricción |
| Escritorio GNOME / KDE | La detección automática funciona |
| Navegador snap / flatpak | Detección automática: el registro lo cubre; de lo contrario, `--cookies FILE` exportado mediante una extensión del navegador |
| Servidor sin cabeza | `--cookies FILE`: el respaldo universal; `--transport webbridge` como último recurso |

<a id="an-export-ran-under-the-wrong-account-multi-account" data-pplx-source-anchor="true"></a>
## Una exportación se ejecutó con la cuenta incorrecta (varias cuentas)

**Problema**: los hilos archivados se obtuvieron con la sesión de la cuenta incorrecta, por ejemplo, una ejecución de `--account alice` extrajo datos como `bob`, o el archivo muestra hilos que no pertenecen a la cuenta prevista.

**Causa**: con varias cuentas iniciadas sesión en el mismo navegador, el token de sesión activo (`__Secure-next-auth.session-token`) puede pertenecer a una cuenta diferente de la que se pretendía. Si el `email` de la cuenta objetivo no está registrado en la configuración de nivel de usuario, la herramienta no puede detectar esto y solo registra una advertencia.

**Cómo lo previene la herramienta** (`pplx_export/commands/common.py:93`): al inicio, el transporte llama a `GET /api/auth/session` y compara el correo electrónico activo con el registrado. Si no coinciden, enumera automáticamente las cookies de sesión por cuenta del navegador (`__Secure-pplx.session.<user_id>`), sustituye cada una en el token activo y sondea la sesión hasta que el correo electrónico objetivo coincida (`pplx_export/commands/common.py:190`; `pplx_export/core/cookies/loaders.py:175`). Si ningún token coincide, el comando se aborta con un error claro: nunca continúa silenciosamente con la cuenta incorrecta.

**Solución**:

- Registre el `email` de cada cuenta en `[accounts.<name>]` (consulte [Configuración](configuration.md)) y pase `--account` explícitamente.
- Verifique la línea de registro de inicio `[auth] cookie 来源 …，当前账户: …`: nombra el correo electrónico de la sesión activa antes de obtener cualquier dato.
- Para auditar un archivo existente, el `thread.json` de cada hilo lleva un campo `export_via` que registra qué cuenta realizó la exportación (`pplx_export/sites/perplexity/fs_writer.py:229`). `pplx-export sync-deleted` usa el mismo campo para seleccionar la cuenta para la verificación en línea.

Profundidad del mecanismo: [Autenticación de API](../reference/api/api-authentication.md) · [Preguntar y cuentas](../architecture/ask-and-accounts.md).

<a id="config-file-not-found-degraded-mode" data-pplx-source-anchor="true"></a>
## "Archivo de configuración no encontrado" — modo degradado

**Problema**: una advertencia de inicio dice que no se encontró ningún archivo de configuración de nivel de usuario y el comando se ejecuta en modo degradado; o un `--account alice` explícito falla con un error que apunta a `config.example.toml`.

**Causa**: no hay ningún archivo de configuración en ninguna de las tres ubicaciones de búsqueda: `--config PATH`, la variable de entorno `PPLX_EXPORT_CONFIG` o la predeterminada `~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). Dos casos relacionados pero distintos: una **ruta de configuración especificada explícitamente** que no existe genera `ConfigError`; una configuración corrupta (no analizable) siempre genera `ConfigError`: una configuración rota nunca se degrada silenciosamente.

**Efectos del modo degradado**:

- El registro de cuentas está vacío, por lo que la verificación de propiedad de cookies se omite con una advertencia y los comandos se ejecutan como la cuenta de marcador de posición `default` (`pplx_export/commands/common.py:51`). Un `--account` explícito da error en su lugar.
- `pplx-ask ask` omite el movimiento automático al espacio BOT (`moved_to_bot` permanece `false` en el JSON de resultado) y la telemetría lleva un ID de usuario vacío; preguntar y archivar funcionan de lo contrario.
- Los archivos se colocan en la carpeta de cuenta de respaldo derivada del nombre de usuario.

**Solución**: copie `config.example.toml` a `~/.config/pplx-export/config.toml`, complete `[accounts.<name>]` (`display_name` / `email` / `user_id`), `[bot_space]` y `default_account`; consulte [Configuración](configuration.md).

## ENTRY_EXPIRED vs ENTRY_DELETED

**Problema**: al exportar o resincronizar un hilo se informa `ENTRY_EXPIRED` o `ENTRY_DELETED`, y el hilo nunca se puede volver a obtener.

**Causa**: ambos llegan como HTTP 400 desde `GET /rest/thread/<uuid>` con diferentes códigos de error, y ambos son terminales: el hilo ya no existe en la plataforma:

| Código | Significado | Mapeo de la herramienta | Estado terminal |
|---|---|---|---|
| `ENTRY_EXPIRED` | La plataforma purgó el hilo (~3 meses de retención) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | El hilo fue eliminado activamente por el usuario / lado remoto (el efecto descendente de `DELETE /rest/thread/delete_thread_by_entry_uuid`) | `EntryDeletedError`, una subclase de `EntryExpiredError` (`pplx_export/core/errors.py:30`) | `deleted` |

**Lo que significa para su archivo**:

- Ninguno de los dos estados se reintenta nunca, ni con sincronización incremental ni con `--force`. La marca terminal vive en `<out>/index/batch_state.json`.
- La herramienta **nunca elimina ni mueve su archivo local**: la copia del repositorio es la copia de seguridad. El comando de exportación registra el estado terminal y sale correctamente (`pplx_export/commands/export_cmd.py:51`).
- Debido a que la relación de subclase es deliberada, las rutas de código que solo conocen `EntryExpiredError` aún tratan `ENTRY_DELETED` como terminal; las rutas conscientes (lote / exportación / sincronización-eliminados / relleno de modo de búsqueda) lo clasifican precisamente como `deleted`.
- Conclusión práctica: exporte a tiempo. Pasada la purga de ~3 meses, los enlaces de origen de artefactos/informes también caducan de forma irrecuperable.

Relacionado: [Sincronización incremental](incremental-sync.md) · [Respuestas y errores](../reference/api/api-responses-errors.md).

<a id="assets-that-cannot-be-downloaded-toolu_-handles" data-pplx-source-anchor="true"></a>
## Activos que no se pueden descargar (manejadores `toolu_`)

**Problema**: algunas entradas en `assets/assets_manifest.json` tienen versiones marcadas `"no_download_channel": true`, y no existe ningún archivo correspondiente en `assets/files/`.

**Causa**: los manejadores de espacio de trabajo en la nube con prefijo `toolu_` (DOC_FILE / CODE_FILE / UNKNOWN sin una forma de URL) no tienen un canal de descarga de API: `GET /rest/assets/<asset_uuid>/data` devuelve 404 `ASSET_NOT_FOUND` para ellos, y `file-repository/download` rechaza los manejadores `file:repo/...` (400). Este es un **límite conocido de integridad del archivo**, no un error en la exportación. `pplx-export assets-backfill` marca estas versiones `no_download_channel` y las omite (`pplx_export/commands/assets_backfill_cmd.py:356`).

**Solución**:

- Nada que descargar hoy: la bandera es el registro deliberado del límite.
- El contenido a menudo sobrevive en línea: el texto de extracción de página de subagente y las cargas útiles de paso se conservan en el JSON sin procesar del hilo (`raw_entries.json` / `raw_blocks.json`) y en el `turns/` renderizado; verifique allí primero.
- `file-repository/list-files` se rastrea como una posible ruta de rescate futura; consulte [Hoja de ruta de descubrimiento de API](../reference/api/api-discovery-roadmap.md).

Diseño del manifiesto: [Diseño del archivo](archive-layout.md).

<a id="command-seems-hung-long-silences" data-pplx-source-anchor="true"></a>
## El comando parece colgado / silencios largos

**Síntoma**: `index` / `batch` / `export` parece detenerse; un administrador de tareas externo puede eliminarlo como "tiempo de espera agotado".

**Causa**: casi siempre es una espera de retroceso o de solicitud en curso, no un bloqueo. En errores 429 / 5xx / de red, el transporte duerme entre intentos, hasta 300 s por espera (`pplx_export/core/throttle.py`, `Throttle.backoff`).

**Lo que ahora ve (verbosidad predeterminada, no se necesita `-v`)**: la espera se muestra mediante latidos INFO. Un retroceso imprime una línea inicial y luego un tic de cuenta regresiva cada ~10 s (`Throttle.heartbeat_interval`); una sola solicitud que se detiene antes de responder imprime un tic de "aún esperando respuesta"; y las transmisiones de `pplx-ask` imprimen un tic de "aún esperando el flujo de respuesta" mientras una ejecución de deep-research / council está en silencio:

```
22:27:24 [auth] 正在校验账户 cookie（来源 cache）…
22:27:40 退避 ~51s（连续失败 1 次，网络异常重试中）
22:27:50 仍在等待重试，剩余 ~41s
22:28:00 仍在等待重试，剩余 ~31s
```

La espera total no cambia: los latidos solo la hacen visible; interrumpir es seguro en cualquier momento (el estado se escribe atómicamente y la próxima ejecución repara la brecha). `-v` / `--log-file` aún agregan el seguimiento completo de solicitud DEBUG.

**Omitir la sonda de inicio**: `index` / `batch` comienzan con una sonda de sesión que sigue las mismas reglas de retroceso, por lo que en una red deficiente la primera espera puede ser este paso de validación de cuenta. Pase `--skip-auth-check` para omitirlo e ir directamente al trabajo, confiando en la cuenta que ha iniciado sesión actualmente; consulte [Configuración](configuration.md).

**Anti-patrón**: envolver la CLI en un administrador de tareas con un tiempo de espera máximo breve (tareas de agente en segundo plano, envoltorios cron de estilo `timeout(1)`) *mientras* se encadenan cuentas con `&&`: la cascada de retroceso de la primera cuenta consume todo el tiempo de espera y la cuenta encadenada nunca se ejecuta. Una cuenta por invocación, presupuesto generoso: consulte [Presupuesto de tiempo de ejecución para llamantes](rate-limiting.md#runtime-budget-for-callers).

<a id="where-are-the-logs" data-pplx-source-anchor="true"></a>
## ¿Dónde están los registros?

**Consola**: progreso de nivel INFO de forma predeterminada; `-v` / `--verbose` cambia a DEBUG (seguimiento de solicitudes, decisiones internas); las advertencias y errores siempre se muestran.

**Archivo**: pase `--log-file` para capturar el flujo DEBUG completo (`pplx_export/core/logging.py:45`):

- `--log-file` sin un valor termina en `<out>/index/logs/<cmd>-<timestamp>.log` (`pplx_export/commands/common.py:218`), por ejemplo, `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH` escribe en la ruta dada.

**Otros archivos de estado útiles para el diagnóstico** (en `<out>/index/`):

| Archivo | Contenido |
|---|---|
| `.cookies.json` | Caché de cookies (12 h de frescura; escrito atómicamente con 0o600: es una credencial equivalente a inicio de sesión, manténgalo privado) |
| `batch_state.json` | Estado de exportación por hilo, incluidas las marcas terminales `expired` / `deleted` |
| `answer_variants_log.jsonl` | Registro de variantes de reescritura de respuestas |
| `library_*.json` | Instantáneas del índice de biblioteca por cuenta |

<a id="see-also" data-pplx-source-anchor="true"></a>
## Véase también

- [Primeros pasos](getting-started.md) — configuración inicial e importación de cookies
- [Configuración](configuration.md) — cuentas, espacio BOT, modo degradado
- [pplx-ask](pplx-ask.md) — la CLI de consulta interactiva
- [pplx-export](pplx-export.md) — la CLI de archivado
- [Límite de velocidad](rate-limiting.md) — ritmo y disciplina de retroceso
