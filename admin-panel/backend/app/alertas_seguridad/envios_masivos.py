"""Bloqueos por envío a muchos destinatarios, explicados y con su solución en la misma pantalla.

El vigilante de envío masivo (deploy/tools/maquita-anomalia-salida.py) desactiva una cuenta cuando
envía a más destinatarios de la cuenta en pocos minutos: así se comporta una cuenta robada. Pero
también una jefatura que escribe a una lista de 30 personas. Aquí el administrador ve qué pasó, a
quién iba el envío y decide: es correcto (se le permite escribir a esas listas y se reactiva), solo
reactivar, o dejarla bloqueada. El permiso es por cuenta y lista (outbound_anomaly_permisos) y no
cambia quién puede escribir a la lista.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/alertas-seguridad/envios", tags=["alertas-seguridad"])
DIAS = 7
DIRECTOS = "directos"


class Autorizar(BaseModel):
    listas: list[str] = []


class Permiso(BaseModel):
    cuenta: str
    listas: list[str]


def _db(r: Request):
    return r.app.state.db


async def _existe(db, tabla: str) -> bool:
    try:
        return bool(await db.fetchval("SELECT to_regclass($1)", tabla))
    except Exception:
        return False


async def disponible(db) -> bool:
    """La instalación tiene el vigilante con permisos por lista (migración del 13/11/2026)."""
    return await _existe(db, "outbound_anomaly_events") and await _existe(
        db, "outbound_anomaly_permisos"
    )


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def explicar(e: dict, umbral: int, activa: bool) -> dict:
    """Título, qué pasó y qué hacer, en lenguaje llano."""
    listas = [x for x in e["destinos"] if x["es_lista"]]
    directos = sum(x["destinatarios"] for x in e["destinos"] if not x["es_lista"])
    quien = e["nombre"] or e["cuenta"]
    que = (
        f"Envió {_plural(e['mensajes'], 'correo', 'correos')} a "
        f"{_plural(e['destinatarios'], 'persona', 'personas')} en {e['minutos']} minutos. "
        f"El sistema desactiva una cuenta cuando pasa de {umbral}, porque así se comporta una "
        "cuenta robada que envía correo basura."
    )
    if listas:
        detalle = ", ".join(f"{x['lista']} ({x['destinatarios']})" for x in listas)
        que += f" Casi todo iba a listas de la casa: {detalle}"
        que += (
            f"; {_plural(directos, 'fue directo', 'fueron directos')}."
            if directos
            else "."
        )
    pendientes = [x for x in listas if not x["autorizada"]]
    if e["atendido"]:
        hacer = "Ya se revisó."
    elif pendientes:
        nombres = " y ".join(x["lista"] for x in pendientes)
        hacer = (
            f"Si es normal que esta persona escriba a {nombres}, pulse «Es correcto». "
            + ("La cuenta vuelve a funcionar y " if not activa else "")
            + "No se le volverá a bloquear por escribir a esas listas. "
            "Si no reconoce el envío, deje la cuenta bloqueada y cambie la contraseña."
        )
    elif not activa:
        hacer = (
            "Confirme con la persona que el envío fue suyo. Si lo fue, pulse «Reactivar la cuenta». "
            "Si no lo reconoce, déjela bloqueada y cambie la contraseña. Si esta persona necesita "
            "escribir a una lista de la casa, puede darle el permiso más abajo, en «Permisos para "
            "escribir a listas»."
        )
    else:
        hacer = (
            "La cuenta ya está activa. Si el envío fue normal, márquelo como revisado."
        )
    estado = "bloqueada" if not activa else "activa"
    return {
        "titulo": f"Se bloqueó la cuenta de {quien} por escribir a muchas personas a la vez",
        "que_paso": que,
        "que_hacer": hacer,
        "estado": estado,
    }


async def pendientes(db) -> list[dict]:
    """Bloqueos de los últimos días, con lo necesario para decidir. Primero los sin revisar."""
    if not await disponible(db):
        return []
    umbral = (
        await db.fetchval(
            "SELECT threshold_recipients FROM outbound_anomaly_config WHERE id = 1"
        )
        or 0
    )
    filas = await db.fetch(f"""
        SELECT e.id, e.username, e.recipients, e.messages, e.window_minutes, e.action, e.created_at,
               e.desglose, e.atendido, e.atendido_por, e.resolucion, m.name, m.active
        FROM outbound_anomaly_events e LEFT JOIN mailbox m ON m.username = e.username
        WHERE e.created_at > now() - interval '{DIAS} days'
        ORDER BY (e.atendido IS NOT NULL), e.created_at DESC LIMIT 40
        """)
    listas = {
        f["address"].lower()
        for f in await db.fetch("SELECT address FROM mail_groups WHERE active")
    }
    permisos = {
        (f["username"].lower(), f["lista"].lower())
        for f in await db.fetch("SELECT username, lista FROM outbound_anomaly_permisos")
    }
    salida = []
    for f in filas:
        cuenta = f["username"].lower()
        crudo = f["desglose"]
        desglose = json.loads(crudo) if isinstance(crudo, str) else (crudo or {})
        destinos = [
            {
                "lista": k,
                "destinatarios": int(v),
                "es_lista": k != DIRECTOS and k.lower() in listas,
                "autorizada": (cuenta, k.lower()) in permisos,
            }
            for k, v in sorted(desglose.items(), key=lambda kv: -int(kv[1]))
        ]
        e = {
            "id": f["id"],
            "cuenta": cuenta,
            "nombre": f["name"] or "",
            "cuando": f["created_at"].isoformat(),
            "destinatarios": f["recipients"],
            "mensajes": f["messages"],
            "minutos": f["window_minutes"],
            "bloqueo": f["action"] == "locked",
            "destinos": destinos,
            "activa": bool(f["active"]),
            "existe": f["active"] is not None,
            "atendido": f["atendido"].isoformat() if f["atendido"] else None,
            "atendido_por": f["atendido_por"] or "",
            "resolucion": f["resolucion"] or "",
        }
        e.update(explicar(e, umbral, e["activa"]))
        e["listas_por_autorizar"] = [
            x["lista"] for x in destinos if x["es_lista"] and not x["autorizada"]
        ]
        salida.append(e)
    return salida


def sin_revisar(envios: list[dict]) -> int:
    return sum(1 for e in envios if not e["atendido"] and e["existe"])


async def _evento(db, evento_id: int):
    if not await disponible(db):
        raise HTTPException(
            404, "Esta instalación no tiene el vigilante de envío masivo"
        )
    f = await db.fetchrow(
        "SELECT id, username, desglose FROM outbound_anomaly_events WHERE id = $1",
        evento_id,
    )
    if not f:
        raise HTTPException(404, "Ese aviso ya no existe")
    return f


async def _auditar(
    r: Request, a: dict, accion: str, cuenta: str, detalle: dict
) -> None:
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        a["id"],
        a["username"],
        accion,
        cuenta,
        json.dumps(detalle),
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


async def _cerrar(db, evento_id: int, cuenta: str, quien: str, resolucion: str) -> None:
    """Marca como revisados ese aviso y los anteriores sin revisar de la misma cuenta."""
    await db.execute(
        "UPDATE outbound_anomaly_events SET atendido = now(), atendido_por = $3, resolucion = $4 "
        "WHERE username = $2 AND atendido IS NULL AND id <= $1",
        evento_id,
        cuenta,
        quien,
        resolucion,
    )


async def _reactivar(db, cuenta: str) -> bool:
    fila = await db.fetchrow(
        "UPDATE mailbox SET active = true, modified = now() WHERE username = $1 AND active = false "
        "RETURNING username",
        cuenta,
    )
    return bool(fila)


@router.post("/{evento_id}/autorizar")
async def autorizar(
    evento_id: int,
    body: Autorizar,
    r: Request,
    a: dict = Depends(require_role("superadmin", "admin")),
):
    """«Es correcto»: permite a la cuenta escribir a esas listas y la reactiva."""
    db = _db(r)
    f = await _evento(db, evento_id)
    cuenta = f["username"].lower()
    crudo = f["desglose"]
    desglose = json.loads(crudo) if isinstance(crudo, str) else (crudo or {})
    validas = {
        x["address"].lower()
        for x in await db.fetch("SELECT address FROM mail_groups WHERE active")
    }
    pedidas = [x.strip().lower() for x in body.listas] or list(desglose)
    listas = [
        x
        for x in dict.fromkeys(pedidas)
        if x in validas and x in {k.lower() for k in desglose}
    ]
    if not listas:
        raise HTTPException(
            400, "Ese envío no iba a ninguna lista de la casa: no hay permiso que dar"
        )
    for lista in listas:
        await db.execute(
            "INSERT INTO outbound_anomaly_permisos (username, lista, nota, creado_por) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT (username, lista) DO NOTHING",
            cuenta,
            lista,
            "Concedido al revisar un bloqueo por envío a muchas personas",
            a["username"],
        )
    reactivada = await _reactivar(db, cuenta)
    await _cerrar(db, evento_id, cuenta, a["username"], "autorizado")
    await _auditar(
        r,
        a,
        "envio_masivo_autorizar",
        cuenta,
        {"listas": listas, "reactivada": reactivada},
    )
    return {"ok": True, "cuenta": cuenta, "listas": listas, "reactivada": reactivada}


@router.post("/{evento_id}/reactivar")
async def reactivar(
    evento_id: int, r: Request, a: dict = Depends(require_role("superadmin", "admin"))
):
    """Solo reactivar: el envío fue suyo, pero no se le da ningún permiso."""
    db = _db(r)
    f = await _evento(db, evento_id)
    cuenta = f["username"].lower()
    reactivada = await _reactivar(db, cuenta)
    await _cerrar(db, evento_id, cuenta, a["username"], "reactivado")
    await _auditar(r, a, "envio_masivo_reactivar", cuenta, {"reactivada": reactivada})
    return {"ok": True, "cuenta": cuenta, "reactivada": reactivada}


@router.post("/{evento_id}/mantener")
async def mantener(
    evento_id: int, r: Request, a: dict = Depends(require_role("superadmin", "admin"))
):
    """Revisado sin cambios: la cuenta queda como está (bloqueada, si lo estaba)."""
    db = _db(r)
    f = await _evento(db, evento_id)
    cuenta = f["username"].lower()
    await _cerrar(db, evento_id, cuenta, a["username"], "sin_cambios")
    await _auditar(r, a, "envio_masivo_revisado", cuenta, {})
    return {"ok": True, "cuenta": cuenta}


@router.get("/permisos")
async def permisos(r: Request, a=Depends(get_current_admin)):
    db = _db(r)
    if not await disponible(db):
        return {"permisos": []}
    filas = await db.fetch(
        "SELECT id, username, lista, nota, creado_por, creado FROM outbound_anomaly_permisos "
        "ORDER BY username, lista"
    )
    return {"permisos": [{**dict(f), "creado": f["creado"].isoformat()} for f in filas]}


@router.get("/listas")
async def listas_de_la_casa(r: Request, a=Depends(get_current_admin)):
    """Las listas a las que se puede dar permiso, con su número de miembros."""
    db = _db(r)
    if not await disponible(db):
        return {"listas": [], "umbral": 0}
    filas = await db.fetch(
        "SELECT g.address, g.name, (SELECT count(*) FROM mail_group_members m WHERE m.group_id = g.id) AS miembros "
        "FROM mail_groups g WHERE g.active ORDER BY g.address"
    )
    umbral = await db.fetchval(
        "SELECT threshold_recipients FROM outbound_anomaly_config WHERE id = 1"
    )
    return {"listas": [dict(f) for f in filas], "umbral": umbral or 0}


@router.post("/permisos")
async def dar_permiso(
    body: Permiso, r: Request, a: dict = Depends(require_role("superadmin", "admin"))
):
    """Permiso por adelantado: esa cuenta podrá escribir a esas listas sin que se la bloquee."""
    db = _db(r)
    if not await disponible(db):
        raise HTTPException(
            404, "Esta instalación no tiene el vigilante de envío masivo"
        )
    cuenta = body.cuenta.strip().lower()
    if not await db.fetchval("SELECT 1 FROM mailbox WHERE username = $1", cuenta):
        raise HTTPException(
            404, f"No existe ninguna cuenta «{cuenta}». Escriba la dirección completa."
        )
    validas = {
        x["address"].lower()
        for x in await db.fetch("SELECT address FROM mail_groups WHERE active")
    }
    listas = [
        x for x in dict.fromkeys(l.strip().lower() for l in body.listas) if x in validas
    ]
    if not listas:
        raise HTTPException(400, "Elija al menos una lista de la casa")
    for lista in listas:
        await db.execute(
            "INSERT INTO outbound_anomaly_permisos (username, lista, nota, creado_por) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT (username, lista) DO NOTHING",
            cuenta,
            lista,
            "Concedido por adelantado desde el panel",
            a["username"],
        )
    await _auditar(r, a, "envio_masivo_dar_permiso", cuenta, {"listas": listas})
    return {"ok": True, "cuenta": cuenta, "listas": listas}


@router.delete("/permisos/{permiso_id}")
async def quitar_permiso(
    permiso_id: int, r: Request, a: dict = Depends(require_role("superadmin", "admin"))
):
    db = _db(r)
    f = await db.fetchrow(
        "DELETE FROM outbound_anomaly_permisos WHERE id = $1 RETURNING username, lista",
        permiso_id,
    )
    if not f:
        raise HTTPException(404, "Ese permiso ya no existe")
    await _auditar(
        r, a, "envio_masivo_quitar_permiso", f["username"], {"lista": f["lista"]}
    )
    return {"ok": True}
