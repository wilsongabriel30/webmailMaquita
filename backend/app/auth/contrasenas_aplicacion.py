"""Contraseñas de aplicación (D-5): una por cliente externo, revocables, sin tocar la principal.

El segundo factor protege el webmail y la app, pero IMAP, SMTP y ActiveSync directos solo tienen
la contraseña. Con esto, cada cliente (Outlook, Thunderbird, el celular) recibe su propia
contraseña generada aquí; se revoca desde Ajustes o al cambiar la contraseña principal, y con la
política `contrasenas_aplicacion_obligatorias` activa la principal deja de valer fuera del
servidor (Dovecot solo la acepta desde 127.0.0.1/::1, es decir, desde el webmail).

La verificación la hace Dovecot en cada login con `verificar_contrasena_aplicacion()` (bcrypt en
pgcrypto), ver `migrations/2026-09-07-contrasenas-aplicacion.sql`. Aquí solo se generan, listan
y revocan. La contraseña se muestra UNA vez; en la base queda solo el hash y su prefijo.
"""

import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/settings/contrasenas-aplicacion", tags=["contrasenas-aplicacion"]
)

# Sin 0/o/1/l/i: se teclea a mano en un teléfono. 16 símbolos de 31 ≈ 79 bits.
ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"
MAXIMO_POR_USUARIO = 10
POLITICA = "contrasenas_aplicacion_obligatorias"


class Nueva(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=80)
    contrasena_actual: str = Field(..., min_length=1)


def generar() -> str:
    """Cuatro grupos de cuatro, con guiones para leerla; se acepta con o sin ellos."""
    grupos = ["".join(secrets.choice(ALFABETO) for _ in range(4)) for _ in range(4)]
    return "-".join(grupos)


def limpiar(clave: str) -> str:
    return clave.replace("-", "").replace(" ", "")


def _fila(r) -> dict:
    d = dict(r)
    for k in ("creada", "ultimo_uso"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


async def politica_obligatoria(db) -> bool:
    try:
        v = await db.fetchval(
            "SELECT valor FROM auth_politica WHERE clave = $1", POLITICA
        )
    except Exception:
        return False
    return (v or "").lower() == "true"


async def revocar_todas(db, username: str, motivo: str) -> int:
    """Al cambiar la contraseña principal (o por un administrador) caen todas las de aplicación."""
    r = await db.execute(
        "UPDATE contrasenas_aplicacion SET revocada = NOW(), motivo_revocacion = $2 "
        "WHERE username = $1 AND revocada IS NULL",
        username,
        motivo[:80],
    )
    n = int(r.split()[-1]) if r else 0
    if n:
        logger.info(
            "app_passwords_revoked | user=%s | motivo=%s | n=%d", username, motivo, n
        )
    return n


@router.get("")
async def listar(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    filas = await db.fetch(
        "SELECT id, nombre, prefijo, creada, ultimo_uso, ultimo_ip FROM contrasenas_aplicacion "
        "WHERE username = $1 AND revocada IS NULL ORDER BY creada",
        username,
    )
    return {
        "contrasenas": [_fila(r) for r in filas],
        "obligatorias": await politica_obligatoria(db),
        "maximo": MAXIMO_POR_USUARIO,
    }


@router.post("", status_code=201)
async def crear(
    body: Nueva, request: Request, username: str = Depends(get_current_user)
):
    from app.auth.password import verify_imap

    await get_user_password(request, username)  # sesión viva
    # La contraseña principal se pide aquí a propósito: una cookie robada no debe poder
    # fabricarse una llave permanente para IMAP.
    if not verify_imap(username, body.contrasena_actual):
        raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")
    db = request.app.state.db_pool
    n = await db.fetchval(
        "SELECT COUNT(*) FROM contrasenas_aplicacion WHERE username = $1 AND revocada IS NULL",
        username,
    )
    if n >= MAXIMO_POR_USUARIO:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAXIMO_POR_USUARIO} contraseñas de aplicación; revoca alguna",
        )
    clave = generar()
    try:
        fila = await db.fetchrow(
            "INSERT INTO contrasenas_aplicacion (username, nombre, hash, prefijo) "
            "VALUES ($1, $2, crypt($3, gen_salt('bf', 10)), $4) RETURNING id, nombre, prefijo, creada",
            username,
            body.nombre.strip(),
            limpiar(clave),
            clave[:4],
        )
    except (
        Exception
    ) as exc:  # pgcrypto ausente o tabla sin migrar: no se guarda nada a medias
        logger.error(
            "app_password_create_failed | user=%s | %s", username, type(exc).__name__
        )
        raise HTTPException(
            status_code=500,
            detail="No se pudo crear la contraseña de aplicación (revisar pgcrypto y la migración)",
        )
    logger.info(
        "app_password_created | user=%s | id=%s | nombre=%s",
        username,
        fila["id"],
        body.nombre.strip(),
    )
    return {
        **_fila(fila),
        "contrasena": clave,
        "obligatorias": await politica_obligatoria(db),
    }


@router.delete("/{clave_id}")
async def revocar(
    clave_id: int, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool
    r = await db.execute(
        "UPDATE contrasenas_aplicacion SET revocada = NOW(), motivo_revocacion = 'usuario' "
        "WHERE id = $1 AND username = $2 AND revocada IS NULL",
        clave_id,
        username,
    )
    if r == "UPDATE 0":
        raise HTTPException(
            status_code=404, detail="Contraseña de aplicación no encontrada"
        )
    logger.info("app_password_revoked | user=%s | id=%s", username, clave_id)
    return {"status": "revocada"}
