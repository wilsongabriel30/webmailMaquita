"""Acceso de servicio con mínimo privilegio para las rutas `/api/interno/reuniones` (04/11/2026).

Quién puede llamar: solo Raíces, con un token de servicio propio y desde una IP permitida.

- Token: cabecera `Authorization: Bearer <REUNIONES_SERVICIO_TOKEN>`, comparado en tiempo constante.
  Es un secreto NUEVO, distinto del secreto de las sesiones (`SECRET_KEY`, el `WEBMAIL_JWT_SECRET` de
  Raíces) y del de avisos (`NOTIF_SECRET`): quien lo tenga no puede abrir sesiones ni leer correo.
  Sin token configurado (o demasiado corto, o igual a otro secreto) las rutas responden 503.
- IP: la de la conexión que vio nginx (`request.client.host`, que uvicorn toma del último salto de
  `X-Forwarded-For`, el que escribe nginx con `$remote_addr`) debe estar en `REUNIONES_SERVICIO_IPS`
  (sin valor por defecto: sin la lista, nadie entra). Además se exige que el cliente NO haya enviado cabeceras de reenvío:
  la cadena `X-Forwarded-For` que llega debe tener un solo elemento. Así una cabecera inventada no
  sirve, ni siquiera desde la red del enrutador en que nginx confía para `real_ip`.
"""

from __future__ import annotations

import hmac
import logging
import os

from fastapi import HTTPException, Request

log = logging.getLogger("maquita.webmail.interno.reuniones")
security_log = logging.getLogger("security")

IPS_POR_DEFECTO = ""
LARGO_MINIMO = 32


def _token_configurado() -> str:
    tok = (os.getenv("REUNIONES_SERVICIO_TOKEN") or "").strip()
    if len(tok) < LARGO_MINIMO:
        return ""
    otros = {
        (os.getenv("SECRET_KEY") or "").strip(),
        (os.getenv("NOTIF_SECRET") or "").strip(),
        (os.getenv("ADMIN_JWT_SECRET") or "").strip(),
    }
    return "" if tok in otros else tok


def ips_permitidas() -> set[str]:
    crudo = os.getenv("REUNIONES_SERVICIO_IPS", IPS_POR_DEFECTO)
    return {x.strip() for x in crudo.replace(";", ",").split(",") if x.strip()}


def _bearer(request: Request) -> str:
    cab = request.headers.get("authorization", "")
    if cab[:7].lower() != "bearer ":
        return ""
    return cab[7:].strip()


def ip_de_conexion(request: Request) -> str:
    return request.client.host if request.client else ""


def _sin_reenvio_del_cliente(request: Request, ip: str) -> bool:
    """La cadena de reenvío solo puede traer el salto que añadió nginx (la propia IP)."""
    cadena = [
        x.strip()
        for x in request.headers.get("x-forwarded-for", "").split(",")
        if x.strip()
    ]
    if len(cadena) > 1 or (cadena and cadena[0] != ip):
        return False
    real = request.headers.get("x-real-ip", "").strip()
    return not real or real == ip


async def exigir_servicio_reuniones(request: Request) -> str:
    """Dependencia de FastAPI. Devuelve la IP del servicio o corta con 401/403/503."""
    ip = ip_de_conexion(request)
    ruta = request.url.path
    esperado = _token_configurado()
    if not esperado:
        security_log.error("INTERNO_REUNIONES_SIN_TOKEN ip=%s path=%s", ip, ruta)
        raise HTTPException(503, "Servicio interno no configurado")
    if ip not in ips_permitidas() or not _sin_reenvio_del_cliente(request, ip):
        security_log.warning(
            "INTERNO_REUNIONES_IP_RECHAZADA ip=%s xff=%r path=%s",
            ip,
            request.headers.get("x-forwarded-for", "")[:80],
            ruta,
        )
        raise HTTPException(403, "No autorizado")
    recibido = _bearer(request)
    if not recibido or not hmac.compare_digest(
        esperado.encode("utf-8"), recibido.encode("utf-8")
    ):
        security_log.warning(
            "INTERNO_REUNIONES_TOKEN_RECHAZADO ip=%s path=%s", ip, ruta
        )
        raise HTTPException(401, "Token de servicio inválido")
    return ip
