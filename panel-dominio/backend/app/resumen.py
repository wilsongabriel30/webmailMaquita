from fastapi import APIRouter, Depends, Request

from app.sesion import admin_actual
from app.validacion import CLAVE_MINIMA, CUOTA_POR_DEFECTO

router = APIRouter(prefix="/api/resumen", tags=["resumen"])


@router.get("")
async def resumen(request: Request, admin: dict = Depends(admin_actual)):
    filas = await request.app.state.db.fetch(
        """SELECT d.domain, d.description, d.active, d.mailboxes AS max_cuentas, d.aliases AS max_alias,
                  d.maxquota AS cuota_maxima,
                  (SELECT count(*) FROM mailbox m WHERE m.domain = d.domain) AS cuentas,
                  (SELECT count(*) FROM mailbox m WHERE m.domain = d.domain AND m.active) AS cuentas_activas,
                  (SELECT count(*) FROM alias a WHERE a.domain = d.domain AND a.address <> a.goto) AS alias
             FROM domain d WHERE d.domain = ANY($1::varchar[]) ORDER BY d.domain""",
        admin["dominios"],
    )
    return {"dominios": [dict(f) for f in filas], "cuota_por_defecto": CUOTA_POR_DEFECTO, "clave_minima": CLAVE_MINIMA}
