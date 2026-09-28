"""Reconocer una imagen por su contenido, no por el nombre ni por lo que diga el navegador.

Solo formatos de mapa de bits. SVG se rechaza a propósito: es un documento que puede llevar
código, y el logo se muestra en la pantalla de entrada del correo.
"""

FORMATOS = {"png": ".png", "jpeg": ".jpg", "webp": ".webp", "ico": ".ico"}


def formato_de(datos: bytes) -> str | None:
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if datos.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(datos) >= 12 and datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp"
    if datos.startswith(b"\x00\x00\x01\x00") and len(datos) >= 22:
        return "ico"
    return None


def medidas(datos: bytes, formato: str) -> tuple[int, int] | None:
    """Ancho y alto cuando es barato saberlo (PNG). Sirve para rechazar imágenes desmesuradas."""
    if formato == "png" and len(datos) >= 24 and datos[12:16] == b"IHDR":
        return int.from_bytes(datos[16:20], "big"), int.from_bytes(datos[20:24], "big")
    return None
