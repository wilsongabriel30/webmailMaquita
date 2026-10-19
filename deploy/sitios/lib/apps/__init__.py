"""Catálogo de aplicaciones libres instalables en un sitio (además de WordPress y Joomla).

Cada módulo expone:
  NOMBRE, DESCRIPCION, LICENCIA, CATEGORIA, RAIZ_WEB (subcarpeta servida por nginx, o «»), REGLAS_NGINX
  (texto con $socket), instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave)
  → url del administrador (o {"url_admin", "asistente"} si la persona termina el instalador web), y
  opcionalmente BD (None = no usa base de datos), clave_admin(meta, usuario, nueva), cron(meta) y
  terminar(meta) (cierra el instalador web). Las recetas nuevas usan apps/receta.py.
"""

from . import dolibarr, matomo, moodle

CATALOGO = {"moodle": moodle, "dolibarr": dolibarr, "matomo": matomo}

# Las dos de siempre (su instalación está en aplicaciones.py).
BASICAS = {
    "wordpress": {"nombre": "WordPress", "categoria": "Sitios y blogs", "licencia": "GPLv2+",
                  "descripcion": "Sitios, blogs y noticias. El más usado; miles de plantillas y complementos libres. "
                                 "Admite tienda en línea (WooCommerce)."},
    "joomla": {"nombre": "Joomla", "categoria": "Sitios y blogs", "licencia": "GPLv2+",
               "descripcion": "Portales con varias secciones, usuarios registrados y varios idiomas."},
}
CATEGORIAS_PREVIAS = {"moodle": "Educación", "dolibarr": "Gestión y CRM", "matomo": "Estadísticas"}


def lista():
    """Lo que muestra el panel al elegir aplicación."""
    salida = [{"id": k, **v, "modo": "automatica", "verificacion": "suma oficial", "bd": True} for k, v in BASICAS.items()]
    for k, m in CATALOGO.items():
        salida.append({"id": k, "nombre": m.NOMBRE, "descripcion": m.DESCRIPCION, "licencia": m.LICENCIA,
                       "categoria": getattr(m, "CATEGORIA", CATEGORIAS_PREVIAS.get(k, "Otras")),
                       "modo": "asistente" if getattr(m, "ASISTENTE", False) else "automatica",
                       "verificacion": getattr(m, "VERIFICACION", "suma oficial"),
                       "bd": getattr(m, "BD", "mariadb") is not None})
    return salida


def existe(app):
    return app in BASICAS or app in CATALOGO
