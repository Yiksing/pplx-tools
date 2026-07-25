---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/index.md"
translation_source_sha256: "4687af317a6aa8c7f17c6b758463042f3f6fa6f00ba78bc0ec76464bc1bec69b"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="user-guide" data-pplx-source-anchor="true"></a>
# Guía de usuario

Documentación orientada a tareas para instalar, configurar y operar
`pplx-export` y `pplx-ask`.

<a id="start-here" data-pplx-source-anchor="true"></a>
## Comience aquí

- [Primeros pasos](getting-started.md) — instale los comandos, inicialice
  la configuración y ejecute la primera exportación.
- [Configuración](configuration.md) — cuentas, fuentes de cookies, directorios raíz de salida
  y ajustes del espacio BOT.

<a id="command-reference" data-pplx-source-anchor="true"></a>
## Referencia de comandos

- [pplx-export](pplx-export.md) — comandos de indexación, exportación y archivo por lotes.
- [pplx-ask](pplx-ask.md) — consultas de búsqueda en streaming, investigación profunda, consejo y estudio.
- [Comandos de mantenimiento](maintenance-commands.md) — operaciones de renderizado, relleno,
  relaciones y sincronización.

<a id="archives-and-synchronization" data-pplx-source-anchor="true"></a>
## Archivos y sincronización

- [Estructura del archivo](archive-layout.md) — archivos, índices, estado y respuestas
  sin procesar retenidas.
- [Modos de conversación](modes.md) — límites de artefactos para cada modo compatible.
- [Sincronización incremental](incremental-sync.md) — parada temprana, puntos de control y
  comportamiento de reanudación.

<a id="operations" data-pplx-source-anchor="true"></a>
## Operaciones

- [Límite de velocidad](rate-limiting.md) — cadencia de solicitudes segura y programación.
- [Solución de problemas](troubleshooting.md) — fallos comunes y rutas de recuperación.

Para detalles de implementación, continúe con el
[mapa de lectura de arquitectura](../architecture/index.md).
