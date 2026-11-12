"""Cuentas «solo webmail»: cerrar IMAP, POP3 y SMTP por cuenta, sin tocar el resto del servidor.

En las cuentas marcadas, la contraseña principal no sirve desde fuera del propio servidor: a quien
la pruebe se le responde «contraseña incorrecta» aunque acierte. El webmail sigue funcionando y los
equipos de la persona entran con contraseñas de aplicación. Lo aplica Dovecot al validar (tabla
auth_cuentas_solo_web en la consulta del passdb); aquí solo se administra la lista.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.solo_webmail.indicaciones import indicacion

router = APIRouter(prefix="/api/solo-webmail", tags=["solo-webmail"])
DIAS_DE_USO = 14
LARGO_MOTIVO = 200

_CUENTAS = """
SELECT m.username, COALESCE(m.name, '') AS nombre,
       s.username IS NOT NULL AS protegida, COALESCE(s.motivo, '') AS motivo, s.creada AS desde,
       COALESCE(s.por, '') AS por, COALESCE(t.enabled, false) AS dos_pasos, COALESCE(c.n, 0) AS claves_aplicacion
FROM mailbox m
LEFT JOIN auth_cuentas_solo_web s ON s.username = m.username
LEFT JOIN user_totp t ON t.username = m.username
LEFT JOIN (SELECT username, count(*) AS n FROM contrasenas_aplicacion WHERE revocada IS NULL GROUP BY 1) c
       ON c.username = m.username
WHERE m.active = true
ORDER BY m.username
"""

_USO = f"""
SELECT cuenta, COALESCE(sum(ok), 0) AS accesos, max(hora) FILTER (WHERE ok > 0) AS ultimo,
       count(DISTINCT ip) FILTER (WHERE fallos > 0 AND ok = 0) AS direcciones_con_fallos,
       COALESCE(sum(fallos), 0) AS fallos
FROM seg_accesos_detalle
WHERE servicio IN ('imap', 'pop3', 'smtp') AND ip::text NOT IN ('127.0.0.1', '::1')
  AND hora > now() - interval '{DIAS_DE_USO} days'
GROUP BY cuenta
"""


def _db(r: Request):
    return r.app.state.db


async def _uso_por_cuenta(db) -> tuple[dict, bool]:
    """Accesos desde fuera por cuenta. Si la instalación no recoge accesos, devuelve ({}, False)."""
    try:
        if not await db.fetchval("SELECT to_regclass('seg_accesos_detalle')"):
            return {}, False
        return {f["cuenta"]: f for f in await db.fetch(_USO)}, True
    except Exception:
        return {}, False


@router.get("")
async def listar(r: Request, a=Depends(get_current_admin)):
    db = _db(r)
    uso, hay_datos = await _uso_por_cuenta(db)
    cuentas = []
    for f in await db.fetch(_CUENTAS):
        u = uso.get(f["username"])
        accesos = int(u["accesos"]) if u else 0
        con_fallos = int(u["direcciones_con_fallos"]) if u else 0
        cuentas.append(
            {
                **dict(f),
                "accesos_externos": accesos,
                "ultimo_acceso_externo": u["ultimo"] if u else None,
                "direcciones_con_fallos": con_fallos,
                "intentos_fallidos": int(u["fallos"]) if u else 0,
                "indicacion": indicacion(
                    f["protegida"],
                    accesos,
                    f["claves_aplicacion"],
                    con_fallos,
                    hay_datos,
                ),
            }
        )
    return {
        "cuentas": cuentas,
        "dias_de_uso": DIAS_DE_USO,
        "hay_datos_de_uso": hay_datos,
        "protegidas": sum(1 for c in cuentas if c["protegida"]),
        "con_intentos": sum(1 for c in cuentas if c["indicacion"]["nivel"] == "alerta"),
    }


class Cambio(BaseModel):
    activo: bool
    motivo: str = ""


@router.put("/{username:path}")
async def cambiar(
    username: str, body: Cambio, r: Request, a=Depends(require_superadmin)
):
    db = _db(r)
    username = (username or "").strip().lower()
    if not await db.fetchval(
        "SELECT 1 FROM mailbox WHERE username = $1 AND active = true", username
    ):
        raise HTTPException(404, "Esa cuenta no existe o está desactivada")
    motivo = " ".join((body.motivo or "").split())[:LARGO_MOTIVO]
    if body.activo:
        await db.execute(
            "INSERT INTO auth_cuentas_solo_web (username, motivo, por) VALUES ($1, $2, $3) "
            "ON CONFLICT (username) DO UPDATE SET motivo = EXCLUDED.motivo, por = EXCLUDED.por",
            username,
            motivo,
            a["username"],
        )
    else:
        await db.execute(
            "DELETE FROM auth_cuentas_solo_web WHERE username = $1", username
        )
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        a["id"],
        a["username"],
        "solo_webmail_activar" if body.activo else "solo_webmail_quitar",
        username,
        json.dumps({"motivo": motivo}),
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )
    return {"ok": True, "username": username, "protegida": body.activo}
