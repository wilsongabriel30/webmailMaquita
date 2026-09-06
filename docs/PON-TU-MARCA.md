# Pon tu marca — guía de branding para adoptantes

Cualquier organización que baje el repo puede dejarlo con **su** identidad. Esto cubre qué se
hace desde el **panel** (sin tocar código) y los 2-3 ajustes **manuales** que faltan.

## 1) Panel de administración → Personalización (lo principal, sin código)
En `https://TU-DOMINIO:8443` → **Personalización**:
- **Nombre de la organización** (`org_name`), **eslogan**, **contacto**, **texto de pie**.
- **Subir logo** y **favicon** (se guardan en `uploads/branding/`, servidos por `/api/branding`).

Eso ya **fluye automáticamente** a:
- El **login** del correo.
- Las **pantallas de seguridad** (2FA, verificación de enlace, simulacro de phishing, retención
  legal) y el **prompt de IA** — usan `org_name` (desde v1.1.1).
- El **Drive**: el **favicon y el color** se toman de `/api/branding` (desde v1.2.x).

## 2) Nombre del Drive (`drive_name`)
El Drive muestra un nombre de producto (por defecto **«Nube Maquita»**). Cámbialo con **una sola
perilla** (tabla `config_kv` del Almacén), sin editar plantillas:
```sql
-- en la BD del Almacén:
INSERT INTO config_kv (clave, valor) VALUES ('drive_name', 'Nube Acme')
ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor;
```
Reinicia `maquita-almacen`. Se aplica a toda la UI del Drive (título, bienvenida, menú, avisos).

## 3) Color primario (`primary_color`)
Existe en `branding_settings` pero **aún no** tiene campo en el panel (pendiente). Sételo por SQL:
```sql
-- en la BD del webmail (maildb):
INSERT INTO branding_settings (key, value) VALUES ('primary_color', '#0b6a0b')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
```
El Drive lo aplica como variable CSS `--brand-primary` (vía `/api/branding`).

## 4) Íconos de la PWA (celular)
`frontend/public/icons/icon-192.png`, `icon-512.png` y `apple-touch-icon.png` son los del logo por
defecto. **No los sustituyas en `frontend/public/`** (ensuciarías el árbol de git y chocarían en
cada `git pull`): déjalos en `branding/local/`, un directorio **no versionado** que replica la
estructura de `dist/` y que `deploy-webmail.sh` copia encima tras construir.
```bash
# Pillow hace falta. En Debian 13 pip está protegido (PEP 668): usa un entorno propio.
python3 -m venv /tmp/iconos && /tmp/iconos/bin/pip install -q pillow
mkdir -p branding/local/icons
/tmp/iconos/bin/python - <<'PY'
from PIL import Image
logo = Image.open('mi-logo.png').convert('RGBA')
for size, name in [(192,'icon-192.png'),(512,'icon-512.png'),(180,'apple-touch-icon.png')]:
    logo.resize((size,size)).save(f'branding/local/icons/{name}')
print('iconos PWA generados en branding/local/icons/')
PY
bash deploy-webmail.sh --solo-frontend
```

- **`manifest.json` no hay que tocarlo**: el despliegue inyecta `name`, `short_name` y
  `description` desde `app_name`, que es el nombre con el que el celular instala la app; los
  iconos se referencian por su nombre fijo, así que basta con la carpeta de arriba.
- **La caché del navegador se refresca sola**: el despliegue renueva la versión de caché del
  service worker (`CACHE_NAME`) en cada publicación, sobre `dist/`, sin tocar el fuente. No hay
  que editar `sw.js` a mano.
- El nombre visible del producto (título de la pestaña, emisor del segundo factor, avisos, pie de
  correos, manifest) sale de `app_name` en `branding_settings`; el de la organización, de
  `org_name`. Ninguno vive en código.
- **Tras cambiar `app_name`/`org_name`**: `systemctl restart maquita-webmail` (el backend los
  guarda en memoria al arrancar) y `bash deploy-webmail.sh --solo-frontend`.

## 5) Favicon del Drive (fallback estático)
El Drive usa el favicon de `/api/branding` si lo subiste al panel. Como respaldo estático puedes
reemplazar `almacen/servicio/estaticos/favicon.ico`.

---
### Pendientes «ideales» (mejoras, no bloquean)
- Campo de **color** en el panel de Personalización (hoy es SQL — punto 3).
- **Generar los íconos PWA server-side** desde el logo subido (hoy es el comando del punto 4).

Con el panel (1) + estos ajustes, cualquier réplica queda con su marca en minutos.
