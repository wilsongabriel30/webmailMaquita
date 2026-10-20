# Apps propias de la organización (Android)

El webmail ofrece «Descargar app para Android» (menú del perfil y Configuración) **solo si el servidor tiene
una versión publicada**. Sin ella, el webmail guía a configurar el correo en Outlook o en el celular
(ActiveSync o IMAP), o a instalar el webmail como aplicación (PWA), que ya llevan el nombre de la organización.

## Publicar la app en un servidor

En `/opt/maquita-webmail/descargas-app/` (fuera del repositorio; la crea el instalador):

| Archivo | Qué es |
|---|---|
| `maquita-mail.apk` | El APK firmado de **la organización** (nombre técnico fijo, como los servicios `maquita-*`). |
| `maquita-mail.json` | Manifiesto de actualización (ver abajo). |

nginx los sirve en `https://mail.<dominio>/webmail/descargas/` (`deploy/webmail/nginx/descargas-app.conf`): solo
archivos `.apk` y `.json` con nombre simple (no copias `.bak` ni carpetas); lo que no existe da 404. En
instalaciones anteriores la ruta la añade el ajuste `deploy/ajustes/50-nginx-descargas-app.sh` al actualizar.

Manifiesto:

```json
{
  "versionCode": 22,
  "versionName": "1.3.8",
  "nombre": "Correo Ejemplo",
  "url": "https://mail.example.org/webmail/descargas/maquita-mail.apk",
  "sha256": "…suma del APK…",
  "tamano": 8991532,
  "minimoVersionCode": 0,
  "notas": "Qué cambia en esta versión.",
  "fecha": "2026-10-20"
}
```

`nombre` es opcional: si falta, el webmail usa el nombre del producto de la marca (`app_name` de
Personalización). El panel marca los teléfonos atrasados comparando con `versionName`/`fecha`.

## La app de cada organización (para quien la compila)

**No se publica el APK de otra organización**: llevaría su nombre, su logo, su firma y su lista de servidores.
Cada organización necesita su variante, compilada desde el mismo código con un **perfil de organización**
(fuera del repositorio público): identificador del paquete, nombre, servidor por omisión, ícono, color y
almacén de claves propio. Requisitos para que el servidor la reconozca:

- Agente de usuario con `CorreoApp/<versión>` (la de Maquita usa `MaquitaMail/…`; los dos se aceptan): así el
  servidor la trata como app propia (sesión de confianza, segundo factor) y el webmail no ofrece descargarla
  dentro de ella.
- Marca al iniciar: `GET /api/branding` (público) da `org_name`, `app_name`, `logo_url`, `favicon_url` y
  `primary_color`; los textos dicen el nombre de la organización.
- Actualización: el manifiesto de arriba en el mismo servidor.

## Windows

Las apps de escritorio actuales (Teams y Drive de Maquita) están atadas a los servicios de Maquita y no se
reparten a otras organizaciones. En el escritorio, el webmail instalado como aplicación (PWA) lleva la marca
de cada organización.
