"""Duración de cada tramo de un envío desde el webmail (15/11/2026).

Motivo: el correo interno tardaba y no había forma de saber en qué paso del servidor se iba el
tiempo. Cada envío deja UNA línea en el registro:

    ENVIO_TRAMOS user=... total_ms=... limites=.. dlp_cuerpo=.. buzon=.. firma=.. ...

Solo mide y registra: no cambia el envío y nunca lanza errores.
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(
    "maquita.webmail.envio_tramos"
)  # hijo del registro del webmail: así sale en el diario
AVISO_MS = 3000  # por encima de esto la línea sale como WARNING


class Tramos:
    def __init__(self, usuario: str) -> None:
        self.usuario = usuario
        self.inicio = self.ultimo = time.monotonic()
        self.partes: list[tuple[str, int]] = []

    def marca(self, nombre: str) -> None:
        ahora = time.monotonic()
        self.partes.append((nombre, int((ahora - self.ultimo) * 1000)))
        self.ultimo = ahora

    def cerrar(self, resultado: str = "ok") -> None:
        try:
            total = int((time.monotonic() - self.inicio) * 1000)
            detalle = " ".join(f"{n}={ms}" for n, ms in self.partes)
            nivel = log.warning if total > AVISO_MS else log.info
            nivel(
                "ENVIO_TRAMOS user=%s resultado=%s total_ms=%d %s",
                self.usuario,
                resultado,
                total,
                detalle,
            )
        except Exception:  # noqa: BLE001
            pass
