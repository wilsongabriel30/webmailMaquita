#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueba de carga del webmail: inicio de sesión + bandeja + búsqueda.

Simula usuarios que abren la bandeja y buscan, como lo hace la interfaz:
  1. POST /api/auth/login (una vez por cuenta; se mide aparte)
  2. GET  /api/mail/messages/INBOX?page=1&per_page=50          («bandeja»)
  3. GET  /api/mail/messages/INBOX?search=<término>             («búsqueda» en cabeceras)
  4. POST /api/auth/logout al terminar (no deja sesiones abiertas)
No crea, mueve ni borra correo. Solo usa la biblioteca estándar de Python.

Uso:
  prueba-carga-webmail.py --url https://mail.example.org --cuentas cuentas.txt \\
      [--concurrencia 20] [--duracion 60] [--busqueda factura] [--mezcla 80]
  cuentas.txt: una cuenta por línea, «usuario@dominio:clave» (sin segundo factor).
  Con una sola cuenta: --usuario prueba@example.org y CLAVE en el entorno.

Límites del propio webmail que hay que tener en cuenta (no son fallos del servidor):
- 300 lecturas/min por usuario (RATE_LIMIT_READ_PER_MIN) → reparte la carga entre
  varias cuentas o sube el límite en el entorno de pruebas. Los 429 se cuentan aparte.
- 20 intentos de inicio de sesión cada 5 min por IP → pocas cuentas por máquina de carga.

Salida: p50/p95/p99/máx por operación, peticiones/s, códigos y comparación con los
objetivos de docs/GRAN-ESCALA.md. Código de salida 1 si no se cumplen o hay errores.
"""
import argparse
import concurrent.futures
import http.cookiejar
import json
import math
import os
import random
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "MaquitaPruebaCarga/1.0"

# Objetivos (milisegundos) con el servidor de referencia de docs/GRAN-ESCALA.md.
OBJETIVOS = {
    "login": {"p50": 600, "p95": 1500},
    "bandeja": {"p50": 300, "p95": 800},
    "busqueda": {"p50": 800, "p95": 2500},
}
MAX_ERRORES = 0.01  # 1 % de respuestas 5xx o sin respuesta


class Sesion:
    """Una cuenta con su tarro de cookies (la sesión del webmail va en cookies)."""

    def __init__(self, base, usuario, clave, contexto):
        self.base, self.usuario, self.clave = base.rstrip("/"), usuario, clave
        self.tarro = http.cookiejar.CookieJar()
        self.abridor = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.tarro),
            urllib.request.HTTPSHandler(context=contexto),
        )

    def peticion(self, metodo, ruta, cuerpo=None, tiempo=60):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(self.base + ruta, data=datos, method=metodo)
        req.add_header("User-Agent", UA)
        req.add_header("Accept", "application/json")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        if datos is not None:
            req.add_header("Content-Type", "application/json")
        t0 = time.perf_counter()
        try:
            with self.abridor.open(req, timeout=tiempo) as r:
                r.read()
                return r.status, (time.perf_counter() - t0) * 1000
        except urllib.error.HTTPError as e:
            return e.code, (time.perf_counter() - t0) * 1000
        except Exception:
            return None, (time.perf_counter() - t0) * 1000

    def entrar(self):
        return self.peticion(
            "POST", "/api/auth/login", {"username": self.usuario, "password": self.clave}
        )

    def salir(self):
        self.peticion("POST", "/api/auth/logout", {})


class Medidas:
    def __init__(self):
        self.lock = threading.Lock()
        self.tiempos: dict[str, list[float]] = {}
        self.codigos: dict[str, dict] = {}

    def anotar(self, op, codigo, ms):
        with self.lock:
            self.codigos.setdefault(op, {})
            clave = str(codigo) if codigo is not None else "sin-respuesta"
            self.codigos[op][clave] = self.codigos[op].get(clave, 0) + 1
            if codigo is not None and 200 <= codigo < 300:
                self.tiempos.setdefault(op, []).append(ms)


def percentil(valores, p):
    if not valores:
        return None
    v = sorted(valores)  # rango más cercano: el menor valor que deja el p % por debajo
    k = max(0, min(len(v) - 1, math.ceil(p / 100 * len(v)) - 1))
    return v[k]


def leer_cuentas(args):
    cuentas = []
    if args.cuentas:
        with open(args.cuentas, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and ":" in linea:
                    u, c = linea.split(":", 1)
                    cuentas.append((u.strip(), c))
    elif args.usuario:
        clave = os.environ.get("CLAVE") or args.clave
        if not clave:
            sys.exit("Falta la clave: CLAVE en el entorno o --clave")
        cuentas.append((args.usuario, clave))
    if not cuentas:
        sys.exit("Indica --cuentas archivo o --usuario")
    return cuentas


def trabajador(sesiones, medidas, fin, args):
    carpeta = urllib.parse.quote(args.carpeta, safe="")
    bandeja = f"/api/mail/messages/{carpeta}?page=1&per_page=50"
    busqueda = f"/api/mail/messages/{carpeta}?page=1&per_page=50&search=" + urllib.parse.quote(
        args.busqueda
    )
    n = 0
    while time.monotonic() < fin and (not args.peticiones or n < args.peticiones):
        s = random.choice(sesiones)
        if random.randint(1, 100) <= args.mezcla:
            op, ruta = "bandeja", bandeja
        else:
            op, ruta = "busqueda", busqueda
        codigo, ms = s.peticion("GET", ruta)
        medidas.anotar(op, codigo, ms)
        n += 1
        if args.pausa:
            time.sleep(args.pausa)


def resumen(medidas, segundos, verificar):
    ok_total = True
    print(f"\n{'operación':<10} {'n':>7} {'p50':>8} {'p95':>8} {'p99':>8} {'máx':>8}  códigos")
    for op in ("login", "bandeja", "busqueda"):
        t = medidas.tiempos.get(op, [])
        cod = medidas.codigos.get(op, {})
        total = sum(cod.values())
        if not total:
            continue
        p50, p95, p99 = percentil(t, 50), percentil(t, 95), percentil(t, 99)
        fmt = lambda x: f"{x:8.0f}" if x is not None else "       -"  # noqa: E731
        print(
            f"{op:<10} {total:>7} {fmt(p50)} {fmt(p95)} {fmt(p99)} {fmt(max(t) if t else None)}"
            f"  {json.dumps(cod, sort_keys=True)}"
        )
        errores = sum(v for k, v in cod.items() if k == "sin-respuesta" or k.startswith("5"))
        if total and errores / total > MAX_ERRORES:
            print(f"  ✗ {op}: {errores} errores de {total} (más del {MAX_ERRORES:.0%})")
            ok_total = False
        if cod.get("429"):
            print(f"  ! {op}: {cod['429']} respuestas 429 (límite de tasa por usuario, ver --help)")
        obj = OBJETIVOS.get(op, {})
        if verificar and t:
            for nombre, valor in (("p50", p50), ("p95", p95)):
                if nombre in obj and valor > obj[nombre]:
                    print(f"  ✗ {op}: {nombre} {valor:.0f} ms > objetivo {obj[nombre]} ms")
                    ok_total = False
    lecturas = sum(len(medidas.tiempos.get(op, [])) for op in ("bandeja", "busqueda"))
    print(f"\nduración {segundos:.1f} s · {lecturas / max(segundos, 0.001):.1f} lecturas correctas/s")
    return ok_total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="https://mail.example.org (sin barra final)")
    ap.add_argument("--cuentas", help="archivo con «usuario:clave» por línea")
    ap.add_argument("--usuario")
    ap.add_argument("--clave", help="mejor en la variable CLAVE (no queda en el historial)")
    ap.add_argument("--concurrencia", type=int, default=20)
    ap.add_argument("--duracion", type=float, default=60, help="segundos")
    ap.add_argument("--peticiones", type=int, default=0, help="por hilo; 0 = sin límite")
    ap.add_argument("--carpeta", default="INBOX")
    ap.add_argument("--busqueda", default="factura")
    ap.add_argument("--mezcla", type=int, default=80, help="%% de bandeja (el resto, búsqueda)")
    ap.add_argument("--pausa", type=float, default=0.0, help="segundos entre peticiones de un hilo")
    ap.add_argument("--inseguro", action="store_true", help="no verificar el certificado (laboratorio)")
    ap.add_argument("--sin-objetivos", action="store_true", help="solo medir, no comparar")
    args = ap.parse_args()

    contexto = ssl.create_default_context()
    if args.inseguro:
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE

    medidas = Medidas()
    sesiones = []
    for usuario, clave in leer_cuentas(args):
        s = Sesion(args.url, usuario, clave, contexto)
        codigo, ms = s.entrar()
        medidas.anotar("login", codigo, ms)
        if codigo == 200:
            sesiones.append(s)
        else:
            print(f"No se pudo entrar con {usuario}: {codigo}")
    if not sesiones:
        print("Ninguna cuenta pudo iniciar sesión.")
        resumen(medidas, 0, False)
        return 1

    print(
        f"{len(sesiones)} sesiones · {args.concurrencia} hilos · {args.duracion:.0f} s · "
        f"{args.mezcla}% bandeja / {100 - args.mezcla}% búsqueda"
    )
    inicio = time.monotonic()
    fin = inicio + args.duracion
    try:
        with concurrent.futures.ThreadPoolExecutor(args.concurrencia) as ex:
            for f in [ex.submit(trabajador, sesiones, medidas, fin, args) for _ in range(args.concurrencia)]:
                f.result()
    finally:
        segundos = time.monotonic() - inicio
        for s in sesiones:
            s.salir()
    return 0 if resumen(medidas, segundos, not args.sin_objetivos) else 1


if __name__ == "__main__":
    sys.exit(main())
