"""Orquestador: corre los analizadores en orden y agrega el veredicto.

Para agregar un motor nuevo: crear un archivo en analyzers/ que herede de
Analyzer y añadirlo a la lista ANALYZERS. Nada más.
"""

import logging
import os
import tempfile

from app.safeattach.analyzers.archive import Archive
from app.safeattach.analyzers.clamav import ClamAV
from app.safeattach.analyzers.filetype import FileType
from app.safeattach.analyzers.oletools import OleTools
from app.safeattach.analyzers.yara_rules import Yara
from app.safeattach.detonation.docker_sandbox import DockerSandbox
from app.safeattach.verdict import SUSPICIOUS, Finding, ScanReport

logger = logging.getLogger("safeattach")

# Orden: motores rápidos/baratos primero; detonación (cara) al final.
ANALYZERS = [ClamAV(), FileType(), OleTools(), Archive(), Yara(), DockerSandbox()]

# Motores obligatorios (R-04): además del atributo `obligatorio` de cada motor, por entorno.
_OBLIGATORIOS = {
    m.strip()
    for m in os.getenv("SAFEATTACH_MOTORES_OBLIGATORIOS", "clamav").split(",")
    if m.strip()
}
_MARCAS_FALLO = ("error", "no disponible", "timeout")


def _motor_fallido(detalle) -> bool:
    return detalle is None or str(detalle).lower().startswith(_MARCAS_FALLO)


def _anotar_fallo(a, report: ScanReport) -> None:
    """Motor obligatorio caído: sospechoso y anotado en `errores` (fallo cerrado)."""
    if a.name in report.errores:
        return
    report.errores.append(a.name)
    report.findings.append(
        Finding(a.name, SUSPICIOUS, "motor obligatorio no disponible: fallo cerrado")
    )
    logger.error(
        "SAFEATTACH_MOTOR_OBLIGATORIO_CAIDO motor=%s fichero=%s",
        a.name,
        report.filename,
    )


def scan(content: bytes, filename: str, content_type: str = "") -> ScanReport:
    report = ScanReport(filename=filename)
    suffix = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        path = tmp.name
    try:
        for a in ANALYZERS:
            obligatorio = a.name in _OBLIGATORIOS or getattr(a, "obligatorio", False)
            try:
                if a.applies(filename, content_type):
                    a.analyze(path, content, report)
                    if obligatorio and _motor_fallido(report.engines.get(a.name)):
                        _anotar_fallo(a, report)
            except Exception as e:  # un motor no debe tumbar el resto
                logger.warning("analizador %s falló: %s", a.name, e)
                report.engines[a.name] = f"error: {e}"
                if obligatorio:
                    _anotar_fallo(a, report)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return report
