"""Panel · Dispositivos: mensajes urgentes al personal, con acuse de lectura por equipo."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.comun import auditar, db, texto

router = APIRouter(prefix="/api/dispositivos/mensajes", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")


@router.get("")
async def listar(request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        """SELECT m.id, m.titulo, m.nivel, m.requiere_acuse, m.destino, m.creado_por, m.creado_en, m.caduca_en,
                  count(me.*) AS destinatarios,
                  count(me.entregado_en) AS entregados, count(me.leido_en) AS leidos
           FROM disp_mensajes m LEFT JOIN disp_mensajes_equipos me ON me.mensaje_id = m.id
           GROUP BY m.id ORDER BY m.creado_en DESC LIMIT 100""")
    return {"mensajes": [dict(f) for f in filas]}


@router.get("/{mensaje_id}")
async def detalle(mensaje_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    m = await db(request).fetchrow("SELECT * FROM disp_mensajes WHERE id = $1", mensaje_id)
    if m is None:
        raise HTTPException(404, "Mensaje no encontrado")
    filas = await db(request).fetch(
        """SELECT e.id, e.nombre, e.modelo, e.custodio_nombre, e.custodio_email, e.ultimo_contacto,
                  me.entregado_en, me.leido_en
           FROM disp_mensajes_equipos me JOIN disp_equipos e ON e.id = me.equipo_id
           WHERE me.mensaje_id = $1 ORDER BY me.leido_en NULLS FIRST, e.nombre""", mensaje_id)
    return {"mensaje": dict(m), "equipos": [dict(f) for f in filas]}


@router.post("")
async def enviar(request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    titulo = texto(b.get("titulo"), 160)
    cuerpo = str(b.get("texto") or "").strip()[:4000]
    if not titulo or not cuerpo:
        raise HTTPException(400, "El mensaje necesita título y texto")
    nivel = b.get("nivel") if b.get("nivel") in ("informativo", "importante", "urgente") else "urgente"
    ids = b.get("equipos")
    horas = int(b.get("horas_validez") or 72)
    if not 1 <= horas <= 24 * 30:
        raise HTTPException(400, "La validez debe estar entre 1 hora y 30 días")
    async with db(request).acquire() as con, con.transaction():
        m = await con.fetchrow(
            "INSERT INTO disp_mensajes (titulo, texto, nivel, requiere_acuse, destino, creado_por, caduca_en) "
            "VALUES ($1,$2,$3,$4,$5,$6, NOW() + make_interval(hours => $7)) RETURNING id",
            titulo, cuerpo, nivel, bool(b.get("requiere_acuse", True)),
            "equipos" if ids else "todos", admin["username"], horas)
        if ids:
            ids = [int(i) for i in ids][:2000]
            n = await con.execute(
                "INSERT INTO disp_mensajes_equipos (mensaje_id, equipo_id) "
                "SELECT $1, id FROM disp_equipos WHERE estado IN ('activo', 'perdido') AND id = ANY($2::int[])", m["id"], ids)
        else:
            n = await con.execute(
                "INSERT INTO disp_mensajes_equipos (mensaje_id, equipo_id) "
                "SELECT $1, id FROM disp_equipos WHERE estado IN ('activo', 'perdido')", m["id"])
    total = int(n.split()[-1])
    await auditar(request, admin, "dispositivo_mensaje", str(m["id"]), {"titulo": titulo, "nivel": nivel, "destinatarios": total})
    return {"id": m["id"], "destinatarios": total}
