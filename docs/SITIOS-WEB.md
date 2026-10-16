# Sitios web (panel → Hospedaje → Sitios web)

Publica páginas web en el mismo servidor del correo, cada una aislada: su dominio, su usuario de
sistema, su pool de PHP-FPM, su base de datos y su acceso a archivos. Desde el panel se crea el
sitio, se instala WordPress o Joomla, se activa el FTP seguro y se pide el certificado HTTPS.

## Instalación

```bash
sudo bash deploy/webmail/instalar-app.sh sitios
```

Instala PHP-FPM, MariaDB, vsftpd, ModSecurity con OWASP CRS, fail2ban y WP-CLI (verificado con su SHA-512 oficial), configura el FTP
solo con cifrado y el SFTP encerrado, y deja el ayudante `/usr/local/sbin/maquita-sitios`.
Es idempotente: se puede repetir.

Si el servidor está detrás de NAT, redirige al servidor los puertos **80 y 443** (web),
**21 y 40000–40100/TCP** (FTP) y **22** (SFTP, si se quiere ofrecer).

## Qué hace cada acción

| Acción | Qué ocurre |
|---|---|
| Nuevo sitio | Usuario de sistema sin shell, carpeta `/srv/sitios/<dominio>/` (`publico/` es lo que se sirve), pool de PHP propio con `open_basedir` y funciones de ejecución desactivadas, vhost de nginx con cabeceras de seguridad. Responde también con `www.` salvo que se desmarque. |
| Instalar WordPress | Paquete `.zip` oficial verificado con la SHA-1 de downloads.wordpress.org, configurado con WP-CLI, cada archivo comprobado contra api.wordpress.org (`wp core verify-checksums`) y paquete de idioma español. XML-RPC cerrado y edición de archivos desde el escritorio desactivada. |
| Instalar Joomla | Paquete completo oficial de la última versión estable, verificado con SHA-256 contra dos fuentes que deben coincidir (notas de la versión y GitHub), instalado con su propia línea de órdenes; la carpeta `installation/` se borra al terminar. |
| FTP | Activa la cuenta del sitio con una clave nueva (se muestra una sola vez). Vale para **FTPS explícito** (puerto 21) y **SFTP** (puerto 22); el FTP sin cifrar se rechaza. La cuenta queda encerrada en la carpeta del sitio y no tiene consola. |
| HTTPS | Certificado de Let's Encrypt por HTTP (el dominio ya debe apuntar a la IP pública del servidor). Si `www` aún no existe en el DNS, se emite solo para el dominio. Renovación automática. En WordPress actualiza la dirección del sitio a `https://`. |
| Dar de baja | Hay que escribir el dominio para confirmar. Copia la base de datos a un `.sql`, la borra junto con su usuario, quita el vhost, el pool y la cuenta, y mueve los archivos a `/srv/sitios-papelera/<dominio>-<fecha>/`. |

| Entrar (WordPress) | Abre el escritorio sin contraseña: el panel pide un vale aleatorio de un solo uso, WordPress guarda solo su huella SHA-256 como transitorio de 60 s y el complemento obligatorio `acceso-panel.php` inicia la sesión y lo borra. Reusar el enlace o inventar uno → 403. |
| Nueva contraseña | Contraseña nueva para el administrador de la aplicación (WordPress con WP-CLI, Joomla con su CLI `user:reset-password`); la anterior deja de valer. |
| Seguridad | Versión, actualizaciones pendientes de núcleo, complementos y temas, e integridad de los archivos del núcleo contra api.wordpress.org. «Actualizar ahora» lo pone todo al día. |

Las contraseñas generadas (administrador de la aplicación, FTP) se muestran una sola vez y no se
guardan en el panel ni en la auditoría. Cada acción queda en la auditoría del panel
(`sitio_crear`, `sitio_app`, `sitio_ftp_*`, `sitio_ssl`, `sitio_borrar`).

## Seguridad

- El panel corre sin privilegios. Todo lo que toca el sistema pasa por `maquita-sudo`, que solo
  admite las subacciones de `maquita-sitios` con la forma exacta de sus argumentos; el ayudante
  vuelve a validarlos. Los textos libres (título del sitio) viajan en base64url.
- Los nombres del correo (`mail.`, `autodiscover.`, `autoconfig.`, `mta-sts.`…) y los que ya usa
  otro vhost del servidor no se pueden usar como sitio.
- Si el alta o la instalación fallan a medias, se deshace lo hecho.

## Protección contra ataques

Por capas, de fuera hacia dentro:

| Capa | Qué hace |
|---|---|
| fail2ban (iptables) | Bloquea la IP en el cortafuegos del sistema: 5 inicios de sesión fallidos de WordPress en 10 min (1 h), 3 peticiones de escáner (`.env`, `.git`, `phpmyadmin`, `phpunit`…) (24 h), 20 respuestas 403/429 en 10 min (1 h); quien reincide 3 veces en un día, una semana (`recidive`). Vigila el registro común `/var/log/nginx/sitios-acceso.log`. |
| Límites de nginx | Por IP: 30 peticiones/s con ráfaga de 80, 50 conexiones simultáneas; inicio de sesión (POST a `wp-login.php` o a la administración de Joomla) 10 por minuto. Exceso → 429. |
| Cortafuegos de aplicación | ModSecurity 3 con OWASP CRS 3.3 en modo bloqueo: inyección SQL, XSS, inclusión de archivos, ejecución de órdenes, escáneres conocidos. WordPress con las excepciones oficiales de CRS; en la administración de Joomla no se aplican las reglas XSS (su editor las dispara). Registro: `/var/log/nginx/sitios-waf.log`. |
| Archivos prohibidos | Ocultos (`.git`, `.env`), copias y volcados (`.bak`, `.sql`, `.log`…), comprimidos en la raíz (`backup.zip`), PHP en carpetas de subidas. WordPress: `xmlrpc.php`, `wp-config.php`, `readme.html`, scripts internos de `wp-includes` y `wp-admin/includes`, `mu-plugins`, `debug.log`. Joomla: `configuration.php`, archivos de ejemplo, PHP en `logs`, `tmp`, `cache`, `cli`, `libraries`. |
| WordPress por dentro | Complemento obligatorio `seguridad-sitio.php` (de root, el sitio no puede tocarlo): sin XML-RPC ni pingbacks, sin contraseñas de aplicación, versión oculta, enumeración de usuarios cerrada (`?author=`, `/wp-json/wp/v2/users`, mapa del sitio de usuarios), mensaje único de error de inicio de sesión, actualizaciones automáticas de todo. `wp-config`: sin editor de archivos, cron del sistema, actualización automática del núcleo, HTTPS obligatorio en el escritorio al activar el certificado. Complemento oficial «Two Factor» para el segundo factor. Sin `hello` ni `akismet`. Enlaces legibles. |
| Joomla por dentro | Carpeta `installation` borrada, prefijo de tablas aleatorio, estadísticas hacia joomla.org apagadas. |
| Aislamiento | Cada sitio con su usuario, su pool de PHP (`open_basedir`, sin `exec`/`system`/`proc_open`…), su base de datos y su FTP encerrado. |
| Tareas programadas | `sitios-cron.timer` cada 5 min (WordPress `cron event run`, Joomla `scheduler:run`), no las visitas. |

Probado con ataques simulados: SQLi, XSS, LFI, RCE y User-Agent de `sqlmap` → 403; búsqueda normal → 200;
15 POST seguidos a `wp-login.php` → 429 desde el 7.º; IP de prueba bloqueada por fail2ban en iptables;
editor de WordPress (REST) y de Joomla guardando contenido con HTML sin bloqueos.

## Licencias

Todo es software libre y nada se redistribuye en este repositorio: se instala desde los
repositorios de Debian o se descarga del origen oficial en el momento de usarlo.

| Componente | Licencia | Origen |
|---|---|---|
| WordPress | GPLv2 o posterior | downloads.wordpress.org |
| Joomla | GPLv2 o posterior | github.com/joomla/joomla-cms (versiones publicadas) |
| WP-CLI | MIT | github.com/wp-cli/wp-cli (versiones publicadas) |
| PHP | Licencia PHP 3.01 | Debian |
| MariaDB | GPLv2 | Debian |
| vsftpd | GPLv2 | Debian |
| OpenSSH (SFTP) | BSD | Debian |
| nginx | BSD-2 | Debian |
| ModSecurity 3 y conector nginx | Apache 2.0 | Debian |
| OWASP CRS 3.3 | Apache 2.0 | Debian |
| fail2ban | GPLv2 | Debian |
| Two Factor (complemento de WordPress) | GPLv2 o posterior | wordpress.org |
| Certbot / Let's Encrypt | Apache 2.0 | Debian |

## Archivos

- `deploy/sitios/instalar.sh`: instalación de la sección.
- `deploy/sitios/maquita-sitios` y `deploy/sitios/lib/`: ayudante (validación, sitios,
  aplicaciones, acceso, seguridad, plantillas de nginx y PHP-FPM).
- `deploy/sitios/wordpress/`: complementos obligatorios de WordPress.
- `deploy/sitios/nginx/`: límites, registro común y cortafuegos de aplicación.
- `deploy/sitios/fail2ban/`: vigilancias y filtros.
- `admin-panel/backend/app/sitios/router.py`: API `/api/sitios`.
- `admin-panel/frontend/src/pages/Sitios.tsx` y `pages/sitios/`: pantalla.
- Metadatos de cada sitio: `/etc/maquita-sitios/<dominio>.json` (solo root).
