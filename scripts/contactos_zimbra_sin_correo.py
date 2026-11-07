#!/opt/maquita-webmail/backend/venv/bin/python
"""Contactos manuales de Zimbra que el importador del 20/10 omitió por no tener correo (05/11/2026).

El importador `/root/importar_pim.py` cargó los 340 contactos con correo y dejó fuera 81 tarjetas de
«Contacts» (nombre y teléfono, sin correo). Este script las importa desde la exportación final del
4/11 (`/root/pim-import-todos-20261104/pim-export-20261104/<cuenta>/contactos--Contacts.vcf`) a
`user_contacts` con `source='zimbra_sin_correo'`.

Uso (desde /opt/maquita-webmail):
    scripts/contactos_zimbra_sin_correo.py                 # simula
    scripts/contactos_zimbra_sin_correo.py --aplicar       # crea y deja registro JSON
    scripts/contactos_zimbra_sin_correo.py --revertir /var/lib/maquita-webmail/contactos_sin_correo_<fecha>.json

No duplica: se omite si el propietario ya tiene un contacto con el mismo nombre (sin distinguir
mayúsculas) o, si la tarjeta trae teléfono, con el mismo teléfono.
"""
import argparse
import asyncio
import glob
import json
import os
import re
import sys
from datetime import datetime

import asyncpg

EXPORT = "/root/pim-import-todos-20261104/pim-export-20261104"
REGISTROS = "/var/lib/maquita-webmail"
FUENTE = "zimbra_sin_correo"


def _dsn():
    for linea in open("/opt/maquita-webmail/backend/.env", encoding="utf-8"):
        if linea.startswith("DATABASE_URL="):
            return linea.split("=", 1)[1].strip().replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("DATABASE_URL no encontrada")


def leer_vcards(texto: str) -> list[dict]:
    tarjetas, actual = [], None
    for cruda in texto.replace("\r\n", "\n").replace("\n ", "").split("\n"):
        u = cruda.strip()
        if u.upper() == "BEGIN:VCARD":
            actual = {}
        elif u.upper() == "END:VCARD":
            if actual is not None:
                tarjetas.append(actual)
            actual = None
        elif actual is not None and ":" in u:
            clave, valor = u.split(":", 1)
            nombre = clave.split(";")[0].upper()
            valor = valor.strip()
            if not valor:
                continue
            if nombre == "EMAIL":
                actual.setdefault("email", valor.lower())
            elif nombre == "FN":
                actual["display_name"] = valor
            elif nombre == "N":
                partes = valor.split(";")
                actual["last_name"] = partes[0].strip() if partes else ""
                actual["first_name"] = partes[1].strip() if len(partes) > 1 else ""
            elif nombre == "TEL":
                tipo = clave.upper()
                destino = "phone_mobile" if "CELL" in tipo else ("phone_work" if "WORK" in tipo else "phone")
                actual.setdefault(destino, valor)
            elif nombre == "ORG":
                actual["organization"] = valor.replace(";", " ").strip()
            elif nombre == "TITLE":
                actual["job_title"] = valor
            elif nombre == "NOTE":
                actual["notes"] = valor.replace("\\n", "\n")
            elif nombre == "ADR":
                p = (valor.split(";") + [""] * 7)[:7]
                actual["address_street"], actual["address_city"] = p[2], p[3]
                actual["address_state"], actual["address_zip"], actual["address_country"] = p[4], p[5], p[6]
            elif nombre == "URL":
                actual["website"] = valor
    return tarjetas


def _tel_norm(t: str) -> str:
    return re.sub(r"\D", "", t or "")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--revertir", metavar="JSON")
    ap.add_argument("--solo", help="una sola cuenta")
    a = ap.parse_args()
    db = await asyncpg.connect(_dsn())
    try:
        if a.revertir:
            ids = json.load(open(a.revertir))["ids"]
            n = await db.execute("DELETE FROM user_contacts WHERE id = ANY($1::int[]) AND source = $2", ids, FUENTE)
            print("revertido:", n, "ids:", len(ids))
            return
        creados, resumen = [], {}
        for ruta in sorted(glob.glob(os.path.join(EXPORT, "*", "contactos--Contacts.vcf"))):
            cuenta = os.path.basename(os.path.dirname(ruta)).lower()
            if a.solo and cuenta != a.solo.lower():
                continue
            activo = await db.fetchval("SELECT 1 FROM mailbox WHERE lower(username)=$1 AND active", cuenta)
            if not activo:
                continue
            for t in leer_vcards(open(ruta, encoding="utf-8", errors="replace").read()):
                if t.get("email"):
                    continue  # esos ya los importó importar_pim.py
                nombre = (t.get("display_name") or " ".join(x for x in (t.get("first_name"), t.get("last_name")) if x)).strip()
                tel = t.get("phone_mobile") or t.get("phone") or t.get("phone_work") or ""
                if not nombre and not tel:
                    continue
                if not nombre:
                    nombre = tel
                existe = await db.fetchval(
                    """SELECT 1 FROM user_contacts WHERE lower(owner)=$1 AND deleted_at IS NULL
                       AND (lower(display_name)=lower($2) OR ($3 <> '' AND regexp_replace(coalesce(phone,'')||coalesce(phone_mobile,''),'\\D','','g') LIKE '%'||$3||'%'))""",
                    cuenta, nombre, _tel_norm(tel))
                if existe:
                    resumen.setdefault(cuenta, [0, 0])[1] += 1
                    continue
                resumen.setdefault(cuenta, [0, 0])[0] += 1
                if a.aplicar:
                    cols = ["display_name", "first_name", "last_name", "phone", "phone_mobile", "phone_work", "organization",
                            "job_title", "notes", "address_street", "address_city", "address_state", "address_zip",
                            "address_country", "website"]
                    vals = [nombre] + [t.get(c, "") or "" for c in cols[1:]]
                    nuevo = await db.fetchval(
                        f"INSERT INTO user_contacts (owner, {', '.join(cols)}, email, source) VALUES "
                        f"($1, {', '.join(f'${i}' for i in range(2, len(cols) + 2))}, '', $%d) RETURNING id" % (len(cols) + 2),
                        cuenta, *vals, FUENTE)
                    creados.append(nuevo)
        total = sum(v[0] for v in resumen.values())
        for c, (n, d) in sorted(resumen.items()):
            print(f"{c}\t{'crear' if not a.aplicar else 'creados'}={n}\tya_existian={d}")
        print(f"TOTAL cuentas={len(resumen)} contactos={total} modo={'APLICAR' if a.aplicar else 'SIMULACION'}")
        if a.aplicar and creados:
            os.makedirs(REGISTROS, exist_ok=True)
            reg = os.path.join(REGISTROS, f"contactos_sin_correo_{datetime.now():%Y%m%d-%H%M%S}.json")
            json.dump({"fuente": FUENTE, "ids": creados}, open(reg, "w"))
            print("registro para revertir:", reg)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
