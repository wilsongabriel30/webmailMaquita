"""Reenvío de una cuenta: además de su buzón (o en vez de él), su correo llega a otras direcciones.

Se guarda en la fila de la propia cuenta en `alias`: «cuenta → cuenta, destino1, destino2».
Sin destinos, la fila vuelve a «cuenta → cuenta». Nunca se deja sin ningún destino: el correo
se perdería.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app import destinos
from app.alcance import exigir_alcance
from app.sesion import admin_actual, auditar

router = APIRouter(prefix="/api/reenvios", tags=["reenvios"])


def _partes(cuenta: str, goto: str) -> dict:
    lista = [d.strip() for d in (goto or "").split(",") if d.strip()]
    return {"cuenta": cuenta, "conserva_copia": cuenta in lista or not lista, "destinos": [d for d in lista if d != cuenta]}


@router.get("")
async def listar(request: Request, admin: dict = Depends(admin_actual)):
    filas = await request.app.state.db.fetch(
        """SELECT a.address, a.goto FROM alias a JOIN mailbox m ON m.username = a.address
            WHERE a.domain = ANY($1::varchar[]) AND a.goto <> a.address ORDER BY a.address""",
        admin["dominios"])
    return [_partes(f["address"], f["goto"]) for f in filas]


@router.put("/{cuenta:path}")
async def guardar(cuenta: str, request: Request, admin: dict = Depends(admin_actual)):
    cuenta = str(cuenta or "").strip().lower()
    dominio = exigir_alcance(admin, cuenta)
    db = request.app.state.db
    if not await db.fetchval("SELECT 1 FROM mailbox WHERE username = $1", cuenta):
        raise HTTPException(404, "No encontrado")
    datos = await request.json()
    lista, externos = await destinos.validar(db, admin, datos.get("destinos"), salvo=cuenta)
    copia = bool(datos.get("conserva_copia", True))
    if not lista and not copia:
        raise HTTPException(400, "Sin destinos y sin copia el correo se perdería")
    goto = ",".join(([cuenta] if copia else []) + lista)
    antes = await db.fetchval("SELECT goto FROM alias WHERE address = $1", cuenta)
    await db.execute(
        """INSERT INTO alias (address, goto, domain, active) VALUES ($1, $2, $3, true)
           ON CONFLICT (address) DO UPDATE SET goto = EXCLUDED.goto, modified = NOW()""",
        cuenta, goto, dominio)
    await auditar(request, admin, "reenvio_guardar", cuenta,
                  {"antes": antes, "destinos": lista, "externos": externos, "conserva_copia": copia})
    return _partes(cuenta, goto)
