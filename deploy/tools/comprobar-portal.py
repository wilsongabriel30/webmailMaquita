#!/usr/bin/env python3
"""Comprueba que un portal de empresa está listo ANTES de darlo de alta.

Uso:  comprobar-portal.py mail.empresa.example [--servidor 192.0.2.10]

Un portal activo hace que a las cuentas de esa empresa se les entregue ese nombre como
servidor de correo (Outlook, teléfonos, enlaces). Si el nombre no resuelve, o no está en el
certificado de la web, de IMAP o de SMTP, esas cuentas dejan de poder configurarse.

Comprueba: que el nombre resuelve, y que el certificado que se presenta en 443, 993 y 465
es válido para ese nombre y no está por vencer. Con --servidor se conecta a esa dirección en
vez de a la que diga el DNS (para probar antes de publicar el registro).

Sale con 0 si todo está bien y con 1 si algo falla.
"""
import socket
import ssl
import sys
from datetime import datetime, timezone

PUERTOS = ((443, "web"), (993, "IMAP"), (465, "SMTP"))
DIAS_MINIMOS = 15


def certificado(nombre: str, puerto: int, destino: str) -> tuple[bool, str]:
    contexto = ssl.create_default_context()
    try:
        with socket.create_connection((destino, puerto), timeout=8) as s:
            with contexto.wrap_socket(s, server_hostname=nombre) as tls:
                vence = datetime.strptime(tls.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except ssl.SSLCertVerificationError as e:
        return False, f"el certificado no vale para este nombre ({e.verify_message})"
    except (OSError, ssl.SSLError) as e:
        return False, f"no se pudo conectar ({e})"
    dias = (vence - datetime.now(timezone.utc)).days
    if dias < DIAS_MINIMOS:
        return False, f"el certificado vence en {dias} días"
    return True, f"certificado válido, vence en {dias} días"


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    nombre = argv[0].strip().lower().rstrip(".")
    destino = argv[argv.index("--servidor") + 1] if "--servidor" in argv else None
    bien = True
    try:
        direcciones = sorted({i[4][0] for i in socket.getaddrinfo(nombre, 443, proto=socket.IPPROTO_TCP)})
        print(f"  bien   DNS: {nombre} -> {', '.join(direcciones)}")
    except OSError:
        print(f"  {'aviso' if destino else 'FALLA'}  DNS: {nombre} no resuelve")
        bien = bool(destino)
    for puerto, servicio in PUERTOS:
        ok, detalle = certificado(nombre, puerto, destino or nombre)
        print(f"  {'bien ' if ok else 'FALLA'}  {servicio} ({puerto}): {detalle}")
        bien = bien and ok
    print("Listo para darlo de alta." if bien else "NO lo des de alta todavía: corrige lo que falla.")
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
