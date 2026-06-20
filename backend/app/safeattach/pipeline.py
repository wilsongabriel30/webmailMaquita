"""Orquestador: corre los analizadores en orden y agrega el veredicto.

Para agregar un motor nuevo: crear un archivo en analyzers/ que herede de
Analyzer y añadirlo a la lista ANALYZERS. Nada más.
"""
import logging
import os
import tempfile

from app.safeattach.verdict import ScanReport
from app.safeattach.analyzers.clamav import ClamAV
from app.safeattach.analyzers.filetype import FileType
from app.safeattach.analyzers.oletools import OleTools
from app.safeattach.analyzers.archive import Archive
from app.safeattach.analyzers.yara_rules import Yara
from app.safeattach.detonation.docker_sandbox import DockerSandbox

logger = logging.getLogger("safeattach")

# Orden: motores rápidos/baratos primero; detonación (cara) al final.
ANALYZERS = [ClamAV(), FileType(), OleTools(), Archive(), Yara(), DockerSandbox()]


def scan(content: bytes, filename: str, content_type: str = "") -> ScanReport:
    report = ScanReport(filename=filename)
    suffix = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        path = tmp.name
    try:
        for a in ANALYZERS:
            try:
                if a.applies(filename, content_type):
                    a.analyze(path, content, report)
            except Exception as e:                       # un motor no debe tumbar el resto
                logger.warning("analizador %s falló: %s", a.name, e)
                report.engines[a.name] = f"error: {e}"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return report
