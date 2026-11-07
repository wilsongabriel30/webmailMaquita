#!/opt/maquita-webmail/backend/venv/bin/python
"""Etiquetas de Zimbra → etiquetas del webmail (05/11/2026).

Las etiquetas (tags) de Zimbra llegaron con la migración como keywords IMAP (p. ej. «EQUEJOVEN:FLAG55651»,
«PROCESOS») que Dovecot conserva pero el webmail no muestra: este solo enseña sus etiquetas de base de datos
(`user_labels` + `message_labels`). Este script crea, por cuenta, la etiqueta que falte y la asigna a los
mismos correos que llevan el keyword, para que cada persona vea su correo organizado como lo tenía.

Uso (como root, en /opt/maquita-webmail):
    scripts/etiquetas_zimbra_a_webmail.py                 # simula: no escribe nada
    scripts/etiquetas_zimbra_a_webmail.py --aplicar       # crea etiquetas y asignaciones
    scripts/etiquetas_zimbra_a_webmail.py --aplicar --solo usuario@dominio
    scripts/etiquetas_zimbra_a_webmail.py --aplicar --saltar a@x --saltar b@y
    scripts/etiquetas_zimbra_a_webmail.py --revertir /var/lib/maquita-webmail/etiquetas_zimbra_<fecha>.json

Cada `--aplicar` deja un registro JSON con los ids creados; `--revertir` borra exactamente eso y nada más.
Reglas: los keywords de sistema ($Forwarded, Junk, $MailFlagBit…) se ignoran; el sufijo «:FLAGnnn» de Zimbra se
quita; no se duplica una etiqueta ya existente con el mismo nombre (sin distinguir mayúsculas): se reutiliza;
una asignación ya presente no se repite; un keyword sin correos no crea etiqueta.
"""
import argparse
import asyncio
import datetime as dt
import json
import os
import re
import subprocess
import sys

import asyncpg

RAIZ_VMAIL = "/var/vmail"
DIR_REGISTROS = "/var/lib/maquita-webmail"
PALETA = ["#8764b8", "#0078d4", "#107c10", "#d83b01", "#038387", "#ca5010", "#d13438", "#5c2e91", "#004e8c", "#498205"]
IGNORADOS = {
    "forwarded", "nonjunk", "junk", "junkrecorded", "redirected", "notjunk", "phishing", "notphishing",
    "seen", "answered", "flagged", "deleted", "draft", "recent",
}
SUFIJO_ZIMBRA = re.compile(r":FLAG\d+$")


def dsn() -> str:
    for ruta in ("backend/.env", ".env"):
        try:
            for linea in open(ruta, encoding="utf-8"):
                if linea.startswith("DATABASE_URL="):
                    return linea.split("=", 1)[1].strip()
        except OSError:
            pass
    sys.exit("No encuentro DATABASE_URL en backend/.env")


def keywords_de_maildir(maildir: str) -> set:
    """Keywords no estándar declarados en los ficheros dovecot-keywords del buzón (raíz y subcarpetas)."""
    encontrados = set()
    if not os.path.isdir(maildir):
        return encontrados
    candidatos = [os.path.join(maildir, "dovecot-keywords")]
    for nombre in os.listdir(maildir):
        if nombre.startswith("."):
            candidatos.append(os.path.join(maildir, nombre, "dovecot-keywords"))
    for ruta in candidatos:
        try:
            for linea in open(ruta, encoding="utf-8", errors="replace"):
                partes = linea.strip().split(" ", 1)
                if len(partes) != 2:
                    continue
                kw = partes[1].strip()
                if not kw or kw.startswith("$") or kw.lower() in IGNORADOS:
                    continue
                encontrados.add(kw)
        except OSError:
            continue
    return encontrados


def nombre_etiqueta(keyword: str) -> str:
    return SUFIJO_ZIMBRA.sub("", keyword).strip()[:100]


def correos_con_keyword(usuario: str, keyword: str) -> list:
    """[(carpeta, uid)] de los correos que llevan el keyword, vía índice de Dovecot (barato en IO)."""
    salida = subprocess.run(
        ["doveadm", "fetch", "-u", usuario, "mailbox uid", "KEYWORD", keyword],
        capture_output=True, text=True, timeout=300,
    ).stdout
    pares, carpeta = [], None
    for linea in salida.splitlines():
        if linea.startswith("mailbox: "):
            carpeta = linea[9:].strip()
        elif linea.startswith("uid: ") and carpeta:
            pares.append((carpeta, int(linea[5:])))
    return pares


async def procesar_cuenta(db, usuario: str, maildir: str, aplicar: bool, registro: dict) -> dict:
    resumen = {"usuario": usuario, "etiquetas_nuevas": [], "etiquetas_reutilizadas": [], "asignaciones": 0}
    keywords = keywords_de_maildir(maildir)
    if not keywords:
        return resumen
    existentes = {r["name"].lower(): (r["id"], r["name"]) for r in await db.fetch(
        "SELECT id, name FROM user_labels WHERE owner = $1", usuario)}
    ya_asignado = {(r["folder"], r["message_uid"], r["label_id"]) for r in await db.fetch(
        "SELECT folder, message_uid, label_id FROM message_labels WHERE owner = $1", usuario)}
    # Varios keywords pueden dar el mismo nombre (mayúsculas, sufijo :FLAG): se agrupan.
    por_nombre: dict = {}
    for kw in sorted(keywords):
        por_nombre.setdefault(nombre_etiqueta(kw).lower(), []).append(kw)
    color_i = len(existentes)
    for clave, kws in por_nombre.items():
        if not clave:
            continue
        correos = []
        for kw in kws:
            correos.extend(correos_con_keyword(usuario, kw))
        correos = sorted(set(correos))
        if not correos:
            continue
        if clave in existentes:
            label_id, nombre = existentes[clave]
            resumen["etiquetas_reutilizadas"].append(f"{nombre} ({len(correos)})")
        else:
            nombre = nombre_etiqueta(kws[0])
            color = PALETA[color_i % len(PALETA)]
            color_i += 1
            label_id = None
            if aplicar:
                label_id = await db.fetchval(
                    "INSERT INTO user_labels (owner, name, color) VALUES ($1, $2, $3) RETURNING id",
                    usuario, nombre, color)
                registro["etiquetas"].append(label_id)
            existentes[clave] = (label_id, nombre)
            resumen["etiquetas_nuevas"].append(f"{nombre} ({len(correos)})")
        nuevas = [(c, u) for c, u in correos if (c, u, label_id) not in ya_asignado]
        if aplicar and nuevas:
            filas = await db.fetch(
                """INSERT INTO message_labels (owner, folder, message_uid, label_id)
                   SELECT $1, x.folder, x.uid, $2 FROM unnest($3::text[], $4::int[]) AS x(folder, uid)
                   RETURNING id""",
                usuario, label_id, [c for c, _ in nuevas], [u for _, u in nuevas])
            registro["asignaciones"].extend(r["id"] for r in filas)
        resumen["asignaciones"] += len(nuevas)
    return resumen


async def revertir(db, ruta: str):
    reg = json.load(open(ruta, encoding="utf-8"))
    n1 = await db.execute("DELETE FROM message_labels WHERE id = ANY($1::int[])", reg["asignaciones"])
    n2 = await db.execute("DELETE FROM user_labels WHERE id = ANY($1::int[])", reg["etiquetas"])
    print(f"Revertido {ruta}: {n1} asignaciones, {n2} etiquetas")


async def principal(args):
    db = await asyncpg.connect(dsn())
    try:
        if args.revertir:
            await revertir(db, args.revertir)
            return
        cuentas = await db.fetch("SELECT username, maildir FROM mailbox WHERE active ORDER BY username")
        registro = {"fecha": dt.datetime.now().isoformat(timespec="seconds"), "etiquetas": [], "asignaciones": []}
        total_et, total_as, con_cambios = 0, 0, 0
        for c in cuentas:
            usuario = c["username"]
            if args.solo and usuario not in args.solo:
                continue
            if usuario in (args.saltar or []):
                continue
            maildir = os.path.join(RAIZ_VMAIL, c["maildir"], "Maildir")
            r = await procesar_cuenta(db, usuario, maildir, args.aplicar, registro)
            if r["etiquetas_nuevas"] or r["asignaciones"]:
                con_cambios += 1
                total_et += len(r["etiquetas_nuevas"])
                total_as += r["asignaciones"]
                print(f"{usuario}: nuevas={r['etiquetas_nuevas']} reutilizadas={r['etiquetas_reutilizadas']} "
                      f"asignaciones={r['asignaciones']}")
        modo = "APLICADO" if args.aplicar else "SIMULACIÓN"
        print(f"\n{modo}: {con_cambios} cuentas, {total_et} etiquetas nuevas, {total_as} asignaciones")
        if args.aplicar:
            os.makedirs(DIR_REGISTROS, exist_ok=True)
            ruta = os.path.join(DIR_REGISTROS, "etiquetas_zimbra_" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
            json.dump(registro, open(ruta, "w", encoding="utf-8"))
            print(f"Registro para revertir: {ruta}")
    finally:
        await db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Convierte los keywords IMAP de Zimbra en etiquetas del webmail")
    p.add_argument("--aplicar", action="store_true", help="escribe en la base de datos (por defecto solo simula)")
    p.add_argument("--solo", action="append", help="procesar solo esta cuenta (repetible)")
    p.add_argument("--saltar", action="append", help="no procesar esta cuenta (repetible)")
    p.add_argument("--revertir", metavar="JSON", help="borra lo creado por una ejecución anterior")
    asyncio.run(principal(p.parse_args()))
