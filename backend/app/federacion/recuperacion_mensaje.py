"""Lo que el servidor del destinatario comprueba en el correo guardado antes de retirarlo.

Solo se atiende la recuperación de un correo que este mismo servidor recibió y autenticó
(DKIM o DMARC del dominio del remitente). La cabecera `Authentication-Results` válida es la
más alta y tiene que ser la de este servidor: las que traiga el correo de fuera no cuentan.
"""

from __future__ import annotations

import email
import re
import socket
import subprocess
from email.message import Message
from email.utils import parseaddr
from urllib.parse import urlparse

from app.config import get_settings

MAQUITA_SUDO = "/usr/local/sbin/maquita-sudo"
_DKIM = re.compile(r"dkim=pass[^;]*?header\.d=([a-z0-9.-]+)")
_DMARC_FROM = re.compile(r"dmarc=pass[^;]*?header\.from=([a-z0-9.-]+)")


def cabeceras(destinatario: str, message_id: str) -> Message | None:
    """Cabeceras del correo en el buzón del destinatario (None si no está)."""
    try:
        r = subprocess.run(
            [
                "sudo",
                "-n",
                MAQUITA_SUDO,
                "doveadm",
                "fetch",
                "-u",
                destinatario,
                "hdr",
                "header",
                "message-id",
                message_id,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    if r.returncode != 0 or "hdr:" not in r.stdout:
        return None
    primera = r.stdout.split("\f")[0].split("hdr:", 1)[1].lstrip("\n")
    return email.message_from_string(primera)


def dominio_from(msg: Message) -> str:
    direccion = parseaddr(str(msg.get("From", "")))[1]
    return direccion.rsplit("@", 1)[-1].strip().lower() if "@" in direccion else ""


def identidades_del_servidor() -> set[str]:
    """Nombres con los que este servidor firma su `Authentication-Results`."""
    s = get_settings()
    crudo = getattr(s, "recall_federado_authserv", "") or ""
    nombres = {n.strip().lower() for n in crudo.split(",") if n.strip()}
    if not nombres:
        nombres = {
            (urlparse(s.public_base_url).hostname or "").lower(),
            socket.getfqdn().lower(),
        }
    return {n for n in nombres if n}


def alineado(firmante: str, dominio: str) -> bool:
    """Alineación relajada: mismo dominio o uno subdominio del otro."""
    return (
        firmante == dominio
        or dominio.endswith("." + firmante)
        or firmante.endswith("." + dominio)
    )


def autenticado(msg: Message, dominio: str, identidades: set[str]) -> bool:
    """¿Este servidor autenticó el correo como del dominio del remitente?"""
    todas = msg.get_all("Authentication-Results") or []
    if not todas or not dominio:
        return False
    texto = " ".join(str(todas[0]).split()).lower()
    servidor = texto.split(";", 1)[0].split()
    if not servidor or servidor[0] not in identidades:
        return False
    if any(alineado(m.group(1), dominio) for m in _DMARC_FROM.finditer(texto)):
        return True
    return any(alineado(m.group(1).strip("."), dominio) for m in _DKIM.finditer(texto))
