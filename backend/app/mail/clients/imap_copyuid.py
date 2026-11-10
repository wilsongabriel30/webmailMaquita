"""Lectura de la respuesta COPYUID de IMAP (RFC 4315, UIDPLUS).

Tras un `UID MOVE` o `UID COPY`, Dovecot responde `OK [COPYUID <uidvalidity> <uids origen> <uids destino>] …`.
Los dos conjuntos tienen la misma cantidad de elementos y se corresponden uno a uno, en orden. Con ese mapa
las etiquetas de base de datos (carpeta + uid) pueden seguir al correo a su carpeta nueva.
"""

import re

_COPYUID = re.compile(r"COPYUID\s+(\d+)\s+([\d:,]+)\s+([\d:,]+)", re.IGNORECASE)


def _texto(linea) -> str:
    if isinstance(linea, (bytes, bytearray)):
        return linea.decode("utf-8", errors="replace")
    return str(linea)


def expandir_conjunto(conjunto: str) -> list[int]:
    """«1,3:5,9» → [1, 3, 4, 5, 9]. Un rango invertido («5:3») se recorre igual, de menor a mayor."""
    salida: list[int] = []
    for parte in conjunto.split(","):
        parte = parte.strip()
        if not parte:
            continue
        if ":" in parte:
            a, b = parte.split(":", 1)
            inicio, fin = int(a), int(b)
            if inicio > fin:
                inicio, fin = fin, inicio
            salida.extend(range(inicio, fin + 1))
        else:
            salida.append(int(parte))
    return salida


def mapa_copyuid(lineas) -> dict[int, int] | None:
    """Mapa {uid origen: uid destino} a partir de las líneas de la respuesta; None si no viene COPYUID.

    Si el servidor devolviera conjuntos de distinto tamaño (no debería), se descarta el mapa entero:
    es preferible no trasladar una etiqueta a trasladarla a otro correo.
    """
    for linea in lineas or ():
        m = _COPYUID.search(_texto(linea))
        if not m:
            continue
        origen = expandir_conjunto(m.group(2))
        destino = expandir_conjunto(m.group(3))
        if not origen or len(origen) != len(destino):
            return None
        return dict(zip(origen, destino))
    return None
