"""Motor: ClamAV (firmas)."""

import subprocess

from app.safeattach.analyzers.base import Analyzer
from app.safeattach.verdict import MALICIOUS, Finding


class ClamAV(Analyzer):
    name = "clamav"
    obligatorio = True

    def analyze(self, path, content, report):
        # 05/11/2026: primero INSTREAM por el socket de clamd (funciona con PrivateTmp, donde
        # clamdscan --fdpass fallaba con «Not a regular file» y marcaba el adjunto sospechoso).
        from app.safeattach.analyzers import clamd_instream

        out = clamd_instream.escanear(content)
        if not out.startswith("error:"):
            report.engines["clamav"] = out
            if out.endswith("FOUND"):
                name = out[: -len("FOUND")].strip() or "desconocido"
                report.findings.append(Finding("clamav", MALICIOUS, f"firma: {name}"))
            return
        # Respaldo: clamdscan clásico (entornos sin socket local)
        try:
            r = subprocess.run(
                ["clamdscan", "--no-summary", "--fdpass", path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            out = r.stdout.strip()
            report.engines["clamav"] = out or "ok"
            if "FOUND" in out:
                name = out.split(":")[1].strip() if ":" in out else "desconocido"
                report.findings.append(Finding("clamav", MALICIOUS, f"firma: {name}"))
        except FileNotFoundError:
            report.engines["clamav"] = "no disponible"
        except subprocess.TimeoutExpired:
            report.engines["clamav"] = "timeout"
