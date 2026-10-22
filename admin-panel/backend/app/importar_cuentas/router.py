"""Importar cuentas de correo desde un CSV (panel general).

Dos pasos: la vista previa revisa el archivo fila a fila sin tocar nada; «aplicar» lo vuelve a
revisar entero contra la base de ese momento (nunca se fía de la vista previa) y crea solo las
filas válidas. Las contraseñas que se generan se devuelven UNA vez, en un CSV descargable: no se
guardan ni se anotan en la auditoría.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.importar_cuentas import datos
from app.importar_cuentas.formato_csv import (
    MAX_BYTES, MAX_FILAS, ErrorArchivo, claves_csv, generar_clave, informe_csv, leer, para_mostrar, revisar,
)
from app.wrappers.doveadm import generate_password_hash

router = APIRouter(prefix="/api/importar-cuentas", tags=["importar-cuentas"])
AJENO = "El dominio {dominio} no está en este servidor: créelo primero en Dominios"
HASHES_A_LA_VEZ = 8


async def _audit(r: Request, a: dict, action: str, target: str, details: dict):
    await r.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details),
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


async def _revisado(request: Request) -> list[dict]:
    cuerpo = await request.json()
    try:
        filas = leer(cuerpo.get("csv") if isinstance(cuerpo, dict) else None)
    except ErrorArchivo as e:
        raise HTTPException(400, str(e))
    dominios, ocupadas = await datos.contexto(request.app.state.db, filas)
    return revisar(filas, dominios, ocupadas, AJENO)


@router.get("/limites")
async def limites(admin: dict = Depends(get_current_admin)):
    return {"max_filas": MAX_FILAS, "max_bytes": MAX_BYTES, "columnas": ["correo", "nombre", "clave", "cuota_mb", "alias"]}


@router.post("/vista-previa")
async def vista_previa(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    filas = await _revisado(request)
    validas = sum(f["valida"] for f in filas)
    return {"filas": [para_mostrar(f) for f in filas], "validas": validas, "con_errores": len(filas) - validas}


@router.post("/aplicar")
async def aplicar(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    filas = await _revisado(request)
    db = request.app.state.db
    validas = [f for f in filas if f["valida"]]
    limite = asyncio.Semaphore(HASHES_A_LA_VEZ)

    async def hash_de(f: dict) -> str:
        if not f["clave"]:
            f["clave_generada"] = generar_clave(f["correo"])
        async with limite:
            return await generate_password_hash(f["clave"] or f["clave_generada"])

    hashes = await asyncio.gather(*(hash_de(f) for f in validas), return_exceptions=True)
    creadas = []
    for f, h in zip(validas, hashes):
        if isinstance(h, BaseException):
            f["errores"].append("No se pudo calcular el hash de la contraseña")
            continue
        try:
            await datos.crear(db, f, h)
            f["creada"] = True
            creadas.append(f)
        except Exception as e:
            ya = "duplicate key" in str(e) or "already exists" in str(e)
            f["errores"].append("Ya existe (se creó mientras tanto)" if ya else "No se pudo crear la cuenta")
            datos.log.error("importar %s: %s", f["correo"], type(e).__name__)
    resultados = [{**para_mostrar(f), "resultado": "creada" if f.get("creada") else "omitida"} for f in filas]
    await _audit(request, admin, "mailbox_importar", f"{len(creadas)} cuentas", {
        "filas": len(filas), "creadas": [f["correo"] for f in creadas], "omitidas": len(filas) - len(creadas),
        "claves_generadas": sum(1 for f in creadas if f.get("clave_generada")),
        "alias": sum(len(f["alias"]) for f in creadas),
    })
    return {
        "creadas": len(creadas), "omitidas": len(filas) - len(creadas), "resultados": resultados,
        "informe_csv": informe_csv(resultados), "claves_csv": claves_csv(creadas),
    }
