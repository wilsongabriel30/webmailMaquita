"""Safe Links — enlaces de la casa y dominios de confianza (05/11/2026).

Motivo: la pasarela marcaba como sospechosos sus PROPIOS enlaces. Un enlace ya reescrito
(«https://<portal del correo>/api/safelink?u=…») volvía a reescribirse al mostrar el correo
(doble envoltura: pasa al citar o reenviar un correo ya protegido) y la heurística de marcas
veía la marca en el portal del correo, cuyo dominio registrable no es el oficial. Resultado:
«Imita a «<marca>» pero el dominio real es <otro dominio de la casa>» y los «Ver RIDE / Ver XML» del SRI no abrían.

Reglas:
- Un enlace que ya apunta a la pasarela NO se vuelve a envolver.
- Al evaluar, se desenvuelven las pasarelas anidadas hasta llegar al destino real.
- Todos los dominios de la organización (y el portal del correo) son de la casa: nunca sospechosos.
- Dominios de confianza (SRI y los de ORG_DOMINIOS_CONFIABLES) abren directo.
"""

from urllib.parse import parse_qs, urlparse

from app import organizacion

# Entidades públicas cuyos enlaces llegan a diario (facturas electrónicas del SRI).
CONFIABLES_FIJOS = frozenset({"sri.gob.ec"})

RUTA_PASARELA = "/api/safelink"


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def _bajo(host: str, dominios) -> bool:
    return any(host == d or host.endswith("." + d) for d in dominios if d)


def dominios_de_la_casa() -> frozenset:
    propios = set(organizacion.dominios_propios())
    for u in (organizacion.url_correo(),):
        h = _host(u)
        if h:
            propios.add(h)
    try:
        from app.config import get_settings

        h = _host(get_settings().public_base_url or "")
        if h:
            propios.add(h)
    except Exception:  # noqa: BLE001
        pass
    return frozenset(propios)


def es_de_la_casa(host: str) -> bool:
    return bool(host) and _bajo(host.lower(), dominios_de_la_casa())


def es_confiable(host: str) -> bool:
    if not host:
        return False
    host = host.lower()
    confiables = set(CONFIABLES_FIJOS) | {
        d.lower() for d in organizacion.lista("ORG_DOMINIOS_CONFIABLES")
    }
    return es_de_la_casa(host) or _bajo(host, confiables)


def es_pasarela(url: str) -> bool:
    """¿El enlace ya es un enlace de la pasarela de Safe Links (propio o de otro portal de la casa)?"""
    try:
        p = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    return p.path == RUTA_PASARELA and es_de_la_casa((p.hostname or "").lower())


def desenvolver(url: str, maximo: int = 5) -> str:
    """Devuelve el destino real de una pasarela anidada (o la misma URL si no lo es)."""
    import html as html_lib

    from . import rewriter

    actual = url
    for _ in range(maximo):
        if not es_pasarela(actual):
            break
        u = (parse_qs(urlparse(actual).query).get("u") or [""])[0]
        if not u:
            break
        try:
            actual = html_lib.unescape(rewriter.decode_url(u))
        except Exception:  # noqa: BLE001
            break
    return actual
