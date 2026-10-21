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
SUBIDAS_PORTAL = "/var/lib/maquita-sitios/subidas-portal"
SUBIDAS = "/var/lib/maquita-sitios/subidas"

# Tamaño de las bases de datos de cada sitio.
MARIADB = "/usr/bin/mariadb"
RUNUSER = "/usr/sbin/runuser"
