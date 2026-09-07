#!/usr/bin/env python3
"""Normalización de una sola vez de todas las firmas guardadas (hallazgo de usuario, 07/09/2026).

Recorre las firmas de las personas (`user_signatures`, `user_identities`, `user_preferences`)
y las del panel (`mail_signatures`, `mail_user_signatures`), las pasa por
`app.mail.firmas.normalizar_firma` y cuenta. Sin `--aplicar` no escribe nada. Una firma con
alguna imagen que no se pudo traer (aviso «Se quitó la imagen») se deja como está y se
informa, salvo con `--forzar`. Nunca imprime el HTML de nadie: solo dueño, id y avisos.

    cd /opt/maquita-webmail/backend && venv/bin/python ../deploy/tools/firmas-normalizar.py [--aplicar] [--forzar]
"""

import asyncio
import os
import sys

import asyncpg

sys.path.insert(0, os.getcwd())
from app.config import get_settings  # noqa: E402
from app.mail.firmas import normalizar_firma  # noqa: E402

TABLAS = (
    # (tabla, columna con la firma, columna del dueño, clave de la fila)
    ("user_signatures", "html_content", "owner", "id"),
    ("user_identities", "signature_html", "username", "id"),
    ("user_preferences", "signature_html", "username", "username"),
    ("mail_signatures", "html_content", "domain", "id"),
    ("mail_user_signatures", "custom_html", "username", "id"),
)


async def main(aplicar: bool, forzar: bool) -> int:
    con = await asyncpg.connect(get_settings().database_url)
    totales = {
        "revisadas": 0,
        "sin_cambios": 0,
        "normalizadas": 0,
        "saltadas": 0,
        "imagenes": 0,
    }
    try:
        for tabla, columna, duenio, clave in TABLAS:
            try:
                filas = await con.fetch(
                    f"SELECT {clave} AS clave, {duenio} AS duenio, {columna} AS html FROM {tabla} "
                    f"WHERE coalesce({columna}, '') <> '' ORDER BY 1"
                )
            except asyncpg.UndefinedTableError:
                print(f"{tabla}: no existe (se omite)")
                continue
            n = {"sin_cambios": 0, "normalizadas": 0, "saltadas": 0}
            for fila in filas:
                totales["revisadas"] += 1
                correo = fila["duenio"] if "@" in (fila["duenio"] or "") else None
                r = normalizar_firma(fila["html"], correo_usuario=correo)
                totales["imagenes"] += r.imagenes
                for aviso in r.avisos:
                    print(
                        f"  {tabla} {clave}={fila['clave']} ({fila['duenio']}): {aviso}"
                    )
                if r.html == fila["html"]:
                    n["sin_cambios"] += 1
                    continue
                if (
                    any(a.startswith("Se quitó la imagen") for a in r.avisos)
                    and not forzar
                ):
                    n["saltadas"] += 1
                    print(
                        f"  {tabla} {clave}={fila['clave']}: se deja como está (imagen no recuperable; --forzar la aplicaría)"
                    )
                    continue
                n["normalizadas"] += 1
                if aplicar:
                    await con.execute(
                        f"UPDATE {tabla} SET {columna} = $1 WHERE {clave} = $2",
                        r.html,
                        fila["clave"],
                    )
            for k in n:
                totales[k] += n[k]
            print(
                f"{tabla}: {len(filas)} con firma, {n['normalizadas']} normalizadas, "
                f"{n['sin_cambios']} ya correctas, {n['saltadas']} saltadas"
            )
    finally:
        await con.close()
    print(
        f"total: {totales['revisadas']} revisadas, {totales['normalizadas']} normalizadas, "
        f"{totales['sin_cambios']} ya correctas, {totales['saltadas']} saltadas, "
        f"{totales['imagenes']} imágenes traídas al servidor"
        + ("" if aplicar else "  (sin --aplicar no se ha escrito nada)")
    )
    return 1 if totales["saltadas"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--aplicar" in sys.argv, "--forzar" in sys.argv)))
