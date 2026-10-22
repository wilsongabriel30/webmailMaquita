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
| **Mi sitio web**: crear sitios en sus dominios y subdominios, hasta su cuota | Dar de baja un sitio (sigue publicado mientras tanto) | Sitios de otros dominios o con nombres del correo (`mail.`, `webmail.`, `autoconfig.`…) |
| Instalar una aplicación del catálogo, entrar sin contraseña, contraseña nueva del administrador, revisar y actualizar | Más sitios, disco o espacio de bases (cuota del dominio) | Aplicaciones propias (Python, Node), reglas propias de nginx, tienda |
| HTTPS (Let's Encrypt) y FTP cifrado o SFTP | Versiones o extensiones de PHP que no estén instaladas | Instalar PHP, tocar puertos o el cortafuegos |
| Trabajos de cron, bases de datos adicionales con phpMyAdmin o Adminer | | Alias de dominio de un sitio, buscadores |
| Ajustes y versión de PHP (de las instaladas), archivos de configuración con versiones anteriores | | |
| Subir un paquete propio o migrar un sitio con el respaldo de su base | | |
| Web (v1.10): redirecciones, carpetas con contraseña, páginas de error, hotlinking, IP bloqueadas, optimización y caché | | |
| Cuentas FTP adicionales encerradas en una subcarpeta, administrador de archivos con papelera | | |
| Copias del sitio (crear, descargar, restaurar, borrar), registros, visitas (GoAccess) y disponibilidad | | Comprobaciones del sistema (`disponibilidad-comprobar`, `datos-noche`) |
| Registros DNS de su zona, si la sirve este servidor | Cambiar registros del correo o de los servidores de nombres (se ven, pero protegidos) | Crear o borrar zonas |

Quién administra qué lo decide el superadministrador en el panel general:
**Administración → Administradores de dominio**. Ahí también se confirman las eliminaciones y se
restablece el segundo factor de quien perdió el teléfono.

### Mi sitio web

El portal no tiene privilegios, así que no instala nada por sí mismo: cada operación sobre un sitio
la pide por un socket Unix (`/run/maquita-sitios-portal.sock`) a un intermediario root aparte,
que vuelve a comprobar la sesión y el alcance en la base antes de llamar a `maquita-sitios`. Si
alguien tomara el portal, seguiría sin alcanzar más que lo que puede un administrador de dominio
con sesión válida, sobre sus dominios. El portal comprueba también el alcance antes de llamar
(lo ajeno da 404 sin salir del portal), reenvía la ficha de la sesión y lo audita todo en
`pd_auditoria`, nunca con contraseñas: las que se generan se muestran una sola vez.

Lo subido (paquetes, respaldos de base, archivos editados) se escribe por trozos en
`/var/lib/maquita-sitios/subidas-portal`, con un nombre al azar y un tope, y el intermediario lo
recoge de ahí. La sección se descarga solo al abrirla, y la tarjeta del inicio se pide aparte para
no hacer esperar al resto.

Lo que se descarga (un archivo del sitio, una copia, el informe de visitas) va por el mismo camino al
revés: el intermediario lo hace del usuario del portal y lo deja en esa carpeta con un nombre nuevo
al azar; el portal da un enlace de un solo uso (`/api/sitios/descargas/…`, 10 minutos) que lo
reclama con un rename, lo envía por trozos y lo borra. El portal nunca lee la carpeta de descargas
de `maquita-sitios`, que comparte con el panel general. El informe de GoAccess se sirve con
`Content-Security-Policy: sandbox`. Las copias del sitio cuentan para el disco del dominio.

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
- **Sin dependencias en el navegador.** La pantalla es HTML, CSS y JavaScript a mano (unos 45 KB,
  y unos 55 KB más de «Mi sitio web», que solo se descargan al abrir esa sección), sin paso de
  compilación: carga bien en conexiones lentas y no hay cadena de suministro que vigilar.

Aun si alguien tomara el control del portal, lo más que alcanzaría es lo que ya puede hacer un
administrador de dominio, y todo queda en `pd_auditoria`, que el portal puede escribir pero no
leer ni borrar.

## Instalación

En un servidor instalado con `deploy/webmail/instalar.sh`, todo lo de abajo lo hace un solo instalador
(idempotente; si el servidor tiene sitios web, instala también su intermediario):

```bash
sudo bash deploy/webmail/instalar-app.sh portal-dominio
```

Lo que hace, por si hay que hacerlo a mano en otro tipo de instalación:

Requisitos: el esquema de correo ya instalado (tablas `domain`, `mailbox`, `alias`), Python 3.11+,
`openssl`, nginx y PostgreSQL. Se asume el repositorio en `/opt/maquita-webmail`.

```bash
# 1. Usuario del sistema, sin shell ni directorio propio
useradd --system --no-create-home --shell /usr/sbin/nologin maquita-dominio

# 2. Entorno de Python
cd /opt/maquita-webmail/panel-dominio/backend
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# 3. Base de datos: tablas (como dueño de la base), usuario del portal y permisos
psql -d maildb -f ../deploy/esquema.sql -f ../deploy/esquema-2-autonomia.sql
psql -d maildb -c "CREATE ROLE panel_dominio LOGIN PASSWORD 'una-clave-larga-al-azar'"
psql -d maildb -f ../deploy/permisos.sql -f ../deploy/permisos-2-autonomia.sql

# 3b. Carpeta de logos, compartida con el panel general y legible por el webmail
groupadd --system maquita-marca
usermod -aG maquita-marca maquita-dominio && usermod -aG maquita-marca maquita-admin
mkdir -p /opt/maquita-webmail/uploads/branding/empresas
chgrp -R maquita-marca /opt/maquita-webmail/uploads/branding/empresas && chmod 2775 /opt/maquita-webmail/uploads/branding/empresas

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

## Sitios web desde el portal: el intermediario

El portal no tiene `sudo` ni debe tenerlo. Lo que toca el sistema en «Mi sitio web» lo hace
`maquita-sitios-portal` (código en `deploy/sitios/portal/`), un programa de root que systemd arranca
por cada conexión a `/run/maquita-sitios-portal.sock` (grupo `maquita-dominio`, modo 0660). No se fía
del portal: comprueba con `SO_PEERCRED` que llama `maquita-dominio`, vuelve a verificar la sesión en
la base con las credenciales de `panel-dominio.env`, solo acepta su lista de órdenes sobre sitios de
los dominios asignados y pasa cada orden por el validador de `maquita-sudo` antes de ejecutarla.

Se instala solo, con `deploy/sitios/instalar.sh`, cuando en el servidor están a la vez los sitios web
y el portal. Si el portal se instala después, o en un servidor que ya tenía los dos:

```bash
sudo bash deploy/sitios/portal/instalar.sh --pendiente   # qué falta, sin tocar nada
sudo bash deploy/sitios/portal/instalar.sh               # o el ajuste 58: deploy/ajustes/aplicar-ajustes.sh --aplicar
```

Deja: el programa y sus módulos (`/usr/local/sbin`, `/usr/local/lib/maquita-sitios-portal`), el
socket y su servicio, la carpeta de subidas del portal (`/var/lib/maquita-sitios/subidas-portal`,
`maquita-dominio` 0700) con su `ReadWritePaths` en la unidad del portal (archivo complementario en
`maquita-panel-dominio.service.d/`), la ruta `/api/sitios` en el nginx del portal (520 MB y 1200 s;
el resto sigue con 64 KB y 30 s; respaldo en `/var/backups/maquita-sitios-portal/`) y la tabla de
cuotas. Si la base está en otro equipo, aplica allí, como dueño de la base:

```bash
psql -d maildb -f panel-dominio/deploy/esquema-4-sitios.sql -f panel-dominio/deploy/permisos-4-sitios.sql
```

Las cuotas (sitios, disco y bases por dominio; por defecto 1 sitio, 2 GB y 1 GB) se fijan en el panel
general, al editar al administrador de dominio. Cada petición queda en el registro del sistema con la
marca `MAQUITA_SITIOS_PORTAL` (`journalctl -t maquita-sitios-portal`).

## Variables de entorno

| Variable | Por defecto | Para qué |
|---|---|---|
| `PD_DB_PASS` | (obligatoria) | Clave del usuario `panel_dominio` |
| `PD_DB_HOST`, `PD_DB_PORT`, `PD_DB_NAME`, `PD_DB_USER` | `127.0.0.1`, `5432`, `maildb`, `panel_dominio` | Conexión |
| `PD_DB_SSL` | (vacío) | `require` si la base de datos está en otro equipo |
| `PD_HORAS_SESION` | `8` | Duración de una sesión |
| `PD_MINUTOS_SOPORTE` | `60` | Duración de una sesión de soporte del superadministrador (de 5 a 240; ver `docs/ENTRADA-OIDC-Y-SOPORTE.md`) |
| `PD_TOTP_OBLIGATORIO` | `1` | Exigir segundo factor |
| `PD_EMISOR` | `Portal de dominio` | Nombre que muestra la aplicación de códigos |
| `PD_DIR_MARCA` | `/opt/maquita-webmail/uploads/branding/empresas` | Carpeta de logos e iconos |
| `PD_MARCA_MAX_KB` | `512` | Peso máximo de una imagen |
| `PD_SELECTORES_DKIM` | `default,dkim,mail,selector1,selector2` | Selectores que consulta la verificación DNS |
| `PD_SOCKET_SITIOS` | `/run/maquita-sitios-portal.sock` | Socket del intermediario de los sitios |
| `PD_DIR_SUBIDAS` | `/var/lib/maquita-sitios/subidas-portal` | Carpeta donde el portal deja lo subido |
| `PD_SUBIDA_MAX_MB` | `512` | Peso máximo de un paquete o de un respaldo de base |
| `PD_ARCHIVO_MAX_KB` | `1024` | Peso máximo de un archivo de configuración editado en pantalla |
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
