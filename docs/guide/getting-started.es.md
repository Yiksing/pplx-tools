---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/getting-started.md"
translation_source_sha256: "d98ba1f32b1e75bff7b3d51ef17e833417ecaf283996152cfa3342455b6eca7a"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="getting-started" data-pplx-source-anchor="true"></a>
# Primeros pasos

Desde una copia recién obtenida hasta un primer archivo local: instale los dos comandos, cree la
configuración a nivel de usuario, elija un canal de cookies y realice una primera exportación.

<a id="requirements" data-pplx-source-anchor="true"></a>
## Requisitos

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — utilizado para instalar las herramientas y ejecutar el conjunto de pruebas
- **Un navegador de escritorio con sesión iniciada en Perplexity** — las herramientas reutilizan sus cookies de sesión;
  nunca se almacena ningún token en la configuración

El descifrado de cookies utiliza `browser_cookie3`. La detección automática cubre Edge, Chrome, Firefox y
Safari; Brave, Chromium, Opera y Vivaldi funcionan mediante `--cookies-from`.

<a id="install" data-pplx-source-anchor="true"></a>
## Instalación

No se necesita clonar — instale directamente desde la URL de git:

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

Desde un clon local (raíz del repositorio):

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

Esto instala dos comandos: `pplx-export` (archivado) y `pplx-ask` (consultas
interactivas). Verifique:

```bash
pplx-export --version
pplx-export --help           # overview with examples; each subcommand has its own --help
pplx-ask --help
```

`uvx --from . pplx-export` ejecuta un comando único sin instalación.

<a id="create-the-user-level-config" data-pplx-source-anchor="true"></a>
## Crear la configuración a nivel de usuario

El registro de cuentas (nombre visible / correo electrónico / user_id) y el espacio BOT son datos
personales y **no se confirman en el repositorio**; residen en un archivo TOML externo.
Plantilla: `config.example.toml` en la raíz del repositorio.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

1. Cree el directorio de configuración.
2. Copie la plantilla a la ruta predeterminada.
3. `chmod 600` — el archivo contiene datos personales; manténgalo solo para el propietario.
4. Complete `[accounts.<name>]` — la clave es el nombre de usuario de la cuenta (tal como aparece en
   las URL de hilos / la biblioteca); establezca `display_name`, `email`, `user_id` y elija un
   `default_account`.
5. Complete `[bot_space]` — donde se recopilan los hilos creados por `pplx-ask` después de su
   finalización (se puede crear un espacio real con `pplx-ask space-create`).

**Alternativa automática:** `pplx-export init` genera este archivo por usted —
enumera las cookies de sesión por cuenta en su navegador, sondea
`/api/auth/session` para obtener el correo electrónico / nombre visible de cada token, establece
`default_account` en la cuenta activa actualmente, empareja el espacio BOT por
título y escribe el TOML de forma atómica con permisos 0600 (un archivo existente
solo se sobrescribe con `--force`).

```bash
pplx-export init                     # discover accounts, write the default config path
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --bot-title TITLE   # match/create a different space title (default BOT)
pplx-export init --config /path/to/config.toml   # write to a custom path
```

Banderas: `--force` sobrescribe una configuración existente; `--create-bot-space [TITLE]`
crea el espacio a través de la API cuando no coincide ningún título (una operación de escritura en la
cuenta; un TITLE explícito impulsa tanto el emparejamiento como la creación); `--bot-title TITLE`
se utiliza tanto para el emparejamiento como para la creación. Tenga en cuenta que para
`init` — a diferencia de cualquier otro comando — `--config` es la ruta de **escritura**, no
la ruta de carga. Detalles completos: [pplx-export → init](pplx-export.md#init).

La referencia completa de campos se encuentra en [Configuración](configuration.md).

**Prioridad de carga** (la más alta primero):

| # | Fuente |
|---|--------|
| 1 | `--config PATH` |
| 2 | Variable de entorno `PPLX_EXPORT_CONFIG` |
| 3 | `~/.config/pplx-export/config.toml` (predeterminado) |

!!! nota "Cuando falta la configuración"
    Los comandos sin `--account` se ejecutan en modo degradado: la verificación de propiedad del correo electrónico se
    omite con una advertencia (los comandos sin conexión no se ven afectados); un `--account` explícito
    genera un error que señala a `config.example.toml`. Cuando se omite `--account`,
    se utiliza `default_account` de la configuración.

<a id="choose-a-cookie-channel" data-pplx-source-anchor="true"></a>
## Elegir un canal de cookies

Las credenciales provienen de las cookies de sesión de Perplexity iniciadas en su navegador local, leídas
mediante `browser_cookie3` — incluida la enumeración de tokens de múltiples cuentas y el cambio automático.
Cuatro canales:

| Canal | Cómo | Notas |
|---------|-----|-------|
| Detección automática (predeterminado) | sin bandera | caché fresca de 12 h primero, luego almacenes del navegador en el orden edge→chrome→firefox→safari |
| Navegador nombrado | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| Archivo de cookies | `--cookies /path/to/cookies.txt` | Archivo de cookies Netscape o JSON exportado |
| WebBridge | `--transport webbridge` | obtención en contexto de página — el canal de respaldo, solo se usa cuando se solicita explícitamente |

En Linux, las instalaciones de navegadores snap y flatpak también se detectan automáticamente — sus rutas de
perfil están cubiertas por el registro integrado. La matriz completa de Linux (llavero, entornos de
escritorio, paquetes de distribución):
[Solución de problemas → Descifrado de cookies en Linux](troubleshooting.md#linux-cookie-decryption).

```bash
pplx-export export <thread_url>                                 # default: auto-detect browser store
pplx-export export <thread_url> --cookies-from edge             # import from a specific browser
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # use a cookie file
pplx-export export <thread_url> --transport webbridge           # WebBridge page context (explicit fallback)
```

Después de obtener las cookies, la herramienta llama a `/api/auth/session` e imprime el correo electrónico
actual de la cuenta para que pueda confirmar que se está utilizando la cuenta correcta — tenga cuidado si `--account`
no coincide con la cuenta de cookies. El diseño de transporte/credenciales se cubre en
[Ask y cuentas](../architecture/ask-and-accounts.md).

<a id="first-run" data-pplx-source-anchor="true"></a>
## Primera ejecución

```bash
pplx-export index --account alice     # fetch the library index
pplx-export export <thread_url>       # export a single thread
pplx-export batch --account alice     # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run       # offline re-render, zero network
```

1. **`index`** obtiene el índice de la biblioteca de la cuenta — el punto de entrada sobre el que `batch` y
   los demás comandos de toda la cuenta se basan.
2. **`export`** archiva un hilo de principio a fin: conserva las respuestas API sin procesar
   (`raw_*.json`) junto con Markdown para que la representación se pueda reproducir sin conexión.
3. **`batch`** recorre toda la biblioteca. Se detiene temprano una vez que todo lo restante ya está
   archivado (parada temprana incremental), escribe puntos de control reanudables y acepta
   `--full` para un recorrido completo. Detalles: [Sincronización incremental](incremental-sync.md).
4. **`re-render --dry-run`** demuestra la ruta sin conexión: regenera `conversation.md`
   + `turns/` a partir de archivos sin procesar locales sin red. Use `--dry-run` para escribir los
   resultados. Consulte [Operaciones sin conexión](../architecture/offline-operations.md).

Una vez que eso funcione, `pplx-ask ask "<prompt>"` ejecuta una consulta en streaming y archiva el
hilo resultante automáticamente — consulte [pplx-ask](pplx-ask.md).

<a id="where-archives-land" data-pplx-source-anchor="true"></a>
## Dónde se almacenan los archivos

Los archivos se escriben en `./web_archive/` de forma predeterminada (anule con `--out`): un
directorio por hilo.

| Ruta | Contenido |
|------|---------|
| `conversation.md`, `turns/` | conversación renderizada |
| `thread.json` | metadatos del hilo + registro de interrupciones |
| `sources.md` / `sources.json` | citas |
| `report.md` | informe de deep-research / council / study |
| `assets/` | activos descargados (modo Computer) |
| `raw_*.json` | respuestas API sin procesar conservadas — los archivos exitosos se pueden volver a renderizar sin conexión sin volver a obtenerlos |

El contrato completo del directorio: [Estructura del archivo](archive-layout.md).

<a id="next-steps" data-pplx-source-anchor="true"></a>
## Próximos pasos

- ¿Algo salió mal? → [Solución de problemas](troubleshooting.md)
- Referencia comando por comando → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [Comandos de mantenimiento](maintenance-commands.md)
- Los cinco modos de conversación → [Modos](modes.md)
