"""Veredicto agregado del análisis de un adjunto."""

from dataclasses import dataclass, field

CLEAN, SUSPICIOUS, MALICIOUS = "clean", "suspicious", "malicious"
_ORDER = {CLEAN: 0, SUSPICIOUS: 1, MALICIOUS: 2}


@dataclass
class Finding:
    engine: str
    severity: str  # clean | suspicious | malicious
    detail: str = ""


@dataclass
class ScanReport:
    filename: str
    findings: list = field(default_factory=list)
    engines: dict = field(default_factory=dict)  # motor -> detalle crudo
    errores: list = field(
        default_factory=list
    )  # motores OBLIGATORIOS que no respondieron

    @property
    def result(self) -> str:
        if not self.findings:
            return CLEAN
        return max((f.severity for f in self.findings), key=lambda s: _ORDER.get(s, 0))

    @property
    def threats(self) -> list:
        return [
            {"engine": f.engine, "threat": f.detail}
            for f in self.findings
            if f.severity != CLEAN
        ]

    def to_dict(self) -> dict:
        return {
            "result": self.result,
            "threats": self.threats,
            "details": self.engines,
            "errors": list(self.errores),
            "filename": self.filename,
        }
