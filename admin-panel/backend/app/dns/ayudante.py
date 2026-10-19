"""Llamada al ayudante root /usr/local/sbin/maquita-dns (por maquita-sudo) y auditoría común."""

import asyncio
import base64
import json

from fastapi import HTTPException, Request

from app.wrappers.privilegios import con_sudo

AYUDANTES = {
    "dns": "/usr/local/sbin/maquita-dns",
    "sitios": "/usr/local/sbin/maquita-sitios",
    "cortafuegos": "/usr/local/sbin/maquita-cortafuegos",
    "identidad": "/usr/local/sbin/maquita-identidad",
    "actualizar": "/usr/local/sbin/maquita-actualizar",
    "respaldos": "/usr/local/sbin/maquita-respaldos",
}


def b64(datos) -> str:
    """JSON o texto en base64url: así los valores libres no viajan como argumentos sueltos por sudo."""
    if not isinstance(datos, str):
        datos = json.dumps(datos, ensure_ascii=False)
    return base64.urlsafe_b64encode(datos.encode()).decode().rstrip("=")


async def ayudante(cual: str, *args: str, tiempo: int = 60) -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            *con_sudo(AYUDANTES[cual], *args), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError:
        raise HTTPException(503, "Esta función no está instalada en el servidor")
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=tiempo)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(504, "La operación tardó demasiado")
    texto = (out or b"").decode().strip()
    if not texto:
        motivo = (err or b"").decode(errors="replace").strip().splitlines()
        if proc.returncode == 3:
            raise HTTPException(503, "Esta función no está instalada en el servidor")
        raise HTTPException(400, (motivo[-1] if motivo else "la orden fue rechazada")[:300])
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        raise HTTPException(500, "respuesta no válida del ayudante")
    if isinstance(datos, dict) and datos.get("error"):
        raise HTTPException(400, datos["error"])
    return datos


async def auditar(r: Request, admin: dict, accion: str, objetivo: str, detalles: dict | None = None):
    await r.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"],
        admin["username"],
        accion,
        objetivo,
        json.dumps(detalles) if detalles else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )
