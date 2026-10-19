"""Catálogo de aplicaciones libres instalables en un sitio (además de WordPress y Joomla).

Cada módulo expone:
  NOMBRE, DESCRIPCION, LICENCIA, RAIZ_WEB (subcarpeta servida por nginx, o «»),
  instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave) -> url del admin,
  clave_admin(meta, usuario, nueva), reglas_nginx (texto con $socket), y opcionalmente cron(meta).
"""

from . import dolibarr, matomo, moodle

CATALOGO = {"moodle": moodle, "dolibarr": dolibarr, "matomo": matomo}
