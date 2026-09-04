# Librerías locales del chat

Copias servidas por el propio chat, sin salir a internet.

## Por qué están aquí (T4 + separación de origen, 2026-09-04)

Las plantillas ya apuntaban a `/static/vendor/...`, pero **los archivos no estaban
en el chat**: los servía el sistema que lo alojaba. Bajo `mail.maquita.org` la
ruta `/static/` cae en un proxy hacia Raíces, así que el chat cargaba sus
librerías de otro servidor sin que nadie lo hubiera decidido.

Eso pasaba desapercibido porque funcionaba. Se destapó al probar el chat en su
**origen propio** (`mensajeria.maquita.org`), donde esa ruta daba 404: sin
Socket.IO no hay tiempo real, así que la separación de origen se habría llevado
el chat por delante.

## Qué hay

| Archivo | Origen | Uso |
|---|---|---|
| `cdn.socket.io/4.5.4/socket.io.min.js` | socket.io 4.5.4 | tiempo real del chat |
| `cdn.jsdelivr.net/npm/sweetalert2@11.js` | SweetAlert2 11 | diálogos |

La estructura de carpetas imita la ruta del CDN original a propósito: así se ve
de dónde vino cada archivo y las plantillas no cambian.

## Al actualizar

Descargar la versión nueva, dejarla aquí y comprobar que se sirve desde el
origen del chat, no desde el del correo:

    curl -o /dev/null -w '%{http_code}\n' \
      https://mensajeria.maquita.org/static/vendor/cdn.socket.io/4.5.4/socket.io.min.js
