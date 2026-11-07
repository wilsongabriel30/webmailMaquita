"""Registro de cada llamada al modelo de IA (05/11/2026).

Hasta hoy solo quedaban en el registro los errores; cuando una función tardaba 73 s (sugerencias de
respuesta de Luis Bastidas, 14:06) no había forma de saber si fue el modelo de calidad en frío, la cola
de la pasarela o el respaldo. Ahora cada intento deja una línea:
    LLM_LLAMADA modelo=… gpu=… ms=… estado=ok|vacia|timeout|error|gateway_error intento=N
Se consulta con: journalctl -u maquita-webmail --since "hoy" -o cat | grep LLM_LLAMADA
"""

import logging
import time

logger = logging.getLogger(
    "maquita.webmail.ia"
)  # hijo del logger configurado: así salen las líneas INFO
UMBRAL_LENTO_MS = 20000


class Cronometro:
    def __init__(self, ia: dict, intento: int):
        self.modelo = ia.get("model", "?")
        self.gpu = ia.get("preferir_gpu") or "-"
        self.intento = intento
        self.inicio = time.monotonic()

    def anotar(self, estado: str, data: dict | None = None):
        ms = int((time.monotonic() - self.inicio) * 1000)
        modelo_real = (data or {}).get("modelo") or self.modelo
        gpu_real = (data or {}).get("gpu") or self.gpu
        nivel = (
            logging.WARNING if ms > UMBRAL_LENTO_MS or estado != "ok" else logging.INFO
        )
        logger.log(
            nivel,
            "LLM_LLAMADA modelo=%s gpu=%s ms=%d estado=%s intento=%d",
            modelo_real,
            gpu_real,
            ms,
            estado,
            self.intento,
        )
