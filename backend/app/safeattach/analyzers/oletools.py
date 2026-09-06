"""Motor: macros en documentos Office (olevba)."""
import json
import subprocess

from app.safeattach.analyzers.base import Analyzer
from app.safeattach.verdict import MALICIOUS, SUSPICIOUS, Finding

OFFICE = (".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf",
          ".docm", ".xlsm", ".pptm")
OLEVBA = "/opt/maquita-webmail/backend/venv/bin/olevba"


class OleTools(Analyzer):
    name = "oletools"

    def applies(self, filename, mime):
        return filename.lower().endswith(OFFICE)

    def analyze(self, path, content, report):
        try:
            r = subprocess.run([OLEVBA, "--json", path],
                               capture_output=True, text=True, timeout=30)
            if not (r.returncode == 0 and r.stdout.strip()):
                report.engines["oletools"] = "sin macros"
                return
            data = json.loads(r.stdout)
            report.engines["oletools"] = data if isinstance(data, list) else str(data)[:500]
            for item in (data if isinstance(data, list) else []):
                if not isinstance(item, dict):
                    continue
                kw = item.get("keyword", "?")
                if item.get("type") == "AutoExec":
                    report.findings.append(Finding("oletools", MALICIOUS, f"macro AutoExec: {kw}"))
                elif item.get("type") == "Suspicious":
                    report.findings.append(Finding("oletools", SUSPICIOUS, f"sospechoso: {kw}"))
        except FileNotFoundError:
            report.engines["oletools"] = "olevba no disponible"
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            report.engines["oletools"] = "error/timeout"
