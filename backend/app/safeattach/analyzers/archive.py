"""Motor: inspecciona ZIP en busca de ejecutables ocultos."""

import zipfile

from app.safeattach.analyzers.base import Analyzer
from app.safeattach.verdict import SUSPICIOUS, Finding

BAD_EXT = (
    ".exe",
    ".scr",
    ".js",
    ".vbs",
    ".jar",
    ".bat",
    ".cmd",
    ".ps1",
    ".lnk",
    ".hta",
    ".com",
    ".pif",
)


class Archive(Analyzer):
    name = "archive"

    def applies(self, filename, mime):
        return filename.lower().endswith(".zip")

    def analyze(self, path, content, report):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                report.engines["archive"] = f"{len(names)} archivos"
                for n in names:
                    if n.lower().endswith(BAD_EXT):
                        report.findings.append(
                            Finding("archive", SUSPICIOUS, f"ejecutable en zip: {n}")
                        )
        except Exception:
            report.engines["archive"] = "no es zip válido / cifrado"
