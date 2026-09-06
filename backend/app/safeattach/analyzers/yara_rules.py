"""Motor: reglas YARA estáticas (best-effort)."""

import os
import subprocess

from app.safeattach.analyzers.base import Analyzer
from app.safeattach.verdict import MALICIOUS, Finding

RULES_DIR = os.getenv(
    "SAFEATTACH_YARA_DIR", "/opt/maquita-webmail/deploy/safeattach/yara"
)


class Yara(Analyzer):
    name = "yara"

    def analyze(self, path, content, report):
        import glob

        rules = sorted(
            glob.glob(os.path.join(RULES_DIR, "*.yar"))
            + glob.glob(os.path.join(RULES_DIR, "*.yara"))
        )
        if not rules:
            report.engines["yara"] = "sin reglas"
            return
        try:
            r = subprocess.run(
                ["yara", "-w"] + rules + [path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            hits = [ln.split()[0] for ln in r.stdout.splitlines() if ln.strip()]
            report.engines["yara"] = hits or "sin coincidencias"
            for rule in hits:
                report.findings.append(Finding("yara", MALICIOUS, f"regla: {rule}"))
        except FileNotFoundError:
            report.engines["yara"] = "yara no instalado"
        except subprocess.TimeoutExpired:
            report.engines["yara"] = "timeout"
