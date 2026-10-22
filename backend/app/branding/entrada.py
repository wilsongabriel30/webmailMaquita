"""Pantalla de entrada personalizada por dominio, sin configurar nada.

Quien abre `mail.<dominio>` o `webmail.<dominio>` ve una pantalla de entrada pensada para
su empresa: el campo de correo sugiere `usuario@<dominio>`, aparece «Correo de <empresa>»
bajo el logo, «¿Olvidaste tu contraseña?» dice a quién escribir y el color es el de su marca.

Todo sale de lo que ya existe: la tabla `domain` (qué dominios atiende el servidor),
`portal_empresa` (nombres de servidor propios), `branding_empresa` (marca de cada empresa) y
los administradores del dominio (`pd_admins` del panel de dominio o `domain_admins`).

EL NOMBRE DE SERVIDOR NO ES DE FIAR
La cabecera Host la escribe quien hace la petición. Se normaliza (minúsculas, sin puerto ni
punto final), se exige que sea un nombre de servidor bien formado y solo se acepta si el
dominio que resulta existe y está activo en el servidor. Con cualquier otra cosa se devuelven
los valores generales: así nadie consigue que la pantalla muestre un dominio inventado.

Lo que se publica es lo que ya enseña cualquier pantalla de entrada: el dominio, el nombre de
la empresa, su color y UN correo de contacto. Nunca listas de usuarios.
"""

import re
import time

from app import organizacion
from app.branding.service import ORG_NAME_FALLBACK
from app.portales.resolucion import dominio_del_portal, host_peticion

CACHE_SEGUNDOS = 60

# Prefijos con los que la gente entra al correo de un dominio.
PREFIJOS = ("mail.", "webmail.")

_NOMBRE_SERVIDOR = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
_CORREO = re.compile(r"^[a-z0-9._%+-]{1,64}@[a-z0-9.-]{1,253}\.[a-z]{2,63}$")
_COLOR = re.compile(r"^#(?:[0-9a-f]{3}|[0-9a-f]{6})$", re.I)

_dominios: frozenset = frozenset()
_dominios_hasta: float = 0.0
_por_dominio: dict[str, tuple[float, dict]] = {}


def olvidar_cache() -> None:
    """Descarta las cachés (para las pruebas y tras editar dominios o marcas)."""
    global _dominios_hasta
    _dominios_hasta = 0.0
    _por_dominio.clear()


def nombre_valido(host: str) -> bool:
    return bool(_NOMBRE_SERVIDOR.match(host or ""))


async def _dominios_activos(db) -> frozenset:
    """Dominios activos del servidor, con caché de un minuto."""
    global _dominios, _dominios_hasta
    ahora = time.monotonic()
    if _dominios_hasta > ahora:
        return _dominios
    try:
        filas = await db.fetch("SELECT domain FROM domain WHERE active = true")
        _dominios = frozenset(
            (f["domain"] or "").lower() for f in filas if f["domain"] != "ALL"
        )
        _dominios_hasta = ahora + CACHE_SEGUNDOS
    except Exception:
        # Sin base: pantalla general. Se reintenta pronto.
        _dominios = frozenset()
        _dominios_hasta = ahora + 5
    return _dominios


async def dominio_de_entrada(db, request) -> str | None:
    """Dominio de correo que corresponde al nombre de servidor de la petición, o None.

    Manda el portal de empresa dado de alta; si no hay, `mail.<dominio>` y
    `webmail.<dominio>` llevan a `<dominio>`. Solo si ese dominio existe en el servidor.
    """
    host = host_peticion(request)
    if not nombre_valido(host):
        return None
    activos = await _dominios_activos(db)
    portal = await dominio_del_portal(db, request)
    if portal and portal in activos:
        return portal
    for prefijo in PREFIJOS:
        if host.startswith(prefijo):
            candidato = host[len(prefijo) :]
            return candidato if candidato in activos else None
    return host if host in activos else None


async def _marca(db, dominio: str) -> dict:
    try:
        filas = await db.fetch(
            "SELECT clave, valor FROM branding_empresa WHERE dominio = $1 "
            "AND clave IN ('org_name', 'primary_color', 'org_email')",
            dominio,
        )
        return {f["clave"]: (f["valor"] or "").strip() for f in filas if f["valor"]}
    except Exception:
        return {}


def _correo_valido(valor) -> str | None:
    v = (valor or "").strip().lower()
    return v if _CORREO.match(v) else None


async def _administrador(db, dominio: str) -> str | None:
    """Un correo de quien administra el dominio: el más antiguo del panel de dominio y, si
    no hay, el del registro de administradores de dominio del correo."""
    consultas = (
        """SELECT a.username FROM pd_admins a
             JOIN pd_admin_dominios d ON d.admin_id = a.id
            WHERE lower(d.domain) = $1 AND a.active
            ORDER BY d.assigned_at, a.id LIMIT 5""",
        """SELECT username FROM domain_admins
            WHERE lower(domain) = $1 AND is_active = true
            ORDER BY username LIMIT 5""",
    )
    for sql in consultas:
        try:
            filas = await db.fetch(sql, dominio)
        except Exception:
            continue  # tabla ausente o sin permiso: se prueba la siguiente
        for f in filas:
            correo = _correo_valido(f["username"])
            if correo:
                return correo
    return None


async def _calcular(db, dominio: str, org_general: str | None) -> dict:
    marca = await _marca(db, dominio)
    datos: dict = {"dominio": dominio, "login_placeholder": f"usuario@{dominio}"}
    org = marca.get("org_name")
    if not org and dominio in organizacion.dominios_propios():
        org = org_general  # el dominio de la casa lleva el nombre de la marca general
    if org:
        datos["bienvenida"] = f"Correo de {org}"
    contacto = _correo_valido(marca.get("org_email")) or await _administrador(
        db, dominio
    )
    if contacto:
        datos["contacto_admin"] = contacto
    if _COLOR.match(marca.get("primary_color", "")):
        datos["primary_color"] = marca["primary_color"]
    return datos


async def datos_de_entrada(db, request, org_general: str | None = None) -> dict:
    """Campos de la pantalla de entrada para el dominio de la petición ({} si no hay)."""
    dominio = await dominio_de_entrada(db, request)
    if not dominio:
        return {}
    if org_general == ORG_NAME_FALLBACK:
        org_general = None
    ahora = time.monotonic()
    guardado = _por_dominio.get(dominio)
    if guardado and guardado[0] > ahora:
        return dict(guardado[1])
    datos = await _calcular(db, dominio, org_general)
    _por_dominio[dominio] = (ahora + CACHE_SEGUNDOS, datos)
    return dict(datos)
