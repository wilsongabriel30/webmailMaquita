"""Claves SSH de las cuentas SFTP de un sitio (la principal y las adicionales de ftp_cuentas.py).

sshd lee las claves de CARPETA/<usuario> (AuthorizedKeysFile del bloque «Match Group sitios», que pone el ajuste
71): archivos de root, fuera del encierro, que la cuenta no puede cambiar. Cada línea lleva «restrict» (sin
reenvíos, sin terminal) y la cuenta sigue encerrada en su carpeta con internal-sftp, como con contraseña.

Solo se aceptan claves ed25519, ECDSA y RSA de 3072 bits o más, comprobadas con «ssh-keygen -l». La clave pública
se guarda en el meta (meta["claves_ssh"]) para rehacer los archivos; el archivo de una cuenta solo existe mientras
la cuenta puede entrar: la principal, con el acceso FTP/SFTP activado; una adicional, mientras exista.
"""

import base64
import os
import re
import secrets
import struct
import subprocess
import tempfile
import time

from comun import ErrorSitio, guardar_meta, leer_meta

CARPETA = "/etc/ssh/claves-sitios"
SSH_KEYGEN = "/usr/bin/ssh-keygen"
MAXIMO = 10  # por cuenta
TIPOS = {"ssh-ed25519": "ED25519", "ecdsa-sha2-nistp256": "ECDSA", "ecdsa-sha2-nistp384": "ECDSA",
         "ecdsa-sha2-nistp521": "ECDSA", "ssh-rsa": "RSA"}
RSA_MINIMO = 3072
RE_DATOS = re.compile(r"[A-Za-z0-9+/]{40,16000}={0,3}")
RE_COMENTARIO = re.compile(r"[A-Za-z0-9@._+ -]{1,100}")
RE_ID = re.compile(r"[0-9a-f]{8}")
RE_HUELLA = re.compile(r"^(\d{3,5}) (SHA256:[A-Za-z0-9+/]{43}) .*\(([A-Z0-9-]{2,12})\)$")


# --- Validación de una clave pública ---


def _tipo_interno(datos):
    """El tipo que lleva dentro la clave (los 4 primeros bytes son su longitud): debe coincidir con el declarado."""
    try:
        crudo = base64.b64decode(datos, validate=True)
        (largo,) = struct.unpack(">I", crudo[:4])
        return crudo[4:4 + largo].decode("ascii") if 0 < largo <= 40 else None
    except (ValueError, struct.error, UnicodeDecodeError):
        return None


def _huella(linea):
    """(bits, huella SHA256, tipo según ssh-keygen) o ErrorSitio."""
    with tempfile.NamedTemporaryFile("w", suffix=".pub", delete=False) as f:
        f.write(linea + "\n")
        temporal = f.name
    try:
        r = subprocess.run([SSH_KEYGEN, "-l", "-E", "sha256", "-f", temporal], capture_output=True, text=True,
                           timeout=20, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    finally:
        os.remove(temporal)
    m = RE_HUELLA.match((r.stdout or "").strip())
    if r.returncode != 0 or not m:
        raise ErrorSitio("ssh-keygen no reconoce la clave: pega la clave PÚBLICA completa (el contenido del .pub)")
    return int(m.group(1)), m.group(2), m.group(3)


def validar(texto):
    """{"tipo", "datos", "comentario", "bits", "huella"} de una clave pública aceptable, o ErrorSitio."""
    if not isinstance(texto, str) or len(texto) > 17000:
        raise ErrorSitio("clave no válida")
    texto = texto.strip()
    if not texto or re.search(r"[\x00-\x1f\x7f]", texto):
        raise ErrorSitio("pega UNA sola clave pública, en una línea")
    partes = texto.split(None, 2)
    if len(partes) < 2 or partes[0] not in TIPOS:
        raise ErrorSitio("tipo de clave no admitido: usa ed25519 (recomendada), ECDSA o RSA de 3072 bits o más "
                         "(sin opciones delante de la clave)")
    tipo, datos = partes[0], partes[1]
    if not RE_DATOS.fullmatch(datos) or _tipo_interno(datos) != tipo:
        raise ErrorSitio("la clave está incompleta o no corresponde a su tipo")
    comentario = partes[2].strip() if len(partes) == 3 else ""
    comentario = comentario if RE_COMENTARIO.fullmatch(comentario or "-") else ""
    bits, huella, tipo_keygen = _huella(f"{tipo} {datos}")
    if tipo_keygen != TIPOS[tipo]:
        raise ErrorSitio("la clave no corresponde a su tipo")
    if tipo == "ssh-rsa" and bits < RSA_MINIMO:
        raise ErrorSitio(f"clave RSA de {bits} bits: demasiado débil. Usa ed25519 o RSA de {RSA_MINIMO} bits o más")
    return {"tipo": tipo, "datos": datos, "comentario": comentario, "bits": bits, "huella": huella}


# --- Cuentas del sitio ---


def cuentas(meta):
    """{cuenta: (usuario de sistema, puede entrar)}: «principal» y cada cuenta FTP adicional."""
    salida = {"principal": (meta["usuario"], bool(meta.get("ftp")))}
    for c in meta.get("ftp_cuentas", []):
        salida[c["nombre"]] = (c["usuario"], True)
    return salida


def _archivo(usuario):
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", usuario):
        raise ErrorSitio("usuario de sistema no válido")
    return os.path.join(CARPETA, usuario)


def _escribir(ruta, lineas):
    os.makedirs(CARPETA, mode=0o755, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644), "w") as f:
        f.write("".join(l + "\n" for l in lineas))
    os.chmod(tmp, 0o644)
    os.replace(tmp, ruta)


def sincronizar(meta):
    """Rehace los archivos de claves de todas las cuentas del sitio según el meta (y quita los que sobran)."""
    for cuenta, (usuario, activa) in cuentas(meta).items():
        ruta = _archivo(usuario)
        lineas = [f"restrict {c['tipo']} {c['datos']}" + (f" {c['comentario']}" if c.get("comentario") else "")
                  for c in meta.get("claves_ssh", []) if c["cuenta"] == cuenta]
        if activa and lineas:
            _escribir(ruta, lineas)
        elif os.path.lexists(ruta):
            os.remove(ruta)


def quitar_cuenta(meta, cuenta, usuario):
    """Al dar de baja una cuenta adicional: sus claves y su archivo (no guarda el meta)."""
    meta["claves_ssh"] = [c for c in meta.get("claves_ssh", []) if c["cuenta"] != cuenta]
    ruta = _archivo(usuario)
    if os.path.lexists(ruta):
        os.remove(ruta)


def quitar_todas(meta):
    """Al dar de baja el sitio."""
    for usuario, _activa in cuentas(meta).values():
        ruta = _archivo(usuario)
        if os.path.lexists(ruta):
            os.remove(ruta)
    meta.pop("claves_ssh", None)


# --- Órdenes ---


def _publica(meta, c):
    usuario, activa = cuentas(meta).get(c["cuenta"], (None, False))
    return {"id": c["id"], "cuenta": c["cuenta"], "usuario": usuario, "tipo": c["tipo"], "bits": c["bits"],
            "huella": c["huella"], "comentario": c.get("comentario", ""), "creada": c.get("creada"), "activa": activa}


def listar(dominio):
    meta = leer_meta(dominio)
    return {"dominio": dominio, "maximo": MAXIMO,
            "cuentas": [{"cuenta": n, "usuario": u, "activa": a} for n, (u, a) in cuentas(meta).items()],
            "claves": [_publica(meta, c) for c in meta.get("claves_ssh", [])]}


def agregar(dominio, cuenta, texto):
    meta = leer_meta(dominio)
    if cuenta not in cuentas(meta):
        raise ErrorSitio("esa cuenta no es de este sitio")
    clave = validar(texto)
    suyas = [c for c in meta.get("claves_ssh", []) if c["cuenta"] == cuenta]
    if len(suyas) >= MAXIMO:
        raise ErrorSitio(f"como máximo {MAXIMO} claves por cuenta")
    if any(c["huella"] == clave["huella"] for c in suyas):
        raise ErrorSitio("esa clave ya está añadida en esta cuenta")
    nueva = {"id": secrets.token_hex(4), "cuenta": cuenta, **clave, "creada": time.strftime("%Y-%m-%d %H:%M")}
    meta.setdefault("claves_ssh", []).append(nueva)
    sincronizar(meta)
    guardar_meta(meta)
    return {**listar(dominio), "agregada": _publica(meta, nueva)}


def borrar(dominio, ident):
    if not isinstance(ident, str) or not RE_ID.fullmatch(ident):
        raise ErrorSitio("clave no válida")
    meta = leer_meta(dominio)
    if not any(c["id"] == ident for c in meta.get("claves_ssh", [])):
        raise ErrorSitio("esa clave no está en este sitio")
    meta["claves_ssh"] = [c for c in meta["claves_ssh"] if c["id"] != ident]
    sincronizar(meta)
    guardar_meta(meta)
    return listar(dominio)
