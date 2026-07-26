---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "39f85a86f94a3b326e9d3b9a74e9452a379a4745667b57c124c9512bfd1d9755"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="configuration" data-pplx-source-anchor="true"></a>
# Configuración

pplx-export mantiene tus datos de identidad — el registro de cuentas (nombres para mostrar, correos de inicio de sesión, IDs de usuario) y el espacio BOT — en un archivo TOML a nivel de usuario que reside fuera del repositorio. Esta página cubre dónde se encuentra ese archivo, cada campo que acepta, qué sucede cuando falta y cómo el registro gestiona el manejo de cookies para múltiples cuentas.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## Por qué la configuración reside fuera del repositorio

El registro de cuentas y el espacio BOT son datos personales y **nunca se confirman** al repositorio (`pplx_export/config.py:7-12`). El repositorio solo incluye una plantilla de marcador de posición, `config.example.toml`; tus valores reales van en una copia privada. Todo lo demás que la herramienta necesita — el dominio del sitio, las URL de la API, la raíz de archivo predeterminada — es una constante de código (`pplx_export/config.py:50-58`), no una configuración de usuario.

El TOML solo contiene datos de identidad. La obtención de cookies y la selección del transporte son indicadores CLI por invocación, no campos de configuración — consulte [Indicadores CLI, no campos de configuración](#cli-flags-not-config-fields) a continuación.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## Ubicación y prioridad de carga

`configure()` (`pplx_export/config.py:113`) resuelve la ruta de configuración con esta prioridad (`pplx_export/config.py:95-110`):

| Prioridad | Fuente | Cuenta como explícito |
|---|---|---|
| 1 | Indicador CLI `--config PATH` | sí |
| 2 | Variable de entorno `PPLX_EXPORT_CONFIG` | sí |
| 3 | `~/.config/pplx-export/config.toml` (ruta predeterminada) | no |

"Explícito" importa para el comportamiento de error cuando el archivo falta — consulte [modo degradado](#missing-config-degraded-mode). Ambas entradas CLI recargan la configuración en modo estricto después del análisis de argumentos (`pplx_export/cli.py:223`, `pplx_export/ask_cli.py:278`); la carga en tiempo de importación (`pplx_export/config.py:174-179`) es tolerante a fallos, por lo que importar el paquete nunca falla por un archivo faltante.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## Creación de tu configuración

!!! tip "Alternativa automática"
    `pplx-export init` puede generar este archivo automáticamente — descubre las cuentas con sesión iniciada desde las cookies de tu navegador y escribe el TOML con permisos 0600. Consulte [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

Luego edita la copia. La plantilla utiliza marcadores de posición puros — copia la estructura, reemplaza cada valor:

```toml
# Default account used when --account is not given (a key of [accounts.<name>] below)
default_account = "alice"

# Account registry: key = account username (the username in thread URLs / library)
[accounts.alice]
# Full display name: used for archive directory naming (web_archive/<display name>/…)
display_name = "Alice Example"
# Login email: verifies cookie ownership
email = "alice@example.com"
# Account uid (required for thread-viewed telemetry)
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT space: where threads created by pplx-ask are collected after completion
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

Estilo de marcador de posición: `alice`/`bob` son nombres de usuario de cuentas ficticios, los correos usan `example.com` y los UUID usan la forma de todos ceros `00000000-0000-4000-8000-…`. En tu archivo real, la clave de la tabla **debe ser el nombre de usuario real de la cuenta** tal como aparece en las URL de los hilos y en tu biblioteca.

!!! warning "Mantenlo privado"
    La configuración real contiene datos personales (correos, IDs de usuario). El permiso recomendado es `0o600`; nunca lo confirmes en ningún repositorio git (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## Referencia de campos

<a id="top-level" data-pplx-source-anchor="true"></a>
### Nivel superior

| Campo | Tipo | Significado |
|---|---|---|
| `default_account` | string | Clave de una tabla `[accounts.<name>]`, utilizada cuando no se proporciona `--account` (`pplx_export/commands/common.py:84-85`). Vacío/faltante = modo degradado. |

### `[accounts.<name>]`

Una tabla por cuenta; `<name>` es el nombre de usuario de la cuenta. El registro se carga en tres diccionarios claveados por nombre de usuario: `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Campo | Tipo | Requerido | Significado |
|---|---|---|---|
| `display_name` | string | no | Nombre para mostrar completo, utilizado para el nombrado del directorio de archivo (`web_archive/<display name>/…`); se usa el nombre de usuario si se omite. Consulte [Disposición del archivo](archive-layout.md). |
| `email` | string | recomendado | Correo de inicio de sesión. El transporte verifica la propiedad de la cookie contra él, evitando "una exportación para la cuenta B que lleva la sesión de la cuenta A" (`pplx_export/config.py:69-72`). En caso de discrepancia, la herramienta enumera los tokens de sesión por cuenta en el navegador y cambia automáticamente — consulte [Modelo de cookies para múltiples cuentas](#multi-account-cookie-model). |
| `user_id` | string | para telemetría `pplx-ask` | UID de cuenta, requerido por la telemetría de hilos vistos (`pplx_export/config.py:73-75`). Léelo desde `GET /api/auth/linked-accounts`, que devuelve `user_id` / `email` / `display_name` de cada cuenta con sesión iniciada — consulte [Autenticación de API](../reference/api/api-authentication.md). |

### `[bot_space]`

El espacio BOT es el punto de recolección para los hilos creados por `pplx-ask` después de que se completan (`pplx_export/config.py:76-79`). Crea el espacio con `pplx-ask space-create` (consulte [pplx-ask](pplx-ask.md)), luego regístralo aquí.

| Campo | Tipo | Significado |
|---|---|---|
| `uuid` | string | UUID del espacio. `pplx-ask` mueve los hilos terminados aquí (`pplx_export/ask_cli.py:156-158`); cuando está vacío, se omite el paso de movimiento. |
| `slug` | string | Slug de URL del espacio. Se carga en `BOT_SPACE_SLUG` (`pplx_export/config.py:79`); la CLI en tiempo de ejecución no lo lee — la herramienta de mantenimiento de fixtures lo consume, construyendo un par de reemplazo de identidad a partir de él (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### Indicadores CLI, no campos de configuración

El TOML no tiene configuraciones de transporte o cookies. Se eligen por invocación:

| Aspecto | Dónde se establece |
|---|---|
| Ruta del archivo de configuración | `--config PATH`, o `PPLX_EXPORT_CONFIG` |
| Fuente de cookies | `--cookies-from BROWSER` / `--cookies FILE` |
| Transporte | `--transport cookie\|webbridge` (solo `pplx-export`; predeterminado `cookie`) |

Consulte [pplx-export](pplx-export.md) para la referencia completa de indicadores.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## Configuración faltante: modo degradado

Cuando no se carga nada, los registros a nivel de módulo permanecen vacíos y `LOADED_CONFIG_PATH` es `None` (`pplx_export/config.py:83-85`). Comportamiento por escenario (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`):

| Escenario | Comportamiento |
|---|---|
| Sin configuración en la ruta predeterminada, no se proporciona `--account` | Modo degradado: se registra una advertencia y los comandos se ejecutan con una cuenta de marcador de posición (`username='default'`); se omite la verificación de propiedad del correo. Los comandos diarios sin conexión no se ven afectados (`pplx_export/commands/common.py:86-90`). |
| Sin configuración, `--account` explícito | `SystemExit` nombrando el orden de búsqueda y señalando `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| Configuración cargada, `--account` no registrado | `SystemExit` nombrando el archivo cargado, pidiéndote que agregues `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| Ruta explícita (`--config` / variable de entorno) no existe | `ConfigError` en modo estricto (`pplx_export/config.py:140-146`). |
| El archivo existe pero no se puede analizar | Siempre `ConfigError` — una configuración corrupta no debe degradarse silenciosamente (`pplx_export/config.py:147-150`). |
| `--account` omitido, configuración cargada | Se usa `default_account` (`pplx_export/commands/common.py:84-85`). |

Qué cubren los "comandos sin conexión" y cómo las ejecuciones degradadas interactúan con el archivo se detalla en [Operaciones sin conexión](../architecture/offline-operations.md).

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## Modelo de cookies para múltiples cuentas

Con varias cuentas con sesión iniciada en el mismo navegador, el almacén contiene una cookie de sesión **por cuenta**, y el campo `email` de la configuración le dice a la herramienta cuál necesita:

- Cada cuenta con sesión iniciada tiene una cookie `__Secure-pplx.session.<uid>` (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`); el sufijo `<uid>` es el `user_id` de la cuenta.
- La cuenta **activa** es aquella cuyo token se encuentra actualmente en `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). Cambiar de cuenta = escribir el valor de la cookie por cuenta de la cuenta objetivo en esa cookie — no se necesita interfaz de navegador (`pplx_export/core/cookies/loaders.py:180-187`).
- Al inicio, el transporte sondea `GET https://www.perplexity.ai/api/auth/session` y compara el correo devuelto con `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- En caso de discrepancia, `_try_switch_account` (`pplx_export/commands/common.py:190-215`) enumera cada token de cuenta en el navegador mediante `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`, prefiriendo entradas en el subdominio `www.`), prueba cada uno en `__Secure-next-auth.session-token` y reconstruye el transporte en la primera coincidencia.
- Si ningún token coincide, el comando sale nombrando ambos correos y pidiéndote que inicies sesión con la cuenta objetivo en el navegador primero (`pplx_export/commands/common.py:142-145`) — consulte [Solución de problemas](troubleshooting.md).
- Una cuenta sin `email` registrado procede sin verificación, con una advertencia pidiéndote que confirmes el inicio de sesión en el navegador tú mismo (`pplx_export/commands/common.py:146-149`).

Para el flujo completo de cambio y la semántica del endpoint de sesión, consulte [Ask y cuentas](../architecture/ask-and-accounts.md) y [Autenticación de API](../reference/api/api-authentication.md).

<a id="cookie-cache" data-pplx-source-anchor="true"></a>
## Caché de cookies

Después de una validación exitosa, las cookies resueltas se almacenan en caché para que las ejecuciones posteriores omitan el navegador:

| Propiedad | Valor |
|---|---|
| Ruta | `<archive root>/index/.cookies.json` — sigue `--out` (`pplx_export/commands/common.py:111`) |
| Frescura | 12 horas (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`); una caché obsoleta o corrupta se trata como ausente |
| Contenido | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Escritura | Atómica: archivo temporal creado con modo `0o600`, luego `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Cubierto por `.gitignore` (`**/index/.cookies.json`) |

Orden de resolución de cookies (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`): `--cookies-from` explícito → archivo `--cookies` explícito → caché fresca → detección automática de navegadores (edge → chrome → firefox → safari). La caché se actualiza después de cada validación de cuenta exitosa (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## Protección de tus archivos

- `chmod 600` tu `config.toml` — contiene datos personales (correos, IDs de usuario).
- La caché de cookies ya se escribe con modo `0o600` por la herramienta; las cookies de sesión son credenciales equivalentes a un inicio de sesión.
- Si creas manualmente un archivo de cookies para `--cookies`, aplica `chmod 600` también.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## Cuando falla la autenticación

Cookies caducadas, una cuenta que el cambio automático no puede encontrar, errores de permisos del llavero del navegador y otros fallos de autenticación se cubren en [Solución de problemas](troubleshooting.md).
