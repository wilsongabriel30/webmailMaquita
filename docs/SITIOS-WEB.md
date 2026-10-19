# Sitios web (panel → Hospedaje → Sitios web)

Publica páginas web en el mismo servidor del correo, cada una aislada: su dominio, su usuario de
sistema, su pool de PHP-FPM, su base de datos y su acceso a archivos. Desde el panel se crea el
sitio, se instala una aplicación del catálogo (29, ver «Catálogo de aplicaciones»), se
crean bases de datos adicionales, se activa el FTP seguro y se pide el certificado HTTPS.

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
| Instalar Moodle | Paquete oficial de packaging.moodle.org (última rama estable con su SHA-256 publicada), instalado con `admin/cli/install.php`. Se sirve desde `public/` (el código y `config.php` quedan fuera de la web); `moodledata` va en la carpeta privada. Tarda unos 3 minutos. |
| Instalar Dolibarr | Última versión estable de GitHub, paquete de SourceForge verificado con su MD5 publicado, instalado con sus pasos de línea de órdenes (`install/step1`, `step2`, `step5`). Se sirve desde `htdocs/`; documentos en la carpeta privada; `install.lock` puesto y `/install/` y `/conf/` cerrados en nginx. |
| Instalar Matomo | Paquete oficial adjunto a la versión de GitHub (SHA-256 de GitHub). Matomo no tiene instalador por línea de órdenes: el ayudante recorre su asistente web desde el propio servidor. IP de las visitas anonimizada; solo se ejecutan los PHP de entrada (reglas oficiales de matomo-nginx). |
| Tienda (WordPress) | WooCommerce desde wordpress.org, comprobado con `wp plugin verify-checksums` y en español. Sustituye a PrestaShop: su versión 9 no tiene paquete libre descargable y la 8 no admite PHP 8.4. |
| Bases | Hasta 10 bases adicionales por sitio, **MariaDB o PostgreSQL**, para aplicaciones propias. Cada una con su usuario, que solo entra desde este servidor y solo a su base; la contraseña se muestra una vez. Al borrar una base se copia antes a `<carpeta privada>/<base>.sql` (del dueño del sitio, descargable por SFTP); al dar de baja el sitio, las copias van a la papelera. |
| Herramientas | **phpMyAdmin** (paquete de Debian) y **Adminer** (versión de GitHub verificada) en `/herramientas/phpmyadmin/` y `/herramientas/adminer/` del panel (8443), con su misma protección. Pool de PHP propio (`herramientas-bd`, `open_basedir`, sin ejecución de órdenes). Adminer solo ofrece los servidores de este equipo (complemento `login-servers`): no sirve de puente hacia otras máquinas. |
| FTP | Activa la cuenta del sitio con una clave nueva (se muestra una sola vez). Vale para **FTPS explícito** (puerto 21) y **SFTP** (puerto 22); el FTP sin cifrar se rechaza. La cuenta queda encerrada en la carpeta del sitio y no tiene consola. |
| HTTPS | Certificado de Let's Encrypt por HTTP (el dominio ya debe apuntar a la IP pública del servidor). Si `www` aún no existe en el DNS, se emite solo para el dominio. Renovación automática. En WordPress actualiza la dirección del sitio a `https://`. |
| Dar de baja | Hay que escribir el dominio para confirmar. Copia la base de datos a un `.sql`, la borra junto con su usuario, quita el vhost, el pool y la cuenta, y mueve los archivos a `/srv/sitios-papelera/<dominio>-<fecha>/`. |

| Entrar (WordPress) | Abre el escritorio sin contraseña: el panel pide un vale aleatorio de un solo uso, WordPress guarda solo su huella SHA-256 como transitorio de 60 s y el complemento obligatorio `acceso-panel.php` inicia la sesión y lo borra. Reusar el enlace o inventar uno → 403. |
| Nueva contraseña | Contraseña nueva para el administrador de la aplicación (WordPress con WP-CLI, Joomla con su CLI `user:reset-password`); la anterior deja de valer. |
| Seguridad | Versión, actualizaciones pendientes de núcleo, complementos y temas, e integridad de los archivos del núcleo contra api.wordpress.org. «Actualizar ahora» lo pone todo al día. En Moodle, Dolibarr y Matomo muestra la versión instalada (se actualizan desde su propia administración). |

Las contraseñas generadas (administrador de la aplicación, FTP) se muestran una sola vez y no se
guardan en el panel ni en la auditoría. Cada acción queda en la auditoría del panel
(`sitio_crear`, `sitio_app`, `sitio_app_terminar`, `sitio_propia_*`, `sitio_tienda`, `sitio_base_crear`, `sitio_base_borrar`,
`sitio_base_entrar`, `sitio_avanzado_*`, `sitio_alias`, `sitio_cron_*`, `sitio_paquete`, `sitio_migracion`, `sitio_ftp_*`, `sitio_ssl`, `sitio_borrar`).

La ruta `/api/sitios` del panel tiene un tiempo de espera de 20 minutos (fragmento
`snippets/herramientas-bd.conf`): las instalaciones largas (Moodle) superan los 120 s del resto de `/api/`.

## Catálogo de aplicaciones («Instalar aplicación»)

Cada aplicación es un archivo en `deploy/sitios/lib/apps/` (receta) que el ayudante descubre solo: basta
añadir el archivo con `NOMBRE`, `DESCRIPCION`, `LICENCIA`, `CATEGORIA`, `VERIFICACION`, `RAIZ_WEB`, `BD`,
`REGLAS_NGINX` e `instalar()`; las herramientas comunes están en `apps/receta.py`. El panel las muestra por
categorías y con buscador (`GET /api/sitios/catalogo`).

| Categoría | Aplicaciones |
|---|---|
| Sitios y blogs | WordPress, Joomla, Drupal, Backdrop CMS, Concrete CMS, Grav |
| Wikis y documentación | MediaWiki, DokuWiki |
| Foros y comunidad | phpBB, MyBB, Elgg |
| Educación | Moodle, Chamilo |
| Archivos y galerías | Nextcloud, Omeka S, Piwigo, ProjectSend |
| Gestión y CRM | Dolibarr, EspoCRM, SuiteCRM |
| Soporte y proyectos | GLPI, osTicket, Kanboard |
| Encuestas y marketing | LimeSurvey, Mautic |
| Tienda en línea | OpenCart (y WooCommerce sobre WordPress) |
| Estadísticas y utilidades | Matomo, FreshRSS, YOURLS |

- **Verificación** (por orden de preferencia): suma publicada por el proyecto, firma GPG del proyecto
  (MediaWiki), SHA-256 que calcula GitHub del adjunto o, si el proyecto no publica nada, solo HTTPS de su
  origen oficial (se anota la suma del archivo instalado). Una descarga que no coincide cancela la instalación.
- Todas se instalan solas (sin asistente web). Si algo falla, el sitio vuelve a quedar vacío y sin base, y el
  vhost se publica solo si nginx lo acepta (si lo rechaza se deja el anterior: nunca se rompe el resto de sitios).
- Omeka S y ProjectSend entran con el **correo** del administrador (el panel lo muestra como usuario).
- Notas: OpenCart y Mautic quedan en inglés (sus instaladores no traen español); Chamilo ocupa ~1,5 GB;
  SuiteCRM tiene una excepción del cortafuegos solo para el campo `query` de `/api/graphql`; Nextcloud
  admite WebDAV en todo el sitio y no analiza el cuerpo en `remote.php`/`public.php` (subidas grandes).
- Pendiente: al activar HTTPS o añadir alias no se actualizan las direcciones que guardan algunas
  aplicaciones (Nextcloud `trusted_domains`, Elgg `wwwroot`, ProjectSend `APP_URL`); cambiarlas en su
  administración o en «Avanzado».

## Configuración avanzada («Avanzado» de cada sitio)

| Pestaña | Qué permite |
|---|---|
| nginx | Reglas propias que se incluyen dentro del `server {}` del sitio (`/etc/maquita-sitios/nginx-extra/<dominio>.conf`). Se rechazan `include`, `load_module`, `lua`, `perl`, `js_*`, `ssl_certificate*` y `root`/`alias` fuera de la carpeta del sitio. Se comprueba con `nginx -t`; si falla, se deja la versión anterior. |
| PHP | Memoria, subida, tiempos, campos por formulario y mostrar errores, con límites; se aplican al pool del sitio y se comprueban con `php-fpm -t`. |
| Archivos | Leer y editar cualquier archivo de texto de `publico/` (hasta 1 MB); se guarda con su dueño y permisos, y en los `.php` se avisa si la sintaxis falla. |
| Versiones | Antes de cada cambio se copia lo anterior a `/var/lib/maquita-sitios/versiones/<dominio>/` (últimas 50); «Restaurar» vuelve a cualquiera (y guarda antes lo actual). |

«Copiar sin contraseñas» copia al portapapeles el texto con claves, contraseñas y sales tachadas (`***`),
para consultarlo con otra persona sin exponerlas. No sale del navegador.

## Subdominios y dominios alias («Nuevo sitio» y «Dominios»)

- **Subdominio**: «Nuevo sitio» → «Subdominio» (p. ej. `blog` + `midominio.org`). Es un sitio independiente,
  con su propia aplicación, base, FTP y certificado; por defecto sin `www.`.
- **Registro DNS automático**: si el nombre pertenece a una zona de «Zonas DNS», el panel crea el registro A hacia
  la IP web del servidor (o avisa si ya existía); si el DNS está en otro proveedor, indica a qué IP apuntarlo. Al dar de
  baja el sitio, el registro DNS no se borra (puede usarse para otra cosa).
- **Dominios alias** («Dominios» de cada sitio): hasta 10 dominios más que muestran el mismo sitio (con su `www.` si el
  sitio lo tiene). No pueden ser de otro sitio ni del correo o el panel. Si el sitio tiene HTTPS, el certificado se
  amplía con los alias que ya apuntan aquí; los que aún no, quedan solo por HTTP (se ve en la ventana) hasta volver
  a guardarlos.

## Trabajos de cron («Cron» de cada sitio)

Como el cron de cPanel: hasta 20 trabajos por sitio con horario de cinco campos (`*/15 * * * *`, `0 3 * * 0`,
`@daily`…; si se indica día del mes y día de la semana a la vez se rechaza, porque cron y systemd los combinan
distinto). Cada trabajo es un temporizador de systemd (`sitio-<usuario>-cron-<id>`) que ejecuta la orden con
`/bin/sh`, el usuario del sitio y desde su carpeta pública, con el mismo encierro que las aplicaciones propias (solo
escribe en `publico` y la carpeta privada, sin privilegios, 512 MB, una CPU, una hora como máximo). La salida va a
`registros/cron-<id>.log` (rotado con los demás registros) y el panel muestra la última ejecución, el resultado, la
próxima, «Ejecutar ahora» y «Salida». Al dar de baja el sitio se quitan sus temporizadores.

## Subir paquete y migrar desde otro hosting («Subir paquete»)

En un sitio vacío, hasta 512 MB:
- **Paquete propio** (.zip o .tar.gz de una aplicación que no está en el catálogo): se extrae con las mismas
  protecciones que las descargas (sin rutas fuera del destino ni enlaces peligrosos; máximo 3 GB y 150 000 archivos
  descomprimidos), se detecta la carpeta pública (`public/`, `htdocs/`, `web/`…) y, si se pide, se prepara una base
  MariaDB vacía cuyos datos se muestran una vez para el instalador de la aplicación.
- **Migración** (archivos + respaldo `.sql` o `.sql.gz` de la base): la base se importa **con el usuario del sitio**,
  que solo entra a su base; se quitan antes `CREATE DATABASE`, `USE` y los `DEFINER`, así un respaldo no puede tocar
  otras bases. Después se reconoce la aplicación y se le pone la conexión nueva: WordPress (`wp-config.php` y la
  dirección vieja reemplazada por la nueva en toda la base con `wp search-replace`, respetando datos serializados;
  el sitio pasa a ser «WordPress» en el panel, con «Entrar» y «Seguridad»), Joomla (`configuration.php`, rutas de
  registros y temporales) o `.env` (Laravel y similares). Si algo falla, el sitio vuelve a quedar vacío y sin base.

## Entrada directa a las bases («Bases» → «Entrar con phpMyAdmin / Adminer»)

Abre la herramienta ya conectada a esa base, sin escribir contraseña. Las contraseñas de las bases no se guardan:
cada «Entrar» crea un **usuario temporal** (`pv_…`) con permisos solo sobre esa base que vence a las 2 horas
(en PostgreSQL, miembro del dueño con `SET ROLE` al dueño, así lo que cree no queda huérfano) y un **vale de un solo
uso** de 60 s que lee `/herramientas/adminer/entrar.php`. phpMyAdmin usa su autenticación `signon` (servidor 9,
`/etc/phpmyadmin/conf.d/maquita-entrada.php`); en Adminer un complemento acepta el vale en lugar de su ficha de
sesión. El trabajo programado de los sitios borra los usuarios vencidos. Queda en la auditoría (`sitio_base_entrar`).

## Aplicaciones propias («Aplicación propia» y «Gestionar»)

Para el código de la propia institución, en un sitio sin otra aplicación.

| Tipo | Cómo se publica |
|---|---|
| Estática | HTML/CSS/JS (también React, Vue o Svelte ya compilados). Sin repositorio se sube por SFTP a `publico`; con repositorio git se clona en `app` y se publica la carpeta indicada (p. ej. `dist`). Opción «una sola página»: las rutas desconocidas van a `index.html`. Sin PHP. |
| Python | WSGI (Flask, Django: gunicorn) o ASGI (FastAPI, Starlette: uvicorn). Entorno virtual propio en `entorno/`, `requirements.txt` al desplegar. Entrada `módulo:objeto` (p. ej. `app:app`, `proyecto.wsgi:application`). |
| Node.js | `npm ci --omit=dev` (o `npm install` sin `package-lock.json`); entrada un archivo `.js` o `npm start`. |

- **Código**: por SFTP en `app/` o clonado de un repositorio git **público** por HTTPS (sin usuario ni clave
  en la dirección). «Desplegar» hace `git pull --ff-only`, instala dependencias y reinicia; sin repositorio,
  solo dependencias y reinicio. Sin código todavía, queda una aplicación de ejemplo.
- **Servicio** `sitio-<usuario>` de systemd con el usuario del sitio. La aplicación escucha en `HOST:PORT`
  (127.0.0.1 y un puerto interno 20000–29999 que da el panel) y nginx la publica en el dominio, con HTTPS,
  límites, cortafuegos de aplicación y WebSocket. Al arrancar se exige una respuesta HTTP real (gunicorn abre
  el puerto aunque la aplicación no cargue).
- **Encierro**: `ProtectSystem=strict` (solo escribe en `app/` y `tmp/`), sin privilegios ni capacidades,
  `/etc/maquita-sitios` y la papelera inaccesibles, `SocketBindAllow`/`SocketBindDeny` (solo puede abrir sus
  puertos), memoria 768 MB, CPU 150 %, 256 tareas. Probado: no lee `/etc/shadow` ni la configuración, no escribe
  en `publico` y no abre otros puertos.
- **Variables de entorno** desde «Gestionar»: `/etc/maquita-sitios/entorno/<dominio>.env` (solo root; systemd
  las entrega). Los valores no vuelven al panel ni van a la auditoría ni al registro de `maquita-sudo`.
  `PORT`, `HOST`, `PUERTO_PUBLICO`, `HOME`, `PATH`, `NODE_ENV` y `PYTHONUNBUFFERED` las pone el panel.
- **Puerto público** opcional (servicios que no son web): 1024–65535, ni reservados ni en uso. La aplicación lo
  recibe en `PUERTO_PUBLICO` y el cortafuegos lo abre mientras exista (ver `docs/CORTAFUEGOS.md`).
- **Registros**: las últimas 100 líneas de `journalctl` en «Gestionar».
- **Quitar aplicación**: para el servicio, cierra su puerto, borra el entorno virtual y deja el código en
  `/srv/sitios-papelera/<dominio>-app-<fecha>/`; el sitio vuelve a la página con PHP. Dar de baja el sitio hace
  lo mismo.
- Bases de datos: las adicionales del botón «Bases» (MariaDB o PostgreSQL), con su cadena en una variable.

Todos los sitios: nginx solo sigue un enlace simbólico si apunta a algo del mismo dueño
(`disable_symlinks if_not_owner`), para que un enlace subido por SFTP o traído en un repositorio no pueda
mostrar archivos de otro sitio.

## Seguridad

- El panel corre sin privilegios. Todo lo que toca el sistema pasa por `maquita-sudo`, que solo
  admite las subacciones de `maquita-sitios` con la forma exacta de sus argumentos; el ayudante
  vuelve a validarlos. Los textos libres (título del sitio) viajan en base64url.
- Los nombres del correo (`mail.`, `autodiscover.`, `autoconfig.`, `mta-sts.`…) y los que ya usa
  otro vhost del servidor no se pueden usar como sitio.
- Si el alta o la instalación fallan a medias, se deshace lo hecho.

## Buscadores e IA (botón «Buscadores» de cada sitio)

- **Revisión** como la haría un buscador (`curl --resolve` contra el propio servidor, con el mismo nombre y
  certificado): portada, `robots.txt` que no bloquee, mapa del sitio (`/sitemap.xml` o `/wp-sitemap.xml`),
  `llms.txt` (descripción para asistentes de IA), datos schema.org `Organization`, `meta description`,
  ausencia de `noindex` y HTTPS.
- **IndexNow** (Bing, Yandex, Seznam, Naver…): cada sitio tiene su clave (`<clave>.txt` en la raíz). «Avisar
  ahora» manda la portada y las direcciones del mapa del sitio; WordPress además avisa solo al publicar
  (complemento obligatorio `visibilidad-sitio.php`).
- **Google** no admite avisos: el panel pone en la zona DNS el TXT de verificación de Search Console (si la
  zona se administra en este servidor); luego se verifica y se envía el mapa del sitio desde Search Console.
- **WordPress**: visible para buscadores (`blog_public`), enlaces legibles, lema por defecto «Sitio web de …»
  (sin él no hay descripción), datos schema.org de la institución en la portada y `meta description`.
- **Identidad**: «Aplicar en todo» de Personalización actualiza también `llms.txt` y los datos schema.org de
  los sitios con WordPress o Joomla (sin tocar su contenido; el lema de WordPress solo si era el de fábrica).

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
| Moodle, Dolibarr y Matomo | Perfil «aplicación» del cortafuegos: CRS completo salvo las reglas XSS en POST (los editores de contenido las disparan) y admitiendo `text/plain` (lo usa Moodle). Moodle con límite de inicio de sesión; ficheros internos de cada aplicación cerrados en nginx. |
| Tareas programadas | `sitios-cron.timer` cada 5 min (WordPress `cron event run`, Joomla `scheduler:run`, Moodle `admin/cli/cron.php`, Matomo `core:archive`), no las visitas. |

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
| Moodle | GPLv3 | packaging.moodle.org |
| Dolibarr | GPLv3 o posterior | sourceforge.net/projects/dolibarr (enlazado desde dolibarr.org) |
| Matomo | GPLv3 o posterior | github.com/matomo-org/matomo (versiones publicadas) |
| WooCommerce | GPLv3 | wordpress.org |
| Gunicorn (aplicaciones Python) | MIT | PyPI, en el entorno de cada aplicación |
| Uvicorn (aplicaciones ASGI) | BSD-3 | PyPI, en el entorno de cada aplicación |
| Node.js y npm | MIT / Artistic 2.0 | Debian o el ya instalado |
| Git | GPLv2 | Debian |
| PostgreSQL | Licencia PostgreSQL (tipo BSD) | Debian |
| phpMyAdmin | GPLv2 | Debian |
| Adminer y su complemento `login-servers` | Apache 2.0 o GPLv2 (a elegir) | github.com/vrana/adminer (versiones publicadas) |

## Archivos

- `deploy/sitios/instalar.sh`: instalación de la sección.
- `deploy/sitios/maquita-sitios` y `deploy/sitios/lib/`: ayudante (validación, sitios,
  aplicaciones, acceso, seguridad, plantillas de nginx y PHP-FPM).
- `deploy/sitios/lib/propias.py` y `propias_servicio.py`: aplicaciones propias (servicio, dependencias, puertos).
- `admin-panel/backend/app/sitios/propias.py`: API `/api/sitios/<dominio>/propia`.
- `deploy/sitios/lib/apps/`: catálogo (un archivo por aplicación, descubierto solo), `receta.py` (herramientas comunes) y descargas verificadas; `lib/bases.py`: bases adicionales; `lib/acceso_bd.py`: entrada directa.
- `deploy/sitios/lib/alias.py`, `tareas.py`, `paquete.py` y `migracion.py`: alias, cron, paquetes propios y migraciones.
- `admin-panel/backend/app/sitios/dominios.py`, `tareas.py` y `paquete.py`: API de alias y DNS, cron y subidas.
- `deploy/sitios/herramientas/`: phpMyAdmin y Adminer del panel.
- `deploy/sitios/wordpress/`: complementos obligatorios de WordPress.
- `deploy/sitios/nginx/`: límites, registro común y cortafuegos de aplicación.
- `deploy/sitios/fail2ban/`: vigilancias y filtros.
- `admin-panel/backend/app/sitios/router.py`: API `/api/sitios`.
- `admin-panel/frontend/src/pages/Sitios.tsx` y `pages/sitios/`: pantalla.
- Metadatos de cada sitio: `/etc/maquita-sitios/<dominio>.json` (solo root).
