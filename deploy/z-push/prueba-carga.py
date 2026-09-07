#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueba de carga de Z-Push: N «dispositivos» sincronizando a la vez.

Cada dispositivo (DeviceId distinto) hace lo que hace un teléfono al añadir la cuenta:
  1. OPTIONS /Microsoft-Server-ActiveSync (versiones del protocolo)
  2. FolderSync con SyncKey 0 (WBXML real): Z-Push autentica contra Dovecot y lista carpetas de
     correo (IMAP), calendario y tareas (CalDAV) y contactos (CardDAV). Es la petición más cara.
Mide tiempos, códigos y errores. No crea ni modifica nada en el buzón.

Uso: prueba-carga.py --usuario correo@dominio --clave '...' [--host mail.dominio] [--dispositivos 50]
     (o CLAVE en el entorno, para no dejarla en el historial)
Salida: resumen (p50/p95/max, códigos) y código de salida 1 si algún dispositivo falló.
"""
import argparse
import base64
import concurrent.futures
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

# FolderSync {SyncKey: "0"} en WBXML (código de página 7, FolderHierarchy): es el arranque estándar.
FOLDERSYNC_WBXML = bytes([0x03, 0x01, 0x6A, 0x00, 0x00, 0x07, 0x56, 0x52, 0x03, 0x30, 0x00, 0x01, 0x01])
UA = "MaquitaPruebaCarga/1.0"


def peticion(url, metodo, auth, cuerpo=None, tiempo=120):
    req = urllib.request.Request(url, data=cuerpo, method=metodo)
    req.add_header("Authorization", "Basic " + auth)
    req.add_header("User-Agent", UA)
    if cuerpo is not None:
        req.add_header("Content-Type", "application/vnd.ms-sync.wbxml")
        req.add_header("MS-ASProtocolVersion", "14.1")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=tiempo) as r:
            return r.status, time.time() - t0, dict(r.headers), r.read()[:64]
    except urllib.error.HTTPError as e:
        return e.code, time.time() - t0, dict(e.headers), b""
    except Exception as e:
        return None, time.time() - t0, {"error": str(e)[:80]}, b""


def dispositivo(i, host, usuario, auth):
    did = f"MAQPRUEBA{i:04d}"
    base = f"https://{host}/Microsoft-Server-ActiveSync"
    q = f"?Cmd=FolderSync&User={urllib.request.quote(usuario)}&DeviceId={did}&DeviceType=SmartPhone"
    c1, t1, h1, _ = peticion(base, "OPTIONS", auth)
    c2, t2, h2, cuerpo = peticion(base + q, "POST", auth, FOLDERSYNC_WBXML)
    ok = c1 == 200 and c2 == 200 and cuerpo[:1] == b"\x03"  # respuesta WBXML
    return {"disp": did, "options": c1, "foldersync": c2, "t_options": t1, "t_foldersync": t2, "ok": ok,
            "versiones": h1.get("MS-ASProtocolVersions", h1.get("error", "")), "detalle": h2.get("error", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--clave", default=os.getenv("CLAVE", ""))
    ap.add_argument("--host", default="mail.maquita.org")
    ap.add_argument("--dispositivos", type=int, default=50)
    a = ap.parse_args()
    if not a.clave:
        sys.exit("falta --clave o CLAVE en el entorno")
    auth = base64.b64encode(f"{a.usuario}:{a.clave}".encode()).decode()
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.dispositivos) as ex:
        res = list(ex.map(lambda i: dispositivo(i, a.host, a.usuario, auth), range(a.dispositivos)))
    total = time.time() - t0
    tf = sorted(r["t_foldersync"] for r in res)
    fallos = [r for r in res if not r["ok"]]
    print(f"dispositivos: {a.dispositivos}  tiempo total: {total:.1f}s  fallos: {len(fallos)}")
    print(f"FolderSync p50 {statistics.median(tf):.2f}s  p95 {tf[int(len(tf) * 0.95) - 1]:.2f}s  max {tf[-1]:.2f}s")
    print("versiones ActiveSync:", res[0]["versiones"])
    codigos = {}
    for r in res:
        codigos[(r["options"], r["foldersync"])] = codigos.get((r["options"], r["foldersync"]), 0) + 1
    print("códigos (OPTIONS, FolderSync):", codigos)
    for r in fallos[:5]:
        print("  fallo:", r)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
