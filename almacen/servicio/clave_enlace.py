# -*- coding: utf-8 -*-
"""Clave opcional de los enlaces compartidos (F-08, tercera revisión).

Antes: la clave viajaba en el query (`?clave=`: historial, registros del proxy, referer) y se
guardaba como SHA-256 sin sal (atacable sin coste si se filtra la base). Ahora:

- La clave llega en la cabecera `X-Clave-Enlace` o en el cuerpo JSON (`clave`); NUNCA en la URL.
- Se guarda con Argon2id (sal por clave). Los hashes antiguos (SHA-256 hexadecimal) se siguen
  aceptando en tiempo constante y se migran a Argon2id en el primer acierto.
- Límite de intentos por enlace + IP (tabla `compartidos_intentos`): 10 fallos cada 10 minutos.
- Las respuestas públicas llevan `Referrer-Policy: no-referrer` y `Cache-Control: no-store`.
"""
import hashlib
import hmac
import time

from flask import request

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    _PH = PasswordHasher()  # Argon2id por defecto (time=3, memoria 64 MiB, paralelismo 4)
except ImportError:  # el módulo sigue cargando; hash_clave avisa al usarse
    _PH = None
    VerifyMismatchError = Exception

INTENTOS_MAX = 10
VENTANA_SEG = 600
CABECERA = "X-Clave-Enlace"
CABECERAS_PUBLICAS = {"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}


def hash_clave(clave: str) -> str:
    if _PH is None:
        raise RuntimeError("Falta argon2-cffi (almacen/requirements.txt)")
    return _PH.hash(clave)


def verificar_clave(guardado: str | None, clave: str) -> tuple[bool, bool]:
    """(coincide, hay_que_rehashear). Acepta Argon2id y el SHA-256 heredado."""
    if not guardado:
        return True, False
    if guardado.startswith("$argon2"):
        if _PH is None:
            return False, False
        try:
            _PH.verify(guardado, clave)
        except VerifyMismatchError:
            return False, False
        except Exception:
            return False, False
        return True, _PH.check_needs_rehash(guardado)
    # heredado: 64 hex de SHA-256 sin sal
    esperado = hashlib.sha256(clave.encode()).hexdigest()
    ok = hmac.compare_digest(esperado, guardado)
    return ok, ok


def leer_clave() -> str:
    """Clave de la petición actual: cabecera o cuerpo JSON. El query se ignora a propósito."""
    c = request.headers.get(CABECERA, "")
    if not c and request.is_json:
        c = (request.get_json(silent=True) or {}).get("clave", "") or ""
    return str(c)[:256]


def _ip() -> str:
    return (request.headers.get("X-Real-IP") or request.remote_addr or "?")[:64]


def asegurar_tabla_intentos(conexion):
    with conexion() as con, con.cursor() as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS compartidos_intentos (
                   token TEXT NOT NULL, ip TEXT NOT NULL, ventana BIGINT NOT NULL,
                   n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (token, ip, ventana))"""
        )


def intentos_agotados(conexion, token: str) -> bool:
    """True si esta IP ya falló demasiadas veces con este enlace en la ventana actual."""
    ventana = int(time.time() // VENTANA_SEG)
    with conexion() as con, con.cursor() as cur:
        cur.execute(
            "SELECT n FROM compartidos_intentos WHERE token = %s AND ip = %s AND ventana = %s",
            (token, _ip(), ventana),
        )
        fila = cur.fetchone()
        return bool(fila) and int(fila[0]) >= INTENTOS_MAX


def anotar_fallo(conexion, token: str) -> None:
    ventana = int(time.time() // VENTANA_SEG)
    with conexion() as con, con.cursor() as cur:
        cur.execute(
            """INSERT INTO compartidos_intentos (token, ip, ventana, n) VALUES (%s, %s, %s, 1)
               ON CONFLICT (token, ip, ventana) DO UPDATE SET n = compartidos_intentos.n + 1""",
            (token, _ip(), ventana),
        )
        cur.execute("DELETE FROM compartidos_intentos WHERE ventana < %s", (ventana - 2,))


def comprobar_clave(conexion, comp: dict, ejecutar) -> tuple[bool, int]:
    """Comprueba la clave del enlace `comp` (dict con token y clave_hash) contra la petición.
    Devuelve (ok, codigo_http): 200 si vale, 401 si no, 429 si la IP agotó los intentos."""
    if not comp.get("clave_hash"):
        return True, 200
    token = comp["token"]
    if intentos_agotados(conexion, token):
        return False, 429
    ok, rehash = verificar_clave(comp["clave_hash"], leer_clave())
    if not ok:
        anotar_fallo(conexion, token)
        return False, 401
    if rehash and _PH is not None:
        try:
            ejecutar("UPDATE compartidos SET clave_hash = %s WHERE token = %s", (hash_clave(leer_clave()), token))
        except Exception:
            pass
    return True, 200
