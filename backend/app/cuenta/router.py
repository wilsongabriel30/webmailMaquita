"""Descubrimiento de cuenta por dominio para la cuenta del sistema de Android (una sola llamada).

Dado un correo, resuelve a qué portal pertenece (mail.example.org o el de su empresa) y devuelve todo
lo que el gestor de cuentas de Android necesita para dar de alta la cuenta y sus sincronizaciones:
IMAP/SMTP, CalDAV/CardDAV, la API del canal propio y el servidor de avisos push. Público (no expone
datos privados: solo qué servidores usar); la contraseña se valida al conectar cada servicio.
"""

import re

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/cuenta", tags=["cuenta"])
_CORREO = re.compile(r"^[^@\s]{1,64}@([a-z0-9.-]{1,253})$", re.I)


async def _host_de_dominio(request: Request, dominio: str) -> str:
    """El nombre de servidor del portal de esa empresa, o el del correo general si no tiene portal."""
    from app.portales import direcciones

    db = getattr(request.app.state, "db_pool", None)
    return await direcciones.servidor_de_dominio(db, dominio) or direcciones.servidor_general()


async def _organizacion(request: Request, dominio: str, host: str) -> str:
    try:
        v = await request.app.state.db_pool.fetchval(
            "SELECT valor FROM branding_empresa WHERE dominio = $1 AND clave = 'org_name'",
            dominio,
        )
        if v:
            return v
    except Exception:
        pass
    from app.config import get_settings

    return getattr(get_settings(), "org_name", "") or "Maquita"


@router.get("/descubrir")
async def descubrir(request: Request, correo: str = Query(..., max_length=254)):
    m = _CORREO.match(correo.strip().lower())
    if not m:
        return {
            "encontrado": False,
            "detalle": "Escribe tu correo completo, por ejemplo nombre@example.org",
        }
    correo = correo.strip().lower()
    dominio = m.group(1)
    host = await _host_de_dominio(request, dominio)
    base = f"https://{host}"
    servidor_push = None
    try:
        v = await request.app.state.db_pool.fetchval(
            "SELECT valor -> 'push' ->> 'servidor' FROM disp_config WHERE clave = 'politica'"
        )
        servidor_push = v
    except Exception:
        pass
    return {
        "encontrado": True,
        "correo": correo,
        "usuario": correo,  # el usuario es SIEMPRE el correo completo
        "dominio": dominio,
        "organizacion": await _organizacion(request, dominio, host),
        "servidor": host,
        "imap": {"host": host, "puerto": 993, "seguridad": "ssl"},
        "smtp": {
            "host": host,
            "puerto": 465,
            "seguridad": "ssl",
            "alternativo": {"puerto": 587, "seguridad": "starttls"},
        },
        "caldav": {
            "url": f"{base}/dav/",
            "descubrimiento": f"{base}/.well-known/caldav",
            "auth": "basic",
        },
        "carddav": {
            "url": f"{base}/dav/",
            "descubrimiento": f"{base}/.well-known/carddav",
            "auth": "basic",
        },
        "api": {"base": base, "ws": f"wss://{host}/api/ws"},
        "push": (
            {"servidor": servidor_push, "protocolo": "ntfy"} if servidor_push else None
        ),
        "auth": {
            "tipo": "password",
            "nota": "Usa la misma contraseña del correo web. Si tienes verificación en dos pasos, crea una contraseña de aplicación en Ajustes → Seguridad.",
        },
    }
