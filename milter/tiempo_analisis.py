"""Presupuesto de tiempo del análisis de adjuntos en el milter (05/11/2026).

Motivo: la detonación en Docker tarda 4-15 s por adjunto y se hacía en serie sin tope por
mensaje. Un correo con 4 adjuntos retenía el DATA de Postfix más de 60 s, el webmail cortaba
a los 60 s y mostraba «error» aunque Postfix ya lo había encolado (riesgo de envío duplicado).

Red de seguridad (NO la causa de los 60 s, que fue saturación de disco): todo el análisis de adjuntos
de un mensaje dispone de PRESUPUESTO_S segundos en total (60 s, igual que 4 adjuntos al tope anterior)
(cada adjunto, como máximo POR_ADJUNTO_S o lo que quede). Al agotarse se deja de analizar y
el correo sigue su camino (fail-open) con la cabecera X-Maquita-Scan: parcial-tiempo y una
línea ANALISIS_PARCIAL_POR_TIEMPO en el registro. Además queda la duración de cada adjunto
(ADJUNTO_ANALIZADO) y de cada mensaje (ANALISIS_MENSAJE), en WARNING si pasan de AVISO_S.
"""
from __future__ import annotations

import logging
import os
import time

log = logging.getLogger("maquita_milter")

PRESUPUESTO_S = float(os.getenv("MILTER_PRESUPUESTO_ADJUNTOS_S", "60"))
POR_ADJUNTO_S = float(os.getenv("MILTER_TIMEOUT_POR_ADJUNTO_S", "15"))
AVISO_S = float(os.getenv("MILTER_AVISO_LENTO_S", "5"))
MINIMO_UTIL_S = 0.5   # con menos de medio segundo no vale la pena lanzar otro motor


class Presupuesto:
    """Cronómetro del análisis de adjuntos de UN mensaje."""

    def __init__(self) -> None:
        self.inicio = time.monotonic()

    def transcurrido(self) -> float:
        return time.monotonic() - self.inicio

    def restante(self) -> float:
        return PRESUPUESTO_S - self.transcurrido()

    def timeout_adjunto(self) -> float:
        """Tiempo máximo para el siguiente adjunto; 0 si el presupuesto está agotado."""
        r = min(POR_ADJUNTO_S, self.restante())
        return r if r >= MINIMO_UTIL_S else 0.0


def anotar_adjunto(archivo: str, inicio: float, resultado: str, tamano: int = 0) -> None:
    ms = int((time.monotonic() - inicio) * 1000)
    nivel = log.warning if ms > AVISO_S * 1000 else log.info
    nivel("ADJUNTO_ANALIZADO archivo=%s bytes=%d ms=%d resultado=%s", (archivo or "")[:80], tamano, ms, resultado or "limpio")


def anotar_parcial(remitente: str, pendientes: int, presupuesto: Presupuesto) -> None:
    log.warning(
        "ANALISIS_PARCIAL_POR_TIEMPO de=%s adjuntos_sin_analizar=%d transcurrido_ms=%d presupuesto_s=%s",
        (remitente or "")[:120], pendientes, int(presupuesto.transcurrido() * 1000), PRESUPUESTO_S,
    )


def anotar_mensaje(remitente: str, sentido: str, inicio: float, parcial: bool) -> None:
    ms = int((time.monotonic() - inicio) * 1000)
    nivel = log.warning if ms > AVISO_S * 1000 else log.info
    nivel("ANALISIS_MENSAJE de=%s sentido=%s ms=%d parcial_tiempo=%s", (remitente or "")[:120], sentido, ms, "si" if parcial else "no")
