"""Ciclo de vida de sesión: `sid` + `auth_version` (F-01 / F-04, tercera revisión ASVS).

Vocabulario (ver docs/DISENO-SESIONES.md):
- sid       identificador de sesión (dispositivo/navegador); 128 bits aleatorios.
- av        generación de autenticación del usuario; sube en cada revocación global.
- kind      normal | impersonation | oidc | saml.
- abs_exp   vencimiento absoluto de la sesión: ninguna renovación lo supera.

Regla única, aplicada en toda frontera (REST, WebSocket, refresh, chat): una petición
vale si (a) el token está firmado y no vencido, (b) existe su sesión `sid`, (c) su `av`
es el actual del usuario y (d) no ha pasado `abs_exp`.

Estado:
  PostgreSQL  auth_estado(username, auth_version)   refresh_tokens(+sid, session_kind,
              absolute_expires_at, auth_version)
  Redis       sess:{u}:{sid}  imap_pass:{u}:{sid}  imap_master:{u}:{sid}  sids:{u}  av:{u}
"""

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from app.auth.jwt import create_access_token, create_refresh_token
from app.config import get_settings
from app.core.session import decrypt_password, encrypt_password

log = logging.getLogger("seguridad.sesiones")
security_log = logging.getLogger("security")

KINDS = ("normal", "impersonation", "oidc", "saml")
CANAL_REVOCACION = "revocacion"
TTL_AV_CACHE = 86400

# Oyentes de revocación (el chat se registra aquí en F-03): reciben (username, sid|"*", av).
OYENTES_REVOCACION: list = []


def nuevo_sid() -> str:
    return secrets.token_urlsafe(16)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- auth_version
async def av_actual(db, redis, username: str) -> int:
    """Generación vigente del usuario. Caché en Redis; si no está, la base la rellena."""
    try:
        v = await redis.get(f"av:{username}")
        if v:
            return int(v)
    except Exception as exc:
        log.warning("av:%s no legible en Redis: %s", username, exc)
    row = await db.fetchval(
        "SELECT auth_version FROM auth_estado WHERE username = $1", username
    )
    av = int(row) if row else 1
    try:
        await redis.set(f"av:{username}", av, ex=TTL_AV_CACHE)
    except Exception:
        pass
    return av


async def subir_av(db, redis, username: str) -> int:
    """Sube la generación (write-through a Redis). Un token con la anterior ya no vale."""
    av = await db.fetchval(
        """INSERT INTO auth_estado (username, auth_version) VALUES ($1, 2)
           ON CONFLICT (username) DO UPDATE
             SET auth_version = auth_estado.auth_version + 1, updated_at = now()
           RETURNING auth_version""",
        username,
    )
    try:
        await redis.set(f"av:{username}", av, ex=TTL_AV_CACHE)
    except Exception as exc:
        # La base ya subió; la caché vieja viviría hasta 24 h. Se intenta borrar y se avisa.
        security_log.error(
            "AV_CACHE_NO_ACTUALIZADA user=%s av=%s error=%s",
            username,
            av,
            str(exc)[:120],
        )
        try:
            await redis.delete(f"av:{username}")
        except Exception:
            pass
    return int(av)


# ---------------------------------------------------------------- emisión
def _ttl_hasta(abs_exp: datetime, tope_seg: int) -> int:
    restante = int((abs_exp - _ahora()).total_seconds())
    return max(1, min(tope_seg, restante))


async def crear_sesion(
    db,
    redis,
    request,
    username: str,
    password_imap: str,
    *,
    kind: str = "normal",
    abs_exp: datetime | None = None,
    master: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """Crea una sesión completa: estado en Redis, refresh en la base y access JWT.

    Devuelve {access, refresh_raw, refresh_expires_at, sid, av, abs_exp, access_ttl}.
    """
    assert kind in KINDS, kind
    s = get_settings()
    ahora = _ahora()
    if abs_exp is None:
        abs_exp = ahora + timedelta(days=s.refresh_token_expire_days)
    sid = nuevo_sid()
    av = await av_actual(db, redis, username)
    ttl_access = _ttl_hasta(abs_exp, s.access_token_expire_minutes * 60)
    ttl_abs = _ttl_hasta(abs_exp, 10**9)

    pipe = redis.pipeline()
    pipe.set(
        f"imap_pass:{username}:{sid}", encrypt_password(password_imap), ex=ttl_access
    )
    if master:
        pipe.set(f"imap_master:{username}:{sid}", master, ex=ttl_abs)
    pipe.hset(
        f"sess:{username}:{sid}",
        mapping={
            "kind": kind,
            "av": av,
            "abs_exp": int(abs_exp.timestamp()),
            "ua": (
                user_agent or (request.headers.get("user-agent", "") if request else "")
            )[:200],
            "ip": (request.client.host if request and request.client else "")[:64],
            "creada": int(ahora.timestamp()),
        },
    )
    pipe.expire(f"sess:{username}:{sid}", ttl_access)
    pipe.sadd(f"sids:{username}", sid)
    await pipe.execute()

    access = create_access_token(username, sid=sid, av=av, kind=kind, abs_exp=abs_exp)
    refresh_raw, refresh_hash = create_refresh_token()
    refresh_expires_at = min(
        ahora + timedelta(days=s.refresh_token_expire_days), abs_exp
    )
    await db.execute(
        """INSERT INTO refresh_tokens
             (username, token_hash, expires_at, user_agent, ip_address,
              sid, session_kind, absolute_expires_at, auth_version)
           VALUES ($1, $2, $3, $4, $5::inet, $6, $7, $8, $9)""",
        username,
        refresh_hash,
        refresh_expires_at,
        (user_agent or (request.headers.get("user-agent", "") if request else ""))[
            :500
        ],
        (request.client.host if request and request.client else None) or "0.0.0.0",
        sid,
        kind,
        abs_exp,
        av,
    )
    return {
        "access": access,
        "refresh_raw": refresh_raw,
        "refresh_expires_at": refresh_expires_at,
        "sid": sid,
        "av": av,
        "abs_exp": abs_exp,
        "access_ttl": ttl_access,
    }


async def prorrogar(redis, username: str, sid: str, abs_exp: datetime) -> None:
    """Keep-alive de una sesión `normal`: el TTL nunca supera abs_exp."""
    s = get_settings()
    ttl = _ttl_hasta(abs_exp, s.access_token_expire_minutes * 60)
    pipe = redis.pipeline()
    pipe.expire(f"imap_pass:{username}:{sid}", ttl)
    pipe.expire(f"sess:{username}:{sid}", ttl)
    await pipe.execute()


# ---------------------------------------------------------------- comprobación
async def sesion_valida(db, redis, payload: dict) -> tuple[str, str] | None:
    """Aplica la regla única a un access JWT ya decodificado. Devuelve (username, sid)
    o None. Fallo cerrado: si no se puede saber, no vale."""
    username = payload.get("sub")
    sid = payload.get("sid")
    av = payload.get("av")
    abs_exp = payload.get("abs_exp")
    if not username or not sid or av is None or not abs_exp:
        return None  # token anterior al modelo sid/av: hay que volver a entrar
    if int(abs_exp) <= int(_ahora().timestamp()):
        return None
    try:
        if int(av) != await av_actual(db, redis, username):
            return None
        if not await redis.exists(f"sess:{username}:{sid}"):
            return None
    except Exception as exc:
        security_log.error(
            "SESION_NO_VERIFICABLE user=%s error=%s", username, str(exc)[:120]
        )
        return None
    return username, sid


# ---------------------------------------------------------------- revocación
async def _publicar(redis, username: str, sid: str, av: int, motivo: str) -> None:
    mensaje = {"user": username, "sid": sid, "av": av, "motivo": motivo}
    try:
        await redis.publish(CANAL_REVOCACION, json.dumps(mensaje))
    except Exception as exc:
        security_log.error(
            "REVOCACION_NO_PUBLICADA user=%s sid=%s error=%s",
            username,
            sid,
            str(exc)[:120],
        )
    for oyente in list(OYENTES_REVOCACION):
        try:
            await oyente(username, sid, av, motivo)
        except Exception as exc:
            security_log.error(
                "REVOCACION_OYENTE_FALLIDO oyente=%s user=%s error=%s",
                getattr(oyente, "__name__", "?"),
                username,
                str(exc)[:120],
            )


def _claves(username: str, sid: str) -> list[str]:
    return [
        f"sess:{username}:{sid}",
        f"imap_pass:{username}:{sid}",
        f"imap_master:{username}:{sid}",
    ]


async def cerrar_sid(
    db, redis, username: str, sid: str, motivo: str = "logout"
) -> None:
    """Cierra UNA sesión: sus claves, su refresh. Las demás siguen."""
    pipe = redis.pipeline()
    pipe.delete(*_claves(username, sid))
    pipe.srem(f"sids:{username}", sid)
    await pipe.execute()
    await db.execute(
        "UPDATE refresh_tokens SET is_revoked = true "
        "WHERE username = $1 AND sid = $2 AND is_revoked = false",
        username,
        sid,
    )
    security_log.info("SESION_CERRADA user=%s sid=%s motivo=%s", username, sid, motivo)
    await _publicar(redis, username, sid, await av_actual(db, redis, username), motivo)


async def revocar_todo(db, redis, username: str, motivo: str) -> int:
    """Revoca TODAS las sesiones del usuario: sube av, revoca refreshes, borra estado.
    Un re-login posterior no revive nada: los tokens viejos traen el av anterior."""
    av = await subir_av(db, redis, username)
    await db.execute(
        "UPDATE refresh_tokens SET is_revoked = true "
        "WHERE username = $1 AND is_revoked = false",
        username,
    )
    try:
        sids = await redis.smembers(f"sids:{username}")
    except Exception:
        sids = set()
    claves = [f"sids:{username}"]
    for sid in sids:
        sid = sid.decode() if isinstance(sid, bytes) else sid
        claves += _claves(username, sid)
    try:
        await redis.delete(*claves)
    except Exception as exc:
        security_log.error(
            "REVOCACION_REDIS_FALLIDA user=%s error=%s", username, str(exc)[:120]
        )
    security_log.warning(
        "SESIONES_REVOCADAS user=%s av=%s sesiones=%s motivo=%s",
        username,
        av,
        len(sids),
        motivo,
    )
    await _publicar(redis, username, "*", av, motivo)
    return av


# ---------------------------------------------------------------- procesos de fondo
async def credencial_de_alguna_sesion(
    redis, username: str
) -> tuple[str, str, str] | None:
    """Para tareas sin petición (correo programado, sondeo): (sid, contraseña, usuario IMAP)
    de la primera sesión viva del usuario. Una que no descifra se cierra en el acto."""
    try:
        sids = await redis.smembers(f"sids:{username}")
    except Exception:
        return None
    for sid in sids:
        sid = sid.decode() if isinstance(sid, bytes) else sid
        raw = await redis.get(f"imap_pass:{username}:{sid}")
        if not raw:
            await redis.srem(f"sids:{username}", sid)
            continue
        try:
            clave = decrypt_password(raw.decode() if isinstance(raw, bytes) else raw)
        except Exception:
            log.error(
                "Credencial cacheada de %s (sid %s) no descifra; sesión invalidada "
                "[CREDENCIAL_NO_DESCIFRA]",
                username,
                sid,
            )
            await redis.delete(*_claves(username, sid))
            await redis.srem(f"sids:{username}", sid)
            continue
        master = await redis.get(f"imap_master:{username}:{sid}")
        if master:
            master = master.decode() if isinstance(master, bytes) else master
        return sid, clave, (f"{username}*{master}" if master else username)
    return None


async def listar_sesiones(
    redis, username: str, sid_actual: str | None = None
) -> list[dict]:
    """[L-01] Sesiones vivas de la persona: sid, tipo, dispositivo, IP, creada, vence, actual.
    Viva = con estado `sess:{u}:{sid}` en Redis (sin él ni el access ni el refresh valen);
    un sid del índice sin estado se retira. La actual va primero; el resto, por fecha.
    """
    try:
        sids = await redis.smembers(f"sids:{username}")
    except Exception as exc:
        log.error("SESIONES_NO_LISTABLES user=%s error=%s", username, str(exc)[:120])
        return []
    salida = []
    for sid in sids:
        sid = sid.decode() if isinstance(sid, bytes) else sid
        datos = await redis.hgetall(f"sess:{username}:{sid}")
        if not datos:
            await redis.srem(f"sids:{username}", sid)
            continue
        d = {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in datos.items()
        }
        salida.append(
            {
                "sid": sid,
                "tipo": d.get("kind") or "normal",
                "dispositivo": d.get("ua") or "",
                "ip": d.get("ip") or "",
                "creada": int(d.get("creada") or 0),
                "vence": int(d.get("abs_exp") or 0),
                "actual": sid == sid_actual,
            }
        )
    salida.sort(key=lambda x: (not x["actual"], -x["creada"]))
    return salida


async def cerrar_todas_en_redis(redis, username: str) -> None:
    """Cierra todas las sesiones SOLO en Redis (para código sin acceso a la base). Los
    tokens dejan de valer porque su sesión ya no existe; el refresh también, porque
    exige la sesión viva. La generación no sube: llamar a revocar_todo cuando se pueda.
    """
    try:
        sids = await redis.smembers(f"sids:{username}")
    except Exception:
        return
    claves = [f"sids:{username}"]
    for sid in sids:
        sid = sid.decode() if isinstance(sid, bytes) else sid
        claves += _claves(username, sid)
    await redis.delete(*claves)
    security_log.warning(
        "SESIONES_CERRADAS_REDIS user=%s sesiones=%s", username, len(sids)
    )
