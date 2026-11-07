#!/opt/maquita-webmail/backend/venv/bin/python
"""Reconstruye la libreta «de afuera» de cada buzón a partir de su carpeta Enviados (05/11/2026).

Zimbra tenía por cuenta la libreta «Emailed Contacts» (100.841 direcciones en total): cada persona a la
que alguien escribió alguna vez. Se decidió no copiarla el 20/10 y el personal la echa de menos
(«los contactos de afuera no están»). Zimbra la construía exactamente con los destinatarios de los
correos enviados, así que aquí se rehace leyendo las cabeceras To/Cc de la carpeta Sent de cada buzón
(ya migrada completa a este servidor), sin tocar Zimbra:

  - `sent_recipients` (autocompletar del redactor): TODOS los destinatarios, con nombre y última fecha.
  - `user_contacts` (Contactos → Mis contactos): los destinatarios EXTERNOS (fuera de los dominios de la
    casa) a los que se escribió al menos MIN_ENVIOS veces, con `source='enviados_historico'`.
    Los internos ya están en el Directorio.

Uso (desde /opt/maquita-webmail):
    scripts/contactos_desde_enviados.py --solo cuenta@dominio          # simula una cuenta
    scripts/contactos_desde_enviados.py                                # simula todas
    scripts/contactos_desde_enviados.py --aplicar [--solo cuenta]      # aplica y deja registro JSON
    scripts/contactos_desde_enviados.py --revertir /var/lib/maquita-webmail/contactos_enviados_<fecha>.json
Reversible: el registro guarda los ids creados en ambas tablas (lo ya existente no se toca ni se revierte).
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime


def decodificar_nombre(nombre: str) -> str:
    """Nombres codificados RFC 2047 («=?utf-8?Q?Mu=C3=B1oz?=») a texto legible (05/11/2026)."""
    if "=?" not in nombre:
        return nombre
    try:
        return str(make_header(decode_header(nombre)))
    except Exception:  # noqa: BLE001
        return nombre

import asyncpg

REGISTROS = "/var/lib/maquita-webmail"
FUENTE = "enviados_historico"
MIN_ENVIOS = 2
CARPETAS_ENVIADOS = ("Sent", "Enviados", "Sent Items", "INBOX.Sent")
RE_CORREO = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[a-z]{2,}$", re.I)


def _env(clave: str) -> str:
    for ruta in ("/etc/maquita-mail/organizacion.env", "/opt/maquita-webmail/backend/.env", "/opt/maquita-webmail/.env"):
        try:
            for linea in open(ruta, encoding="utf-8"):
                if linea.startswith(clave + "="):
                    return linea.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return ""


def dominios_casa() -> set[str]:
    # Dominios de la casa y portal del correo: organizacion.env, no el código (07/11/2026).
    base = {d.lower() for d in re.split(r"[,\s]+", _env("ORG_DOMINIOS_GRUPOS")) if d}
    portal = _env("ORG_URL_CORREO").split("//")[-1].split("/")[0].split(":")[0]
    if portal:
        base.add(portal.lower())
    for d in re.split(r"[,\s]+", _env("ORG_DOMINIOS_INSTITUCIONALES")):
        if d:
            base.add(d.lower())
    return base


def _dsn() -> str:
    return _env("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")


def carpeta_enviados(cuenta: str) -> str | None:
    salida = subprocess.run(["doveadm", "mailbox", "list", "-u", cuenta], capture_output=True, text=True, timeout=60).stdout
    carpetas = {l.strip() for l in salida.splitlines()}
    return next((c for c in CARPETAS_ENVIADOS if c in carpetas), None)


def destinatarios_de(cuenta: str, carpeta: str) -> dict:
    """{correo: {nombre: contador, 'n': envíos, 'ultimo': datetime}} a partir de To/Cc de Enviados."""
    proc = subprocess.run(
        ["doveadm", "fetch", "-u", cuenta, "hdr.to hdr.cc hdr.date", "mailbox", carpeta, "ALL"],
        capture_output=True, text=True, errors="replace", timeout=7200,
    )
    datos: dict = {}
    cabeceras = {"to": "", "cc": "", "date": ""}
    actual = None

    def cerrar():
        fecha = None
        try:
            fecha = parsedate_to_datetime(cabeceras["date"].strip()) if cabeceras["date"].strip() else None
            if fecha and fecha.tzinfo:
                fecha = fecha.astimezone().replace(tzinfo=None)
        except Exception:  # noqa: BLE001
            fecha = None
        for nombre, correo in getaddresses([cabeceras["to"], cabeceras["cc"]]):
            correo = correo.strip().lower()
            if not RE_CORREO.match(correo) or correo == cuenta.lower():
                continue
            d = datos.setdefault(correo, {"nombres": defaultdict(int), "n": 0, "ultimo": None})
            d["n"] += 1
            nombre = re.sub(r"\s+", " ", decodificar_nombre(nombre).strip().strip('"'))
            if nombre and nombre.lower() != correo:
                d["nombres"][nombre] += 1
            if fecha and (d["ultimo"] is None or fecha > d["ultimo"]):
                d["ultimo"] = fecha
        for k in cabeceras:
            cabeceras[k] = ""

    for linea in proc.stdout.splitlines():
        if linea.startswith("hdr.to: "):
            if actual is not None:
                cerrar()
            actual = "to"
            cabeceras["to"] = linea[8:]
        elif linea.startswith("hdr.cc: "):
            actual = "cc"
            cabeceras["cc"] = linea[8:]
        elif linea.startswith("hdr.date: "):
            actual = "date"
            cabeceras["date"] = linea[10:]
        elif linea.startswith(("\t", " ")) and actual:
            cabeceras[actual] += " " + linea.strip()
        elif linea == "" and actual == "date":
            cerrar()
            actual = None
    if actual is not None:
        cerrar()
    return datos


async def procesar_cuenta(db, cuenta: str, aplicar: bool, casa: set[str], registro: dict) -> tuple[int, int, int, int]:
    carpeta = carpeta_enviados(cuenta)
    if not carpeta:
        return (0, 0, 0, 0)
    datos = destinatarios_de(cuenta, carpeta)
    nuevos_sr = nuevos_uc = 0
    candidatos_uc = 0
    for correo, d in datos.items():
        nombre = max(d["nombres"].items(), key=lambda kv: kv[1])[0] if d["nombres"] else ""
        if aplicar:
            fila = await db.fetchrow(
                """INSERT INTO sent_recipients (sender, recipient_email, recipient_name, last_sent_at)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (sender, recipient_email) DO UPDATE SET
                     recipient_name = CASE WHEN coalesce(sent_recipients.recipient_name,'') = '' THEN EXCLUDED.recipient_name ELSE sent_recipients.recipient_name END,
                     last_sent_at = GREATEST(coalesce(sent_recipients.last_sent_at, EXCLUDED.last_sent_at), coalesce(EXCLUDED.last_sent_at, sent_recipients.last_sent_at))
                   RETURNING id, (xmax = 0) AS insertado""",
                cuenta, correo, nombre[:200] if nombre else None, d["ultimo"],
            )
            if fila["insertado"]:
                nuevos_sr += 1
                registro["sent_recipients"].append(fila["id"])
        else:
            if not await db.fetchval("SELECT 1 FROM sent_recipients WHERE sender=$1 AND recipient_email=$2", cuenta, correo):
                nuevos_sr += 1
        dominio = correo.rsplit("@", 1)[-1]
        if d["n"] < MIN_ENVIOS or dominio in casa:
            continue
        candidatos_uc += 1
        if await db.fetchval(
            "SELECT 1 FROM user_contacts WHERE lower(owner)=$1 AND lower(email)=$2 AND deleted_at IS NULL", cuenta, correo
        ):
            continue
        nuevos_uc += 1
        if aplicar:
            partes = nombre.split() if nombre else []
            nuevo = await db.fetchval(
                """INSERT INTO user_contacts (owner, display_name, first_name, last_name, email, source, last_contacted_at, usage_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id""",
                cuenta, (nombre or correo)[:200], (partes[0] if partes else "")[:100],
                (" ".join(partes[1:]) if len(partes) > 1 else "")[:100], correo, FUENTE, d["ultimo"], d["n"],
            )
            registro["user_contacts"].append(nuevo)
    return (len(datos), nuevos_sr, candidatos_uc, nuevos_uc)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--solo", action="append", help="cuenta(s) concreta(s)")
    ap.add_argument("--revertir", metavar="JSON")
    a = ap.parse_args()
    db = await asyncpg.connect(_dsn())
    try:
        if a.revertir:
            reg = json.load(open(a.revertir))
            n1 = await db.execute("DELETE FROM user_contacts WHERE id = ANY($1::int[]) AND source=$2", reg["user_contacts"], FUENTE)
            n2 = await db.execute("DELETE FROM sent_recipients WHERE id = ANY($1::int[])", reg["sent_recipients"])
            print("revertido:", n1, n2)
            return
        if a.solo:
            cuentas = [c.lower() for c in a.solo]
        else:
            cuentas = [r["u"] for r in await db.fetch("SELECT lower(username) AS u FROM mailbox WHERE active ORDER BY 1")]
        casa = dominios_casa()
        registro = {"fuente": FUENTE, "inicio": datetime.now().isoformat(), "user_contacts": [], "sent_recipients": []}
        tot = [0, 0, 0, 0]
        print(f"modo={'APLICAR' if a.aplicar else 'SIMULACION'} cuentas={len(cuentas)} min_envios={MIN_ENVIOS}", flush=True)
        for i, cuenta in enumerate(cuentas, 1):
            try:
                r = await procesar_cuenta(db, cuenta, a.aplicar, casa, registro)
            except Exception as e:  # noqa: BLE001
                print(f"{cuenta}\tERROR {e}", flush=True)
                continue
            for k in range(4):
                tot[k] += r[k]
            print(f"[{i}/{len(cuentas)}] {cuenta}\tdestinatarios={r[0]}\tautocompletar_nuevos={r[1]}\texternos_frecuentes={r[2]}\tcontactos_nuevos={r[3]}", flush=True)
        print(f"TOTAL destinatarios={tot[0]} autocompletar_nuevos={tot[1]} externos_frecuentes={tot[2]} contactos_nuevos={tot[3]}", flush=True)
        if a.aplicar:
            os.makedirs(REGISTROS, exist_ok=True)
            ruta = os.path.join(REGISTROS, f"contactos_enviados_{datetime.now():%Y%m%d-%H%M%S}.json")
            json.dump(registro, open(ruta, "w"))
            print("registro para revertir:", ruta, flush=True)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
