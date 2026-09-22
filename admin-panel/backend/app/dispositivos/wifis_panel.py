"""Panel · Dispositivos: wifi de las sedes que se comparte con la flota (22/09/2026)."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.codigo_cifrado import cifrar, descifrar
from app.dispositivos.comun import auditar, db, texto

router = APIRouter(prefix="/api/dispositivos/wifis", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")


async def _subir_version(d) -> int:
    v = int(await d.fetchval("SELECT valor->>'version' FROM disp_config WHERE clave = 'wifis'") or 1) + 1
    await d.execute("INSERT INTO disp_config (clave, valor) VALUES ('wifis', jsonb_build_object('version', $1::int)) "
                    "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = NOW()", v)
    return v


@router.get("")
async def listar(request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        """SELECT w.id, w.sede, w.ssid, w.seguridad, w.oculta, w.activa, w.nota, w.version, w.actualizado_por, w.actualizado_en,
                  (w.clave_cifrada IS NOT NULL) AS con_clave,
                  (SELECT count(*) FROM disp_equipos e WHERE e.wifi_ssid = w.ssid AND e.wifi_en > NOW() - interval '1 hour') AS conectados_ahora,
                  (SELECT json_agg(json_build_object('quien', c.quien, 'origen', c.origen, 'detalle', c.detalle, 'hecho_en', c.hecho_en) ORDER BY c.hecho_en DESC)
                     FROM (SELECT * FROM disp_wifis_cambios c WHERE c.wifi_id = w.id ORDER BY c.hecho_en DESC LIMIT 5) c) AS cambios
             FROM disp_wifis w ORDER BY w.sede, w.ssid""")
    version = await db(request).fetchval("SELECT valor->>'version' FROM disp_config WHERE clave = 'wifis'")
    import json
    return {"version": int(version or 1), "redes": [{**dict(f), "cambios": json.loads(f["cambios"]) if isinstance(f["cambios"], str) else (f["cambios"] or [])} for f in filas]}


@router.post("")
async def guardar(request: Request, admin: dict = Depends(_ADMIN)):
    """Alta o actualización (por id). La clave solo se guarda si viene; vacía la deja como estaba."""
    b = await request.json()
    sede, ssid = texto(b.get("sede"), 120), texto(b.get("ssid"), 32)
    if not sede or not ssid:
        raise HTTPException(400, "Indique la sede y el nombre de la red")
    seguridad = b.get("seguridad") if b.get("seguridad") in ("WPA", "WPA3", "NONE") else "WPA"
    clave = (b.get("clave") or "").strip()
    if seguridad != "NONE" and clave and not 8 <= len(clave) <= 63:
        raise HTTPException(400, "La clave wifi tiene entre 8 y 63 caracteres")
    cifrada = cifrar(clave) if clave and seguridad != "NONE" else None
    if clave and seguridad != "NONE" and not cifrada:
        raise HTTPException(503, "Falta DISP_CODIGO_CLAVE en el panel: no se puede guardar la clave cifrada")
    d = db(request)
    wid = b.get("id")
    async with d.acquire() as con, con.transaction():
        if wid:
            await con.execute(
                """UPDATE disp_wifis SET sede = $2, ssid = $3, seguridad = $4, oculta = $5, activa = $6, nota = $7,
                       clave_cifrada = CASE WHEN $8::text IS NOT NULL THEN $8 WHEN $4 = 'NONE' THEN NULL ELSE clave_cifrada END,
                       version = version + 1, actualizado_por = $9, actualizado_en = NOW() WHERE id = $1""",
                int(wid), sede, ssid, seguridad, bool(b.get("oculta")), bool(b.get("activa", True)), texto(b.get("nota"), 160) or "", cifrada, admin["username"])
        else:
            if seguridad != "NONE" and not cifrada:
                raise HTTPException(400, "Indique la clave de la red")
            wid = await con.fetchval(
                "INSERT INTO disp_wifis (sede, ssid, clave_cifrada, seguridad, oculta, nota, actualizado_por) VALUES ($1,$2,$3,$4,$5,$6,$7) "
                "ON CONFLICT (sede, ssid) DO UPDATE SET clave_cifrada = COALESCE(EXCLUDED.clave_cifrada, disp_wifis.clave_cifrada), seguridad = EXCLUDED.seguridad, "
                "oculta = EXCLUDED.oculta, activa = TRUE, nota = EXCLUDED.nota, version = disp_wifis.version + 1, actualizado_por = EXCLUDED.actualizado_por, actualizado_en = NOW() RETURNING id",
                sede, ssid, cifrada, seguridad, bool(b.get("oculta")), texto(b.get("nota"), 160) or "", admin["username"])
        await con.execute("INSERT INTO disp_wifis_cambios (wifi_id, origen, quien, detalle) VALUES ($1, 'panel', $2, $3)",
                          int(wid), admin["username"], "Clave actualizada desde el panel" if cifrada else "Datos actualizados desde el panel")
        v = await _subir_version(con)
    await auditar(request, admin, "dispositivo_wifi_guardar", str(wid), {"sede": sede, "ssid": ssid, "clave_cambiada": bool(cifrada)})
    return {"ok": True, "id": int(wid), "version": v}


@router.get("/{wifi_id}/clave")
async def ver_clave(wifi_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    c = await db(request).fetchval("SELECT clave_cifrada FROM disp_wifis WHERE id = $1", wifi_id)
    await auditar(request, admin, "dispositivo_wifi_ver_clave", str(wifi_id))
    return {"clave": descifrar(c) if c else None}


@router.delete("/{wifi_id}")
async def borrar(wifi_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    d = db(request)
    await d.execute("DELETE FROM disp_wifis WHERE id = $1", wifi_id)
    await _subir_version(d)
    await auditar(request, admin, "dispositivo_wifi_borrar", str(wifi_id))
    return {"ok": True}
