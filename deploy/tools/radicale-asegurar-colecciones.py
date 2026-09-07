#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Asegura en Radicale las colecciones base de cada buzón: `default` (calendario con eventos y
tareas) y `contacts` (libreta). Idempotente.

El webmail las crea la primera vez que la persona abre Calendario o Contactos; Z-Push no las
crea, y un dispositivo que sincroniza ANTES de ese primer uso recibe 404 del CalDAV/CardDAV y
Z-Push devuelve 500 (visto el 07/09/2026 con la cuenta de prueba). Con esto, cualquier buzón
activo tiene sus colecciones desde el principio, entre por donde entre.

Uso:  radicale-asegurar-colecciones.py correo@dominio [...]   (buzones concretos)
      radicale-asegurar-colecciones.py --todos                (todos los buzones activos de maildb)
Radicale confía en la cabecera X-Remote-User (auth http_x_remote_user) y solo escucha en 127.0.0.1:
esta herramienta corre en el propio servidor y pone la cabecera con el correo completo.
"""
import os
import sys
import urllib.error
import urllib.request

RADICALE = os.getenv("RADICALE_URL", "http://127.0.0.1:5232").rstrip("/")

MKCALENDAR = """<?xml version="1.0" encoding="UTF-8"?>
<C:mkcalendar xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:set><D:prop>
    <D:displayname>Calendario</D:displayname>
    <C:supported-calendar-component-set><C:comp name="VEVENT"/><C:comp name="VTODO"/></C:supported-calendar-component-set>
  </D:prop></D:set>
</C:mkcalendar>"""
MKCOL_LIBRETA = """<?xml version="1.0" encoding="UTF-8"?>
<D:mkcol xmlns:D="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
  <D:set><D:prop>
    <D:resourcetype><D:collection/><CR:addressbook/></D:resourcetype>
    <D:displayname>Contactos</D:displayname>
  </D:prop></D:set>
</D:mkcol>"""


def _pedir(metodo, ruta, usuario, cuerpo=None):
    req = urllib.request.Request(f"{RADICALE}{ruta}", data=cuerpo.encode() if cuerpo else None, method=metodo)
    req.add_header("X-Remote-User", usuario.strip().lower())
    if cuerpo:
        req.add_header("Content-Type", "application/xml; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def asegurar(usuario):
    """Devuelve (calendario, libreta) con 'existía', 'creada' o 'error <código>'."""
    salida = []
    for ruta, metodo, cuerpo in ((f"/{usuario}/default/", "MKCALENDAR", MKCALENDAR),
                                 (f"/{usuario}/contacts/", "MKCOL", MKCOL_LIBRETA)):
        if _pedir("PROPFIND", ruta, usuario) in (207, 200):
            salida.append("existía")
            continue
        c = _pedir(metodo, ruta, usuario, cuerpo)
        salida.append("creada" if c in (201, 200) else f"error {c}")
    return tuple(salida)


def buzones_activos():
    import psycopg2

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        for l in open("/opt/maquita-webmail/backend/.env", encoding="utf-8"):
            if l.startswith("DATABASE_URL="):
                dsn = l.split("=", 1)[1].strip()
    with psycopg2.connect(dsn) as con, con.cursor() as cur:
        cur.execute("SELECT username FROM mailbox WHERE active ORDER BY 1")
        return [r[0] for r in cur.fetchall()]


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    usuarios = buzones_activos() if argv == ["--todos"] else argv
    fallos = 0
    for u in usuarios:
        cal, lib = asegurar(u)
        if "error" in cal or "error" in lib:
            fallos += 1
        print(f"{u}: calendario {cal}, contactos {lib}")
    print(f"buzones: {len(usuarios)}  con error: {fallos}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
