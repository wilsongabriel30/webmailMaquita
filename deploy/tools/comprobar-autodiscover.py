#!/usr/bin/env python3
"""Comprueba, dominio por dominio, que Outlook y los celulares van a poder autoconfigurarse.

Para cada dominio de correo (los activos de maildb, o los que se pasen): DNS público por DoH
(`autodiscover.<d>`, `_autodiscover._tcp`, `MX`), certificado que presenta el host al que apunta
(¿cubre `autodiscover.<d>`?), respuesta real del autodiscover por HTTPS (XML de ActiveSync) y la
redirección de respaldo por HTTP (puerto 80, lo que Outlook prueba si el TLS falla).

Uso:  cd /opt/maquita-webmail/backend && venv/bin/python ../deploy/tools/comprobar-autodiscover.py [dominio ...]
      variables: MAIL_HOST (canónico, por defecto mail.maquita.org)
Sale con 1 si algún dominio cuyo correo ya entra aquí (MX) o cuyo autodiscover apunta aquí no autoconfigura.
"""

import os
import socket
import ssl
import sys

import httpx

MAIL_HOST = os.getenv("MAIL_HOST", "mail.maquita.org")
DOH = "https://dns.google/resolve"
XML = (
    '<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/mobilesync/requestschema/2006">'
    "<Request><EMailAddress>{correo}</EMailAddress><AcceptableResponseSchema>"
    "http://schemas.microsoft.com/exchange/autodiscover/mobilesync/responseschema/2006"
    "</AcceptableResponseSchema></Request></Autodiscover>"
)


def doh(nombre, tipo):
    try:
        r = httpx.get(DOH, params={"name": nombre, "type": tipo}, timeout=8)
        return [
            a["data"].rstrip(".")
            for a in r.json().get("Answer", [])
            if a.get("type") in (1, 5, 15, 33)
        ]
    except Exception:
        return []


def ip_publica_canonica():
    ips = [x for x in doh(MAIL_HOST, "A") if x.replace(".", "").isdigit()]
    return ips[0] if ips else ""


def san_del_host(nombre, ip):
    """Nombres del certificado que presenta `ip` cuando se le pide `nombre` (SNI)."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, 443), timeout=6) as s, ctx.wrap_socket(
            s, server_hostname=nombre
        ) as t:
            cert = t.getpeercert(binary_form=True)
        import subprocess

        out = subprocess.run(
            ["openssl", "x509", "-noout", "-ext", "subjectAltName"],
            input=ssl.DER_cert_to_PEM_cert(cert),
            capture_output=True,
            text=True,
        ).stdout
        import re

        return re.findall(r"DNS:([^,\s]+)", out)
    except Exception:
        return []


def _curl(args):
    """(código HTTP, cuerpo o cabeceras). Sin verificar el certificado: eso ya lo mira san_del_host."""
    import subprocess

    try:
        r = subprocess.run(
            ["curl", "-sk", "-m", "10", "-w", "\n%{http_code}"] + args,
            capture_output=True,
            text=True,
        )
        cuerpo, _, codigo = r.stdout.rpartition("\n")
        return (codigo.strip() or "sin respuesta"), cuerpo
    except Exception as e:
        return type(e).__name__, ""


def cubre(sans, nombre):
    dominio = nombre.split(".", 1)[1]
    return nombre in sans or f"*.{dominio}" in sans


def comprobar(dominio, ip_canonica):
    host = f"autodiscover.{dominio}"
    a = doh(host, "A")
    ips = [x for x in a if x.replace(".", "").isdigit()]
    cname = [x for x in a if not x.replace(".", "").isdigit()]
    srv = doh(f"_autodiscover._tcp.{dominio}", "SRV")
    mx = doh(dominio, "MX")
    apunta_aqui = ip_canonica in ips
    mx_host = mx[0].split(" ")[-1] if mx else ""
    # «nuestro»: el correo ya entra aquí (MX) o el autodiscover ya apunta aquí; en ambos casos debe autoconfigurar.
    nuestro = apunta_aqui or mx_host == MAIL_HOST
    fila = {
        "dominio": dominio,
        "autodiscover": (cname[0] + " → " if cname else "")
        + (",".join(ips) or "sin A"),
        "aquí": "sí" if apunta_aqui else "no",
        "srv": srv[0] if srv else "—",
        "mx": mx_host or "—",
        "cert": "—",
        "https": "—",
        "http80": "—",
    }
    if ips:
        # Desde el propio servidor no se llega a la IP pública (NAT en horquilla): se habla con 127.0.0.1
        # pidiendo el nombre, que es lo que hace un cliente de fuera.
        destino = "127.0.0.1" if ips[0] == ip_canonica else ips[0]
        sans = san_del_host(host, destino)
        fila["cert"] = (
            "cubre" if cubre(sans, host) else ("no cubre" if sans else "sin TLS")
        )
        codigo, cuerpo = _curl(
            [
                "--resolve",
                f"{host}:443:{destino}",
                "-X",
                "POST",
                "-H",
                "Content-Type: text/xml",
                "--data-binary",
                XML.format(correo=f"prueba@{dominio}"),
                f"https://{host}/autodiscover/autodiscover.xml",
            ]
        )
        fila["https"] = codigo + (" ActiveSync" if "MobileSync" in cuerpo else "")
        codigo, cuerpo = _curl(
            [
                "--resolve",
                f"{host}:80:{destino}",
                "-I",
                f"http://{host}/autodiscover/autodiscover.xml",
            ]
        )
        destino_redir = next(
            (
                l.split(":", 1)[1].strip()
                for l in cuerpo.splitlines()
                if l.lower().startswith("location:")
            ),
            "",
        )
        fila["http80"] = (
            f"{codigo} → {destino_redir[:60]}" if codigo in ("301", "302") else codigo
        )
    fila["ok"] = (
        (not nuestro)
        or fila["https"].endswith("ActiveSync")
        or (fila["http80"].startswith("302") and MAIL_HOST in fila["http80"])
    )
    return fila


def dominios_maildb():
    try:
        import asyncio

        import asyncpg

        sys.path.insert(0, os.getcwd())
        from app.config import get_settings

        async def q():
            c = await asyncpg.connect(get_settings().database_url)
            try:
                return [
                    r["domain"]
                    for r in await c.fetch(
                        "SELECT domain FROM domain WHERE active ORDER BY 1"
                    )
                ]
            finally:
                await c.close()

        return asyncio.run(q())
    except Exception as e:
        sys.exit(
            f"no pude leer los dominios de maildb ({type(e).__name__}); pásalos como argumentos"
        )


def main(argv):
    dominios = argv or dominios_maildb()
    ip = ip_publica_canonica()
    print(f"host canónico {MAIL_HOST} → {ip or 'sin A pública'}\n")
    cab = ("dominio", "autodiscover", "aquí", "srv", "mx", "cert", "https", "http80")
    filas = [comprobar(d, ip) for d in dominios]
    anchos = {c: max(len(c), *(len(str(f[c])) for f in filas)) for c in cab}
    print("  ".join(c.ljust(anchos[c]) for c in cab))
    for f in filas:
        print(
            "  ".join(str(f[c]).ljust(anchos[c]) for c in cab)
            + ("" if f["ok"] else "   <- NO autoconfigura")
        )
    malos = [f["dominio"] for f in filas if not f["ok"]]
    print(
        f"\n{len(filas)} dominios; con MX o autodiscover aquí: {sum(1 for f in filas if f['aquí'] == 'sí' or f['mx'] == MAIL_HOST)}; de esos, sin autoconfiguración: {len(malos)}"
    )
    print(
        "Los que no apuntan aquí todavía (otro servidor) se resuelven el día del corte: ver OPERACION.md «Autodiscover por dominio»."
    )
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
