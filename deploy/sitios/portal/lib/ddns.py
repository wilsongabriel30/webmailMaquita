"""Fichas del DNS dinámico (v1.11): quién puede cambiar la IP de qué nombre, y con qué contraseña.

Cada ficha es un nombre dentro de la zona de un dominio asignado (casa.example.org) con su usuario y su
contraseña propios, distintos de los del portal: son los que se escriben en el router o en ddclient. La
contraseña es una ficha al azar de 144 bits que se muestra una sola vez; aquí se guarda solo su hash (SHA-256,
suficiente para un secreto al azar de ese tamaño) y se compara en tiempo constante.

Todo vive en un archivo de root (rutas.DDNS/fichas.json, 0600) que solo lee y escribe este intermediario, con
un cerrojo para que dos actualizaciones a la vez no se pisen.
"""

import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import time

import rutas
from errores import ErrorPortal

MAX_POR_ZONA = 20
VISIBLES = ("id", "zona", "nombre", "usuario", "creado", "ip4", "ip6", "actualizado")


def _archivo():
    return os.path.join(rutas.DDNS, "fichas.json")


@contextlib.contextmanager
def cerrojo():
    os.makedirs(rutas.DDNS, mode=0o700, exist_ok=True)
    fd = os.open(os.path.join(rutas.DDNS, ".cerrojo"), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def cargar():
    try:
        with open(_archivo()) as f:
            datos = json.load(f)
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        raise ErrorPortal(503, "No se pudieron leer las fichas del DNS dinámico")
    fichas = datos.get("fichas") if isinstance(datos, dict) else None
    return [f for f in fichas or [] if isinstance(f, dict)]


def guardar(fichas):
    os.makedirs(rutas.DDNS, mode=0o700, exist_ok=True)
    tmp = _archivo() + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600), "w") as f:
        json.dump({"fichas": fichas}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _archivo())


def hash_de(clave):
    return hashlib.sha256(clave.encode()).hexdigest()


def clave_correcta(ficha, clave):
    esperado = ficha.get("clave_hash") if ficha else None
    # Sin ficha se compara igual con un hash cualquiera: tarda lo mismo exista o no el usuario.
    return hmac.compare_digest(hash_de(clave), esperado or hash_de(secrets.token_hex(16))) and bool(esperado)


def visible(ficha):
    return {k: ficha.get(k) for k in VISIBLES}


def de_zona(fichas, zona):
    return [f for f in fichas if f.get("zona") == zona]


def nueva(fichas, zona, nombre):
    """Añade una ficha (sin guardar) y devuelve (ficha, contraseña en claro)."""
    if len(de_zona(fichas, zona)) >= MAX_POR_ZONA:
        raise ErrorPortal(409, f"Se admiten hasta {MAX_POR_ZONA} nombres de DNS dinámico por dominio")
    if any(f.get("zona") == zona and f.get("nombre") == nombre for f in fichas):
        raise ErrorPortal(409, f"{nombre}.{zona} ya tiene DNS dinámico")
    usados = {f.get("id") for f in fichas} | {f.get("usuario") for f in fichas}
    ident = secrets.token_hex(4)
    while ident in usados or f"ddns-{ident}" in usados:
        ident = secrets.token_hex(4)
    ficha = {"id": ident, "zona": zona, "nombre": nombre, "usuario": f"ddns-{ident}", "clave_hash": None,
             "creado": time.strftime("%Y-%m-%d %H:%M"), "ip4": None, "ip6": None, "actualizado": None, "peticiones": []}
    clave = renovar(ficha)
    fichas.append(ficha)
    return ficha, clave


def renovar(ficha):
    """Contraseña nueva (la anterior deja de valer): se devuelve en claro UNA vez y se guarda su hash."""
    clave = secrets.token_urlsafe(18)
    ficha["clave_hash"] = hash_de(clave)
    return clave


def buscar(fichas, zona, ident):
    for f in fichas:
        if f.get("zona") == zona and f.get("id") == ident:
            return f
    raise ErrorPortal(404, "No encontrado")


def por_usuario(fichas, usuario):
    return next((f for f in fichas if hmac.compare_digest(str(f.get("usuario") or ""), usuario)), None)
