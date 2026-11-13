"""Avisos de correo al instante para la app móvil, con la app cerrada y sin servicios de Google (AM-01).

Cómo funciona:
1. La app registra el teléfono (`POST /api/mobile/register-device`, con sesión). El servidor le asigna un
   tema secreto del ntfy propio (`disp_correo_<32 hex>`) y se lo devuelve junto con la dirección del ntfy.
2. La app se suscribe a ese tema (UnifiedPush/ntfy). No necesita credenciales de ntfy: el tema es el secreto.
3. Cuando el filtro de correo avisa de que hay un mensaje en camino para una cuenta
   (`/api/interno/correo-en-camino`), se publica en el tema de cada teléfono activo de esa cuenta.
4. El aviso NO lleva nada del correo: solo «hay correo nuevo» y para qué cuenta. La app, con su sesión,
   pide el detalle por la API de siempre. Sin sesión válida, el aviso no sirve para leer nada.

Deja de avisarse a un teléfono cuando se da de baja (`unregister-device`), cuando su sesión se cierra o
caduca, cuando la persona apaga los avisos o cuando lleva demasiado sin sincronizar.

Publicar es de «mejor esfuerzo»: si ntfy no responde, la app sigue teniendo su revisión periódica.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets

import httpx

from app.branding.service import marca_corta

logger = logging.getLogger("mobile")

PREFIJO_TEMA = (
    "disp_correo_"  # el usuario de ntfy del servidor solo puede publicar en disp_*
)
DIAS_SIN_SINCRONIZAR = 45  # un teléfono que no aparece en este tiempo deja de recibir
PAUSA_ENTRE_AVISOS_S = 3  # como mucho un aviso por teléfono en este intervalo
RETRASO_ENTREGA_S = 2.0  # el aviso de «en camino» llega antes que el correo al buzón
MAX_TELEFONOS_POR_AVISO = 200
PUERTO_PUBLICO = os.environ.get("NTFY_PUERTO_PUBLICO", "2587")
_URL = os.environ.get("NTFY_URL_INTERNO", "http://127.0.0.1:2586")
_TOKEN = os.environ.get("NTFY_TOKEN", "")
_cliente: httpx.AsyncClient | None = None
_tareas: set = set()


def disponible() -> bool:
    """El servidor tiene con qué publicar avisos (ntfy configurado)."""
    return bool(_TOKEN)


def nuevo_tema() -> str:
    return PREFIJO_TEMA + secrets.token_hex(16)


def bloque_push(host: str, tema: str | None, avisos: bool) -> dict | None:
    """Lo que la app necesita para suscribirse; None si no hay canal o los avisos están apagados."""
    if not tema or not avisos or not disponible():
        return None
    servidor = (host or "").split(":")[0].strip().lower()
    return {
        "protocolo": "ntfy",
        "servidor": f"https://{servidor}:{PUERTO_PUBLICO}",
        "tema": tema,
        "contenido": "ninguno",
    }


def cuerpo_aviso(cuenta: str) -> str:
    """Mensaje que viaja por ntfy. Sin remitente, asunto ni texto del correo."""
    return json.dumps(
        {"tipo": "correo_nuevo", "cuenta": cuenta, "v": 1}, separators=(",", ":")
    )


def _c() -> httpx.AsyncClient:
    global _cliente
    if _cliente is None:
        _cliente = httpx.AsyncClient(timeout=4.0)
    return _cliente


async def _publicar(tema: str, cuenta: str) -> bool:
    try:
        r = await _c().post(
            f"{_URL}/{tema}",
            content=cuerpo_aviso(cuenta).encode(),
            headers={
                "Authorization": f"Bearer {_TOKEN}",
                "Priority": "high",
                "Title": marca_corta(),
                "X-Tags": "correo",
                "Cache": "yes",
            },
        )
        return r.status_code < 300
    except Exception:
        logger.debug("aviso_movil_fallo tema=%s…", tema[:18], exc_info=True)
        return False


async def telefonos_a_avisar(db, redis, cuentas: list[str]) -> list[dict]:
    """Teléfonos activos, con avisos encendidos, sesión viva y sin aviso en los últimos segundos."""
    if not cuentas or not disponible():
        return []
    filas = await db.fetch(
        f"""
        SELECT id, lower(user_email) AS cuenta, device_id, push_topic, sid FROM mobile_devices
        WHERE lower(user_email) = ANY($1::text[]) AND is_active AND avisos
          AND push_topic IS NOT NULL AND sid IS NOT NULL
          AND last_sync > now() - interval '{DIAS_SIN_SINCRONIZAR} days'
        LIMIT {MAX_TELEFONOS_POR_AVISO}
        """,
        cuentas,
    )
    salida = []
    for f in filas:
        # La sesión con la que se registró el teléfono debe seguir abierta.
        if not await redis.exists(f"sess:{f['cuenta']}:{f['sid']}"):
            continue
        # Varios correos seguidos (o varios destinatarios del mismo) no son una ráfaga de avisos.
        if not await redis.set(
            f"aviso_movil:{f['id']}", "1", nx=True, ex=PAUSA_ENTRE_AVISOS_S
        ):
            continue
        salida.append(dict(f))
    return salida


async def avisar(db, redis, cuentas: list[str]) -> int:
    """Publica el aviso en los teléfonos de esas cuentas. Devuelve cuántos se avisaron."""
    telefonos = await telefonos_a_avisar(
        db, redis, sorted({c.lower() for c in cuentas})
    )
    if not telefonos:
        return 0
    await asyncio.sleep(RETRASO_ENTREGA_S)
    enviados = [
        t["id"] for t in telefonos if await _publicar(t["push_topic"], t["cuenta"])
    ]
    if enviados:
        await db.execute(
            "UPDATE mobile_devices SET ultimo_aviso = now(), avisos_enviados = avisos_enviados + 1 "
            "WHERE id = ANY($1::int[])",
            enviados,
        )
    return len(enviados)


def programar(db, redis, cuentas: list[str]) -> None:
    """Lanza el aviso en segundo plano: quien llama (el filtro de correo) no espera ni se entera de fallos."""
    if not cuentas or not disponible() or db is None or redis is None:
        return

    async def _tarea():
        try:
            await avisar(db, redis, cuentas)
        except Exception:
            logger.warning("aviso_movil_error", exc_info=True)

    t = asyncio.create_task(_tarea())
    _tareas.add(t)
    t.add_done_callback(_tareas.discard)
