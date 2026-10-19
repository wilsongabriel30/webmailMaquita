#!/usr/bin/env python3
"""Instala Adminer (Apache 2.0 / GPLv2) para el panel: archivo compilado y el complemento oficial
login-servers, ambos de la última versión de GitHub (vrana/adminer) con su SHA-256. Uso: como root."""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, "/usr/local/lib/maquita-sitios")
from apps import descargas  # noqa: E402
from comun import ErrorSitio  # noqa: E402

DESTINO = "/usr/local/share/adminer-panel"
try:
    version, url, sha = descargas.github_ultima("vrana/adminer", r"adminer-[0-9.]+\.php")
    _, url_zip, sha_zip = descargas.github_ultima("vrana/adminer", r"adminer-[0-9.]+\.zip")
except ErrorSitio as e:
    # Ya instalado: se conserva el actual y se intenta actualizar la próxima vez (no detiene la instalación).
    if os.path.exists(os.path.join(DESTINO, "index.php")):
        print(f"Adminer: se conserva el instalado ({e})")
        sys.exit(0)
    sys.exit(f"Adminer: {e}")
with tempfile.TemporaryDirectory() as tmp:
    descargas.descargar(url, os.path.join(tmp, "adminer.php"))
    descargas.comprobar(os.path.join(tmp, "adminer.php"), sha, "sha256", "Adminer")
    descargas.descargar(url_zip, os.path.join(tmp, "adminer.zip"))
    descargas.comprobar(os.path.join(tmp, "adminer.zip"), sha_zip, "sha256", "Adminer")
    descargas.extraer(os.path.join(tmp, "adminer.zip"), os.path.join(tmp, "fuente"))
    complemento = os.path.join(tmp, "fuente", "plugins", "login-servers.php")
    os.makedirs(os.path.join(DESTINO, "adminer-plugins"), exist_ok=True)
    shutil.copyfile(os.path.join(tmp, "adminer.php"), os.path.join(DESTINO, "index.php"))
    shutil.copyfile(complemento, os.path.join(DESTINO, "adminer-plugins", "login-servers.php"))
print(f"Adminer {version} instalado en {DESTINO}")
