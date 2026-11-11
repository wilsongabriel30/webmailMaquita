"""Lado del remitente: pedir al servidor del destinatario que retire un correo enviado por error."""

from __future__ import annotations

from app.federacion import recuperacion_protocolo as protocolo
from app.federacion import red

TTL_CAPACIDAD_S = 600
TIEMPO_SOLICITUD_S = 25.0
ESTADOS = (
    protocolo.ESTADO_RECUPERADO,
    protocolo.ESTADO_FUERA_DE_PLAZO,
    protocolo.ESTADO_NO_RECUPERADO,
)


def _dominio(direccion: str) -> str:
    return direccion.rsplit("@", 1)[-1].strip().lower()


async def servidor_compatible(redis, dominio: str) -> str:
    """Host del servidor del dominio si admite la recuperación («» si no). Se recuerda 10 minutos."""
    if not protocolo.activo():
        return ""
    clave = f"fed:cap:{dominio}"
    try:
        guardado = await redis.get(clave)
        if guardado is not None:
            return guardado.decode() if isinstance(guardado, bytes) else guardado
    except Exception:
        pass
    encontrado = ""
    for host in await red.servidores_de(dominio):
        cap = await red.llamar(host, "GET", protocolo.RUTA_BASE, tiempo_s=5.0)
        if (
            cap
            and cap.get("activo") is True
            and cap.get("version") == protocolo.VERSION
        ):
            encontrado = host
            break
    try:
        await redis.setex(clave, TTL_CAPACIDAD_S, encontrado)
    except Exception:
        pass
    return encontrado


async def _pedir(
    redis, remitente: str, destinatario: str, message_id: str
) -> dict | None:
    host = await servidor_compatible(redis, _dominio(destinatario))
    if not host:
        return None
    solicitud = protocolo.Solicitud(
        token=protocolo.nuevo_token(),
        message_id=message_id,
        remitente=remitente,
        destinatario=destinatario,
    )
    await protocolo.guardar(redis, solicitud)
    try:
        r = await red.llamar(
            host,
            "POST",
            protocolo.RUTA_SOLICITAR,
            solicitud.model_dump(),
            tiempo_s=TIEMPO_SOLICITUD_S,
        )
    finally:
        await protocolo.olvidar(redis, solicitud)
    if not r or r.get("estado") not in ESTADOS:
        return None
    return {"estado": r["estado"], "leido": r.get("leido"), "servidor": host}


async def recuperar_en_otro_servidor(
    redis, remitente: str, destinatario: str, message_id: str
) -> dict | None:
    """Resultado del otro servidor ({estado, leido, servidor}) o None si no admite la recuperación.

    Nunca lanza: ante cualquier fallo se devuelve None y quien llama sigue con el aviso de
    «enviado por error».
    """
    try:
        return await _pedir(redis, remitente, destinatario, message_id)
    except Exception as exc:
        red.logger.warning("federación: recuperación en otro servidor falló: %s", exc)
        return None
