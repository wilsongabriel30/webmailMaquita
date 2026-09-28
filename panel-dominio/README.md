# Portal de administradores de dominio

Un servidor de correo suele alojar varios dominios de organizaciones distintas. Este portal
permite que cada organización administre **sus** cuentas y alias sin ver nada de las demás,
y sin entrar al panel general del servidor.

## Qué puede hacer un administrador de dominio

| Sí, por su cuenta | Lo pide y lo confirma el administrador general | No |
|---|---|---|
| Ver las cuentas, alias y grupos de sus dominios | Eliminar una cuenta (queda desactivada mientras tanto) | Ver o tocar otros dominios |
| Crear cuentas; editar nombre, teléfono y cuota | | Leer correo de nadie |
| Cambiar contraseñas; activar y desactivar cuentas | | Tocar la configuración del servidor |
| Alias y reenvíos, también hacia direcciones de fuera | | Crear administradores o asignarse dominios |
| Grupos de distribución y sus miembros | | Publicar nombres de servidor (exige DNS y certificado) |
| Marca: nombre, lema, contacto, color, logo e icono | | |
| Verificar el DNS de su dominio (MX, SPF, DKIM, DMARC) | | |

Quién administra qué lo decide el superadministrador en el panel general:
**Administración → Administradores de dominio**. Ahí también se confirman las eliminaciones y se
restablece el segundo factor de quien perdió el teléfono.

### Segundo factor

Es obligatorio (se apaga con `PD_TOTP_OBLIGATORIO=0`, solo para pruebas). En su primera entrada,
cada administrador cambia la contraseña que le dieron y después da de alta un código en su
teléfono; hasta entonces el portal no le deja hacer nada más. Un código vale una sola vez.

## Por qué es un servicio aparte

Es la parte más expuesta del sistema: la usan personas de fuera. Por eso es la que menos puede.

- **Otro proceso y otro puerto.** Si el portal cae, el panel general y el correo siguen.
- **Otro usuario del sistema**, sin `sudo`, sin escritura en disco y sin acceso a los buzones
  (ver el confinamiento en `deploy/maquita-panel-dominio.service`).
- **Otro usuario de base de datos** con permisos mínimos (`deploy/permisos.sql`): no puede leer
  las contraseñas guardadas, ni borrar buzones, ni leer la configuración ni la auditoría.
- **Sin secretos compartidos.** Las sesiones son fichas al azar guardadas como hash; una sesión
  del portal no sirve en el panel general ni en el webmail.
- **Sin dependencias en el navegador.** La pantalla es HTML, CSS y JavaScript a mano (unos 45 KB),
  sin paso de compilación: carga bien en conexiones lentas y no hay cadena de suministro que vigilar.

Aun si alguien tomara el control del portal, lo más que alcanzaría es lo que ya puede hacer un
administrador de dominio, y todo queda en `pd_auditoria`, que el portal puede escribir pero no
leer ni borrar.

## Instalación

Requisitos: el esquema de correo ya instalado (tablas `domain`, `mailbox`, `alias`), Python 3.11+,
`openssl`, nginx y PostgreSQL. Se asume el repositorio en `/opt/webmail`.

```bash
# 1. Usuario del sistema, sin shell ni directorio propio
useradd --system --no-create-home --shell /usr/sbin/nologin maquita-dominio

# 2. Entorno de Python
cd /opt/webmail/panel-dominio/backend
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# 3. Base de datos: tablas (como dueño de la base), usuario del portal y permisos
psql -d maildb -f ../deploy/esquema.sql -f ../deploy/esquema-2-autonomia.sql
psql -d maildb -c "CREATE ROLE panel_dominio LOGIN PASSWORD 'una-clave-larga-al-azar'"
psql -d maildb -f ../deploy/permisos.sql -f ../deploy/permisos-2-autonomia.sql

# 3b. Carpeta de logos, compartida con el panel general y legible por el webmail
groupadd --system maquita-marca
usermod -aG maquita-marca maquita-dominio && usermod -aG maquita-marca maquita-admin
mkdir -p /opt/webmail/uploads/branding/empresas
chgrp -R maquita-marca /opt/webmail/uploads/branding/empresas && chmod 2775 /opt/webmail/uploads/branding/empresas

# 4. Entorno del servicio (solo lo lee root; systemd se lo pasa al proceso)
install -m 600 /dev/null /etc/maquita-mail/panel-dominio.env
echo "PD_DB_PASS=una-clave-larga-al-azar" > /etc/maquita-mail/panel-dominio.env

# 5. Servicio y nginx
cp ../deploy/maquita-panel-dominio.service /etc/systemd/system/
cp ../deploy/panel-dominio-proxy.conf /etc/nginx/snippets/
cp ../deploy/nginx-panel-dominio.conf /etc/nginx/sites-enabled/panel-dominio   # ajusta nombre y certificado
systemctl daemon-reload && systemctl enable --now maquita-panel-dominio
nginx -t && systemctl reload nginx
```

El portal queda en `https://<tu-servidor>:8444/`. Abre ese puerto en el cortafuegos solo a quien
deba llegar.

## Variables de entorno

| Variable | Por defecto | Para qué |
|---|---|---|
| `PD_DB_PASS` | (obligatoria) | Clave del usuario `panel_dominio` |
| `PD_DB_HOST`, `PD_DB_PORT`, `PD_DB_NAME`, `PD_DB_USER` | `127.0.0.1`, `5432`, `maildb`, `panel_dominio` | Conexión |
| `PD_DB_SSL` | (vacío) | `require` si la base de datos está en otro equipo |
| `PD_HORAS_SESION` | `8` | Duración de una sesión |
| `PD_TOTP_OBLIGATORIO` | `1` | Exigir segundo factor |
| `PD_EMISOR` | `Portal de dominio` | Nombre que muestra la aplicación de códigos |
| `PD_DIR_MARCA` | `/opt/webmail/uploads/branding/empresas` | Carpeta de logos e iconos |
| `PD_MARCA_MAX_KB` | `512` | Peso máximo de una imagen |
| `PD_SELECTORES_DKIM` | `default,dkim,mail,selector1,selector2` | Selectores que consulta la verificación DNS |
| `PD_RESOLUTORES_DOH` | `https://dns.google/resolve,https://cloudflare-dns.com/dns-query` | Resolutores públicos por HTTPS, en orden |

## Reglas que conviene conocer

- **Cuota.** El tope por cuenta es el `maxquota` del dominio; si el dominio no tiene, 5 GB. Una
  cuenta que ya tenía más la conserva, pero desde el portal no se puede subir por encima del tope.
- **Límites del dominio.** Se respetan `mailboxes` y `aliases` de la tabla `domain` (0 = sin límite).
- **Destinos de alias, grupos y reenvíos.** Dentro de los dominios propios el destino tiene que
  existir, para no perder correo por un error de tecleo. Fuera de ellos se acepta cualquier
  dirección y queda anotada en la auditoría como destino externo. Un grupo solo admite miembros de
  fuera si se le activa expresamente.
- **Marca.** Imágenes PNG, JPG o WebP (ICO para el icono) de hasta 512 KB, reconocidas por su
  contenido. SVG se rechaza: es un documento que puede llevar código. La carpeta de logos es lo
  único del disco que el portal puede escribir.
- **Eliminar cuentas.** El portal no puede: su usuario de base de datos no tiene ese permiso.
- **Contraseñas.** Mínimo 10 caracteres con tres clases de carácter. La contraseña inicial de un
  administrador de dominio es temporal: hasta que la cambia, el portal no le deja hacer nada más.
- **Bloqueo.** Cinco intentos fallidos bloquean la cuenta 15 minutos; nginx limita además los
  intentos por dirección IP.

- **Verificación DNS.** Se pregunta por HTTPS a un resolutor público, no al del servidor: en una
  red con DNS dividido el resolutor local enseña la zona interna, que no es la que ve el mundo.
  El portal necesita salida HTTPS hacia esos resolutores. Distingue «el registro falta», «el
  dominio no existe en internet» y «no se pudo consultar».

## Pruebas

Tres niveles, de menor a mayor:

```bash
# 1. Unitarias: validaciones, alcance y contraseñas
cd panel-dominio/backend && venv/bin/pip install pytest && venv/bin/python -m pytest tests -q

# 2. Aislamiento contra el servicio instalado (como root en el servidor): intenta salirse
#    del dominio por la API, por la base de datos y por el sistema de archivos
panel-dominio/backend/venv/bin/python panel-dominio/pruebas/prueba_aislamiento.py

# 3. Recorrido con navegador de verdad (Chromium, Playwright): entrada, cambio de clave
#    obligatorio, cuentas, alias, HTML en los nombres, teléfono de 360 px y salida
cd pruebas-navegador && npx playwright test -c playwright.portal-dominio.config.js
```

El recorrido con navegador encontró lo que las otras dos no podían ver: etiquetas sin enlazar
a su casilla, un «null» impreso en pantalla y tablas incómodas en teléfono.

## Pendiente (se agradecen opiniones)

- Firmas corporativas y respuestas automáticas por dominio. Hoy exigen escribir en los buzones,
  y eso rompería el aislamiento del portal; hay que darles otra forma.
- Uso de espacio por cuenta (mismo motivo: exigiría dar al portal acceso a Dovecot).
- Rastreo de mensajes del dominio («¿llegó mi correo?»).
- Que el administrador de dominio vea su propia actividad.
