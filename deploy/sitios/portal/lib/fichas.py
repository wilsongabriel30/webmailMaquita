"""Fichas de API del portal («mqd_…»): el intermediario las comprueba en la base igual que una sesión, y además su
alcance, sin fiarse de lo que ya comprobó el portal.

Una ficha la crea un administrador de dominio desde el portal (con su segundo factor), vale hasta su fecha de
caducidad o hasta que la revoque, y solo se guarda su hash. Su alcance es una lista:
  «lectura»  ver (las órdenes de LECTURA de abajo)
  «sitios»   además, las acciones sobre sus sitios web (todas las demás órdenes que no son de DNS)
  «dns»      además, cambiar los registros de sus zonas DNS
Las órdenes que dan acceso directo (entrar al escritorio de la aplicación o a una base, descargar copias o
archivos) no son de lectura: piden «sitios».
"""

import hashlib

import bd
from errores import ErrorPortal

PREFIJO = "mqd_"

SQL_FICHA = """
SELECT json_build_object(
         'id', a.id, 'usuario', a.username, 'activa', a.active,
         'cambiar_clave', a.must_change_password, 'totp', a.totp_enabled,
         'ficha_api', f.id, 'alcances', to_json(f.alcances),
         'dominios', COALESCE((SELECT json_agg(d.domain ORDER BY d.domain)
                                 FROM pd_admin_dominios p JOIN domain d ON d.domain = p.domain
                                WHERE p.admin_id = a.id), '[]'::json))
  FROM pd_fichas_api f JOIN pd_admins a ON a.id = f.admin_id
 WHERE f.token_hash = :'ficha' AND f.revoked_at IS NULL AND f.expires_at > NOW()
 LIMIT 1;
"""

LECTURA = frozenset({
    "listar", "catalogo", "revisar", "tareas", "tarea-registro", "bases", "avanzado", "avanzado-ver", "php-estado",
    "dns-ver", "web", "ftp-cuentas", "registros", "estadisticas", "disponibilidad", "copias", "archivos-listar",
    "archivos-papelera", "bases-usuarios", "waf", "waf-bloqueos", "ssh-claves",
    "propia-estado", "git-estado", "git-credencial", "recursos", "servidor-info", "ddns-ver",
})


def es_ficha(ficha):
    return isinstance(ficha, str) and ficha.startswith(PREFIJO)


def buscar(ficha):
    """La fila de la ficha (con su administrador y sus dominios) o None; sin la tabla, None."""
    try:
        return bd.consultar(SQL_FICHA, {"ficha": hashlib.sha256(ficha.encode()).hexdigest()}, tabla="pd_fichas_api")
    except bd.FaltaTabla:
        return None


def area(orden):
    return "dns" if orden.startswith("dns-") else "sitios"


def exigir_alcance(admin, orden):
    """403 si la ficha de API no alcanza para esa orden. Una sesión del portal (sin «alcances») pasa siempre."""
    alcances = admin.get("alcances")
    if alcances is None:
        return
    if not isinstance(alcances, list):
        raise ErrorPortal(403, "Ficha de API sin alcance")
    if area(orden) in alcances:
        return
    if orden in LECTURA and "lectura" in alcances:
        return
    raise ErrorPortal(403, "La ficha de API no tiene permiso para esta acción")
