"""Ajustes de «Mi sitio web». Todo llega del entorno."""

import os

# Socket del intermediario root (maquita-sitios-portal.socket). Sin él, los sitios no están instalados.
SOCKET = os.getenv("PD_SOCKET_SITIOS", "/run/maquita-sitios-portal.sock")

# Única carpeta del disco, además de los logos, que el portal puede escribir. El intermediario
# recoge de aquí los paquetes y los archivos editados.
DIR_SUBIDAS = os.getenv("PD_DIR_SUBIDAS", "/var/lib/maquita-sitios/subidas-portal")
SUBIDA_MAX_BYTES = int(os.getenv("PD_SUBIDA_MAX_MB", "512")) * 1024 * 1024
# Un archivo de configuración editado en pantalla (wp-config.php, .env, .user.ini…).
ARCHIVO_MAX_BYTES = int(os.getenv("PD_ARCHIVO_MAX_KB", "1024")) * 1024
# Lo subido y no usado (subida cortada, respaldo sin paquete) se borra pasado este tiempo.
MINUTOS_SUBIDA = int(os.getenv("PD_MINUTOS_SUBIDA", "120"))
