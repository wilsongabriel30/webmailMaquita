"""Importar cuentas desde un CSV, en los dominios propios y dentro de sus límites.

Mismas reglas que el alta de una cuenta (cuentas.py): alcance de la sesión, dominio activo, tope de
cuentas y de alias del dominio, cuota máxima y política de contraseñas, con el mismo usuario de base
de permisos mínimos. Un dominio que no es del administrador da el mismo mensaje exista o no.

El navegador manda el archivo por partes (bloques de filas con su cabecera) porque el portal no
admite cuerpos de más de 64 KB. Para que la vista previa cuente bien los topes, cada bloque trae
lo que los anteriores ya ocupan (`pendientes`) y desde qué línea del archivo empieza
(`desplazamiento`). «Aplicar» no se fía de nada de eso: vuelve a revisar cada bloque contra la base
de ese momento, así que lo creado por un bloque ya cuenta para el siguiente.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.claves import hash_buzon
from app.importar.formato_csv import (
    MAX_BYTES, MAX_FILAS, ErrorArchivo, claves_csv, generar_clave, informe_csv, leer, para_mostrar, revisar,
)
from app.sesion import admin_actual, auditar
from app.validacion import CUOTA_POR_DEFECTO, exigir_clave_fuerte

router = APIRouter(prefix="/api/importar-cuentas", tags=["importar-cuentas"])
log = logging.getLogger("panel-dominio")
AJENO = "El dominio {dominio} no es uno de tus dominios"
HASHES_A_LA_VEZ = 4


async def _enrutados(db, dominios: list[str]) -> set[str]:
    try:
        filas = await db.fetch(
            "SELECT dominio FROM enrutamiento_correo WHERE activo AND dominio = ANY($1::varchar[])", dominios)
    except Exception as e:  # sin la migración o sin el permiso (permisos-5-enrutamiento.sql)
        log.warning("importar cuentas: no se pudo leer el enrutamiento (%s)", type(e).__name__)
        return set()
    return {f["dominio"] for f in filas}


async def _contexto(db, admin: dict, filas: list[dict]) -> tuple[dict, set[str]]:
    """Solo se consulta la base por los dominios de la sesión: de los demás no se revela nada."""
    direcciones = sorted({d for f in filas for d in [f["correo"], *f["alias"]]
                          if d.count("@") == 1 and d.split("@")[1] in admin["dominios"]})
    dominios = sorted({d.split("@")[1] for d in direcciones})
    if not dominios:
        return {}, set()
    db_dom = await db.fetch(
        """SELECT d.domain, d.active, d.mailboxes, d.aliases, d.maxquota,
                  (SELECT count(*) FROM mailbox m WHERE m.domain = d.domain) AS cuentas,
                  (SELECT count(*) FROM alias a WHERE a.domain = d.domain
                      AND NOT EXISTS (SELECT 1 FROM mailbox m WHERE m.username = a.address)) AS alias_usados
             FROM domain d WHERE d.domain = ANY($1::varchar[])""", dominios)
    enrutados = await _enrutados(db, dominios)
    info = {}
    for f in db_dom:
        tope = f["maxquota"] if f["maxquota"] and f["maxquota"] > 0 else CUOTA_POR_DEFECTO
        info[f["domain"]] = {
            "activo": bool(f["active"]), "enrutado": f["domain"] in enrutados,
            "max_cuentas": int(f["mailboxes"] or 0), "cuentas": int(f["cuentas"]),
            "max_alias": int(f["aliases"] or 0), "alias": int(f["alias_usados"]),
            "cuota_maxima": int(tope), "cuota_defecto": int(min(CUOTA_POR_DEFECTO, tope)),
        }
    ocupadas = await db.fetch(
        """SELECT address AS d FROM alias WHERE address = ANY($1::varchar[])
           UNION SELECT username FROM mailbox WHERE username = ANY($1::varchar[])
           UNION SELECT lower(address) FROM mail_groups WHERE lower(address) = ANY($1::varchar[])""", direcciones)
    return info, {o["d"] for o in ocupadas}


def _pendientes(valor, admin: dict) -> dict:
    """Lo que los bloques anteriores ya ocupan: solo dominios propios y números razonables."""
    limpio = {"cuentas": {}, "alias": {}}
    if not isinstance(valor, dict):
        return limpio
    for clave in limpio:
        cuentas = valor.get(clave)
        if not isinstance(cuentas, dict):
            continue
        for dominio, n in cuentas.items():
            if dominio in admin["dominios"] and isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= MAX_FILAS * 20:
                limpio[clave][dominio] = n
    return limpio


async def _revisado(request: Request, admin: dict, con_pendientes: bool) -> list[dict]:
    cuerpo = await request.json()
    if not isinstance(cuerpo, dict):
        raise HTTPException(400, "Datos inválidos")
    try:
        filas = leer(cuerpo.get("csv"))
    except ErrorArchivo as e:
        raise HTTPException(400, str(e))
    desplazamiento = cuerpo.get("desplazamiento", 0)
    if isinstance(desplazamiento, int) and not isinstance(desplazamiento, bool) and 0 <= desplazamiento <= 1_000_000:
        for f in filas:
            f["fila"] += desplazamiento
    info, ocupadas = await _contexto(request.app.state.db, admin, filas)
    pendientes = _pendientes(cuerpo.get("pendientes"), admin) if con_pendientes else None
    revisar(filas, info, ocupadas, AJENO, pendientes)
    for f in filas:  # la política de siempre del portal, por si alguna vez se separa de la copia compartida
        if f["valida"] and f["clave"]:
            try:
                exigir_clave_fuerte(f["clave"], f["correo"])
            except HTTPException as e:
                f["errores"].append(e.detail)
                f["valida"] = False
    return filas


@router.get("/limites")
async def limites(admin: dict = Depends(admin_actual)):
    return {"max_filas": MAX_FILAS, "max_bytes": MAX_BYTES, "columnas": ["correo", "nombre", "clave", "cuota_mb", "alias"]}


@router.post("/vista-previa")
async def vista_previa(request: Request, admin: dict = Depends(admin_actual)):
    filas = await _revisado(request, admin, con_pendientes=True)
    validas = [f for f in filas if f["valida"]]
    ocupa = {"cuentas": {}, "alias": {}}
    for f in validas:
        d = f["correo"].split("@")[1]
        ocupa["cuentas"][d] = ocupa["cuentas"].get(d, 0) + 1
        for a in f["alias"]:
            ocupa["alias"][a.split("@")[1]] = ocupa["alias"].get(a.split("@")[1], 0) + 1
    return {"filas": [para_mostrar(f) for f in filas], "validas": len(validas),
            "con_errores": len(filas) - len(validas), "ocupa": ocupa}


async def _crear(db, f: dict, hash_clave: str) -> None:
    local, dominio = f["correo"].split("@")
    async with db.acquire() as con, con.transaction():
        await con.execute(
            """INSERT INTO mailbox (username, password, name, maildir, quota, domain, local_part, active)
               VALUES ($1::varchar, $2::varchar, $3::varchar, $4::varchar, $5, $6::varchar, $7::varchar, true)""",
            f["correo"], hash_clave, f["nombre"], f"{dominio}/{local}/", f["cuota"], dominio, local)
        await con.execute(
            "INSERT INTO alias (address, goto, domain, active) VALUES ($1::varchar, $1::varchar, $2::varchar, true)",
            f["correo"], dominio)
        for a in f["alias"]:
            await con.execute(
                "INSERT INTO alias (address, goto, domain, active) VALUES ($1::varchar, $2::varchar, $3::varchar, true)",
                a, f["correo"], a.split("@")[1])


@router.post("/aplicar")
async def aplicar(request: Request, admin: dict = Depends(admin_actual)):
    filas = await _revisado(request, admin, con_pendientes=False)
    validas = [f for f in filas if f["valida"]]
    limite = asyncio.Semaphore(HASHES_A_LA_VEZ)

    async def hash_de(f: dict) -> str:
        if not f["clave"]:
            f["clave_generada"] = generar_clave(f["correo"])
        async with limite:
            return await hash_buzon(f["clave"] or f["clave_generada"])

    hashes = await asyncio.gather(*(hash_de(f) for f in validas), return_exceptions=True)
    db = request.app.state.db
    creadas = []
    for f, h in zip(validas, hashes):
        if isinstance(h, BaseException):
            f["errores"].append("No se pudo calcular el hash de la contraseña")
            continue
        try:
            await _crear(db, f, h)
            f["creada"] = True
            creadas.append(f)
        except Exception as e:
            ya = "duplicate key" in str(e)
            f["errores"].append("Ya existe (se creó mientras tanto)" if ya else "No se pudo crear la cuenta")
            log.error("importar %s: %s", f["correo"], type(e).__name__)
    resultados = [{**para_mostrar(f), "resultado": "creada" if f.get("creada") else "omitida"} for f in filas]
    await auditar(request, admin, "cuentas_importar", f"{len(creadas)} cuentas", {
        "filas": len(filas), "creadas": [f["correo"] for f in creadas], "omitidas": len(filas) - len(creadas),
        "claves_generadas": sum(1 for f in creadas if f.get("clave_generada")),
        "alias": sum(len(f["alias"]) for f in creadas),
    })
    return {"creadas": len(creadas), "omitidas": len(filas) - len(creadas), "resultados": resultados,
            "informe_csv": informe_csv(resultados), "claves_csv": claves_csv(creadas)}
