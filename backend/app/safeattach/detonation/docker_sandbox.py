"""Detonación dinámica AISLADA en contenedor Docker.

NUNCA ejecuta el archivo en el host: lo corre dentro de un contenedor
efímero sin red, sin privilegios, con límites de CPU/memoria y timeout.
Best-effort: si docker o la imagen no están, se omite sin romper el envío.
Se habilita con SAFEATTACH_DETONATE=1 una vez construida la imagen
(ver deploy/safeattach/README.md).
"""

import os
import shutil
import subprocess
import tempfile

from app.safeattach.analyzers.base import Analyzer
from app.safeattach.verdict import MALICIOUS, SUSPICIOUS, Finding

IMAGE = os.getenv("SAFEATTACH_SANDBOX_IMAGE", "maquita-safeattach-sandbox")
ENABLED = os.getenv("SAFEATTACH_DETONATE", "0") == "1"
TIMEOUT = int(os.getenv("SAFEATTACH_DETONATE_TIMEOUT", "90"))


class DockerSandbox(Analyzer):
    name = "detonation"

    def applies(self, filename, mime):
        return ENABLED

    def analyze(self, path, content, report):
        if not ENABLED:
            report.engines["detonation"] = "deshabilitado"
            return
        if not shutil.which("docker"):
            report.engines["detonation"] = "docker no disponible"
            return
        work = tempfile.mkdtemp(prefix="detonate_")
        try:
            base = os.path.basename(report.filename) or "sample"
            sample = os.path.join(work, base)
            with open(sample, "wb") as f:
                f.write(content)
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:size=256m,exec",
                "-e",
                "HOME=/tmp",
                "--memory",
                "512m",
                "--cpus",
                "1",
                "--pids-limit",
                "128",
                "--user",
                "nobody",
                "--security-opt",
                "no-new-privileges",
                "-v",
                f"{work}:/sample:ro",
                IMAGE,
                "/sample/" + base,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
            out = (r.stdout or "").strip()
            report.engines["detonation"] = out[:1000] or "sin observaciones"
            low = out.lower()
            if "malicious" in low or "malware" in low:
                report.findings.append(
                    Finding(
                        "detonation", MALICIOUS, "comportamiento malicioso en sandbox"
                    )
                )
            elif "suspicious" in low:
                report.findings.append(
                    Finding(
                        "detonation", SUSPICIOUS, "comportamiento sospechoso en sandbox"
                    )
                )
        except subprocess.TimeoutExpired:
            report.engines["detonation"] = "timeout"
            report.findings.append(
                Finding(
                    "detonation", SUSPICIOUS, "el análisis dinámico excedió el tiempo"
                )
            )
        except FileNotFoundError:
            report.engines["detonation"] = "docker no disponible"
        finally:
            shutil.rmtree(work, ignore_errors=True)
