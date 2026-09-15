"""¿Impersonar un buzón exige que el administrador haya entrado con segundo factor?

La respuesta vive en `security_config.impersonar_admin_exige_totp` y se administra desde el
panel (Anti-suplantación y políticas). Si la columna no existe todavía (instalación sin la
migración 2026-09-15) manda la variable de entorno IMPERSONAR_EXIGE_TOTP, que por omisión
es true. El backend del correo aplica exactamente la misma regla al canjear el vale.
"""

from app import config


async def exige_totp_para_impersonar(db) -> bool:
    try:
        valor = await db.fetchval(
            "SELECT impersonar_admin_exige_totp FROM security_config WHERE id = 1"
        )
    except Exception:
        valor = None
    if valor is None:
        return bool(config.IMPERSONAR_EXIGE_TOTP)
    return bool(valor)
