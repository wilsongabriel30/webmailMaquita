"""Lado de quien reacciona: avisar a los otros servidores de la suite que tienen ese correo."""

from __future__ import annotations

from collections import defaultdict

from app.federacion import reacciones_protocolo as protocolo
from app.federacion import red

TTL_CAPACIDAD_S = 600


async def _servidor(redis, dominio: str) -> str:
    """Host del servidor del dominio si admite reacciones («» si no). Se recuerda 10 minutos."""
    clave = f"fed:capreac:{dominio}"
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


async def avisar_otros_servidores(
    redis,
    message_id: str,
    usuario: str,
    nombre: str,
    emoji: str | None,
    externos: set[str],
) -> int:
    """Avisa a los servidores compatibles de las direcciones externas. Devuelve a cuántos llegó.

    Nunca lanza: un servidor que no responde no afecta a la reacción local.
    """
    if not protocolo.activo() or not externos:
        return 0
    entregados = 0
    try:
        por_servidor: dict[str, list[str]] = defaultdict(list)
        for direccion in sorted(externos):
            host = await _servidor(redis, direccion.rsplit("@", 1)[-1].lower())
            if host:
                por_servidor[host].append(direccion)
        for host, destinatarios in por_servidor.items():
            aviso = protocolo.Aviso(
                token=protocolo.nuevo_token(),
                message_id=message_id,
                usuario=usuario,
                nombre=nombre[:200],
                emoji=emoji,
                destinatarios=destinatarios[:200],
            )
            await protocolo.guardar(redis, aviso)
            try:
                r = await red.llamar(
                    host,
                    "POST",
                    protocolo.RUTA_AVISAR,
                    aviso.model_dump(),
                    tiempo_s=25.0,
                )
            finally:
                await protocolo.olvidar(redis, aviso)
            if r and r.get("estado") == "recibida":
                entregados += 1
    except Exception as exc:
        red.logger.warning("federación: aviso de reacción falló: %s", exc)
    return entregados
