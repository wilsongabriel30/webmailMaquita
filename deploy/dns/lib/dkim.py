"""Clave DKIM de cada dominio de correo (selector «mail», RSA 2048, firmada por rspamd).

rspamd busca la clave por el dominio del remitente (/var/lib/rspamd/dkim/<dominio>.mail.key), así que
basta con crearla: no hay que tocar su configuración.
"""

import base64
import grp
import os
import pwd
import subprocess

from comun import DKIM_DIR, SELECTOR_DKIM, ErrorDns, ejecutar


def _ruta(dominio):
    return os.path.join(DKIM_DIR, f"{dominio}.{SELECTOR_DKIM}.key")


def publica(dominio):
    """Clave pública en base64 (el valor «p=» del TXT). La crea si no existe."""
    ruta = _ruta(dominio)
    if not os.path.exists(ruta):
        os.makedirs(DKIM_DIR, mode=0o750, exist_ok=True)
        ejecutar(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", ruta])
        try:
            os.chown(ruta, pwd.getpwnam("_rspamd").pw_uid, grp.getgrnam("_rspamd").gr_gid)
        except KeyError:
            pass
        os.chmod(ruta, 0o640)
    der = subprocess.run(
        ["openssl", "pkey", "-in", ruta, "-pubout", "-outform", "DER"], capture_output=True, timeout=30
    )
    if der.returncode != 0 or not der.stdout:
        raise ErrorDns("no se pudo leer la clave DKIM")
    return base64.b64encode(der.stdout).decode()


def registro(dominio):
    return f"v=DKIM1; k=rsa; p={publica(dominio)}"
