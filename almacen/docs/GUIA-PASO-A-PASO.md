# Guía paso a paso: Almacén + OnlyOffice desde cero

> **Para quién es esta guía:** cualquier persona (pasante, estudiante,
> técnico nuevo) que quiera levantar el Almacén de archivos con edición
> Office en línea en una máquina virtual de **VirtualBox, Proxmox, VMware
> o un servidor físico**. No se necesita experiencia previa con el
> proyecto: cada paso dice qué hace y cómo verificar que quedó bien.

## Lo que vas a construir

Al terminar tendrás, junto a tu webmail, una nube de archivos tipo
Drive/OneDrive donde cada usuario del correo entra con su misma sesión y
puede subir archivos, organizarlos en carpetas, recuperar lo borrado y
**editar documentos Word/Excel/PowerPoint en el navegador, varias
personas a la vez**.

```
[Navegador] ──► [nginx] ──┬── /webmail/          interfaz del correo (React)
                          ├── /api/...           backend del correo (FastAPI)
                          ├── /api/almacen/...   ALMACÉN (este servicio)
                          ├── /archivos-almacen/ página del editor
                          └── /office/...        OnlyOffice (docker)
```

## Requisitos

| Recurso | Mínimo para probar | Recomendado |
|---|---|---|
| Máquina virtual | 2 vCPU, 4 GB RAM, 30 GB disco | 4 vCPU, 8 GB RAM, 60+ GB |
| Sistema operativo | **Debian 13** (recomendado) — Ubuntu Server 22.04/24.04 también sirve | ídem |
| Software previo | El webmail Maquita ya instalado y funcionando | ídem |

> Los comandos de esta guía son los mismos en Debian y Ubuntu (apt,
> systemd, PostgreSQL, nginx y docker se usan idéntico en ambos).
>
> **En VirtualBox:** crea la VM con red en modo *Puente (Bridged)* para
> que tenga su propia IP en tu red. **En Proxmox:** una VM normal con
> disco suficiente para los archivos de los usuarios.

---

## Paso 1 — Base de datos

El Almacén guarda los ARCHIVOS en el disco y solo los METADATOS
(compartidos, papelera, versiones, cuotas) en PostgreSQL — el mismo
PostgreSQL que ya usa el webmail sirve.

```bash
sudo -u postgres psql -c "CREATE USER almacen WITH PASSWORD 'ELIGE_UNA_CLAVE';"
sudo -u postgres psql -c "CREATE DATABASE almacen OWNER almacen;"
```

**Verificar:** `sudo -u postgres psql -l | grep almacen` debe mostrar la base.
Las tablas NO se crean a mano: el servicio las crea solo al arrancar.

## Paso 2 — Entorno Python del servicio

```bash
cd /opt/maquita-webmail/almacen
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

**Verificar:** `venv/bin/python3 -c "import flask, psycopg2, jwt; print('ok')"`

## Paso 3 — Configuración (.env)

```bash
cp .env.example .env
nano .env
```

Lo OBLIGATORIO es solo esto:

1. `WEBMAIL_SECRET_KEY` → copia el valor de `SECRET_KEY` que está en
   `/opt/maquita-webmail/backend/.env`. Con este secreto el Almacén
   reconoce la sesión del correo (por eso no hay segundo login).
2. `ALMACEN_DB_PASSWORD` → la clave que elegiste en el Paso 1.
3. `ALMACEN_ADMINS` → tu correo (podrás recuperar archivos de otros y
   administrar cuotas y alias).

Y crea la carpeta donde vivirán los archivos:

```bash
mkdir -p /opt/maquita-webmail/almacen/datos
```

> ¿Tienes un disco grande o un NAS? Apunta `ALMACEN_RAIZ_DATOS` a esa
> ruta montada en lugar de la carpeta local.

## Paso 4 — Levantar el servicio

```bash
cp deploy/maquita-almacen.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now maquita-almacen
```

**Verificar (las 3 cosas):**

```bash
systemctl status maquita-almacen          # debe decir: active (running)
curl -s http://127.0.0.1:8788/healthz     # debe responder: {"success": true, ...}
journalctl -u maquita-almacen -n 20       # sin errores en rojo
```

## Paso 5 — Publicarlo en nginx

Abre el archivo del sitio del webmail (normalmente en
`/etc/nginx/sites-enabled/`) y pega DENTRO del bloque `server { ... }`
los bloques del archivo **`deploy/nginx-almacen.conf`** de este
directorio (son 3: `/api/almacen/`, `/archivos-almacen/` y `/office/`).

```bash
nginx -t                     # SIEMPRE probar antes de recargar
systemctl reload nginx
```

> ⚠️ Nunca dejes copias de respaldo dentro de `sites-enabled/`: nginx
> carga TODO lo que hay en esa carpeta y fallará por duplicados.
> Guarda los respaldos en otra carpeta (ej. `/root/`).

**Verificar:** `curl -sk https://TU-DOMINIO/api/almacen/cuota` debe
responder `{"error":"No autenticado", ...}` (401). Eso es CORRECTO:
significa que el servicio responde y exige sesión.

## Paso 6 — Reconstruir el frontend del webmail

La sección **Archivos** ya viene en el código del frontend; solo hay que
recompilarlo:

```bash
cd /opt/maquita-webmail && bash deploy-webmail.sh     # o: cd frontend && npm run build
```

**Verificar:** entra al webmail con tu usuario → debe aparecer el icono
📁 **Archivos** en la barra lateral izquierda. Sube un archivo de prueba.

## Paso 7 — OnlyOffice (edición en línea) — opcional pero recomendado

Sin este paso todo funciona, pero los documentos office se descargan en
vez de abrirse en el editor.

```bash
# 7.1 Docker (si no está)
apt install -y docker.io

# 7.2 Genera un secreto y GUÁRDALO
JWT_SECRET=$(openssl rand -hex 32) && echo "SECRETO: $JWT_SECRET"

# 7.3 Levanta el Document Server (tarda 1-2 minutos en arrancar)
mkdir -p /opt/onlyoffice/{data,logs,lib,db}
docker run -i -t -d --name onlyoffice -p 8080:80 --restart=always \
  -e JWT_ENABLED=true -e JWT_SECRET="$JWT_SECRET" \
  -e JWT_HEADER=Authorization -e JWT_IN_BODY=true \
  -v /opt/onlyoffice/logs:/var/log/onlyoffice \
  -v /opt/onlyoffice/data:/var/www/onlyoffice/Data \
  -v /opt/onlyoffice/lib:/var/lib/onlyoffice \
  -v /opt/onlyoffice/db:/var/lib/postgresql \
  onlyoffice/documentserver

# 7.4 Verificar
sleep 90 && curl -s http://localhost:8080/healthcheck    # debe responder: true
```

Luego en `/opt/maquita-webmail/almacen/.env` completa:

```
ALMACEN_ONLYOFFICE_SECRET=el secreto del paso 7.2
ALMACEN_ONLYOFFICE_URL_PUBLICA=https://TU-DOMINIO/office
ALMACEN_ONLYOFFICE_URL_INTERNA=http://127.0.0.1:8080
ALMACEN_URL_PUBLICA=https://TU-DOMINIO
```

Y reinicia: `systemctl restart maquita-almacen`.

> **¿Por qué /office/ y no un dominio aparte?** Los navegadores bloquean
> que una página abra en iframe contenido de OTRO dominio. Al servir el
> editor bajo el mismo dominio del webmail, ese problema desaparece. El
> bloque `/office/` de nginx (Paso 5) ya hace esa magia con la cabecera
> `X-Forwarded-Host`.

**Verificar todo el circuito:**

```bash
curl -sk https://TU-DOMINIO/office/healthcheck    # true
```

En el webmail → Archivos → sube un `.docx` → botón **Editar** → debe
abrirse el editor. Escribe algo, espera unos segundos, cierra y vuelve a
abrir: los cambios deben estar. Abre el mismo archivo desde otro usuario
a la vez: deben verse escribiendo en tiempo real.

---

## Alias de correo (una persona, varios buzones)

Si una persona tiene DOS buzones (por ejemplo `usuario@dominio.org` y
`usuario@dominio.com.ec`), sin alias cada buzón tendría un almacén
separado. Con el alias, ambos abren EL MISMO.

**Cómo funciona:** la tabla `alias_correo` de la BD traduce el buzón
"alias" a su correo "canónico" (el principal) en el momento del login.
Un solo nivel: el canónico no puede ser a su vez un alias.

**Administrarlo (con la sesión de un correo que esté en ALMACEN_ADMINS),
desde la consola del navegador o con curl:**

```bash
# Crear un alias
curl -X POST https://TU-DOMINIO/api/almacen/admin/alias-correo \
  -H 'Content-Type: application/json' \
  -b 'access_token=SU_COOKIE' \
  -d '{"alias":"usuario@dominio.org","canonico":"usuario@dominio.com.ec"}'

# Listar
curl -b 'access_token=SU_COOKIE' https://TU-DOMINIO/api/almacen/admin/alias-correo

# Eliminar
curl -X DELETE -b 'access_token=SU_COOKIE' \
  'https://TU-DOMINIO/api/almacen/admin/alias-correo?alias=usuario@dominio.org'
```

O directo en la base de datos:

```sql
INSERT INTO alias_correo (alias, canonico)
VALUES ('usuario@dominio.org', 'usuario@dominio.com.ec');
```

Los cambios aplican solos en menos de 1 minuto (no hay que reiniciar).

---

## Los dos modos de directorio (¿quién es cada usuario?)

| | `local` (default) | `nomina` |
|---|---|---|
| ¿Para quién? | Instalación autocontenida (solo webmail) | Organizaciones con un directorio central de personal |
| ¿Qué hace? | Cada buzón que entra se registra solo en la tabla `usuarios` de la BD del almacén | El correo del buzón se busca en la columna `email` de la tabla `usuarios` de OTRA base (`NOMINA_DB_*`) y se usa ese id |
| Resultado | Un almacén por buzón (o por persona si usas alias) | **Una sola identidad en toda la organización**: mismo almacén y misma sala de co-edición entren por donde entren |
| Si el correo no existe | Se crea solo | Se niega el acceso (403) |

Para el modo `nomina` se agregan al `.env` las variables `NOMINA_DB_*`
y `ALMACEN_MODO_DIRECTORIO=nomina` (ver `.env.example`).

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `502` en /api/almacen | El servicio no corre | `systemctl status maquita-almacen` y ver `journalctl -u maquita-almacen` |
| `401` siempre, incluso logueado | `WEBMAIL_SECRET_KEY` no coincide con el del backend | Copiar exacto el `SECRET_KEY` de `backend/.env` y reiniciar |
| El editor dice "no configurado" (503) | Faltan las variables ONLYOFFICE en `.env` | Completar Paso 7 y reiniciar el servicio |
| El editor carga y no guarda | El Document Server no llega al callback | Ver que `ALMACEN_URL_PUBLICA` sea correcta y que el contenedor resuelva ese dominio (`--add-host` si hace falta) |
| `413` al subir | Límite de tamaño | Subir `ALMACEN_MAX_SUBIDA` y `client_max_body_size` de nginx |
| nginx no recarga | Respaldo olvidado en sites-enabled | Mover los `.bak` fuera de esa carpeta |

## Mantenimiento

- **Purga de retención** (borra definitivamente lo que lleva más de 90
  días en retención): cron diario sugerido
  `0 3 * * * /opt/maquita-webmail/almacen/venv/bin/python3 /opt/maquita-webmail/almacen/servicio/purgar_retencion.py`
- **Respaldos:** la carpeta de datos (`ALMACEN_RAIZ_DATOS`) + un dump de
  la BD `almacen` respaldan TODO.
- **Actualizar:** `git pull` + reiniciar el servicio + recompilar el
  frontend si hubo cambios en él.
