#!/opt/maquita-webmail/backend/venv/bin/python
"""Unificar las etiquetas de una cuenta con dominio doble en una sola identidad (09/11/2026).

Algunas cuentas tienen sus etiquetas (`user_labels`) y asignaciones (`message_labels`) repartidas entre
`usuario@example.org` y `usuario@example.com` (o, en algún caso, un tercer dominio), porque en algún momento
entraron con una u otra identidad. Hoy entran como `@example.com`, así que las filas del otro owner no se
ven. Este script traslada al owner DESTINO lo que haya en el ORIGEN:

- etiquetas: se fusionan por nombre (sin distinguir mayúsculas ni espacios); la que falte se crea;
- asignaciones: sin duplicar (carpeta + uid + etiqueta); el origen queda sin filas.

Los uids: en la VM 130 cada identidad tiene SU PROPIO Maildir (`/var/vmail/example.org/u` y
`/var/vmail/example.com/u`), así que el uid 254 de INBOX en .org NO es el mismo correo que el 254 en
.com.ec. Por eso, si los maildirs reales (realpath) no coinciden, cada asignación se resuelve por Message-ID
con `doveadm`: se lee la cabecera en el buzón origen y se busca el mismo correo en la misma carpeta del
destino. Lo que no se encuentra NO se traslada ni se borra: se informa y queda en el origen (con
`--trasladar-sin-resolver` se traslada con el uid tal cual; el listado lo marcará faltante y la purga
semanal lo borrará si no aparece). Si los maildirs coinciden (misma ruta real), los uids se copian tal cual.

Idempotente: repetirlo no duplica nada (los `ON CONFLICT DO NOTHING` y la fusión por nombre lo garantizan).
Simula por defecto; con `--aplicar` escribe, en UNA transacción, tras guardar un respaldo JSON de todas las
filas del origen y del destino en /var/lib/maquita-webmail/unificar_etiquetas_<fecha>_<origen>.json.

Cómo correrlo (como root, en la carpeta de la instalación; primero SIEMPRE simular y leer la salida):

    # Simular y luego aplicar para una cuenta
    scripts/unificar_etiquetas_dominio_doble.py --origen usuario@example.org --destino usuario@example.com
    scripts/unificar_etiquetas_dominio_doble.py --origen usuario@example.org --destino usuario@example.com --aplicar

    # Descubrir pares automáticamente (mismo nombre local, maildir real idéntico; destino en --dominio-destino):
    scripts/unificar_etiquetas_dominio_doble.py --auto --dominio-destino example.com

    # OJO: dos buzones con el mismo nombre local en dominios distintos pueden ser PERSONAS distintas.
    # No unificar sin confirmarlo con la organización; el modo simulación lo deja ver sin tocar nada.

Para volver atrás: el JSON de respaldo tiene las filas originales (ids, owner, nombres, asignaciones) de ambos
owners; se reinsertan a mano con psql. Antes de aplicar en producción: respaldo de la BD como siempre.
"""

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field

log = logging.getLogger("unificar_etiquetas")

DIR_RESPALDOS = "/var/lib/maquita-webmail"


# ───────────────────────────── parte pura (probada en tests/test_unificar_etiquetas.py) ─────────────────────────────


def clave_nombre(nombre: str) -> str:
    return " ".join((nombre or "").split()).casefold()


@dataclass
class Plan:
    """Lo que hay que hacer para pasar el origen al destino. Solo datos; nada de BD."""

    # (nombre, color, id_origen): etiquetas que faltan en el destino
    etiquetas_crear: list[tuple[str, str, int]] = field(default_factory=list)
    # id etiqueta origen → id etiqueta destino (solo las que ya existen allí por nombre)
    mapa_etiqueta: dict[int, int] = field(default_factory=dict)
    # (carpeta, uid destino, id etiqueta ORIGEN): asignaciones a insertar en el destino
    asignaciones_insertar: list[tuple[str, int, int]] = field(default_factory=list)
    # ids de message_labels del origen que ya están en destino (o se trasladan): se borran
    asignaciones_borrar: list[int] = field(default_factory=list)
    # asignaciones del origen sin correo equivalente en destino: se dejan e informan
    asignaciones_sin_resolver: list[dict] = field(default_factory=list)
    # ids de user_labels del origen que se borran al final (todas, salvo que les quede algo sin resolver)
    etiquetas_borrar: list[int] = field(default_factory=list)
    etiquetas_conservadas: list[int] = field(default_factory=list)

    def resumen(self) -> str:
        return (
            f"etiquetas: {len(self.mapa_etiqueta)} fusionadas por nombre, {len(self.etiquetas_crear)} por crear, "
            f"{len(self.etiquetas_borrar)} del origen por borrar, {len(self.etiquetas_conservadas)} conservadas; "
            f"asignaciones: {len(self.asignaciones_insertar)} por insertar, {len(self.asignaciones_borrar)} del origen "
            f"por borrar, {len(self.asignaciones_sin_resolver)} sin resolver"
        )


def planificar_fusion(
    etiquetas_origen: list[dict],
    etiquetas_destino: list[dict],
    asignaciones_origen: list[dict],
    asignaciones_destino: list[dict],
    mapa_uid: dict[tuple[str, int], int | None] | None = None,
    trasladar_sin_resolver: bool = False,
) -> Plan:
    """Calcula la fusión. Función pura.

    etiquetas_*: dicts con id, name, color. asignaciones_*: dicts con id, folder, message_uid, label_id.
    mapa_uid: {(carpeta, uid origen): uid destino | None}; None = no se encontró el correo en el destino.
    Si mapa_uid es None, los uids se copian tal cual (mismo buzón físico).
    """
    plan = Plan()
    destino_por_nombre = {clave_nombre(e["name"]): e["id"] for e in etiquetas_destino}
    for e in etiquetas_origen:
        k = clave_nombre(e["name"])
        if k in destino_por_nombre:
            plan.mapa_etiqueta[e["id"]] = destino_por_nombre[k]
        else:
            plan.etiquetas_crear.append((e["name"], e["color"], e["id"]))

    # Qué hay ya en destino, expresado con ids de etiqueta de ORIGEN para comparar.
    destino_por_id_origen = {}
    for id_origen, id_destino in plan.mapa_etiqueta.items():
        destino_por_id_origen.setdefault(id_destino, []).append(id_origen)
    existentes: set[tuple[str, int, int]] = set()
    for a in asignaciones_destino:
        for id_origen in destino_por_id_origen.get(a["label_id"], ()):
            existentes.add((a["folder"], a["message_uid"], id_origen))

    etiquetas_con_pendientes: set[int] = set()
    for a in asignaciones_origen:
        carpeta, uid, etiqueta = a["folder"], a["message_uid"], a["label_id"]
        if mapa_uid is None:
            uid_destino: int | None = uid
        else:
            uid_destino = mapa_uid.get((carpeta, uid))
            if uid_destino is None and trasladar_sin_resolver:
                uid_destino = uid
        if uid_destino is None:
            plan.asignaciones_sin_resolver.append(dict(a))
            etiquetas_con_pendientes.add(etiqueta)
            continue
        clave = (carpeta, uid_destino, etiqueta)
        if clave not in existentes:
            existentes.add(clave)
            plan.asignaciones_insertar.append(clave)
        plan.asignaciones_borrar.append(a["id"])

    for e in etiquetas_origen:
        if e["id"] in etiquetas_con_pendientes:
            plan.etiquetas_conservadas.append(
                e["id"]
            )  # borrarla arrastraría (CASCADE) lo no resuelto
        else:
            plan.etiquetas_borrar.append(e["id"])
    return plan


# ───────────────────────────── acceso a datos y doveadm ─────────────────────────────


def dsn() -> str:
    for ruta in ("backend/.env", ".env"):
        try:
            for linea in open(ruta, encoding="utf-8"):
                if linea.startswith("DATABASE_URL="):
                    return linea.split("=", 1)[1].strip()
        except OSError:
            pass
    sys.exit("No encuentro DATABASE_URL en backend/.env")


def _doveadm(*args: str) -> str:
    try:
        return subprocess.run(
            ["doveadm", *args], capture_output=True, text=True, timeout=60, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("doveadm %s: %s", " ".join(args[:3]), e)
        return ""


def maildir_real(usuario: str) -> str | None:
    """Ruta real del Maildir según Dovecot (`doveadm user`)."""
    salida = _doveadm("user", "-f", "mail_path", usuario) or _doveadm(
        "user", "-f", "mail", usuario
    )
    ruta = salida.strip().splitlines()[-1].strip() if salida.strip() else ""
    if ruta.startswith("maildir:"):
        ruta = ruta.split(":", 1)[1].split(":", 1)[0]
    return os.path.realpath(ruta) if ruta else None


def message_id_en(usuario: str, carpeta: str, uid: int) -> str | None:
    salida = _doveadm(
        "fetch", "-u", usuario, "hdr.message-id", "mailbox", carpeta, "uid", str(uid)
    )
    for linea in salida.splitlines():
        if linea.lower().startswith("hdr.message-id:"):
            valor = linea.split(":", 1)[1].strip()
            return valor or None
    return None


def uid_con_message_id(usuario: str, carpeta: str, message_id: str) -> int | None:
    salida = _doveadm(
        "search", "-u", usuario, "mailbox", carpeta, "header", "message-id", message_id
    )
    uids = []
    for linea in salida.splitlines():
        partes = linea.split()
        if len(partes) == 2 and partes[1].isdigit():
            uids.append(int(partes[1]))
    return max(uids) if uids else None


def resolver_uids(
    origen: str, destino: str, asignaciones: list[dict]
) -> dict[tuple[str, int], int | None]:
    """{(carpeta, uid origen): uid destino | None} consultando a Dovecot por Message-ID."""
    mapa: dict[tuple[str, int], int | None] = {}
    pares = sorted({(a["folder"], a["message_uid"]) for a in asignaciones})
    for i, (carpeta, uid) in enumerate(pares, 1):
        mid = message_id_en(origen, carpeta, uid)
        mapa[(carpeta, uid)] = (
            uid_con_message_id(destino, carpeta, mid) if mid else None
        )
        if i % 50 == 0:
            log.info("  resueltos %d/%d", i, len(pares))
    return mapa


async def cargar(con, owner: str) -> tuple[list[dict], list[dict]]:
    etiquetas = [
        dict(r)
        for r in await con.fetch(
            "SELECT id, name, color FROM user_labels WHERE owner = $1 ORDER BY id",
            owner,
        )
    ]
    asignaciones = [
        dict(r)
        for r in await con.fetch(
            "SELECT id, folder, message_uid, label_id, created_at FROM message_labels WHERE owner = $1 ORDER BY id",
            owner,
        )
    ]
    return etiquetas, asignaciones


def respaldar(origen: str, datos: dict) -> str:
    os.makedirs(DIR_RESPALDOS, exist_ok=True)
    nombre = f"unificar_etiquetas_{dt.datetime.now():%Y%m%d_%H%M%S}_{origen.replace('@', '_')}.json"
    ruta = os.path.join(DIR_RESPALDOS, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1, default=str)
    os.chmod(ruta, 0o600)
    return ruta


async def aplicar(con, origen: str, destino: str, plan: Plan) -> None:
    async with con.transaction():
        ids_destino = dict(plan.mapa_etiqueta)
        for nombre, color, id_origen in plan.etiquetas_crear:
            fila = await con.fetchrow(
                """INSERT INTO user_labels (owner, name, color) VALUES ($1, $2, $3)
                   ON CONFLICT (owner, name) DO UPDATE SET color = user_labels.color RETURNING id""",
                destino,
                nombre,
                color,
            )
            ids_destino[id_origen] = fila["id"]
        for carpeta, uid, id_origen in plan.asignaciones_insertar:
            await con.execute(
                "INSERT INTO message_labels (owner, folder, message_uid, label_id) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                destino,
                carpeta,
                uid,
                ids_destino[id_origen],
            )
        if plan.asignaciones_borrar:
            await con.execute(
                "DELETE FROM message_labels WHERE owner = $1 AND id = ANY($2::int[])",
                origen,
                plan.asignaciones_borrar,
            )
        if plan.etiquetas_borrar:
            await con.execute(
                "DELETE FROM user_labels WHERE owner = $1 AND id = ANY($2::int[])",
                origen,
                plan.etiquetas_borrar,
            )


async def pares_automaticos(con, dominio_destino: str) -> list[tuple[str, str]]:
    filas = await con.fetch(
        """SELECT split_part(owner, '@', 1) AS local, array_agg(DISTINCT owner) AS owners
           FROM user_labels GROUP BY 1 HAVING count(DISTINCT owner) > 1"""
    )
    pares = []
    for f in filas:
        destinos = [o for o in f["owners"] if o.endswith("@" + dominio_destino)]
        if len(destinos) != 1:
            continue
        destino = destinos[0]
        md_destino = maildir_real(destino)
        for origen in f["owners"]:
            if origen == destino:
                continue
            if md_destino and maildir_real(origen) == md_destino:
                pares.append((origen, destino))
            else:
                log.info(
                    "se omite %s → %s: maildir distinto; indíquelo a mano con --origen/--destino",
                    origen,
                    destino,
                )
    return pares


async def unificar(
    con,
    origen: str,
    destino: str,
    aplicar_cambios: bool,
    trasladar_sin_resolver: bool,
    uids_iguales: bool,
) -> Plan:
    log.info("== %s → %s", origen, destino)
    et_o, as_o = await cargar(con, origen)
    et_d, as_d = await cargar(con, destino)
    log.info(
        "origen: %d etiquetas, %d asignaciones; destino: %d etiquetas, %d asignaciones",
        len(et_o),
        len(as_o),
        len(et_d),
        len(as_d),
    )
    if not et_o and not as_o:
        log.info("nada que unificar")
        return Plan()
    mapa_uid = None
    if as_o and not uids_iguales:
        md_o, md_d = maildir_real(origen), maildir_real(destino)
        if md_o and md_o == md_d:
            log.info("mismo Maildir real (%s): los uids se copian tal cual", md_o)
        else:
            log.info(
                "Maildir distinto (%s ≠ %s): se resuelven los uids por Message-ID con doveadm",
                md_o,
                md_d,
            )
            mapa_uid = resolver_uids(origen, destino, as_o)
    plan = planificar_fusion(et_o, et_d, as_o, as_d, mapa_uid, trasladar_sin_resolver)
    log.info("plan: %s", plan.resumen())
    for nombre, _color, _id in plan.etiquetas_crear:
        log.info("  crear en destino: «%s»", nombre)
    for a in plan.asignaciones_sin_resolver[:30]:
        log.info(
            "  sin resolver (queda en origen): etiqueta %s, %s uid %s",
            a["label_id"],
            a["folder"],
            a["message_uid"],
        )
    if not aplicar_cambios:
        log.info("SIMULACIÓN: no se escribió nada. Repita con --aplicar.")
        return plan
    ruta = respaldar(
        origen,
        {
            "origen": origen,
            "destino": destino,
            "etiquetas_origen": et_o,
            "asignaciones_origen": as_o,
            "etiquetas_destino": et_d,
            "asignaciones_destino": as_d,
            "mapa_uid": [[k[0], k[1], v] for k, v in (mapa_uid or {}).items()],
            "plan": plan.__dict__,
        },
    )
    log.info("respaldo: %s", ruta)
    await aplicar(con, origen, destino, plan)
    et_o2, as_o2 = await cargar(con, origen)
    log.info(
        "aplicado. Quedan en origen: %d etiquetas, %d asignaciones (sin resolver)",
        len(et_o2),
        len(as_o2),
    )
    return plan


def principal() -> None:
    import asyncpg

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--origen", help="owner del que se sacan las etiquetas (p. ej. u@example.org)"
    )
    ap.add_argument(
        "--destino", help="owner con el que entra la persona (p. ej. u@example.com)"
    )
    ap.add_argument(
        "--auto",
        action="store_true",
        help="descubrir pares con mismo nombre local y mismo Maildir real",
    )
    ap.add_argument("--dominio-destino", default="example.com")
    ap.add_argument(
        "--aplicar", action="store_true", help="escribir (por defecto solo simula)"
    )
    ap.add_argument("--simular", action="store_true", help="(por defecto) solo informa")
    ap.add_argument(
        "--uids-iguales",
        action="store_true",
        help="no resolver por Message-ID: copiar los uids tal cual",
    )
    ap.add_argument(
        "--trasladar-sin-resolver",
        action="store_true",
        help="trasladar también lo que no se encuentre en el destino",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if not args.auto and not (args.origen and args.destino):
        ap.error("indique --origen y --destino, o --auto")
    if args.origen and args.origen == args.destino:
        ap.error("origen y destino son el mismo owner")

    async def correr():
        con = await asyncpg.connect(dsn())
        try:
            pares = (
                [(args.origen, args.destino)]
                if args.origen
                else await pares_automaticos(con, args.dominio_destino)
            )
            if not pares:
                log.info("no hay pares que unificar")
            for origen, destino in pares:
                await unificar(
                    con,
                    origen,
                    destino,
                    args.aplicar and not args.simular,
                    args.trasladar_sin_resolver,
                    args.uids_iguales,
                )
        finally:
            await con.close()

    asyncio.run(correr())


if __name__ == "__main__":
    principal()
