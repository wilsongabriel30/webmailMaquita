"""¿El vale de impersonación debe llevar la marca de segundo factor?

Misma regla que el panel: manda `security_config.impersonar_admin_exige_totp` (se cambia
desde el panel, en Anti-suplantación y políticas). Si la columna no existe, manda la
opción `impersonar_exige_totp` del entorno, que por omisión es True.
"""


async def exige_totp_para_impersonar(db_pool, settings) -> bool:
    try:
        valor = await db_pool.fetchval(
            "SELECT impersonar_admin_exige_totp FROM security_config WHERE id = 1"
        )
    except Exception:
        valor = None
    if valor is None:
        return bool(settings.impersonar_exige_totp)
    return bool(valor)
