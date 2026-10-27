"""Endpoints de T-74 (contrato acordado con el equipo de la app el 20/10/2026).

POST /api/respaldos/alta-equipo  (sesión del trabajador: cookie `access_token` o `Authorization: Bearer`)
    {"equipo": "WILSONARGUELLO", "machine_guid": "<uuid>", "app": "0.7.2"}
    200 {"codigo", "cliente", "nuevo", "caduca_en_s": 600}
    400 datos_invalidos · 401 sin_sesion · 403 cuenta_no_habilitada · 409 equipo_de_otra_persona
    429 demasiados_intentos · 503 respaldos_no_disponible

POST /api/respaldos/canjear  (sin sesión: tarea de la app como SISTEMA)
    {"codigo": "<43 caracteres>", "machine_guid": "<uuid>"}
    200 {"servidor", "puerto", "cliente", "clave"}   (ORG_SERVIDOR_RESPALDOS / ORG_PUERTO_RESPALDOS)
    400 datos_invalidos · 404 codigo_desconocido · 410 codigo_usado_o_caducado
    403 equipo_no_coincide (el código queda anulado) · 429 demasiados_intentos · 503 respaldos_no_disponible

Errores siempre como {"error": "<código>", "detail": "<texto para la persona>"}.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.respaldos import codigos, limites, urbackup_api, vinculos

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/respaldos", tags=["respaldos"])

SESIONES_VALIDAS = ("normal", "oidc", "app")


def _error(estado: int, codigo: str, texto: str) -> JSONResponse:
    return JSONResponse(status_code=estado, content={"error": codigo, "detail": texto})


def _ip(request: Request) -> str:
    return request.headers.get(
        "X-Real-IP", request.client.host if request.client else ""
    )


def _guid(v) -> str | None:
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError, AttributeError):
        return None


async def _cuerpo(request: Request) -> dict:
    try:
        b = await request.json()
    except Exception:
        return {}
    return b if isinstance(b, dict) else {}


async def _persona(request: Request) -> tuple[str, str]:
    """(correo de la persona, tipo de sesión). Lanza HTTPException 401/403 como el resto del correo."""
    from app.auth.dependencies import get_current_user

    if not request.cookies.get("access_token"):
        cab = request.headers.get("authorization", "")
        if not cab.lower().startswith("bearer "):
            raise HTTPException(401, "Not authenticated")
        # Mismo token que la cookie: se valida con la misma regla (F-01).
        from app.auth.jwt import decode_access_token
        from app.auth.sesiones import sesion_valida

        payload = decode_access_token(cab[7:].strip())
        valida = payload and await sesion_valida(
            request.app.state.db_pool, request.app.state.redis, payload
        )
        if not valida:
            raise HTTPException(401, "Session expired")
        return valida[0].lower(), payload.get("kind", "normal")
    usuario = await get_current_user(request)
    persona = getattr(request.state, "persona", None) or usuario
    return persona.lower(), getattr(request.state, "session_kind", "normal")


def _cuentas_de_prueba() -> set[str]:
    from app import organizacion

    return {c.lower() for c in organizacion.lista("RESPALDOS_CUENTAS_PRUEBA")}


async def _auditar(db, request, usuario, accion, objetivo, detalle) -> None:
    try:
        await db.execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
            "VALUES (NULL, $1, $2, $3, $4::jsonb, $5)",
            usuario,
            accion,
            objetivo,
            json.dumps(detalle, ensure_ascii=False),
            _ip(request),
        )
    except Exception:
        logger.exception("respaldos_auditoria_fallo | %s", accion)


@router.post("/alta-equipo")
async def alta_equipo(request: Request):
    b = await _cuerpo(request)
    equipo = str(b.get("equipo") or "").strip()
    guid = _guid(b.get("machine_guid"))
    app_v = str(b.get("app") or "")[:20]
    if not guid or not equipo or len(equipo) > 63 or not equipo.isprintable():
        return _error(
            400, "datos_invalidos", "Faltan el nombre del equipo o su identificador."
        )

    try:
        usuario, tipo = await _persona(request)
    except HTTPException as e:
        if e.status_code == 401:
            return _error(401, "sin_sesion", "Inicia sesión en la app.")
        return _error(
            403, "cuenta_no_habilitada", "Esta sesión no puede dar de alta equipos."
        )
    if tipo not in SESIONES_VALIDAS and usuario not in _cuentas_de_prueba():
        return _error(
            403, "cuenta_no_habilitada", "Esta sesión no puede dar de alta equipos."
        )

    db = request.app.state.db_pool
    redis = request.app.state.redis
    try:
        cuenta = await vinculos.comprobar_cuenta(db, usuario)
    except vinculos.CuentaNoHabilitada as e:
        logger.info("respaldos_alta_rechazada | user=%s | motivo=%s", usuario, e)
        return _error(
            403,
            "cuenta_no_habilitada",
            "Esta cuenta no tiene respaldo de equipos. Escribe a soporte.",
        )
    if await limites.alta_superada(redis, usuario):
        return _error(
            429,
            "demasiados_intentos",
            "Demasiados intentos. Vuelve a probar en una hora.",
        )

    try:
        decision = await vinculos.decidir_cliente(db, usuario, guid, cuenta)
    except vinculos.CuentaNoHabilitada as e:
        logger.info("respaldos_alta_rechazada | user=%s | motivo=%s", usuario, e)
        return _error(
            403,
            "cuenta_no_habilitada",
            "Soporte todavía no ha vinculado tu equipo de respaldo. Escribe a soporte.",
        )
    except vinculos.EquipoDeOtraPersona as e:
        logger.warning(
            "respaldos_equipo_ajeno | user=%s | guid=%s | dueno=%s", usuario, guid, e
        )
        await _auditar(
            db,
            request,
            usuario,
            "respaldos_equipo_ajeno",
            guid,
            {"equipo": equipo, "dueno": str(e)},
        )
        return _error(
            409,
            "equipo_de_otra_persona",
            "Este equipo está registrado a nombre de otra persona. Soporte lo revisará.",
        )
    if decision["nuevo"] and await limites.nuevos_superados(redis, usuario):
        return _error(
            429,
            "demasiados_intentos",
            "Ya se dieron de alta dos equipos nuevos hoy. Escribe a soporte.",
        )

    try:
        async with urbackup_api.Panel():
            pass  # solo comprobar que el panel responde y acepta al usuario de la API
    except urbackup_api.NoDisponible as e:
        logger.warning("respaldos_no_disponible | alta | %s", e)
        return _error(
            503,
            "respaldos_no_disponible",
            "El servidor de respaldos no responde. Se reintentará en una hora.",
        )

    codigo = await codigos.emitir(
        db,
        user_email=usuario,
        machine_guid=guid,
        equipo=equipo,
        app=app_v,
        decision=decision,
        ip=_ip(request),
    )
    logger.info(
        "respaldos_alta | user=%s | cliente=%s | nuevo=%s",
        usuario,
        decision["cliente"],
        decision["nuevo"],
    )
    return {
        "codigo": codigo,
        "cliente": decision["cliente"],
        "nuevo": decision["nuevo"],
        "caduca_en_s": codigos.VIGENCIA_S,
    }


async def _clave(panel, cod) -> tuple[int, str, str]:
    """(clientid, cliente, clave). Cliente nuevo: si el nombre ya existe en UrBackup se prueba -2, -3…"""
    if not cod["nuevo"]:
        return cod["clientid"], cod["cliente"], await panel.clave_de(cod["clientid"])
    base, _, num = cod["cliente"].rpartition("-")
    if not (base and num.isdigit()):
        base, num = cod["cliente"], "1"
    for n in range(int(num), int(num) + 10):
        nombre = base if n == 1 else f"{base}-{n}"
        try:
            clientid, clave = await panel.crear(nombre)
            return clientid, nombre, clave
        except urbackup_api.NombreOcupado:
            continue
    raise urbackup_api.NoDisponible("no hay nombre libre para el cliente nuevo")


@router.post("/canjear")
async def canjear(request: Request):
    db = request.app.state.db_pool
    ip = _ip(request)
    if await limites.canje_superado(request.app.state.redis, ip):
        return _error(429, "demasiados_intentos", "Demasiados intentos desde esta red.")
    b = await _cuerpo(request)
    texto = str(b.get("codigo") or "")
    guid = _guid(b.get("machine_guid"))
    if not guid or not codigos.FORMATO.match(texto):
        return _error(
            400,
            "datos_invalidos",
            "Código o identificador del equipo con formato incorrecto.",
        )

    cod = await codigos.buscar(db, texto)
    if cod is None:
        return _error(404, "codigo_desconocido", "Código desconocido.")
    if cod["usado_en"] or cod["anulado_en"] or cod["caducado"]:
        return _error(
            410,
            "codigo_usado_o_caducado",
            "El código ya se usó o caducó. Pide uno nuevo.",
        )
    if cod["machine_guid"] != guid:
        await codigos.anular(db, cod["id"], "equipo_no_coincide")
        logger.warning(
            "respaldos_canje_otro_equipo | user=%s | guid=%s", cod["user_email"], guid
        )
        return _error(
            403, "equipo_no_coincide", "El código es de otro equipo y quedó anulado."
        )
    if not await codigos.marcar_usado(db, cod["id"], ip):
        return _error(
            410,
            "codigo_usado_o_caducado",
            "El código ya se usó o caducó. Pide uno nuevo.",
        )

    try:
        async with urbackup_api.Panel() as panel:
            clientid, cliente, clave = await _clave(panel, cod)
    except urbackup_api.NoDisponible as e:
        # El código vuelve a valer (si no caducó): la app reintenta sin pedir otro.
        await db.execute(
            "UPDATE respaldos_codigos SET usado_en = NULL, ip_canje = '' WHERE id = $1",
            cod["id"],
        )
        logger.warning("respaldos_no_disponible | canje | %s", e)
        return _error(
            503,
            "respaldos_no_disponible",
            "El servidor de respaldos no responde. Reintenta en una hora.",
        )

    await db.execute(
        "INSERT INTO respaldos_equipos (machine_guid, user_email, clientid, cliente, equipo, app) "
        "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (machine_guid) DO UPDATE SET "
        "clientid = EXCLUDED.clientid, cliente = EXCLUDED.cliente, equipo = EXCLUDED.equipo, "
        "app = EXCLUDED.app, ultimo_canje = NOW()",
        guid,
        cod["user_email"],
        clientid,
        cliente,
        cod["equipo"],
        cod["app"],
    )
    if cod["nuevo"]:
        await db.execute(
            "INSERT INTO respaldos_vinculos (user_email, clientid, cliente, nota, cargado_por) "
            "VALUES ($1, $2, $3, 'creado por el alta automática', 'alta-equipo') ON CONFLICT (user_email) DO NOTHING",
            cod["user_email"],
            clientid,
            cliente,
        )
    await _auditar(
        db,
        request,
        cod["user_email"],
        "respaldos_canje",
        cliente,
        {
            "clientid": clientid,
            "nuevo": cod["nuevo"],
            "machine_guid": guid,
            "equipo": cod["equipo"],
        },
    )
    logger.info(
        "respaldos_canje | user=%s | cliente=%s | nuevo=%s",
        cod["user_email"],
        cliente,
        cod["nuevo"],
    )
    return {
        "servidor": urbackup_api.servidor(),
        "puerto": urbackup_api.puerto(),
        "cliente": cliente,
        "clave": clave,
    }
