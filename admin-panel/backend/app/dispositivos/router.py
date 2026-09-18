"""Panel · Dispositivos (fase 1): equipos enrolados, su ficha de inventario y los códigos de
enrolamiento. Los teléfonos hablan con el webmail (`/api/dispositivos/*`); este panel lee lo que
reportan y escribe lo que decide Tecnología. Toda acción queda en la auditoría del panel.
"""

import hashlib
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.comun import auditar, db, depreciacion, fecha, imei_valido, texto

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")
_ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"   # sin 0/o/1/l/i: se teclea en un teléfono

_CAMPOS_EQUIPO = """id, id_instalacion, modo, estado, fabricante, modelo, serie, imei, android, version_app,
    nombre, custodio_email, custodio_nombre, centro_costo, sede, fecha_compra, valor_compra, vida_util_meses,
    factura_ref, notas, enrolado_en, ultimo_contacto, ultima_ip, bateria, cargando, almacenamiento_libre,
    almacenamiento_total, red, play_protect, revocado_en, revocado_motivo"""


def _equipo(fila) -> dict:
    d = dict(fila)
    d["depreciacion"] = depreciacion(d.get("valor_compra"), d.get("fecha_compra"), d.get("vida_util_meses") or 36)
    if d.get("valor_compra") is not None:
        d["valor_compra"] = float(d["valor_compra"])
    return d


@router.get("/resumen")
async def resumen(request: Request, admin: dict = Depends(get_current_admin)):
    f = await db(request).fetchrow(
        """SELECT count(*) FILTER (WHERE estado = 'activo') AS activos,
                  count(*) FILTER (WHERE estado = 'activo' AND ultimo_contacto < NOW() - interval '24 hours') AS sin_contacto,
                  count(*) FILTER (WHERE estado = 'perdido') AS perdidos,
                  count(*) FILTER (WHERE estado = 'activo' AND modo = 'limitado') AS limitados
           FROM disp_equipos""")
    eventos = await db(request).fetchval(
        "SELECT count(*) FROM disp_eventos WHERE visto_en IS NULL "
        "AND tipo IN ('admin_desactivado', 'desinstalacion_intento', 'sim_cambiada')")
    return {**dict(f), "eventos_sin_revisar": eventos}


@router.get("/equipos")
async def listar_equipos(request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(f"SELECT {_CAMPOS_EQUIPO} FROM disp_equipos ORDER BY estado, nombre, id")
    return {"equipos": [_equipo(f) for f in filas]}


@router.get("/equipos/{equipo_id}")
async def ver_equipo(equipo_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    f = await db(request).fetchrow(f"SELECT {_CAMPOS_EQUIPO} FROM disp_equipos WHERE id = $1", equipo_id)
    if f is None:
        raise HTTPException(404, "Equipo no encontrado")
    latidos = await db(request).fetch(
        "SELECT recibido_en, ip, datos FROM disp_latidos WHERE equipo_id = $1 ORDER BY recibido_en DESC LIMIT 20", equipo_id)
    eventos = await db(request).fetch(
        "SELECT id, tipo, detalle, recibido_en, visto_por, visto_en FROM disp_eventos WHERE equipo_id = $1 "
        "ORDER BY recibido_en DESC LIMIT 50", equipo_id)
    mensajes = await db(request).fetch(
        "SELECT m.id, m.titulo, m.nivel, m.creado_en, me.entregado_en, me.leido_en FROM disp_mensajes_equipos me "
        "JOIN disp_mensajes m ON m.id = me.mensaje_id WHERE me.equipo_id = $1 ORDER BY m.creado_en DESC LIMIT 30", equipo_id)

    def _j(v):
        return json.loads(v) if isinstance(v, str) else v
    return {
        "equipo": _equipo(f),
        "latidos": [{**dict(x), "datos": _j(x["datos"])} for x in latidos],
        "eventos": [{**dict(x), "detalle": _j(x["detalle"])} for x in eventos],
        "mensajes": [dict(x) for x in mensajes],
    }


@router.put("/equipos/{equipo_id}")
async def guardar_equipo(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    imei = texto(b.get("imei"), 20)
    if imei and not imei_valido(imei):
        raise HTTPException(400, "El IMEI debe tener 15 dígitos válidos (márquelo con *#06# o léalo de la caja)")
    valor = b.get("valor_compra")
    if valor in ("", None):
        valor = None
    else:
        try:
            valor = round(float(valor), 2)
        except (TypeError, ValueError):
            raise HTTPException(400, "Valor de compra inválido")
        if not 0 <= valor <= 100000:
            raise HTTPException(400, "Valor de compra fuera de rango")
    vida = int(b.get("vida_util_meses") or 36)
    if not 6 <= vida <= 120:
        raise HTTPException(400, "La vida útil debe estar entre 6 y 120 meses")
    estado = b.get("estado")
    if estado not in (None, "activo", "perdido", "baja"):
        raise HTTPException(400, "Estado inválido")
    r = await db(request).execute(
        """UPDATE disp_equipos SET nombre = COALESCE($2, ''), custodio_email = $3, custodio_nombre = $4,
               centro_costo = $5, sede = $6, imei = COALESCE($7, imei), serie = COALESCE($8, serie),
               fecha_compra = $9, valor_compra = $10, vida_util_meses = $11, factura_ref = $12, notas = $13,
               estado = CASE WHEN estado = 'revocado' THEN estado ELSE COALESCE($14, estado) END
           WHERE id = $1""",
        equipo_id, texto(b.get("nombre"), 120), texto(b.get("custodio_email"), 255), texto(b.get("custodio_nombre"), 160),
        texto(b.get("centro_costo"), 120), texto(b.get("sede"), 120), imei, texto(b.get("serie"), 80),
        fecha(b.get("fecha_compra")), valor, vida, texto(b.get("factura_ref"), 255),
        (str(b.get("notas") or "")[:4000] or None), estado,
    )
    if r.endswith(" 0"):
        raise HTTPException(404, "Equipo no encontrado")
    await auditar(request, admin, "dispositivo_editar", str(equipo_id),
                  {k: b.get(k) for k in ("nombre", "custodio_email", "centro_costo", "sede", "estado")})
    return {"ok": True}


@router.post("/equipos/{equipo_id}/revocar")
async def revocar_equipo(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    motivo = texto((await request.json()).get("motivo"), 255)
    if not motivo:
        raise HTTPException(400, "Indique el motivo")
    # El token deja de valer: se sustituye por una huella aleatoria que nadie conoce.
    r = await db(request).execute(
        "UPDATE disp_equipos SET estado = 'revocado', revocado_en = NOW(), revocado_motivo = $2, token_hash = $3 WHERE id = $1",
        equipo_id, motivo, hashlib.sha256(secrets.token_bytes(32)).hexdigest())
    if r.endswith(" 0"):
        raise HTTPException(404, "Equipo no encontrado")
    await auditar(request, admin, "dispositivo_revocar", str(equipo_id), {"motivo": motivo})
    return {"ok": True}


@router.post("/eventos/{evento_id}/visto")
async def evento_visto(evento_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    await db(request).execute(
        "UPDATE disp_eventos SET visto_por = $2, visto_en = NOW() WHERE id = $1 AND visto_en IS NULL",
        evento_id, admin["username"])
    return {"ok": True}


# ── Códigos de enrolamiento (la «contraseña de instalación») ─────────────────────────────

@router.get("/codigos")
async def listar_codigos(request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        "SELECT id, prefijo, etiqueta, modo, usos_max, usos, creado_por, creado_en, caduca_en, revocado_en "
        "FROM disp_codigos ORDER BY creado_en DESC LIMIT 200")
    return {"codigos": [dict(f) for f in filas]}


@router.post("/codigos")
async def crear_codigo(request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    modo = b.get("modo") if b.get("modo") in ("propietario", "limitado") else "propietario"
    usos = int(b.get("usos_max") or 1)
    horas = int(b.get("horas_validez") or 72)
    if not 1 <= usos <= 500 or not 1 <= horas <= 24 * 90:
        raise HTTPException(400, "Usos (1-500) u horas de validez (1-2160) fuera de rango")
    grupos = ["".join(secrets.choice(_ALFABETO) for _ in range(4)) for _ in range(3)]
    codigo = "-".join(grupos)
    fila = await db(request).fetchrow(
        "INSERT INTO disp_codigos (codigo_hash, prefijo, etiqueta, modo, usos_max, creado_por, caduca_en) "
        "VALUES ($1,$2,$3,$4,$5,$6, NOW() + make_interval(hours => $7)) RETURNING id, caduca_en",
        hashlib.sha256("".join(grupos).encode()).hexdigest(), grupos[0], texto(b.get("etiqueta"), 120) or "",
        modo, usos, admin["username"], horas)
    await auditar(request, admin, "dispositivo_codigo_crear", str(fila["id"]), {"modo": modo, "usos_max": usos, "horas": horas})
    # El código en claro se devuelve UNA vez; en la base solo queda su huella.
    return {"id": fila["id"], "codigo": codigo, "caduca_en": fila["caduca_en"], "modo": modo, "usos_max": usos}


@router.delete("/codigos/{codigo_id}")
async def revocar_codigo(codigo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    await db(request).execute("UPDATE disp_codigos SET revocado_en = NOW() WHERE id = $1 AND revocado_en IS NULL", codigo_id)
    await auditar(request, admin, "dispositivo_codigo_revocar", str(codigo_id))
    return {"ok": True}
