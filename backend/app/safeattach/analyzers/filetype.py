"""Motor: tipo MIME real vs extensión (detección de disfraz)."""
import os
import subprocess

from app.safeattach.analyzers.base import Analyzer
from app.safeattach.verdict import MALICIOUS, Finding

DANGEROUS = {"application/x-executable", "application/x-dosexec",
             "application/x-msdos-program", "application/x-sharedlib",
             "application/x-elf", "application/x-mach-binary"}


class FileType(Analyzer):
    name = "filetype"

    def analyze(self, path, content, report):
        try:
            r = subprocess.run(["file", "--mime-type", path],
                               capture_output=True, text=True, timeout=10)
            mime = r.stdout.split(":")[1].strip() if ":" in r.stdout else ""
            report.engines["mime_real"] = mime
            ext = os.path.splitext(report.filename)[1]
            if mime in DANGEROUS:
                report.findings.append(
                    Finding("filetype", MALICIOUS,
                            f"ejecutable real ({mime}) con extensión {ext}"))
        except Exception:
            report.engines["mime_real"] = "error"
