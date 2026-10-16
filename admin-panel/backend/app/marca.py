"""Nombre de la organización, del producto y nombre corto (Personalización), para textos de cara a
personas o servidores externos: asuntos de correos del panel, avisos, cabeceras.

Caché de proceso: se rellena al arrancar y cada vez que se guarda la personalización. Si todavía no
hay datos se usan valores neutros (nunca el nombre de otra organización).
"""

_cache = {"org_name": None, "app_name": None, "org_short": None}


async def refrescar(db) -> None:
    try:
        filas = await db.fetch(
            "SELECT key, value FROM branding_settings WHERE key IN ('org_name','app_name','org_short')"
        )
        for f in filas:
            _cache[f["key"]] = (f["value"] or "").strip() or None
    except Exception:
        pass


def org() -> str:
    return _cache["org_name"] or "la organización"


def app() -> str:
    return _cache["app_name"] or "Correo"


def corta() -> str:
    return _cache["org_short"] or app()
