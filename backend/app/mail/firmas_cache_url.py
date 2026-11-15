"""Imágenes externas de la firma ya descargadas: se recuerdan por dirección (15/11/2026).

Motivo: la firma institucional trae sus imágenes como direcciones de la web (logo, iconos) y en
CADA envío se volvían a descargar una tras otra (≈ 0,3 s cada una: 1,9 s por correo con 6
imágenes). Si la web no respondía, cada imagen esperaba 5 s y además se quitaba de la firma.

Aquí se guarda, por dirección y ancho declarado, qué archivo local (ya validado, redimensionado
y en PNG por `firmas_imagenes.guardar_redimensionada`) le corresponde:

- `vigente()`  → la imagen si se descargó hace menos de VIGENCIA_S (24 h): no se vuelve a bajar;
- `ultima()`   → la última copia aunque esté vencida: se usa solo si la descarga nueva falla.

El índice son archivos pequeños en FIRMAS_DIR/.direcciones (lo comparten todos los procesos del
webmail y sobrevive a los reinicios). Cualquier fallo aquí equivale a «no está»: se descarga.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

from app.mail import firmas_imagenes as imagenes

VIGENCIA_S = float(os.getenv("FIRMAS_CACHE_DIRECCIONES_S", str(24 * 3600)))


def _ruta(url: str, ancho: int | None) -> str:
    clave = hashlib.sha256(f"{ancho or 0}|{url}".encode("utf-8", "replace")).hexdigest()
    return os.path.join(imagenes.directorio(), ".direcciones", clave + ".json")


def _leer(url: str, ancho: int | None) -> tuple[imagenes.Imagen, float] | None:
    try:
        with open(_ruta(url, ancho), encoding="utf-8") as f:
            d = json.load(f)
        if d.get("url") != url or not imagenes.ruta_local(d["nombre"]):
            return None
        return imagenes.Imagen(d["nombre"], int(d["ancho"]), int(d["alto"])), float(
            d["cuando"]
        )
    except Exception:  # noqa: BLE001
        return None


def vigente(url: str, ancho: int | None) -> imagenes.Imagen | None:
    r = _leer(url, ancho)
    return r[0] if r and time.time() - r[1] < VIGENCIA_S else None


def ultima(url: str, ancho: int | None) -> imagenes.Imagen | None:
    r = _leer(url, ancho)
    return r[0] if r else None


def guardar(url: str, ancho: int | None, imagen: imagenes.Imagen) -> None:
    try:
        ruta = _ruta(url, ancho)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        temporal = f"{ruta}.{os.getpid()}.tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "url": url,
                    "nombre": imagen.nombre,
                    "ancho": imagen.ancho,
                    "alto": imagen.alto,
                    "cuando": time.time(),
                },
                f,
            )
        os.replace(temporal, ruta)
    except Exception:  # noqa: BLE001
        pass
