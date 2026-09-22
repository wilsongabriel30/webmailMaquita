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


# ── Depuración en un solo paso ───────────────────────────────────────────────────────────────────

_CODIGOS_SOBRANTES = """SELECT c.id FROM disp_codigos c
     WHERE (c.revocado_en IS NOT NULL OR c.usos >= c.usos_max OR (c.caduca_en IS NOT NULL AND c.caduca_en < NOW()))
       AND NOT EXISTS (SELECT 1 FROM disp_equipos e WHERE e.codigo_id = c.id AND e.estado IN ('activo', 'perdido'))"""
_EQUIPOS_SOBRANTES = """SELECT e.id, e.nombre, e.fabricante, e.modelo, e.estado, e.custodio_email, e.ultimo_contacto, e.carpeta_respaldo FROM disp_equipos e
     WHERE e.estado IN ('revocado', 'baja')
        OR (e.ultimo_contacto IS NULL AND e.enrolado_en < NOW() - interval '1 day')"""
_MENSAJES_SOBRANTES = """SELECT m.id, m.titulo FROM disp_mensajes m
     WHERE (m.caduca_en IS NOT NULL AND m.caduca_en < NOW() - interval '30 days')
        OR NOT EXISTS (SELECT 1 FROM disp_mensajes_equipos me WHERE me.mensaje_id = m.id)"""


@router.post("/depurar")
async def depurar(request: Request, admin: dict = Depends(_ADMIN)):
    """Un solo paso. Cuerpo `{confirmacion?: "DEPURAR"}`: sin confirmación devuelve la vista previa
    (qué se borraría); con ella, borra:
    - códigos anulados, agotados o caducados sin equipo activo enrolado con ellos;
    - equipos retirados de la gestión o dados de baja, y los que nunca reportaron en más de un día
      (pruebas que no salieron bien); con todo su historial y sus carpetas en disco;
    - mensajes sin destinatarios o caducados hace más de 30 días.
    Nunca toca equipos activos ni perdidos, ni alertas o reportes de equipos vivos."""
    b = await request.json() if int(request.headers.get("content-length") or 0) else {}
    d = db(request)
    codigos = [r["id"] for r in await d.fetch(_CODIGOS_SOBRANTES)]
    equipos = [dict(r) for r in await d.fetch(_EQUIPOS_SOBRANTES)]
    mensajes = [dict(r) for r in await d.fetch(_MENSAJES_SOBRANTES)]
    vista = {
        "codigos": len(codigos),
        "equipos": [{"id": e["id"], "nombre": e["nombre"] or f"{e['fabricante'] or ''} {e['modelo'] or ''}".strip(), "estado": e["estado"], "custodio": e["custodio_email"]} for e in equipos],
        "mensajes": [{"id": m["id"], "titulo": m["titulo"]} for m in mensajes],
    }
    if (b.get("confirmacion") or "").strip().upper() != "DEPURAR":
        return {"vista_previa": True, **vista}
    if codigos:
        await d.execute("DELETE FROM disp_codigos WHERE id = ANY($1::int[])", codigos)
    carpetas = []
    for e in equipos:
        await d.execute("DELETE FROM disp_equipos WHERE id = $1", e["id"])
        for base, sub in ((RESPALDOS, e["carpeta_respaldo"] or str(e["id"])), (GNSS, str(e["id"]))):
            ruta = os.path.realpath(os.path.join(base, sub))
            if ruta.startswith(os.path.realpath(base) + os.sep) and os.path.isdir(ruta):
                shutil.rmtree(ruta, ignore_errors=True)
                carpetas.append(ruta)
    if mensajes:
        await d.execute("DELETE FROM disp_mensajes WHERE id = ANY($1::int[])", [m["id"] for m in mensajes])
    await auditar(request, admin, "dispositivo_depurar", "todo", {**vista, "carpetas": carpetas})
    return {"vista_previa": False, **vista, "carpetas_borradas": len(carpetas)}
