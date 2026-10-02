"""Dispositivos de confianza para el segundo factor: la app del teléfono no repite el código.

La app Android («MaquitaMailApp» en el agente de usuario) guarda la sesión 7 días; al caducar
vuelve a pedir el código del segundo factor y la gente lo vive como un bloqueo. Aquí, tras
pasar el código UNA vez desde la app, el teléfono queda registrado y las siguientes entradas
desde ese mismo teléfono no piden código:

- Solo se emite y solo se acepta desde la app (agente de usuario). En un navegador nunca.
- La ficha va en una cookie httpOnly limitada a /api/auth/login; en la base solo su hash,
  atada a la cuenta y con caducidad (180 días). La contraseña se sigue pidiendo siempre.
- Cambiar la contraseña revoca todos los dispositivos de la cuenta (igual que las sesiones y
  las contraseñas de aplicación). Cada alta y cada uso quedan en audit_log.
"""

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from app.auth.cookies import dominio_cookie
from fastapi import Request, Response

log = logging.getLogger(__name__)

COOKIE = "dispositivo_confianza"
DIAS = 180
_TABLA = """
CREATE TABLE IF NOT EXISTS dispositivos_confianza (
    id           bigserial PRIMARY KEY,
    username     varchar(255) NOT NULL,
    token_hash   text         NOT NULL UNIQUE,
    user_agent   varchar(300) NOT NULL DEFAULT '',
    created_at   timestamptz  NOT NULL DEFAULT now(),
    expires_at   timestamptz  NOT NULL,
    last_used_at timestamptz,
    revoked_at   timestamptz,
    motivo       varchar(60)
);
CREATE INDEX IF NOT EXISTS dispositivos_confianza_username ON dispositivos_confianza (username)
    WHERE revoked_at IS NULL;
"""
_tabla_ok = False


async def _tabla(db) -> None:
    global _tabla_ok
    if not _tabla_ok:
        await db.execute(_TABLA)
        _tabla_ok = True


def es_app(request: Request) -> bool:
    return "MaquitaMail" in (request.headers.get("user-agent", "") or "")


def _hash(ficha: str) -> str:
    return hashlib.sha256(ficha.encode()).hexdigest()


def _ip(request: Request) -> str | None:
    return (
        request.headers.get("x-real-ip")
        or (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or None)
        or (request.client.host if request.client else None)
    )


async def _auditar(
    db, request: Request, username: str, accion: str, detalles: dict
) -> None:
    try:
        await db.execute(
            "INSERT INTO audit_log (admin_user, action, target, details, ip_address) VALUES ($1, $2, $3, $4::jsonb, $5::inet)",
            username,
            accion,
            "auth",
            json.dumps(detalles),
            _ip(request),
        )
    except Exception as exc:  # la auditoría nunca impide entrar
        log.warning("%s sin auditoría (%s): %s", accion, username, exc)


async def confiado(db, request: Request, username: str) -> bool:
    """¿Esta petición viene de la app, con una ficha vigente de ESTA cuenta? Anota el uso."""
    ficha = (request.cookies.get(COOKIE) or "").strip()
    if not ficha or len(ficha) > 128 or not es_app(request):
        return False
    await _tabla(db)
    fila = await db.fetchrow(
        """UPDATE dispositivos_confianza SET last_used_at = now()
            WHERE token_hash = $1 AND lower(username) = lower($2)
              AND revoked_at IS NULL AND expires_at > now()
        RETURNING id""",
        _hash(ficha),
        username,
    )
    if not fila:
        return False
    await _auditar(
        db, request, username, "dispositivo_confianza_uso", {"id": fila["id"]}
    )
    return True


async def recordar(db, request: Request, response: Response, username: str) -> bool:
    """Tras pasar el código desde la app: registra el teléfono y deja la cookie. Fuera de la
    app no hace nada."""
    if not es_app(request):
        return False
    await _tabla(db)
    ficha = secrets.token_urlsafe(32)
    vence = datetime.now(timezone.utc) + timedelta(days=DIAS)
    fila = await db.fetchrow(
        "INSERT INTO dispositivos_confianza (username, token_hash, user_agent, expires_at) VALUES ($1, $2, $3, $4) RETURNING id",
        username,
        _hash(ficha),
        (request.headers.get("user-agent", "") or "")[:300],
        vence,
    )
    response.set_cookie(
        key=COOKIE,
        value=ficha,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=dominio_cookie(request),
        max_age=DIAS * 86400,
        path="/api/auth/login",
    )
    await _auditar(
        db,
        request,
        username,
        "dispositivo_confianza_alta",
        {
            "id": fila["id"],
            "vence": vence.isoformat(),
            "agente": (request.headers.get("user-agent", "") or "")[:80],
        },
    )
    return True


async def revocar_todos(db, username: str, motivo: str) -> int:
    """Al cambiar la contraseña (o a petición de TI): ningún teléfono sigue de confianza."""
    await _tabla(db)
    r = await db.execute(
        "UPDATE dispositivos_confianza SET revoked_at = now(), motivo = $2 WHERE lower(username) = lower($1) AND revoked_at IS NULL",
        username,
        motivo[:60],
    )
    try:
        return int(r.split()[-1])
    except Exception:
        return 0


async def listar(db, username: str) -> list[dict]:
    await _tabla(db)
    filas = await db.fetch(
        """SELECT id, user_agent, created_at, expires_at, last_used_at FROM dispositivos_confianza
            WHERE lower(username) = lower($1) AND revoked_at IS NULL AND expires_at > now() ORDER BY created_at DESC""",
        username,
    )
    return [dict(f) for f in filas]
