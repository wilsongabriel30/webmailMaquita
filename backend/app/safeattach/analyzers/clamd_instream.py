"""ClamAV por el socket de clamd con INSTREAM (05/11/2026).

Antes se llamaba `clamdscan --fdpass <ruta>`: como el milter y el webmail corren con
PrivateTmp=yes, clamd no ve el archivo (y con el descriptor responde «fd[10]: Not a regular
file. ERROR», 1.300 veces al día). El pipeline lo tomaba como motor obligatorio caído y marcaba
el adjunto sospechoso sin serlo. Con INSTREAM el contenido viaja por el socket y clamd no
necesita ver el archivo. Fail-open hacia el llamador: cualquier problema devuelve "error: ...".
"""

from __future__ import annotations

import os
import socket
import struct

SOCKET = os.getenv("CLAMD_SOCKET", "/var/run/clamav/clamd.ctl")
TROZO = 65536


def escanear(datos: bytes, timeout: float = 60.0) -> str:
    """Devuelve la respuesta de clamd: 'OK', '<firma> FOUND' o 'error: ...'."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(SOCKET)
        try:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(datos), TROZO):
                trozo = datos[i : i + TROZO]
                s.sendall(struct.pack("!I", len(trozo)) + trozo)
            s.sendall(struct.pack("!I", 0))
            resp = b""
            while True:
                x = s.recv(4096)
                if not x:
                    break
                resp += x
        finally:
            s.close()
    except (OSError, socket.timeout) as e:
        return f"error: {e}"
    texto = resp.decode("utf-8", "replace").strip("\0\r\n ")
    # «stream: OK» / «stream: Eicar-Test-Signature FOUND» / «INSTREAM size limit exceeded. ERROR»
    if texto.startswith("stream: "):
        texto = texto[len("stream: ") :]
    if texto.endswith("ERROR"):
        return "error: " + texto
    return texto or "error: respuesta vacía"
