#!/usr/bin/env python3
"""Vuelve a cifrar con la llave DEDICADA lo que quedó cifrado con la antigua (H-02).

Qué toca:
  - user_totp.secret            (antes en claro; ahora cifrado — L-03)
  - nextcloud_accounts.nc_password (antes con la llave derivada de SECRET_KEY)

Cuenta antes y después; sin --aplicar no escribe nada. Ejecutar desde backend/:
    venv/bin/python ../deploy/tools/recifrar-credenciales.py [--aplicar]
Requiere CREDENTIAL_ENCRYPTION_KEY en .env (y SECRET_KEY, para leer lo antiguo).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from app.core import cifrado  # noqa: E402
from app.database import create_db_pool  # noqa: E402

APLICAR = "--aplicar" in sys.argv


async def _totp(pool) -> tuple[int, int]:
    filas = await pool.fetch("SELECT username, secret FROM user_totp")
    pendientes = [f for f in filas if not cifrado.esta_cifrado(f["secret"])]
    if APLICAR:
        for f in pendientes:
            await pool.execute(
                "UPDATE user_totp SET secret = $1 WHERE username = $2",
                cifrado.cifrar(f["secret"]),
                f["username"],
            )
    return len(filas), len(pendientes)


async def _nextcloud(pool) -> tuple[int, int, int]:
    try:
        filas = await pool.fetch(
            "SELECT mail_username, nc_password FROM nextcloud_accounts"
        )
    except Exception:
        return 0, 0, 0
    heredado = cifrado.fernet_heredado_de_secret_key()
    pendientes, imposibles = [], 0
    for f in filas:
        v = f["nc_password"] or ""
        try:
            cifrado.descifrar(v)
            continue  # ya con la llave actual (o la anterior declarada)
        except Exception:
            pass
        try:
            claro = heredado.decrypt(v.encode()).decode()
        except Exception:
            claro = v if not cifrado.esta_cifrado(v) else None  # legado en claro
        if claro is None:
            imposibles += 1
            continue
        pendientes.append((f["mail_username"], claro))
    if APLICAR:
        for u, claro in pendientes:
            await pool.execute(
                "UPDATE nextcloud_accounts SET nc_password = $1 WHERE mail_username = $2",
                cifrado.cifrar(claro),
                u,
            )
    return len(filas), len(pendientes), imposibles


async def main():
    pool = await create_db_pool()
    try:
        t_total, t_pend = await _totp(pool)
        n_total, n_pend, n_imp = await _nextcloud(pool)
    finally:
        await pool.close()
    modo = "APLICADO" if APLICAR else "solo conteo (usa --aplicar)"
    print(f"user_totp: {t_total} filas, {t_pend} recifradas — {modo}")
    print(
        f"nextcloud_accounts: {n_total} filas, {n_pend} recifradas, {n_imp} imposibles (revisar a mano) — {modo}"
    )


asyncio.run(main())
