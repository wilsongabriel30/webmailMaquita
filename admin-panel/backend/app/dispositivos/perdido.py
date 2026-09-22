"""Panel · Dispositivos (fase 2): ubicación, modo perdido y comandos a distancia.

Todo lo de este archivo es sensible. Cada consulta de ubicación y cada comando exige un motivo y
queda en la auditoría del panel (quién, cuándo, a qué equipo y por qué). El borrado remoto solo lo
puede pedir un superadministrador, solo sobre equipos con control completo y escribiendo la frase
de confirmación.
"""

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.comun import auditar, db, fecha, texto
from app.dispositivos import push_panel

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")
_SUPER = require_role("superadmin")

# tipo -> (exige control completo, solo superadmin)
COMANDOS = {
    "localizar": (False, False),   # una posición precisa ahora
    "alarma": (False, False),      # sonar a todo volumen aunque esté en silencio
    "bloquear": (True, False),     # bloquear la pantalla con mensaje y teléfono de contacto
    "borrar": (True, True),        # restablecer de fábrica
    "gnss_crudo": (False, False),  # lote de mediciones GNSS crudas (experimento REGME, etapa 3)
    # `respaldar` se pide desde respaldos.py y `desbloquear` al marcar el equipo como recuperado
}


async def _equipo(request: Request, equipo_id: int):
    f = await db(request).fetchrow(
        "SELECT id, nombre, modelo, modo, estado, ubicacion_autorizada FROM disp_equipos WHERE id = $1", equipo_id)
    if f is None:
        raise HTTPException(404, "Equipo no encontrado")
    if f["estado"] in ("revocado", "baja"):
        raise HTTPException(409, "El equipo ya no está bajo gestión")
    return f


def _motivo(b: dict) -> str:
    m = texto(b.get("motivo"), 255)
    if not m or len(m) < 5:
        raise HTTPException(400, "Indique el motivo (queda en la auditoría)")
    return m


async def _encolar(con, equipo_id: int, tipo: str, parametros: dict, admin: dict, motivo: str) -> int:
    # Un mismo comando pendiente no se duplica: se reutiliza.
    existente = await con.fetchval(
        "SELECT id FROM disp_comandos WHERE equipo_id = $1 AND tipo = $2 AND estado = 'pendiente'", equipo_id, tipo)
    if existente:
        return existente
    cid = await con.fetchval(
        "INSERT INTO disp_comandos (equipo_id, tipo, parametros, creado_por, motivo) VALUES ($1,$2,$3::jsonb,$4,$5) RETURNING id",
        equipo_id, tipo, json.dumps(parametros), admin["username"], motivo)
    push_panel.avisar(await con.fetchval("SELECT push_topic FROM disp_equipos WHERE id = $1", equipo_id), "comando")
    return cid


@router.post("/equipos/{equipo_id}/autorizacion-ubicacion")
async def autorizar_ubicacion(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    """Activa o quita la ubicación periódica. Activarla exige la fecha de la política firmada."""
    b = await request.json()
    await _equipo(request, equipo_id)
    activa = bool(b.get("autorizada"))
    firmada = fecha(b.get("politica_firmada_en")) if activa else None
    if activa and firmada is None:
        raise HTTPException(400, "Indique la fecha en que el custodio firmó la política de uso de dispositivos")
    await db(request).execute(
        "UPDATE disp_equipos SET ubicacion_autorizada = $2, politica_firmada_en = COALESCE($3, politica_firmada_en) WHERE id = $1",
        equipo_id, activa, firmada)
    await auditar(request, admin, "dispositivo_ubicacion_autorizacion", str(equipo_id), {"autorizada": activa, "firmada": firmada})
    return {"ok": True}


@router.post("/equipos/{equipo_id}/perdido")
async def declarar_perdido(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    e = await _equipo(request, equipo_id)
    motivo = _motivo(b)
    mensaje = texto(b.get("mensaje"), 255) or "Este teléfono pertenece a Fundación Maquita. Si lo encontró, por favor llame al número indicado."
    telefono = texto(b.get("telefono"), 40)
    async with db(request).acquire() as con, con.transaction():
        await con.execute(
            "UPDATE disp_equipos SET estado = 'perdido', perdido_en = NOW(), perdido_motivo = $2, perdido_mensaje = $3, "
            "perdido_telefono = $4, baliza_id = COALESCE(baliza_id, $5) WHERE id = $1",
            equipo_id, motivo, mensaje, telefono, secrets.token_hex(8))
        await _encolar(con, equipo_id, "localizar", {}, admin, motivo)
        if e["modo"] == "propietario":
            await _encolar(con, equipo_id, "bloquear", {"mensaje": mensaje, "telefono": telefono}, admin, motivo)
    await auditar(request, admin, "dispositivo_perdido", str(equipo_id), {"motivo": motivo, "bloqueo": e["modo"] == "propietario"})
    return {"ok": True, "bloqueo_encolado": e["modo"] == "propietario"}


@router.post("/equipos/{equipo_id}/recuperado")
async def declarar_recuperado(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    motivo = _motivo(await request.json())
    async with db(request).acquire() as con, con.transaction():
        r = await con.execute(
            "UPDATE disp_equipos SET estado = 'activo', baliza_id = NULL, perdido_mensaje = NULL, perdido_telefono = NULL "
            "WHERE id = $1 AND estado = 'perdido'", equipo_id)
        if r.endswith(" 0"):
            raise HTTPException(409, "El equipo no está declarado perdido")
        await con.execute("UPDATE disp_comandos SET estado = 'anulado', terminado_en = NOW() WHERE equipo_id = $1 AND estado = 'pendiente'", equipo_id)
        await _encolar(con, equipo_id, "desbloquear", {}, admin, motivo)
    await auditar(request, admin, "dispositivo_recuperado", str(equipo_id), {"motivo": motivo})
    return {"ok": True}


@router.post("/equipos/{equipo_id}/comandos")
async def enviar_comando(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    tipo = b.get("tipo")
    if tipo not in COMANDOS:
        raise HTTPException(400, "Comando no admitido")
    exige_control, solo_super = COMANDOS[tipo]
    e = await _equipo(request, equipo_id)
    motivo = _motivo(b)
    if solo_super and admin["role"] != "superadmin":
        raise HTTPException(403, "Solo un superadministrador puede pedir el borrado remoto")
    if exige_control and e["modo"] != "propietario":
        raise HTTPException(409, "Este equipo está en modo limitado: Android no permite esa acción sin control completo")
    parametros = {}
    if tipo == "gnss_crudo":
        parametros = {"segundos": max(10, min(900, int(b.get("segundos") or 60)))}
    if tipo == "bloquear":
        parametros = {"mensaje": texto(b.get("mensaje"), 255), "telefono": texto(b.get("telefono"), 40)}
    if tipo == "borrar":
        if e["estado"] != "perdido":
            raise HTTPException(409, "Primero declare el equipo como perdido")
        if (b.get("confirmacion") or "").strip() != f"BORRAR {equipo_id}":
            raise HTTPException(400, f"Para confirmar escriba exactamente: BORRAR {equipo_id}")
    async with db(request).acquire() as con:
        cid = await _encolar(con, equipo_id, tipo, parametros, admin, motivo)
    await auditar(request, admin, f"dispositivo_comando_{tipo}", str(equipo_id), {"motivo": motivo, "comando": cid})
    return {"id": cid}


@router.get("/equipos/{equipo_id}/comandos")
async def listar_comandos(equipo_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        "SELECT id, tipo, estado, motivo, creado_por, creado_en, entregado_en, terminado_en, resultado "
        "FROM disp_comandos WHERE equipo_id = $1 ORDER BY creado_en DESC LIMIT 50", equipo_id)
    return {"comandos": [{**dict(f), "resultado": json.loads(f["resultado"]) if isinstance(f["resultado"], str) else f["resultado"]} for f in filas]}


@router.delete("/comandos/{comando_id}")
async def anular_comando(comando_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    r = await db(request).execute(
        "UPDATE disp_comandos SET estado = 'anulado', terminado_en = NOW() WHERE id = $1 AND estado = 'pendiente'", comando_id)
    if r.endswith(" 0"):
        raise HTTPException(409, "El comando ya fue entregado al teléfono o no existe")
    await auditar(request, admin, "dispositivo_comando_anular", str(comando_id))
    return {"ok": True}


@router.post("/equipos/{equipo_id}/ubicaciones")
async def ver_ubicaciones(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    """Consulta auditada: es POST porque exige un motivo y deja registro de quién miró."""
    b = await request.json()
    motivo = _motivo(b)
    horas = int(b.get("horas") or 24)
    if not 1 <= horas <= 24 * 90:
        raise HTTPException(400, "El periodo debe estar entre 1 hora y 90 días")
    filas = await db(request).fetch(
        """SELECT u.id, u.tomada_en, u.recibida_en, u.lat, u.lon, u.precision_m, u.fuente, u.origen, u.bateria, u.rssi,
                  COALESCE(NULLIF(v.nombre, ''), v.modelo, 'otro equipo') AS visto_por_nombre
           FROM disp_ubicaciones u LEFT JOIN disp_equipos v ON v.id = u.visto_por
           WHERE u.equipo_id = $1 AND u.tomada_en > NOW() - make_interval(hours => $2)
           ORDER BY u.tomada_en DESC LIMIT 500""", equipo_id, horas)
    await auditar(request, admin, "dispositivo_ver_ubicacion", str(equipo_id), {"motivo": motivo, "horas": horas, "puntos": len(filas)})
    return {"ubicaciones": [dict(f) for f in filas]}
