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


@router.get("")
async def estado(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    activo = await db.fetchrow(
        "SELECT id, prefijo, caduca_en, usos, usos_max, codigo_cifrado FROM disp_codigos "
        "WHERE custodio_email = $1 AND revocado_en IS NULL AND usos < usos_max "
        "AND (caduca_en IS NULL OR caduca_en > NOW()) ORDER BY creado_en DESC LIMIT 1",
        username,
    )
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
    final = _imeis.unir(lista, actual["imeis"])
    await db.execute("UPDATE disp_equipos SET imeis = $2::jsonb, imei = COALESCE(imei, $3) WHERE id = $1", equipo_id, json.dumps(final), final[0])
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES (NULL, $1, 'dispositivo_custodio_imeis', $2, $3::jsonb, $4)",
        username, str(equipo_id), json.dumps({"imeis": final}), request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True, "imeis": final}
