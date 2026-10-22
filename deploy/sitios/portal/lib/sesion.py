"""Quién es y qué le toca: la sesión se comprueba otra vez en la base, sin fiarse del portal.

Las mismas condiciones que app/sesion.py del portal: ficha (como hash) no revocada ni vencida, cuenta
activa, sin la contraseña inicial y con segundo factor si es obligatorio. Los dominios salen de
pd_admin_dominios en cada petición: quitar uno surte efecto al instante.
"""

import hashlib
import json

import bd
import fichas
from errores import ErrorPortal

SQL_SESION = """
SELECT json_build_object(
         'id', a.id, 'usuario', a.username, 'activa', a.active,
         'cambiar_clave', a.must_change_password, 'totp', a.totp_enabled,
         'dominios', COALESCE((SELECT json_agg(d.domain ORDER BY d.domain)
                                 FROM pd_admin_dominios p JOIN domain d ON d.domain = p.domain
                                WHERE p.admin_id = a.id), '[]'::json))
  FROM pd_sesiones s JOIN pd_admins a ON a.id = s.admin_id
 WHERE s.token_hash = :'ficha' AND s.revoked_at IS NULL AND s.expires_at > NOW()
 LIMIT 1;
"""

SQL_CUOTAS = """
SELECT COALESCE(json_object_agg(domain, json_build_object(
         'max_sitios', max_sitios, 'disco_mb', disco_mb, 'bases_mb', bases_mb)), '{}'::json)
  FROM pd_cuotas_sitio
 WHERE domain IN (SELECT json_array_elements_text(:'dominios'::json));
"""

SQL_PORTALES = "SELECT COALESCE(json_agg(lower(host)), '[]'::json) FROM portal_empresa;"
SQL_DOMINIOS = "SELECT COALESCE(json_agg(lower(domain)), '[]'::json) FROM domain;"


def _totp_obligatorio(env):
    return env.get("PD_TOTP_OBLIGATORIO", "1").lower() not in ("0", "no", "false")


def verificar(ficha):
    """Devuelve {"id", "usuario", "dominios"} o lanza ErrorPortal(403)."""
    if not isinstance(ficha, str) or not 20 <= len(ficha) <= 200 or not ficha.isascii():
        raise ErrorPortal(403, "Sesión cerrada o vencida")
    if fichas.es_ficha(ficha):
        return _de_ficha(fichas.buscar(ficha))
    fila = bd.consultar(SQL_SESION, {"ficha": hashlib.sha256(ficha.encode()).hexdigest()})
    if not fila or not fila.get("activa"):
        raise ErrorPortal(403, "Sesión cerrada o vencida")
    if fila.get("cambiar_clave"):
        raise ErrorPortal(403, "Cambia tu contraseña inicial antes de continuar")
    if _totp_obligatorio(bd.entorno_portal()) and not fila.get("totp"):
        raise ErrorPortal(403, "Activa el segundo factor antes de continuar")
    return {"id": fila["id"], "usuario": fila["usuario"],
            "dominios": [str(d).lower() for d in fila.get("dominios") or []]}


def _de_ficha(fila):
    """Una ficha de API vale con las mismas condiciones de la cuenta que una sesión, y lleva su alcance."""
    if not fila or not fila.get("activa") or fila.get("cambiar_clave"):
        raise ErrorPortal(403, "Ficha de API revocada, vencida o de una cuenta desactivada")
    if _totp_obligatorio(bd.entorno_portal()) and not fila.get("totp"):
        raise ErrorPortal(403, "Activa el segundo factor antes de continuar")
    return {"id": fila["id"], "usuario": fila["usuario"], "ficha_api": fila.get("ficha_api"),
            "alcances": [str(a) for a in fila.get("alcances") or []],
            "dominios": [str(d).lower() for d in fila.get("dominios") or []]}


def cuotas_guardadas(dominios):
    """{dominio: {max_sitios, disco_mb, bases_mb}} de pd_cuotas_sitio; sin la tabla, vacío."""
    try:
        return bd.consultar(SQL_CUOTAS, {"dominios": json.dumps(sorted(dominios))}, tabla="pd_cuotas_sitio") or {}
    except bd.FaltaTabla:
        return {}


def nombres_de_portales():
    """Nombres de servidor de los portales por empresa (portal_empresa): nunca pueden ser un sitio."""
    try:
        return set(bd.consultar(SQL_PORTALES, tabla="portal_empresa") or [])
    except bd.FaltaTabla:
        return set()


def dominios_del_servidor():
    return set(bd.consultar(SQL_DOMINIOS) or [])
