# -*- coding: utf-8 -*-
"""Relación entre personas del chat (P2 de la quinta revisión, Alice: M-03/L-01, L-02, L-03).

Una sola regla, sin Flask, para tres cosas que antes cada manejador decidía por su cuenta:

- **Presencia** (`get_presence`, `user_presence`, `estado_presencia`, `/estado/<id>`,
  `/presence/<id>`): solo la ve quien comparte alguna conversación activa con la persona.
  Antes cualquier usuario autenticado podía pedir la presencia de cualquier id, y los cambios
  se emitían a TODOS los conectados.
- **Llamadas** (`call_invite` y el resto de la señalización): el destino tiene que compartir
  conversación con quien llama (la indicada o alguna), ser de la misma organización y no haber
  bloqueo en ningún sentido.
- **Conversación directa** (`get_or_create_direct` por socket): misma organización y sin
  bloqueo, igual que ya hacía la ruta REST.

`relacionados()` se cachea un minuto en Redis; `comparten_conversacion()` con id concreto va
siempre a la base (una llamada recién iniciada sobre una conversación nueva no debe esperar).
"""
import logging
import time

log = logging.getLogger("seguridad.chat.relacion")

TTL_CACHE = 60
CLAVE_CACHE = "chat:relacionados:%s"


def _participante():
    from modulos.chat.infraestructura.persistencia.modelos.modelo_conversacion import (
        ModeloParticipante,
    )

    return ModeloParticipante


def _bloqueo():
    from modulos.chat.infraestructura.persistencia.modelos.modelo_presencia import ModeloBloqueo

    return ModeloBloqueo


def relacionados(db_session, usuario_id, redis=None):
    """Ids con los que `usuario_id` comparte alguna conversación activa (incluido él mismo).
    Si la base falla devuelve solo {usuario_id}: fallo cerrado (no se ve a nadie más)."""
    uid = int(usuario_id)
    if redis is not None:
        try:
            v = redis.get(CLAVE_CACHE % uid)
            if v:
                return {int(x) for x in str(v).split(",") if x}
        except Exception:
            pass
    ids = {uid}
    try:
        P = _participante()
        mias = db_session.query(P.conversation_id).filter(P.user_id == uid, P.is_active.is_(True))
        filas = (
            db_session.query(P.user_id)
            .filter(P.conversation_id.in_(mias), P.is_active.is_(True))
            .distinct()
            .all()
        )
        ids |= {int(f[0]) for f in filas}
    except Exception as exc:
        log.error("RELACION_NO_CONSULTABLE usuario=%s error=%s", uid, str(exc)[:120])
        return {uid}
    if redis is not None:
        try:
            redis.set(CLAVE_CACHE % uid, ",".join(str(i) for i in sorted(ids)), ttl_segundos=TTL_CACHE)
        except Exception:
            pass
    return ids


def olvidar(redis, *usuario_ids):
    """Borra la caché de relación (al crear una conversación nueva)."""
    if redis is None:
        return
    for uid in usuario_ids:
        try:
            redis.delete(CLAVE_CACHE % int(uid))
        except Exception:
            pass


def filtrar_visibles(db_session, usuario_id, ids, redis=None):
    """De `ids`, los que `usuario_id` puede ver (presencia): él mismo y sus relacionados."""
    rel = relacionados(db_session, usuario_id, redis)
    salida = []
    for i in ids or []:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if i in rel:
            salida.append(i)
    return salida


def puede_ver(db_session, usuario_id, otro_id, redis=None):
    return int(otro_id) in relacionados(db_session, usuario_id, redis)


def comparten_conversacion(db_session, usuario_id, otro_id, conversacion_id=None, redis=None):
    """True si ambos son participantes activos de `conversacion_id` (consulta directa) o, sin
    id, si comparten alguna."""
    if conversacion_id:
        try:
            P = _participante()
            n = (
                db_session.query(P.user_id)
                .filter(
                    P.conversation_id == int(conversacion_id),
                    P.user_id.in_([int(usuario_id), int(otro_id)]),
                    P.is_active.is_(True),
                )
                .distinct()
                .count()
            )
            if n == 2:
                return True
        except (TypeError, ValueError):
            return False
        except Exception as exc:
            log.error("RELACION_NO_CONSULTABLE usuario=%s error=%s", usuario_id, str(exc)[:120])
            return False
    return int(otro_id) in relacionados(db_session, usuario_id, redis) and int(otro_id) != int(usuario_id)


def bloqueo_entre(db_session, a, b):
    """True si a bloqueó a b o b bloqueó a a. Si no se puede saber, True (fallo cerrado)."""
    try:
        from sqlalchemy import and_, or_

        B = _bloqueo()
        return (
            db_session.query(B.id)
            .filter(
                or_(
                    and_(B.blocker_id == int(a), B.blocked_id == int(b)),
                    and_(B.blocker_id == int(b), B.blocked_id == int(a)),
                )
            )
            .count()
            > 0
        )
    except Exception as exc:
        log.error("BLOQUEO_NO_CONSULTABLE usuarios=%s,%s error=%s", a, b, str(exc)[:120])
        return True


def puede_contactar(db_session, usuario_id, otro_id):
    """(ok, motivo) para iniciar contacto (conversación directa, llamada): misma organización
    (tenant_chat.primer_bloqueado) y sin bloqueo en ningún sentido."""
    try:
        uid, oid = int(usuario_id), int(otro_id)
    except (TypeError, ValueError):
        return False, "destino_invalido"
    if uid == oid:
        return False, "mismo_usuario"
    try:
        import tenant_chat

        if tenant_chat.primer_bloqueado(db_session, uid, [oid]) is not None:
            return False, "otra_organizacion"
    except Exception as exc:
        log.error("TENANT_NO_CONSULTABLE usuario=%s error=%s", uid, str(exc)[:120])
        return False, "tenant_no_consultable"
    if bloqueo_entre(db_session, uid, oid):
        return False, "bloqueo"
    return True, ""


def puede_llamar(db_session, usuario_id, otro_id, conversacion_id=None, redis=None):
    """(ok, motivo) para señalización de llamadas: contacto permitido y conversación compartida."""
    ok, motivo = puede_contactar(db_session, usuario_id, otro_id)
    if not ok:
        return False, motivo
    if not comparten_conversacion(db_session, usuario_id, otro_id, conversacion_id, redis):
        return False, "sin_conversacion"
    return True, ""
