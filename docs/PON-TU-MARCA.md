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
`frontend/public/icons/icon-192.png`, `icon-512.png` y `apple-touch-icon.png` son **estáticos**
(muestran el logo por defecto hasta reemplazarlos). Genéralos desde tu logo:
```bash
# requiere Pillow: pip install pillow
python3 - <<'PY'
from PIL import Image
logo = Image.open('mi-logo.png').convert('RGBA')
for size, name in [(192,'icon-192.png'),(512,'icon-512.png'),(180,'apple-touch-icon.png')]:
    logo.resize((size,size)).save(f'frontend/public/icons/{name}')
print('iconos PWA generados')
PY
```
Luego reconstruye el frontend (`deploy-webmail.sh --solo-frontend`).

- **`manifest.json` no hay que tocarlo**: referencia los iconos por su nombre fijo, así que basta
  con sustituir los tres ficheros.
- **La caché del navegador se refresca sola**: el despliegue renueva la versión de caché del
  service worker (`CACHE_NAME`) en cada publicación, sobre `dist/`, sin tocar el fuente. No hay
  que editar `sw.js` a mano.
- El nombre visible del producto (emisor del segundo factor, avisos, pie de correos) sale de
  `app_name` en `branding_settings`; el de la organización, de `org_name`. Ninguno vive en código.

## 5) Favicon del Drive (fallback estático)
El Drive usa el favicon de `/api/branding` si lo subiste al panel. Como respaldo estático puedes
reemplazar `almacen/servicio/estaticos/favicon.ico`.

---
### Pendientes «ideales» (mejoras, no bloquean)
- Campo de **color** en el panel de Personalización (hoy es SQL — punto 3).
- **Generar los íconos PWA server-side** desde el logo subido (hoy es el comando del punto 4).

Con el panel (1) + estos ajustes, cualquier réplica queda con su marca en minutos.
