"""Envío inmediato: el servidor acepta el correo al instante y lo envía por detrás (06/11/2026).

Antes el navegador esperaba a que terminara TODO (comprobaciones, análisis de adjuntos en el
webmail y en Postfix, envío y copia en Enviados): la mitad de los envíos tardaba más de 10 s y
algunos más de un minuto; si la persona cerraba la pestaña o miraba Enviados en ese rato, el
correo «no estaba». Ahora:

  POST /api/mail/send-segundo-plano?envio_id=<id>   → 202 al instante (mismo cuerpo que /send)
  GET  /api/mail/send-segundo-plano/<id>            → enviando | enviado | error | desconocido

El trabajo lo hace EXACTAMENTE la misma función que /send (compose.send): mismas reglas de DLP,
sensibilidad, límites, firma, adjuntos grandes al Almacén y copia en Enviados. Si falla, además
de quedar el estado para el navegador, la persona recibe un aviso en la campanita aunque haya
cerrado la pestaña. `envio_id` lo genera el navegador: repetir la petición con el mismo id no
envía dos veces (idempotente).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app import organizacion
from app.auth.dependencies import get_current_user
from app.mail.schemas.messages import ComposeRequest

router = APIRouter(prefix="/api/mail", tags=["mail-compose"])
log = logging.getLogger("envio_segundo_plano")

VIGENCIA_S = 24 * 3600
# Si un envío sigue «enviando» pasado este tiempo, el proceso que lo llevaba se reinició:
# no se sabe si salió y se dice así (nunca se reenvía solo).
ATASCADO_S = 600
_ID = r"^[A-Za-z0-9-]{8,64}$"
_en_curso: set[asyncio.Task] = set()


def _clave(usuario: str, envio_id: str) -> str:
    return f"envio:{usuario}:{envio_id}"


def _texto_error(detalle) -> str:
    """El mismo texto que el navegador obtenía de /send (api/client.ts), para reutilizar su manejo."""
    if isinstance(detalle, str):
        return detalle
    if isinstance(detalle, list):
        return "; ".join(str((e or {}).get("msg") or json.dumps(e)) for e in detalle)
    return json.dumps(detalle, ensure_ascii=False, separators=(",", ":"))


async def _leer(redis, clave: str) -> dict | None:
    crudo = await redis.get(clave)
    if not crudo:
        return None
    try:
        return json.loads(crudo)
    except Exception:
        return None


async def _avisar_fallo(usuario: str, asunto: str, motivo: str) -> None:
    """Campanita (y app de escritorio) aunque la pestaña esté cerrada. Nunca rompe nada."""
    try:
        import httpx

        from app.tareas import avisos

        corto = " ".join((motivo or "").split())
        if corto.startswith("{"):
            corto = "lo bloqueó la protección de datos o de adjuntos"
        cuerpo = {
            "correos": [usuario],
            "tipo": "correo",
            "titulo": "No se pudo enviar tu correo",
            "texto": f"«{(asunto or '(sin asunto)')[:80]}»: {corto[:160]}. Revísalo en Borradores y vuelve a enviarlo.",
            "urgente": True,
            "origen": "correo",
        }
        async with httpx.AsyncClient(timeout=15) as c:
            await c.post(
                f"{avisos.CHAT}/api/chat/notificaciones",
                json=cuerpo,
                headers={"X-Notif-Secret": avisos._secreto()},
            )
    except Exception as e:  # noqa: BLE001
        log.warning("ENVIO_AVISO_FALLIDO user=%s: %r", usuario, e)


async def _enviar(
    request: Request, body: ComposeRequest, usuario: str, clave: str, base: dict
) -> None:
    from app.mail.routers.compose import send

    redis = request.app.state.redis
    t0 = time.monotonic()
    try:
        resultado = await send(request=request, body=body, username=usuario)
        estado = {**base, "estado": "enviado", "fin": time.time()}
        try:
            json.dumps(resultado)
            estado["resultado"] = resultado
        except Exception:
            pass
        log.info(
            "ENVIO_SEGUNDO_PLANO ok user=%s ms=%d",
            usuario,
            int((time.monotonic() - t0) * 1000),
        )
    except HTTPException as e:
        estado = {
            **base,
            "estado": "error",
            "fin": time.time(),
            "codigo": e.status_code,
            "mensaje": _texto_error(e.detail),
        }
        log.warning(
            "ENVIO_SEGUNDO_PLANO error user=%s codigo=%s ms=%d",
            usuario,
            e.status_code,
            int((time.monotonic() - t0) * 1000),
        )
    except Exception as e:  # noqa: BLE001
        estado = {
            **base,
            "estado": "error",
            "fin": time.time(),
            "codigo": 500,
            "mensaje": f"Error al enviar: {str(e)[:200]}",
        }
        log.error("ENVIO_SEGUNDO_PLANO fallo user=%s: %r", usuario, e)
    try:
        await redis.set(
            clave, json.dumps(estado, ensure_ascii=False, default=str), ex=VIGENCIA_S
        )
    except Exception as e:  # noqa: BLE001
        log.error("ENVIO_SEGUNDO_PLANO sin_estado user=%s: %r", usuario, e)
    # 409 = «tardó, pero casi seguro salió» (envio_tardio): no es un fallo que avisar como tal.
    if estado["estado"] == "error" and estado.get("codigo") != 409:
        await _avisar_fallo(usuario, body.subject, estado.get("mensaje", ""))


# Interruptor sin reinicio (Redis «config:envio_inmediato»): «*» = todos; si no, correos separados
# por comas. Sin la clave, ENVIO_INMEDIATO_POR_DEFECTO de organizacion.env (vacío = nadie).
_POR_DEFECTO = organizacion.valor("ENVIO_INMEDIATO_POR_DEFECTO", "")


@router.get("/envio-inmediato/activo")
async def envio_inmediato_activo(
    request: Request, username: str = Depends(get_current_user)
):
    try:
        v = await request.app.state.redis.get("config:envio_inmediato")
        v = (
            (v.decode() if isinstance(v, bytes) else v)
            if v is not None
            else _POR_DEFECTO
        )
    except Exception:
        v = _POR_DEFECTO
    lista = {x.strip().lower() for x in v.split(",") if x.strip()}
    return {"activo": "*" in lista or username.lower() in lista}


@router.post("/send-segundo-plano", status_code=202)
async def enviar_en_segundo_plano(
    request: Request,
    body: ComposeRequest,
    envio_id: str = Query(..., pattern=_ID),
    username: str = Depends(get_current_user),
):
    redis = request.app.state.redis
    clave = _clave(username, envio_id)
    base = {
        "id": envio_id,
        "estado": "enviando",
        "inicio": time.time(),
        "asunto": (body.subject or "")[:200],
    }
    nuevo = await redis.set(
        clave, json.dumps(base, ensure_ascii=False), ex=VIGENCIA_S, nx=True
    )
    if not nuevo:
        # Mismo id otra vez (reintento del navegador): no se envía dos veces.
        return await _leer(redis, clave) or base
    tarea = asyncio.create_task(_enviar(request, body, username, clave, base))
    _en_curso.add(tarea)
    tarea.add_done_callback(_en_curso.discard)
    return base


@router.get("/send-segundo-plano/{envio_id}")
async def estado_envio(
    request: Request,
    envio_id: str = Path(..., pattern=_ID),
    username: str = Depends(get_current_user),
):
    estado = await _leer(request.app.state.redis, _clave(username, envio_id))
    if not estado:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    if (
        estado.get("estado") == "enviando"
        and time.time() - float(estado.get("inicio") or 0) > ATASCADO_S
    ):
        estado = {**estado, "estado": "desconocido"}
    return estado
