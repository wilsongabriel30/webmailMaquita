#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migración de una vez (N-19): las colecciones de Radicale del webmail pasan de `/<parte local>/`
a `/<correo completo>/`, que es el árbol que usa Z-Push (`CALDAV_PATH '/%u/'`). Hasta hoy el
calendario del webmail y el del teléfono eran dos árboles distintos.

Por cada calendario de la tabla `calendars` cuyo `radicale_path` no lleve `@`:
  - mueve `collection-root/<local>/<coleccion>` a `collection-root/<correo>/<coleccion>` (si el
    destino ya existe, copia los .ics que falten y deja el resto como está);
  - actualiza `radicale_path` en la tabla.
El árbol antiguo queda en el respaldo indicado. Sin `--aplicar` solo cuenta. Ejecutar como root
(los ficheros quedan de www-data) con Radicale y el backend parados o en un momento tranquilo.

    cd /opt/maquita-webmail/backend && venv/bin/python ../deploy/tools/radicale-migrar-prefijo.py [--aplicar]
"""
import asyncio
import os
import shutil
import sys
import time

import asyncpg

sys.path.insert(0, os.getcwd())
from app.config import get_settings  # noqa: E402

RAIZ = os.getenv("RADICALE_COLECCIONES", "/var/lib/radicale/collections/collection-root")


def mover(origen: str, destino: str) -> tuple[int, int]:
    """Mueve una colección; si el destino existe, completa los .ics que falten. (movidos, ya_estaban)."""
    if not os.path.isdir(destino):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.copytree(origen, destino, symlinks=True)
        return sum(1 for f in os.listdir(destino) if f.endswith(".ics")), 0
    movidos = repetidos = 0
    for nombre in os.listdir(origen):
        o, d = os.path.join(origen, nombre), os.path.join(destino, nombre)
        if os.path.isfile(o) and not os.path.exists(d):
            shutil.copy2(o, d)
            movidos += 1
        elif os.path.isfile(o):
            repetidos += 1
    return movidos, repetidos


async def main(aplicar: bool) -> int:
    con = await asyncpg.connect(get_settings().database_url)
    filas = await con.fetch("SELECT id, owner_email, radicale_path FROM calendars WHERE position('@' in radicale_path) = 0 ORDER BY owner_email")
    respaldo = f"/root/respaldos-radicale-prefijo-{time.strftime('%Y%m%d-%H%M')}"
    total_ics = 0
    arboles = set()
    for f in filas:
        correo = f["owner_email"].strip().lower()
        local, _, coleccion = f["radicale_path"].partition("/")
        origen = os.path.join(RAIZ, local, coleccion)
        destino = os.path.join(RAIZ, correo, coleccion)
        n_ics = sum(1 for x in os.listdir(origen) if x.endswith(".ics")) if os.path.isdir(origen) else 0
        total_ics += n_ics
        print(f"{correo}: {f['radicale_path']} → {correo}/{coleccion} ({n_ics} ics{'' if os.path.isdir(origen) else ', SIN carpeta'})")
        if not aplicar:
            continue
        if os.path.isdir(origen):
            movidos, repetidos = mover(origen, destino)
            print(f"   copiados {movidos}, ya estaban {repetidos}")
            arboles.add(local)
        await con.execute("UPDATE calendars SET radicale_path = $1 WHERE id = $2", f"{correo}/{coleccion}", f["id"])
    await con.close()
    if aplicar:
        os.makedirs(respaldo, mode=0o700, exist_ok=True)
        for local in arboles:
            shutil.move(os.path.join(RAIZ, local), os.path.join(respaldo, local))
        for raiz, dirs, ficheros in os.walk(RAIZ):
            for x in dirs + ficheros:
                try:
                    shutil.chown(os.path.join(raiz, x), "www-data", "www-data")
                except Exception:
                    pass
        print(f"árboles antiguos en {respaldo}: {sorted(arboles)}")
    print(f"calendarios con prefijo antiguo: {len(filas)}, eventos: {total_ics}" + ("" if aplicar else "  (sin --aplicar no se toca nada)"))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--aplicar" in sys.argv)))
