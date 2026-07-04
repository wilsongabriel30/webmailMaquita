# Almacén Maquita — Archivos + OnlyOffice para el webmail

Nube de archivos personal (estilo Drive/OneDrive) integrada al webmail:
cada usuario del correo tiene su unidad con **subida/descarga, carpetas,
papelera con retención, versiones (hasta 100 por archivo), favoritos,
compartir, cuotas, deduplicación por contenido** y, si se conecta un
OnlyOffice Document Server, **edición colaborativa en línea** de
documentos Word/Excel/PowerPoint (docx, xlsx, pptx, odt, ods, odp).

Es un servicio independiente (Flask + gunicorn + PostgreSQL) que se
autentica con la MISMA sesión del webmail: el usuario inicia sesión en el
correo y la sección **Archivos** funciona sola, sin segunda contraseña.

## Arquitectura

```
navegador ──cookie del webmail──► nginx (mismo dominio)
   ├── /webmail/            → frontend React (sección "Archivos" incluida)
   ├── /api/...             → backend del webmail (FastAPI)
   ├── /api/almacen/...     → ESTE servicio (gunicorn 127.0.0.1:8788)
   ├── /archivos-almacen/…  → página del editor OnlyOffice (este servicio)
   └── /office/...          → OnlyOffice Document Server (docker, opcional)
```

- Los ARCHIVOS viven en el filesystem (`ALMACEN_RAIZ_DATOS`); PostgreSQL
  guarda solo metadatos (compartidos, papelera, versiones, cuotas...).
- Contrato completo de la API: `docs/CONTRATO-API.md` (49 endpoints).

> 🧑‍🎓 **¿Primera vez o quieres el detalle completo?** Hay dos guías pensadas
> para que cualquier estudiante lo replique en una VM (VirtualBox/Proxmox):
> - **[docs/GUIA-PASO-A-PASO.md](docs/GUIA-PASO-A-PASO.md)** — todo desde cero, con verificación de cada paso.
> - **[docs/GUIA-ONLYOFFICE.md](docs/GUIA-ONLYOFFICE.md)** — instalar y conectar OnlyOffice, explicado pieza por pieza.

## Instalación (5 pasos)

```bash
cd /opt/maquita-webmail/almacen

# 1. Base de datos (en el mismo PostgreSQL del webmail)
sudo -u postgres psql -c "CREATE USER almacen WITH PASSWORD 'CAMBIAR';"
sudo -u postgres psql -c "CREATE DATABASE almacen OWNER almacen;"

# 2. Entorno python
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# 3. Configuración
cp .env.example .env && nano .env       # WEBMAIL_SECRET_KEY es OBLIGATORIO:
                                        # el mismo SECRET_KEY de backend/.env
mkdir -p datos                           # o apuntar ALMACEN_RAIZ_DATOS a su NAS

# 4. Servicio
cp deploy/maquita-almacen.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now maquita-almacen
curl -s http://127.0.0.1:8788/healthz    # → {"success": true, ...}

# 5. nginx: copiar los bloques de deploy/nginx-almacen.conf DENTRO del
#    server{} del webmail y recargar
nginx -t && systemctl reload nginx
```

Luego reconstruir el frontend del webmail (`npm run build` o su script de
deploy): la sección **Archivos** aparece en la barra lateral para todos.

## OnlyOffice (edición en línea, opcional)

1. Levantar un Document Server propio (docker, ver comentario en `.env.example`).
   Guardar el secreto JWT que se genere.
2. En `.env`: `ALMACEN_ONLYOFFICE_SECRET`, `ALMACEN_ONLYOFFICE_URL_PUBLICA`
   (https://SU-DOMINIO/office) y `ALMACEN_ONLYOFFICE_URL_INTERNA`.
3. El bloque `/office/` de nginx ya publica el DS bajo el mismo dominio
   (necesario: los navegadores bloquean iframes de dominios distintos).
4. Probar: `https://SU-DOMINIO/office/healthcheck` → `true`, y en Archivos,
   menú de un .docx → **Editar**.

Sin OnlyOffice todo lo demás funciona; los documentos office se descargan
en vez de editarse en línea.

## Administración

- `ALMACEN_ADMINS` (en `.env`): correos con rol master — pueden recuperar
  archivos de cualquier usuario (papelera y retención) y administrar cuotas.
- Cuota por defecto: 20 GB por usuario (`ALMACEN_CUOTA_DEFECTO`).
- Papelera: el usuario la vacía → pasa a RETENCIÓN 90 días (solo admins
  recuperan) → purga definitiva. Cron sugerido:
  `0 3 * * * /opt/maquita-webmail/almacen/venv/bin/python3 /opt/maquita-webmail/almacen/servicio/purgar_retencion.py`
- Vista previa de PDFs: instalar `poppler-utils` (opcional).

## Alias de correo (una persona, varios buzones)

Si alguien tiene dos buzones (ej. usuario@dominio.org y
usuario@dominio.com.ec), regístrale un alias y ambos abrirán EL MISMO
almacén. Se administra con la API (solo administradores):

```
GET    /api/almacen/admin/alias-correo                 lista
POST   /api/almacen/admin/alias-correo                 {"alias": "...", "canonico": "..."}
DELETE /api/almacen/admin/alias-correo?alias=...       elimina
```

Los cambios aplican solos en menos de 1 minuto. Detalle y ejemplos:
[docs/GUIA-PASO-A-PASO.md](docs/GUIA-PASO-A-PASO.md#alias-de-correo-una-persona-varios-buzones).

## Seguridad

- La cookie del webmail es httpOnly y se valida por firma HS256; el logout
  invalida el acceso si `ALMACEN_REDIS_URL` apunta al Redis del webmail.
- El Document Server se autentica con JWT propio (`ALMACEN_ONLYOFFICE_SECRET`);
  sus endpoints de descarga/callback usan tokens firmados de un solo uso
  con expiración — nunca la sesión del usuario.
- La cabecera interna `X-Almacen-Usuario-Id` se descarta SIEMPRE si viene
  del cliente; solo la fija el candado tras validar la cookie.
