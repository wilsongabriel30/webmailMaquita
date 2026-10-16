# Sitios web (panel → Hospedaje → Sitios web)

Publica páginas web en el mismo servidor del correo, cada una aislada: su dominio, su usuario de
sistema, su pool de PHP-FPM, su base de datos y su acceso a archivos. Desde el panel se crea el
sitio, se instala WordPress o Joomla, se activa el FTP seguro y se pide el certificado HTTPS.

## Instalación

```bash
sudo bash deploy/webmail/instalar-app.sh sitios
```

Instala PHP-FPM, MariaDB, vsftpd y WP-CLI (verificado con su SHA-512 oficial), configura el FTP
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
| Certbot / Let's Encrypt | Apache 2.0 | Debian |

## Archivos

- `deploy/sitios/instalar.sh`: instalación de la sección.
- `deploy/sitios/maquita-sitios` y `deploy/sitios/lib/`: ayudante (validación, sitios,
  aplicaciones, acceso, plantillas de nginx y PHP-FPM).
- `admin-panel/backend/app/sitios/router.py`: API `/api/sitios`.
- `admin-panel/frontend/src/pages/Sitios.tsx` y `pages/sitios/`: pantalla.
- Metadatos de cada sitio: `/etc/maquita-sitios/<dominio>.json` (solo root).
