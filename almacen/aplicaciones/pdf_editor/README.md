# Editor de PDF — Aplicación del Drive Maquita

Herramienta para **anotar, firmar y rellenar PDF** que se abre desde el
[Drive Maquita (Almacén)](../../README.md) y trabaja los archivos del Drive.

- Firma digital con certificados `.p12`/`.pfx` (la clave de cifrado se genera en el
  servidor, nunca viaja en el código).
- Anotaciones, formularios, conversión a Word/tablas, OCR y visor.
- Arquitectura hexagonal: `dominio/`, `aplicacion/`, `infraestructura/`, `interfaces/`.
- El módulo se monta con `registrar_modulo(app)` (en `__init__.py`): expone
  `/api/pdf/*` y `/herramientas/editor-pdf/*`. Ya trae la ruta `/editor/drive` para
  abrir un PDF por su ruta en el Drive.

## Arranque como app autónoma

Archivos de la app (sin credenciales en el código; todo por entorno — ver `.env.example`):

- **`config.py`** — configuración desde variables de entorno (2 BD + secreto del Drive).
- **`auth_drive.py`** — puente de autenticación: valida el **token del Drive**
  (cookie `access_token`, JWT con `WEBMAIL_SECRET_KEY` + sesión viva en Redis) y lo
  expone a `flask_login`, para que `@login_required`/`current_user` funcionen sin login
  propio. Mismo contrato que el resto del Almacén.
- **`requirements.txt`** — dependencias (Flask, cryptography, PyMuPDF, OpenCV, etc.).

## Estado

- **Fase 1 — hecha:** código base traído y auditado (sin secretos, sin IPs internas).
- **Fase 2a — hecha:** andamiaje de app autónoma (`config.py`, `auth_drive.py`,
  `requirements.txt`, `.env.example`). El **puente de auth al token del Drive está
  verificado** (token válido → usuario; token inválido o sesión caída → rechazado).
- **Fase 2b — pendiente (despliegue):**
  1. Crear el `venv` con `requirements.txt` e instalar dependencias.
  2. Punto de entrada `app_pdf.py` que cree la app Flask, cargue `config.py`, llame a
     `auth_drive.init_auth(app)` y a `registrar_modulo(app)`; servicio + nginx.
  3. Cablear la lectura/escritura del PDF **contra la API del Drive** (`/api/almacen`):
     abrir un PDF por su ruta y **guardarlo de vuelta** en la misma ruta.
  4. Probar end-to-end: abrir desde el Drive, anotar, firmar y guardar.

Hasta completar la Fase 2b, este directorio es el **código fuente + andamiaje**, no un
servicio en marcha.
