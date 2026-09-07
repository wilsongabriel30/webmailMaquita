"""Autenticación de los clientes DAV externos (Z-Push) delante de Radicale (N-19).

Radicale corre con `auth type = http_x_remote_user`: confía en la cabecera `X-Remote-User` y NO
está expuesto a nadie más que a este backend (127.0.0.1). Z-Push, en su contenedor, llega a
Radicale por un vhost de nginx en el puente de Docker que pregunta aquí (`auth_request`) con la
cabecera `Authorization: Basic` del dispositivo; si se acepta, nginx pone `X-Remote-User` con
el correo y reenvía a Radicale. Así cada dispositivo solo ve las colecciones de su dueño.

Se acepta la contraseña de aplicación (D-5, comparada en SQL) y, mientras la política
`contrasenas_aplicacion_obligatorias` esté en `false`, también la principal (IMAP local).
El acierto de una contraseña de APLICACIÓN se recuerda 120 s en Redis por hash de usuario+clave
(Z-Push hace decenas de peticiones DAV por sincronización y bcrypt no es gratis). El de la
principal NO se recuerda: depende de la política, y activar la política tiene que cortar en el
acto (informe de Andes, 07/09: una principal aceptada antes de activarla seguía valiendo 120 s).
"""

import base64
import hashlib
import logging

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["dav"])

TTL_CACHE = 120
MARCA_ORIGEN = "dav-zpush"  # «IP» que ve la función SQL: no es local, así que la clave de aplicación vale


def credenciales_basic(cabecera: str | None) -> tuple[str, str] | None:
    """(usuario, clave) de una cabecera `Authorization: Basic …`, o None si no la hay o está mal."""
    if not cabecera or not cabecera.lower().startswith("basic "):
        return None
    try:
        crudo = base64.b64decode(cabecera[6:].strip(), validate=True).decode("utf-8")
    except Exception:
        return None
    if ":" not in crudo:
        return None
    usuario, clave = crudo.split(":", 1)
    usuario = usuario.strip().lower()
    if not usuario or "@" not in usuario or not clave:
        return None
    return usuario, clave


def clave_cache(usuario: str, clave: str) -> str:
    return "dav_auth:" + hashlib.sha256(f"{usuario}\0{clave}".encode()).hexdigest()


async def verificar(db, redis, usuario: str, clave: str) -> bool:
    """Contraseña de aplicación por SQL (con caché); principal por IMAP solo mientras no sea
    obligatoria la de aplicación, y nunca en caché."""
    k = clave_cache(usuario, clave)
    try:
        if redis is not None and await redis.get(k):
            return True
    except Exception:
        pass
    try:
        fila = await db.fetchrow(
            'SELECT "user" FROM verificar_contrasena_aplicacion($1, $2, $3)',
            usuario,
            clave,
            MARCA_ORIGEN,
        )
    except Exception as exc:
        logger.error(
            "dav_auth: fallo al consultar contrasenas de aplicacion (%s)",
            type(exc).__name__,
        )
        fila = None
    if fila:
        try:
            if redis is not None:
                await redis.set(k, "1", ex=TTL_CACHE)
        except Exception:
            pass
        return True
    # Contraseña principal: solo mientras no sea obligatoria la de aplicación, y sin caché.
    from app.auth.contrasenas_aplicacion import politica_obligatoria

    if await politica_obligatoria(db):
        return False
    from app.auth.password import verify_imap

    return bool(verify_imap(usuario, clave))


def _rechazo() -> Response:
    return Response(
        status_code=401, headers={"WWW-Authenticate": 'Basic realm="Maquita DAV"'}
    )


@router.get("/dav")
async def autenticar_dav(request: Request):
    """Objetivo de `auth_request`: 200 con `X-Usuario` si las credenciales valen; 401 si no."""
    cred = credenciales_basic(request.headers.get("authorization"))
    if not cred:
        return _rechazo()
    usuario, clave = cred
    if not await verificar(
        request.app.state.db_pool,
        getattr(request.app.state, "redis", None),
        usuario,
        clave,
    ):
        logger.info("dav_auth_rechazado | user=%s", usuario)
        return _rechazo()
    return Response(status_code=200, headers={"X-Usuario": usuario})
