"""«Mi teléfono» en la Configuración del correo (solo lectura desde el 22/09/2026).

Decisión de dirección: el código de enrolamiento lo crea, cambia y anula ÚNICAMENTE Tecnología desde
el panel de administración (Teléfonos institucionales → Códigos de enrolamiento), asignado a una
persona. Aquí la persona solo lo consulta: ve su código vigente (para escribirlo en la app si hace
falta), su vencimiento y sus teléfonos activados. La app Maquita Mail 1.2.8 llama a este mismo GET con
la cookie del correo y, si llega `codigo`, activa la gestión sin teclear nada.

Ya no existen POST (generar) ni DELETE (anular) en esta ruta: la app y el webmail no pueden crear ni
retirar códigos por su cuenta. Cada entrega del código en claro queda en `admin_audit`
(`dispositivo_codigo_ver_custodio`, sin admin_id: lo pidió la propia persona).

No da acceso al correo: es solo para la gestión del equipo. La sesión del correo ya exige el segundo
factor cuando la persona lo tiene activo, así que el código se entrega solo tras esa verificación.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.dispositivos.codigo_cifrado import descifrar

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings/mi-equipo", tags=["mi-equipo"])


async def _equipos_del_usuario(db, username: str) -> list[dict]:
    filas = await db.fetch(
        "SELECT id, nombre, modelo, fabricante, estado, modo, ultimo_contacto, imeis FROM disp_equipos "
        "WHERE custodio_email = $1 AND estado <> 'baja' ORDER BY enrolado_en DESC",
        username,
    )
    salida = []
    for f in filas:
        d = dict(f)
        d["imeis"] = json.loads(d["imeis"]) if isinstance(d["imeis"], str) else (d["imeis"] or [])
        salida.append(d)
    return salida


async def _auditar_lectura(db, request: Request, username: str, codigo_id: int) -> None:
    try:
        await db.execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
            "VALUES (NULL, $1, 'dispositivo_codigo_ver_custodio', $2, $3::jsonb, $4)",
            username,
            str(codigo_id),
            '{"origen": "configuracion-correo"}',
            request.headers.get("X-Real-IP", request.client.host if request.client else ""),
        )
    except Exception:
        logger.exception("auditoria_codigo_custodio_fallo | user=%s", username)


async def _auto_enrolar_activo(db) -> bool:
    """Política «vinculación automática»: al iniciar sesión en la app, el teléfono se vincula solo a la
    cuenta (modo limitado) sin que Tecnología cree un código. Se activa o apaga desde el panel."""
    try:
        v = await db.fetchval("SELECT valor->>'auto_enrolar' FROM disp_config WHERE clave = 'politica'")
        return str(v).lower() in ("true", "1")
    except Exception:
        return False


async def _generar_automatico(db, username: str) -> dict | None:
    """Crea un código de modo limitado, 1 uso, 24 h, asignado a la persona (queda como custodia),
    cifrado para que la app lo reciba en claro. Solo si la política lo permite."""
    import hashlib
    import secrets

    from app.dispositivos.codigo_cifrado import cifrar

    alfabeto = "abcdefghjkmnpqrstuvwxyz23456789"
    grupos = ["".join(secrets.choice(alfabeto) for _ in range(4)) for _ in range(3)]
    claro = "-".join(grupos)
    cifrado = cifrar(claro)
    if not cifrado:
        return None
    fila = await db.fetchrow(
        "INSERT INTO disp_codigos (codigo_hash, prefijo, etiqueta, modo, usos_max, creado_por, autoservicio, custodio_email, caduca_en, codigo_cifrado) "
        "VALUES ($1, $2, 'Vinculación automática al iniciar sesión en la app', 'limitado', 1, $3, true, $3, NOW() + interval '24 hours', $4) "
        "RETURNING id, prefijo, caduca_en, usos, usos_max, codigo_cifrado",
        hashlib.sha256("".join(grupos).encode()).hexdigest(), grupos[0], username, cifrado,
    )
    logger.info("codigo_automatico | user=%s | id=%s", username, fila["id"])
    return fila


@router.get("")
async def estado(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    activo = await db.fetchrow(
        "SELECT id, prefijo, caduca_en, usos, usos_max, codigo_cifrado FROM disp_codigos "
        "WHERE custodio_email = $1 AND revocado_en IS NULL AND usos < usos_max "
        "AND (caduca_en IS NULL OR caduca_en > NOW()) ORDER BY creado_en DESC LIMIT 1",
        username,
    )
    if activo is None and await _auto_enrolar_activo(db):
        activo = await _generar_automatico(db, username)
    codigo = descifrar(activo["codigo_cifrado"]) if activo else None
    if codigo:
        await _auditar_lectura(db, request, username, activo["id"])
    return {
        "tiene_codigo_activo": activo is not None,
        "prefijo": activo["prefijo"] if activo else None,
        "caduca_en": (
            activo["caduca_en"].isoformat() if activo and activo["caduca_en"] else None
        ),
        "codigo": codigo,
        "equipos": await _equipos_del_usuario(db, username),
    }


@router.put("/{equipo_id}/imeis")
async def registrar_imeis(equipo_id: int, request: Request, username: str = Depends(get_current_user)):
    """La persona registra los IMEI de su teléfono (*#06# o la caja) para tenerlos a mano si lo roban.
    Se aceptan de 1 a 4; los que reporta el propio teléfono no se pueden borrar desde aquí."""
    from app.dispositivos import imeis as _imeis

    db = request.app.state.db_pool
    b = await request.json()
    lista = _imeis.normalizar(b.get("imeis"))
    if not lista:
        raise HTTPException(400, "Escribe un IMEI válido: 14 a 17 dígitos (marca *#06# en el teléfono)")
    actual = await db.fetchrow("SELECT imeis, imei FROM disp_equipos WHERE id = $1 AND custodio_email = $2 AND estado <> 'baja'", equipo_id, username)
    if actual is None:
        raise HTTPException(404, "Ese teléfono no está a tu nombre")
    ajenos = await _imeis.ajenos(db, equipo_id, lista)
    if ajenos:
        raise HTTPException(409, f"El IMEI {', '.join(ajenos)} ya está registrado en otro teléfono de Maquita. Revisa el número (*#06#) o avisa a Tecnología.")
    final = _imeis.unir(lista, actual["imeis"])
    origen = _imeis.origenes(await db.fetchval("SELECT imeis_origen FROM disp_equipos WHERE id = $1", equipo_id), lista, "persona")
    await db.execute("UPDATE disp_equipos SET imeis = $2::jsonb, imei = COALESCE(imei, $3), imeis_origen = $4::jsonb WHERE id = $1", equipo_id, json.dumps(final), final[0], json.dumps(origen))
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES (NULL, $1, 'dispositivo_custodio_imeis', $2, $3::jsonb, $4)",
        username, str(equipo_id), json.dumps({"imeis": final}), request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True, "imeis": final}
