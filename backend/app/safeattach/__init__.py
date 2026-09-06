"""SafeAttach — análisis modular de adjuntos (multi-motor + detonación aislada).

Entrada estable para el resto del backend:
    from app.safeattach import scan_attachment
    veredicto = scan_attachment(content, filename, content_type)
    # -> {"result": "clean|suspicious|malicious", "threats": [...], "details": {...}}
"""
from app.safeattach.pipeline import scan
from app.safeattach.verdict import CLEAN, MALICIOUS, SUSPICIOUS  # noqa: F401


def scan_attachment(content: bytes, filename: str, content_type: str = "") -> dict:
    return scan(content, filename, content_type).to_dict()
