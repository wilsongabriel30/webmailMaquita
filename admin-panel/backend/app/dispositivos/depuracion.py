"""Panel · Dispositivos: eliminación definitiva de pruebas fallidas (22/09/2026, pedido de dirección).

Con cientos de teléfonos, anular sin poder borrar es inmanejable. Aquí se borran de verdad códigos,
equipos (con todo su historial: latidos, eventos, mensajes, comandos, ubicaciones, respaldos, alertas y
lotes GNSS, por las claves foráneas en cascada) y mensajes. Solo administradores, con la palabra de
confirmación exacta, y todo queda en `admin_audit`. El teléfono borrado recibe 401 en su siguiente
reporte y apaga el módulo; se puede volver a enrolar con un código nuevo.
Los archivos de respaldo cifrados del equipo en disco se borran con el registro.
"""

import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import require_role
from app.dispositivos.comun import auditar, db

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")
RESPALDOS = os.environ.get("DISP_RESPALDO_DIR", "/mnt/almacen/.respaldo-movil")
GNSS = os.environ.get("DISP_GNSS_DIR", "/var/lib/maquita-webmail/gnss")


def _confirmar(b: dict, esperado: str):
    if (b.get("confirmacion") or "").strip().upper() != esperado.upper():
        raise HTTPException(400, f"Para confirmar escriba exactamente: {esperado}")


@router.delete("/codigos/{codigo_id}/definitivo")
async def borrar_codigo(codigo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    """Borra el código. Los equipos enrolados con él siguen (quedan sin referencia al código)."""
    c = await db(request).fetchrow("SELECT id, prefijo, etiqueta FROM disp_codigos WHERE id = $1", codigo_id)
    if c is None:
        raise HTTPException(404, "Código no encontrado")
    await db(request).execute("DELETE FROM disp_codigos WHERE id = $1", codigo_id)
    await auditar(request, admin, "dispositivo_codigo_borrar", str(codigo_id), {"prefijo": c["prefijo"], "etiqueta": c["etiqueta"]})
    return {"ok": True}


@router.delete("/equipos/{equipo_id}/definitivo")
async def borrar_equipo(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    """Borra el equipo y todo su historial. Cuerpo: {confirmacion: "ELIMINAR <id>"}."""
    b = await request.json()
    _confirmar(b, f"ELIMINAR {equipo_id}")
    e = await db(request).fetchrow("SELECT id, nombre, fabricante, modelo, custodio_email, carpeta_respaldo, estado FROM disp_equipos WHERE id = $1", equipo_id)
    if e is None:
        raise HTTPException(404, "Equipo no encontrado")
    await db(request).execute("DELETE FROM disp_equipos WHERE id = $1", equipo_id)
    borrados = []
    for base, sub in ((RESPALDOS, e["carpeta_respaldo"] or str(equipo_id)), (GNSS, str(equipo_id))):
        ruta = os.path.realpath(os.path.join(base, sub))
        if ruta.startswith(os.path.realpath(base) + os.sep) and os.path.isdir(ruta):
            shutil.rmtree(ruta, ignore_errors=True)
            borrados.append(ruta)
    await auditar(request, admin, "dispositivo_borrar_definitivo", str(equipo_id),
                  {"nombre": e["nombre"], "modelo": f"{e['fabricante'] or ''} {e['modelo'] or ''}".strip(), "custodio": e["custodio_email"], "estado": e["estado"], "carpetas": borrados})
    return {"ok": True, "carpetas_borradas": borrados}


@router.delete("/mensajes/{mensaje_id}")
async def borrar_mensaje(mensaje_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    m = await db(request).fetchrow("SELECT id, titulo FROM disp_mensajes WHERE id = $1", mensaje_id)
    if m is None:
        raise HTTPException(404, "Mensaje no encontrado")
    await db(request).execute("DELETE FROM disp_mensajes WHERE id = $1", mensaje_id)
    await auditar(request, admin, "dispositivo_mensaje_borrar", str(mensaje_id), {"titulo": m["titulo"]})
    return {"ok": True}
