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

## Instalación

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env      # y complétalo (BD, WEBMAIL_SECRET_KEY, REDIS_URL...)
venv/bin/gunicorn 'app_pdf:app' --bind 0.0.0.0:8792     # o: python app_pdf.py
```

`app_pdf.py` crea la app Flask, carga `config.py`, conecta el puente de auth
(`auth_drive.init_auth`) y monta el editor (`registrar_modulo`). Detrás de un proxy,
enruta `/api/pdf/*` y `/herramientas/editor-pdf/*` a este servicio.

## Estado

- **Fase 1 — hecha:** código base auditado (sin secretos, sin IPs internas).
- **Fase 2 — hecha:** app autónoma (`app_pdf.py`, `config.py`, `auth_drive.py`,
  `requirements.txt`, `.env.example`).
  - Puente de auth al token del Drive **verificado** (token válido → usuario; token
    inválido o sesión caída → rechazado).
  - **Arranque autónomo validado**: la app levanta por sí sola y registra sus 73 rutas,
    incluidas `/api/pdf`, `/herramientas/editor-pdf` y `/editor/drive`.
- El editor **ya funciona en producción dentro de Maquita** (integrado, usado desde el
  Drive); esta carpeta es esa misma funcionalidad empaquetada para instalarla aparte.
- **Opcional pendiente:** prueba end-to-end del servicio autónomo sirviendo tráfico real
  con `auth_drive` y BD conectadas (el patrón ya está probado en el Almacén).
