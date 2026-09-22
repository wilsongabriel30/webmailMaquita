"""API que usan los teléfonos institucionales (fase 1). Contrato: docs/DISPOSITIVOS.md.

Enrolamiento con código (la «contraseña de instalación» que entrega Tecnología), latidos con el
estado del equipo, entrega de comandos y de mensajes urgentes con acuse, y eventos de seguridad
(p. ej. que alguien quitó a la app como administradora del dispositivo). El panel de administración
escribe los códigos, mensajes y comandos; aquí solo se entregan al equipo dueño del token.
"""

import json
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dispositivos import anclas as _anclas
from app.dispositivos import imeis as _imeis
from app.dispositivos import ubicacion as _ubic
from app.dispositivos.esquemas import (
    TIPOS_EVENTO,
    Acuse,
    Enrolamiento,
    Evento,
    Latido,
    ResultadoComando,
)
from app.dispositivos.seguridad import (
    equipo_actual,
    hash_secreto,
    ip_cliente,
    limitar,
    limpiar_codigo,
    nuevo_token,
)

logger = logging.getLogger("dispositivos")
router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])

POLITICA_BASE = {"version": 1, "latido_minutos": 15}


def _push_info(pol: dict, topic):
    servidor = (pol.get("push") or {}).get("servidor")
    return (
        {"servidor": servidor, "tema": topic, "protocolo": "ntfy"}
        if servidor and topic
        else None
    )


async def _politica(db) -> dict:
    try:
        v = await db.fetchval("SELECT valor FROM disp_config WHERE clave = 'politica'")
        return {**POLITICA_BASE, **(json.loads(v) if isinstance(v, str) else (v or {}))}
    except Exception:
        return dict(POLITICA_BASE)


async def _custodio_de_sesion(request: Request) -> str | None:
    """Si el enrolamiento llega con la sesión de correo abierta, esa persona queda como custodia."""
    try:
        from app.auth.dependencies import get_current_user

        return await get_current_user(request)
    except Exception:
        return None


@router.post("/enrolar")
async def enrolar(request: Request, body: Enrolamiento):
    ip = ip_cliente(request)
    await limitar(request, f"enrolar:{ip}", 10, 3600)
    db = request.app.state.db_pool
    custodio = await _custodio_de_sesion(request)
    token = nuevo_token()
    topic = "disp_" + secrets.token_hex(16)

    async with db.acquire() as con, con.transaction():
        codigo = await con.fetchrow(
            # Al agotarse el código se borra su copia cifrada (AE-04): ya no hay nada que mostrar.
            "UPDATE disp_codigos SET usos = usos + 1, "
            "codigo_cifrado = CASE WHEN usos + 1 >= usos_max THEN NULL ELSE codigo_cifrado END "
            "WHERE codigo_hash = $1 AND revocado_en IS NULL AND usos < usos_max "
            "AND (caduca_en IS NULL OR caduca_en > NOW()) RETURNING id, modo, custodio_email",
            hash_secreto(limpiar_codigo(body.codigo)),
        )
        if codigo is None:
            logger.warning(
                "enrolamiento_rechazado | ip=%s | instalacion=%s",
                ip,
                body.id_instalacion,
            )
            raise HTTPException(
                403,
                "Código de enrolamiento no válido, agotado o caducado. Pídalo a Tecnología.",
            )
        # El modo lo decide el código (lo que autorizó Tecnología), no lo que diga el teléfono.
        modo = "limitado" if body.modo == "limitado" else codigo["modo"]
        # Un código autoservicio ya trae al custodio (el propio usuario que lo generó).
        if codigo["custodio_email"]:
            custodio = codigo["custodio_email"]
        equipo = await con.fetchrow(
            """INSERT INTO disp_equipos (id_instalacion, token_hash, codigo_id, modo, fabricante, modelo, serie,
                   imei, android, version_app, custodio_email, ultimo_contacto, ultima_ip, push_topic)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW(),$12,$13)
               ON CONFLICT (id_instalacion) DO UPDATE SET
                   token_hash = EXCLUDED.token_hash, codigo_id = EXCLUDED.codigo_id, modo = EXCLUDED.modo,
                   fabricante = EXCLUDED.fabricante, modelo = EXCLUDED.modelo,
                   serie = COALESCE(EXCLUDED.serie, disp_equipos.serie),
                   imei = COALESCE(EXCLUDED.imei, disp_equipos.imei),
                   android = EXCLUDED.android, version_app = EXCLUDED.version_app,
                   custodio_email = COALESCE(disp_equipos.custodio_email, EXCLUDED.custodio_email),
                   estado = 'activo', revocado_en = NULL, revocado_motivo = NULL,
                   ultimo_contacto = NOW(), ultima_ip = EXCLUDED.ultima_ip,
                   push_topic = COALESCE(disp_equipos.push_topic, EXCLUDED.push_topic)
               RETURNING id, nombre, push_topic""",
            body.id_instalacion,
            hash_secreto(token),
            codigo["id"],
            modo,
            body.fabricante,
            body.modelo,
            body.serie,
            body.imei,
            body.android,
            body.version_app,
            custodio,
            ip,
            topic,
        )
        await con.execute(
            "INSERT INTO disp_eventos (equipo_id, tipo, detalle) VALUES ($1, 'enrolado', $2::jsonb)",
            equipo["id"],
            json.dumps({"modo": modo, "ip": ip, "custodio": custodio}),
        )
        lista = _imeis.unir(None, (body.imeis or []) + ([body.imei] if body.imei else []))
        if lista:
            await con.execute(
                "UPDATE disp_equipos SET imeis = $2::jsonb, imei = COALESCE(imei, $3) WHERE id = $1",
                equipo["id"], json.dumps(_imeis.unir(await con.fetchval("SELECT imeis FROM disp_equipos WHERE id = $1", equipo["id"]), lista)), lista[0],
            )
    logger.info(
        "equipo_enrolado | id=%s | modo=%s | modelo=%s | ip=%s",
        equipo["id"],
        modo,
        body.modelo,
        ip,
    )
    return {
        "id_equipo": equipo["id"],
        "token_equipo": token,  # se entrega una sola vez; el servidor guarda solo su huella
        "modo": modo,
        "politica": await _politica(db),
        "push": _push_info(await _politica(db), equipo["push_topic"]),
    }


@router.post("/latido")
async def latido(request: Request, body: Latido, equipo: dict = Depends(equipo_actual)):
    db = request.app.state.db_pool
    ip = ip_cliente(request)
    await limitar(request, f"latido:{equipo['id']}", 30, 600)
    datos = body.model_dump(exclude_none=True)
    datos.pop(
        "ubicacion", None
    )  # la posición nunca queda en el JSON del latido: va a su tabla, y solo si procede
    async with db.acquire() as con, con.transaction():
        await con.execute(
            """UPDATE disp_equipos SET ultimo_contacto = NOW(), ultima_ip = $2,
                   bateria = COALESCE($3, bateria), cargando = COALESCE($4, cargando),
                   almacenamiento_libre = COALESCE($5, almacenamiento_libre),
                   almacenamiento_total = COALESCE($6, almacenamiento_total),
                   red = COALESCE($7, red), version_app = COALESCE($8, version_app),
                   android = COALESCE($9, android), play_protect = COALESCE($10, play_protect),
                   admin_activo = COALESCE($11, admin_activo),
                   wifi_ssid = CASE WHEN $7 IS NULL THEN wifi_ssid WHEN lower($7) LIKE '%wifi%' THEN $12 ELSE NULL END,
                   wifi_bssid = CASE WHEN $7 IS NULL THEN wifi_bssid WHEN lower($7) LIKE '%wifi%' THEN lower($13) ELSE NULL END,
                   wifi_en = CASE WHEN $12 IS NOT NULL THEN NOW() ELSE wifi_en END
               WHERE id = $1""",
            equipo["id"],
            ip,
            body.bateria,
            body.cargando,
            body.almacenamiento_libre,
            body.almacenamiento_total,
            body.red,
            body.version_app,
            body.android,
            body.play_protect,
            body.admin_activo,
            body.wifi_ssid,
            body.wifi_bssid,
        )
        await con.execute(
            "INSERT INTO disp_latidos (equipo_id, ip, datos) VALUES ($1, $2, $3::jsonb)",
            equipo["id"],
            ip,
            json.dumps(datos),
        )
        if body.ubicacion is not None:
            await _ubic.guardar(
                con, equipo, [body.ubicacion], "periodica", ip, body.bateria
            )
        if body.imeis:
            actuales = await con.fetchval("SELECT imeis FROM disp_equipos WHERE id = $1", equipo["id"])
            lista = _imeis.unir(actuales, body.imeis)
            if lista:
                await con.execute("UPDATE disp_equipos SET imeis = $2::jsonb, imei = COALESCE(imei, $3) WHERE id = $1",
                                  equipo["id"], json.dumps(lista), lista[0])
        # Ancla de red: si la IP es de una sede conocida, el equipo está en esa sede (etapa 1).
        try:
            await _anclas.registrar(con, equipo, ip, _ubic.puede_guardar(equipo), body.wifi_bssid)
        except Exception:
            logger.exception("ancla_red_fallo | equipo=%s", equipo["id"])
        comandos = await con.fetch(
            "UPDATE disp_comandos SET estado = 'entregado', entregado_en = NOW() "
            "WHERE equipo_id = $1 AND estado = 'pendiente' RETURNING id, tipo, parametros",
            equipo["id"],
        )
        mensajes = await con.fetch(
            """UPDATE disp_mensajes_equipos me SET entregado_en = COALESCE(me.entregado_en, NOW())
               FROM disp_mensajes m
               WHERE me.mensaje_id = m.id AND me.equipo_id = $1 AND me.leido_en IS NULL
                 AND (m.caduca_en IS NULL OR m.caduca_en > NOW())
               RETURNING m.id, m.titulo, m.texto, m.nivel, m.requiere_acuse, m.creado_en""",
            equipo["id"],
        )
    pol = await _politica(db)
    await _ubic.limpieza_ocasional(db, pol)
    perdido = equipo["estado"] == "perdido"
    buscadas = await db.fetch(
        "SELECT baliza_id FROM disp_equipos WHERE estado = 'perdido' AND baliza_id IS NOT NULL AND id <> $1 LIMIT 50",
        equipo["id"],
    )
    return {
        "ubicacion_activa": _ubic.puede_guardar(equipo),
        "ubicacion_minutos": pol.get("ubicacion_minutos", 15),
        "modo_perdido": (
            {
                "mensaje": equipo["perdido_mensaje"],
                "telefono": equipo["perdido_telefono"],
                "baliza_id": equipo["baliza_id"],
            }
            if perdido
            else None
        ),
        "balizas_buscadas": [b["baliza_id"] for b in buscadas],
        "respaldo": (
            {**pol.get("respaldo", {}), "activo": True}
            if equipo.get("respaldo_activo")
            else {"activo": False}
        ),
        "comandos": [
            {
                "id": c["id"],
                "tipo": c["tipo"],
                "parametros": (
                    json.loads(c["parametros"])
                    if isinstance(c["parametros"], str)
                    else c["parametros"]
                ),
            }
            for c in comandos
        ],
        "mensajes": [
            {
                "id": m["id"],
                "titulo": m["titulo"],
                "texto": m["texto"],
                "nivel": m["nivel"],
                "requiere_acuse": m["requiere_acuse"],
                "creado_en": m["creado_en"].isoformat(),
            }
            for m in mensajes
        ],
        "politica_version": pol.get("version", 1),
        "latido_minutos": (
            pol.get("latido_minutos_perdido", 5)
            if perdido
            else pol.get("latido_minutos", 15)
        ),
    }


@router.post("/comandos/{comando_id}/resultado")
async def resultado_comando(
    comando_id: int,
    request: Request,
    body: ResultadoComando,
    equipo: dict = Depends(equipo_actual),
):
    if body.wifis_vistas:
        # Etapa 2: redes vistas al localizar → triangulación contra los puntos de acceso de Maquita.
        try:
            async with request.app.state.db_pool.acquire() as con:
                await _anclas.guardar_triangulacion(con, equipo, [w.model_dump() for w in body.wifis_vistas], ip_cliente(request), _ubic.puede_guardar(equipo))
        except Exception:
            logger.exception("triangulacion_fallo | equipo=%s", equipo["id"])
    r = await request.app.state.db_pool.execute(
        "UPDATE disp_comandos SET estado = $3, terminado_en = NOW(), resultado = $4::jsonb "
        "WHERE id = $1 AND equipo_id = $2 AND estado IN ('entregado', 'pendiente')",
        comando_id,
        equipo["id"],
        body.estado,
        json.dumps({"detalle": body.detalle}),
    )
    if r.endswith(" 0"):
        raise HTTPException(404, "Comando no encontrado para este equipo")
    return {"ok": True}


@router.post("/mensajes/{mensaje_id}/acuse")
async def acuse_mensaje(
    mensaje_id: int,
    request: Request,
    body: Acuse,
    equipo: dict = Depends(equipo_actual),
):
    r = await request.app.state.db_pool.execute(
        "UPDATE disp_mensajes_equipos SET leido_en = COALESCE(leido_en, NOW()), "
        "entregado_en = COALESCE(entregado_en, NOW()) WHERE mensaje_id = $1 AND equipo_id = $2",
        mensaje_id,
        equipo["id"],
    )
    if r.endswith(" 0"):
        raise HTTPException(404, "Mensaje no encontrado para este equipo")
    return {"ok": True}


@router.post("/evento")
async def evento(request: Request, body: Evento, equipo: dict = Depends(equipo_actual)):
    await limitar(request, f"evento:{equipo['id']}", 60, 3600)
    tipo = body.tipo if body.tipo in TIPOS_EVENTO else "otro"
    detalle = json.dumps(body.detalle or {})
    if len(detalle) > 4000:
        detalle = json.dumps({"truncado": True})
    await request.app.state.db_pool.execute(
        "INSERT INTO disp_eventos (equipo_id, tipo, detalle) VALUES ($1, $2, $3::jsonb)",
        equipo["id"],
        tipo,
        detalle,
    )
    if tipo in ("admin_desactivado", "desinstalacion_intento", "sim_cambiada"):
        logger.warning("evento_seguridad | equipo=%s | tipo=%s", equipo["id"], tipo)
    return {"ok": True}


@router.get("/yo")
async def yo(request: Request, equipo: dict = Depends(equipo_actual)):
    """Lo que la app muestra en «Este equipo es de Maquita»."""
    pol = await _politica(request.app.state.db_pool)
    return {
        "id_equipo": equipo["id"],
        "nombre": equipo["nombre"],
        "modo": equipo["modo"],
        "estado": equipo["estado"],
        "custodio_email": equipo["custodio_email"],
        "custodio_nombre": equipo["custodio_nombre"],
        "contacto_ti": pol.get("contacto_ti"),
        "telefono_ti": pol.get("telefono_ti"),
        "aviso_privacidad": pol.get("aviso_privacidad"),
        "ubicacion_activa": _ubic.puede_guardar(equipo),
        "push": _push_info(pol, equipo.get("push_topic")),
    }


@router.get("/politica")
async def politica(request: Request, equipo: dict = Depends(equipo_actual)):
    return await _politica(request.app.state.db_pool)
