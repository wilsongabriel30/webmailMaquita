#!/usr/bin/env python3
"""Corre DENTRO del contenedor aislado (sin red, sin privilegios, FS de solo
lectura salvo /tmp). Analiza el adjunto y emite un veredicto en stdout.
La última línea es SIEMPRE una de: clean | suspicious | malicious
(la lee el host en docker_sandbox.py)."""
import json
import os
import subprocess
import sys

OFFICE = (".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf",
          ".docm", ".xlsm", ".pptm")


def worst(a, b):
    order = {"clean": 0, "suspicious": 1, "malicious": 2}
    return a if order[a] >= order[b] else b


def main():
    if len(sys.argv) < 2:
        print("clean"); return
    path = sys.argv[1]
    verdict, notes = "clean", []
    ext = os.path.splitext(path)[1].lower()

    if ext in OFFICE:
        # 1) Macros (olevba)
        try:
            r = subprocess.run(["olevba", "--json", path],
                               capture_output=True, text=True, timeout=60)
            data = json.loads(r.stdout) if r.stdout.strip() else []
            for it in (data if isinstance(data, list) else []):
                if not isinstance(it, dict):
                    continue
                if it.get("type") == "AutoExec":
                    verdict = worst(verdict, "malicious"); notes.append("macro autoexec")
                elif it.get("type") == "Suspicious":
                    verdict = worst(verdict, "suspicious"); notes.append("macro sospechosa")
        except Exception as e:
            notes.append(f"olevba: {e}")

        # 2) Render headless: detona fallos de parsing en aislamiento + detecta drops
        before = set(os.listdir("/tmp"))
        try:
            subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf",
                            "--outdir", "/tmp", path],
                           capture_output=True, timeout=70)
        except Exception as e:
            verdict = worst(verdict, "suspicious"); notes.append(f"render falló: {e}")
        dropped = set(os.listdir("/tmp")) - before
        dropped = {d for d in dropped if not d.endswith(".pdf")}
        if dropped:
            verdict = worst(verdict, "suspicious")
            notes.append("archivos generados: " + ",".join(list(dropped)[:5]))

    print(json.dumps({"verdict": verdict, "notes": notes}))
    print(verdict)


if __name__ == "__main__":
    main()
