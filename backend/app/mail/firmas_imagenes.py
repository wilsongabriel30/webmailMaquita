"""Imágenes de las firmas: descarga acotada, tamaño real igual al declarado y nombre estable.

Hallazgo de usuario (Zimbra, 07/09/2026): una firma con el logo a 201 px de ancho se veía
gigante en el destinatario porque el archivo real medía 1.200 px y el cliente ignoraba el
`width`. La regla aquí es una sola: la imagen que viaja en el correo tiene EXACTAMENTE el
tamaño con el que se muestra, y se guarda en el servidor con un nombre que depende de su
contenido, nunca como URL externa.

Límites (fallo cerrado: lo que no cumple, se quita de la firma y se avisa):
- descarga en 5 s como máximo, 2 MB como máximo, tipo `image/*`, sin redes internas;
- ancho máximo 600 px, nunca se amplía;
- salida siempre PNG (conserva transparencia) en FIRMAS_DIR (`/var/lib/maquita-webmail/firmas`).
"""

import base64
import hashlib
import io
import ipaddress
import os
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image

from app.webhooks.salida_segura import (
    Destino,
    DestinoNoPermitido,
    _ip_prohibida,
    resolver_todas,
)

ANCHO_MAX = 600
BYTES_MAX = 2 * 1024 * 1024
TIEMPO_S = 5.0
RUTA_PUBLICA = "/api/firmas/imagen/"
_NOMBRE = re.compile(r"^[0-9a-f]{32}\.png$")
_DATA = re.compile(
    r"^data:(image/[a-z0-9.+-]+);base64,(.+)$", re.IGNORECASE | re.DOTALL
)


class ImagenRechazada(ValueError):
    """Motivo, en palabras para el usuario, por el que una imagen no entra en la firma."""


@dataclass
class Imagen:
    nombre: str
    ancho: int
    alto: int

    @property
    def src(self) -> str:
        return RUTA_PUBLICA + self.nombre


def directorio() -> str:
    return os.getenv("FIRMAS_DIR", "/var/lib/maquita-webmail/firmas")


def ruta_local(nombre: str) -> str | None:
    """Ruta en disco de una imagen por su nombre, o None si el nombre no es válido o no existe."""
    if not _NOMBRE.match(nombre or ""):
        return None
    ruta = os.path.join(directorio(), nombre)
    return ruta if os.path.isfile(ruta) else None


def leer_local(nombre: str) -> bytes | None:
    ruta = ruta_local(nombre)
    if not ruta:
        return None
    with open(ruta, "rb") as f:
        return f.read()


def imagen_local(src: str) -> Imagen | None:
    """La imagen que ya está en el servidor (src `/api/firmas/imagen/<hash>.png`), con su tamaño."""
    if not src.startswith(RUTA_PUBLICA):
        return None
    nombre = src[len(RUTA_PUBLICA) :]
    ruta = ruta_local(nombre)
    if not ruta:
        return None
    with Image.open(ruta) as im:
        return Imagen(nombre, im.width, im.height)


def _destino(url: str) -> Destino:
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ImagenRechazada("solo se admiten direcciones http(s)")
    if p.username or p.password:
        raise ImagenRechazada("dirección con credenciales")
    puerto = p.port or (443 if p.scheme == "https" else 80)
    try:
        ips = [str(ipaddress.ip_address(p.hostname))]
    except ValueError:
        try:
            ips = resolver_todas(p.hostname, puerto)
        except DestinoNoPermitido as exc:
            raise ImagenRechazada("el servidor no existe") from exc
    if any(_ip_prohibida(ipaddress.ip_address(ip)) for ip in ips):
        raise ImagenRechazada("apunta a una red interna")
    return Destino(
        url_original=url, host=p.hostname, ip=ips[0], puerto=puerto, esquema=p.scheme
    )


def descargar(url: str) -> bytes:
    """Descarga acotada (5 s, 2 MB, image/*), conectando a la IP ya validada y revalidando cada salto."""
    cabeceras = {"User-Agent": "MaquitaMail-firmas/1.0", "Accept": "image/*"}
    try:
        with httpx.Client(timeout=TIEMPO_S, follow_redirects=False) as cliente:
            for _salto in range(3):
                destino = _destino(url)
                cab = dict(cabeceras, Host=destino.host)
                ext = (
                    {"sni_hostname": destino.host} if destino.esquema == "https" else {}
                )
                with cliente.stream(
                    "GET", destino.url_fijada, headers=cab, extensions=ext
                ) as r:
                    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get(
                        "location"
                    ):
                        url = urljoin(url, r.headers["location"])
                        continue
                    if r.status_code != 200:
                        raise ImagenRechazada(f"el servidor respondió {r.status_code}")
                    tipo = (
                        r.headers.get("content-type", "").split(";")[0].strip().lower()
                    )
                    if not tipo.startswith("image/"):
                        raise ImagenRechazada(
                            f"no es una imagen ({tipo or 'sin tipo'})"
                        )
                    datos = bytearray()
                    for trozo in r.iter_bytes(65536):
                        datos += trozo
                        if len(datos) > BYTES_MAX:
                            raise ImagenRechazada("pesa más de 2 MB")
                    return bytes(datos)
            raise ImagenRechazada("demasiadas redirecciones")
    except httpx.TimeoutException as exc:
        raise ImagenRechazada("tardó más de 5 s en descargarse") from exc
    except httpx.HTTPError as exc:
        raise ImagenRechazada("no se pudo descargar") from exc


def decodificar_data(uri: str) -> bytes:
    """Imagen incrustada por el editor (`data:image/...;base64,...`)."""
    m = _DATA.match(uri.strip())
    if not m:
        raise ImagenRechazada("imagen incrustada en un formato no admitido")
    if len(m.group(2)) > BYTES_MAX * 4 // 3 + 4:
        raise ImagenRechazada("pesa más de 2 MB")
    try:
        return base64.b64decode(m.group(2), validate=False)
    except Exception as exc:
        raise ImagenRechazada("imagen incrustada ilegible") from exc


def guardar_redimensionada(datos: bytes, ancho_declarado: int | None) -> Imagen:
    """Deja la imagen al ancho declarado (máximo 600, nunca ampliada), en PNG, con nombre por contenido."""
    if len(datos) > BYTES_MAX:
        raise ImagenRechazada("pesa más de 2 MB")
    try:
        im = Image.open(io.BytesIO(datos))
        im.load()
    except Exception as exc:
        raise ImagenRechazada("no es una imagen válida") from exc
    ancho_nat, alto_nat = im.size
    objetivo = min(ancho_declarado or ancho_nat, ANCHO_MAX, ancho_nat)
    objetivo = max(objetivo, 1)
    if im.mode not in ("RGB", "RGBA", "L", "LA"):
        im = im.convert("RGBA")
    if ancho_nat > objetivo:
        alto = max(1, round(alto_nat * objetivo / ancho_nat))
        im = im.resize((objetivo, alto), Image.LANCZOS)
    salida = io.BytesIO()
    im.save(salida, format="PNG", optimize=True)
    contenido = salida.getvalue()
    nombre = hashlib.sha256(contenido).hexdigest()[:32] + ".png"
    carpeta = directorio()
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre)
    if not os.path.exists(ruta):
        temporal = f"{ruta}.{os.getpid()}.tmp"
        with open(temporal, "wb") as f:
            f.write(contenido)
        os.chmod(temporal, 0o644)
        os.replace(temporal, ruta)
    return Imagen(nombre, im.width, im.height)
