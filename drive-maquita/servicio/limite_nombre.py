"""Drive Maquita — nombres demasiado largos (14/09/2026).

El disco del Almacén (NFS/ZFS) admite nombres de hasta 255 BYTES; las tildes
y la ñ ocupan 2 bytes. Al renombrar una carpeta con un nombre kilométrico el
sistema daba «[Errno 36] File name too long», un 500 sin explicación, y en el
explorador parecía que «se quedaba pensando» o «no guardaba».

Aquí se comprueba ANTES de tocar el disco y se devuelve un mensaje claro.
"""
from seguridad_rutas import RutaInvalida

MAX_BYTES = 255


def comprobar(nombre: str) -> None:
    """Lanza RutaInvalida (HTTP 400) si el nombre no cabe en el disco."""
    largo = len((nombre or '').encode('utf-8'))
    if largo > MAX_BYTES:
        sobran = largo - MAX_BYTES
        raise RutaInvalida(
            f'El nombre es demasiado largo ({len(nombre)} caracteres). '
            f'Acórtalo unos {max(sobran, 1)} caracteres: el máximo es 255 y las tildes '
            'cuentan doble.')
