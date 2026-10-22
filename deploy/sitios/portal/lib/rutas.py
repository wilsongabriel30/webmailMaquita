"""Rutas y programas que usa el intermediario. Se leen siempre como `rutas.X` (nunca con
`from rutas import X`), para que las pruebas puedan apuntarlas a una carpeta temporal."""

# Quién puede llamar: el usuario del portal de dominio (y root, para probar a mano).
USUARIO_PORTAL = "maquita-dominio"

# Ayudantes que hacen el trabajo, y el envoltorio cuyos validadores se usan como segunda barrera.
MAQUITA_SITIOS = "/usr/local/sbin/maquita-sitios"
MAQUITA_DNS = "/usr/local/sbin/maquita-dns"
MAQUITA_SUDO = "/usr/local/sbin/maquita-sudo"

# Base de datos del portal: las mismas credenciales (y los mismos permisos mínimos) que él.
ENTORNO_PORTAL = "/etc/maquita-mail/panel-dominio.env"
PSQL = "/usr/bin/psql"
# MAIL_HOST del servidor (el nombre del correo, que nunca puede ser un sitio).
ENTORNO_CORREO = "/opt/maquita-webmail/backend/.env"

# Sitios: metadatos (uno por sitio), carpetas y vhosts de nginx.
META_SITIOS = "/etc/maquita-sitios"
RAIZ_SITIOS = "/srv/sitios"
NGINX_ACTIVOS = "/etc/nginx/sites-enabled"
PREFIJO_VHOST = "sitio-"

# Subidas: el portal deja el archivo en la suya; el intermediario lo pasa a la de maquita-sitios.
# Descargas: al revés; maquita-sitios la deja en subidas/ y el intermediario la pasa a la del portal.
SUBIDAS_PORTAL = "/var/lib/maquita-sitios/subidas-portal"
SUBIDAS = "/var/lib/maquita-sitios/subidas"
# Copias del sitio que controla su dueño (cuentan para el espacio en disco del dominio).
COPIAS = "/var/lib/maquita-sitios/copias"

# v1.11. Secreto del gancho de git de cada sitio (lo escribe maquita-sitios git-gancho; aquí solo se lee) y
# fichas del DNS dinámico (las escribe y lee solo el intermediario).
GANCHOS = "/etc/maquita-sitios/ganchos"
DDNS = "/etc/maquita-sitios/ddns"
# Información del servidor: versión de PHP de serie y puertos de FTP y SFTP (solo se leen).
PHP_BASE = "/etc/maquita-sitios/php-base"
VSFTPD = "/etc/vsftpd.conf"
SSHD = "/etc/ssh/sshd_config"
SSHD_D = "/etc/ssh/sshd_config.d"
# Zonas que sirve maquita-dns (solo se mira si existe la de cada dominio asignado).
ZONAS_DNS = "/etc/maquita-dns"

# Tamaño de las bases de datos de cada sitio.
MARIADB = "/usr/bin/mariadb"
RUNUSER = "/usr/sbin/runuser"
