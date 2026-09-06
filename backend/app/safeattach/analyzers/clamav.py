"""Motor: ClamAV (firmas)."""
import subprocess

from app.safeattach.analyzers.base import Analyzer
from app.safeattach.verdict import MALICIOUS, Finding


class ClamAV(Analyzer):
    name = "clamav"

    def analyze(self, path, content, report):
        try:
            r = subprocess.run(["clamdscan", "--no-summary", "--fdpass", path],
                               capture_output=True, text=True, timeout=60)
            out = r.stdout.strip()
            report.engines["clamav"] = out or "ok"
            if "FOUND" in out:
                name = out.split(":")[1].strip() if ":" in out else "desconocido"
                report.findings.append(Finding("clamav", MALICIOUS, f"firma: {name}"))
        except FileNotFoundError:
            report.engines["clamav"] = "no disponible"
        except subprocess.TimeoutExpired:
            report.engines["clamav"] = "timeout"
