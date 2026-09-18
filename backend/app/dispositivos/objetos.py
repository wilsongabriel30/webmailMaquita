"""Almacén de los respaldos: un archivo por contenido (SHA-256) y por equipo, cifrado en reposo.

Formato: cabecera `MQR1` + 8 bytes de prefijo aleatorio, y después tramas de 1 MiB de texto claro
cifradas con AES-256-GCM (nonce = prefijo + número de trama; datos asociados = equipo, SHA-256 y
número de trama, para que una trama no pueda moverse de sitio ni de archivo). El texto claro nunca
toca el disco: cada trozo se cifra al llegar. La clave maestra vive solo en el `.env` del backend
(`DISP_RESPALDO_CLAVE`); sin ella los respaldos son ilegibles, también para quien administre el
almacén. Todas las funciones son síncronas: se llaman con `asyncio.to_thread`.
"""

import base64
import hashlib
import os
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIA = b"MQR1"
CABECERA = len(MAGIA) + 8
TRAMA = 1024 * 1024
ETIQUETA = 16
SHA_VACIO = hashlib.sha256(b"").hexdigest()


class AlmacenNoDisponible(RuntimeError):
    pass


class Desfase(ValueError):
    """El trozo no continúa donde quedó el archivo."""


def raiz() -> Path:
    return Path(os.environ.get("DISP_RESPALDO_DIR", "/mnt/almacen/.respaldo-movil"))


@lru_cache(maxsize=1)
def _cifrador() -> AESGCM:
    try:
        clave = base64.b64decode(os.environ["DISP_RESPALDO_CLAVE"])
    except Exception as e:
        raise AlmacenNoDisponible("Falta DISP_RESPALDO_CLAVE") from e
    if len(clave) != 32:
        raise AlmacenNoDisponible("DISP_RESPALDO_CLAVE debe ser de 32 bytes en base64")
    return AESGCM(clave)


def comprobar() -> None:
    _cifrador()
    if not raiz().is_dir() or not os.access(raiz(), os.W_OK):
        raise AlmacenNoDisponible(
            f"El almacén de respaldos no está montado o no se puede escribir: {raiz()}"
        )


_CARPETA_OK = __import__("re").compile(r"^[A-Za-z0-9._-]{1,80}$")
_SHA_OK = __import__("re").compile(r"^[0-9a-f]{64}$")


def carpeta_valida(c: str) -> bool:
    # Un solo componente de ruta; "." y ".." saldrían del almacén.
    return bool(_CARPETA_OK.match(c)) and c not in (".", "..")


def carpeta(equipo: dict) -> str:
    """Subcarpeta del equipo dentro del almacén: la configurada, o el id si no hay ninguna."""
    c = (equipo.get("carpeta_respaldo") or "").strip()
    return c if carpeta_valida(c) else str(int(equipo["id"]))


def ruta(carpeta_eq: str, sha: str) -> Path:
    if not carpeta_valida(carpeta_eq) or not _SHA_OK.match(sha):
        raise ValueError("carpeta o contenido no válidos")
    return raiz() / carpeta_eq / "objetos" / sha[:2] / sha


def _datos_asociados(sha: str, k: int) -> bytes:
    return f"{sha}:{k}".encode()


def _tam_cifrado(claro: int) -> int:
    tramas = (claro + TRAMA - 1) // TRAMA
    return CABECERA + claro + tramas * ETIQUETA


def anexar(carpeta_eq: str, sha: str, offset: int, datos: bytes) -> None:
    """Cifra y añade un trozo. `offset` debe ser múltiplo de 1 MiB y coincidir con lo ya guardado."""
    if offset % TRAMA:
        raise Desfase("offset no alineado")
    p = ruta(carpeta_eq, sha)
    if offset == 0:
        p.parent.mkdir(parents=True, exist_ok=True)
        prefijo = os.urandom(8)
        f = open(p, "wb")
        f.write(MAGIA + prefijo)
    else:
        if not p.exists() or p.stat().st_size != _tam_cifrado(offset):
            raise Desfase("el archivo guardado no coincide con el offset")
        with open(p, "rb") as g:
            cab = g.read(CABECERA)
        prefijo = cab[len(MAGIA) :]
        f = open(p, "ab")
    c = _cifrador()
    with f:
        k = offset // TRAMA
        for i in range(0, len(datos), TRAMA):
            f.write(
                c.encrypt(
                    prefijo + k.to_bytes(4, "big"),
                    datos[i : i + TRAMA],
                    _datos_asociados(sha, k),
                )
            )
            k += 1
        f.flush()
        os.fsync(f.fileno())


def leer(carpeta_eq: str, sha: str, desde: int = 0):
    """Generador de texto claro a partir de `desde` (múltiplo de 1 MiB)."""
    c = _cifrador()
    with open(ruta(carpeta_eq, sha), "rb") as f:
        cab = f.read(CABECERA)
        if cab[: len(MAGIA)] != MAGIA:
            raise ValueError("objeto con formato desconocido")
        prefijo = cab[len(MAGIA) :]
        k = desde // TRAMA
        f.seek(CABECERA + k * (TRAMA + ETIQUETA))
        while True:
            bloque = f.read(TRAMA + ETIQUETA)
            if not bloque:
                return
            yield c.decrypt(
                prefijo + k.to_bytes(4, "big"), bloque, _datos_asociados(sha, k)
            )
            k += 1


def verificar(carpeta_eq: str, sha: str, tamano: int) -> bool:
    """Descifra todo y comprueba tamaño y SHA-256 del contenido."""
    h, n = hashlib.sha256(), 0
    try:
        for trozo in leer(carpeta_eq, sha):
            h.update(trozo)
            n += len(trozo)
    except Exception:
        return False
    return n == tamano and h.hexdigest() == sha


def borrar(carpeta_eq: str, sha: str) -> None:
    try:
        ruta(carpeta_eq, sha).unlink()
    except FileNotFoundError:
        pass
