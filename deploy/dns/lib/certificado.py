"""Certificado del correo para todos los dominios del servidor (botón «Certificado del correo»).

Un solo certificado de Let's Encrypt (linaje mail.<dominio principal>) que cubre mail., autoconfig.,
autodiscover. y mta-sts. de cada dominio con zona en este servidor, solo los nombres que desde Internet
ya apuntan a la IP del correo. Luego lo usan nginx (webmail, panel, autoconfiguración, MTA-STS), Postfix,
Dovecot y vsftpd, y queda un gancho que los recarga en cada renovación.

Pensado para dominios de una misma organización: el certificado es público (Certificate Transparency)
y lista todos los nombres. Organizaciones que no deben relacionarse van en servidores distintos.
"""

import glob
import os
import re
import shutil
import subprocess
import time

import comprobar
import zona as Z
from comun import ErrorDns, ejecutar, escribir, servidor

WEBROOT = "/var/www/certbot"
NOMBRES_NGINX = "/etc/nginx/snippets/correo-nombres.conf"
GANCHO = "/etc/letsencrypt/renewal-hooks/deploy/servicios-correo.sh"
SNAKEOIL = ("/etc/ssl/certs/ssl-cert-snakeoil.pem", "/etc/ssl/private/ssl-cert-snakeoil.key")
DOVECOT_PROPIO = ("/etc/dovecot/private/dovecot.pem", "/etc/dovecot/private/dovecot.key")


def _principal():
    host = ejecutar(["postconf", "-h", "myhostname"]).strip()
    if not host.startswith("mail."):
        raise ErrorDns(f"el nombre del servidor de correo ({host}) no empieza por «mail.»")
    return host, host[len("mail."):]


def _candidatos(host, dominio_principal):
    zonas = sorted({z["zona"] for z in Z.listar()} | {dominio_principal})
    nombres = [host]
    for z in zonas:
        for prefijo in ("mail", "autoconfig", "autodiscover", "mta-sts"):
            n = f"{prefijo}.{z}"
            if prefijo == "mta-sts" and not os.path.exists(f"/etc/nginx/sites-enabled/mta-sts.{z}"):
                continue
            if n not in nombres:
                nombres.append(n)
    return nombres


def _apunta(nombre, ip):
    respuesta, _ = comprobar._consultar(nombre, "A")
    return bool(respuesta) and ip in respuesta


def _respaldar(ruta):
    if os.path.exists(ruta):
        shutil.copy2(ruta, f"{ruta}.bak.{time.strftime('%Y%m%d%H%M%S')}")


def _reemplazar(ruta, cambios):
    with open(ruta) as f:
        texto = f.read()
    nuevo = texto
    for viejo, nuevo_valor in cambios:
        nuevo = nuevo.replace(viejo, nuevo_valor)
    if nuevo != texto:
        _respaldar(ruta)
        with open(ruta, "w") as f:
            f.write(nuevo)
        return True
    return False


def _vhost_correo(host):
    ruta = f"/etc/nginx/sites-available/{host}"
    if not os.path.exists(ruta):
        raise ErrorDns(f"no se encontró el sitio del webmail ({ruta})")
    return ruta


def _nombres_en_nginx(host, nombres):
    """Los mail.<dominio> extra se sirven con el mismo webmail (snippet incluido tras server_name)."""
    extra = [n for n in nombres if n.startswith("mail.") and n != host]
    escribir(NOMBRES_NGINX, "# Generado por el panel (Certificado del correo).\n"
             + (f"server_name {' '.join(extra)};\n" if extra else ""), 0o644)
    ruta = _vhost_correo(host)
    with open(ruta) as f:
        lineas = f.read().split("\n")
    incluir = f"    include {NOMBRES_NGINX};"
    salida, cambiado = [], False
    for i, linea in enumerate(lineas):
        salida.append(linea)
        if linea.strip() == f"server_name {host};" and (i + 1 >= len(lineas) or lineas[i + 1].strip() != incluir.strip()):
            salida.append(incluir)
            cambiado = True
    if cambiado:
        _respaldar(ruta)
        with open(ruta, "w") as f:
            f.write("\n".join(salida))
    ejecutar(["nginx", "-t"])
    ejecutar(["systemctl", "reload", "nginx"])


def _usar_en_servicios(host):
    vivo = f"/etc/letsencrypt/live/{host}"
    cadena, llave = f"{vivo}/fullchain.pem", f"{vivo}/privkey.pem"
    cambios = [(SNAKEOIL[0], cadena), (SNAKEOIL[1], llave)]
    for ruta in [_vhost_correo(host), f"/etc/nginx/sites-available/{host}-admin",
                 "/etc/nginx/sites-available/autodiscover-dominios"] + glob.glob("/etc/nginx/sites-available/mta-sts.*"):
        if os.path.exists(ruta) and ".bak" not in ruta:
            _reemplazar(ruta, cambios)
    ejecutar(["nginx", "-t"])
    actual = ejecutar(["postconf", "-h", "smtpd_tls_cert_file"]).strip()
    if actual != cadena:
        _respaldar("/etc/postfix/main.cf")
        ejecutar(["postconf", "-e", f"smtpd_tls_cert_file={cadena}", f"smtpd_tls_key_file={llave}"])
    for ruta in ("/etc/dovecot/dovecot.conf", "/etc/dovecot/conf.d/10-ssl.conf"):
        if os.path.exists(ruta):
            _reemplazar(ruta, [(f"= {DOVECOT_PROPIO[0]}", f"= {cadena}"), (f"= {DOVECOT_PROPIO[1]}", f"= {llave}"),
                               (f"= {SNAKEOIL[0]}", f"= {cadena}"), (f"= {SNAKEOIL[1]}", f"= {llave}")])
    ejecutar(["doveconf", "-n"])
    if os.path.exists("/etc/vsftpd.conf"):
        _reemplazar("/etc/vsftpd.conf", [(f"rsa_cert_file={SNAKEOIL[0]}", f"rsa_cert_file={cadena}"),
                                          (f"rsa_private_key_file={SNAKEOIL[1]}", f"rsa_private_key_file={llave}")])
    os.makedirs(os.path.dirname(GANCHO), exist_ok=True)
    escribir(GANCHO, "#!/bin/sh\n# Generado por el panel: recarga los servicios que usan el certificado del correo.\n"
             "systemctl reload nginx postfix dovecot 2>/dev/null\nsystemctl restart vsftpd 2>/dev/null || true\n", 0o755)
    subprocess.run(["sh", GANCHO], capture_output=True, timeout=120)


def emitir():
    host, principal = _principal()
    ip = servidor()["ip_correo"]
    candidatos = _candidatos(host, principal)
    incluidos = [n for n in candidatos if _apunta(n, ip)]
    omitidos = [n for n in candidatos if n not in incluidos]
    if host not in incluidos:
        raise ErrorDns(f"{host} todavía no apunta a {ip} desde Internet: espere a que propague el DNS")
    _nombres_en_nginx(host, incluidos)
    os.makedirs(WEBROOT, exist_ok=True)
    args = ["certbot", "certonly", "--webroot", "-w", WEBROOT, "--non-interactive", "--agree-tos",
            "-m", f"postmaster@{principal}", "--cert-name", host, "--expand", "--keep-until-expiring",
            # --reuse-key: la clave no cambia en cada renovación (necesario si algún día se publica DANE).
            "--reuse-key", "--key-type", "ecdsa"]
    for n in incluidos:
        args += ["-d", n]
    ejecutar(args, tiempo=600)
    _usar_en_servicios(host)
    return dict(estado(), incluidos=incluidos, omitidos=omitidos)


def estado():
    host, _ = _principal()
    pem = f"/etc/letsencrypt/live/{host}/cert.pem"
    if not os.path.exists(pem):
        return {"emitido": False, "linaje": host}
    salida = ejecutar(["openssl", "x509", "-in", pem, "-noout", "-enddate", "-ext", "subjectAltName"])
    nombres = sorted(re.findall(r"DNS:([^,\s]+)", salida))
    vence = next((l.split("=", 1)[1] for l in salida.splitlines() if l.startswith("notAfter=")), "")
    return {"emitido": True, "linaje": host, "nombres": nombres, "vence": vence,
            "en_uso": ejecutar(["postconf", "-h", "smtpd_tls_cert_file"]).strip().startswith("/etc/letsencrypt/")}


def automatico():
    """Lo lanza el temporizador (cada 30 min): si algún nombre de correo de cualquier dominio ya apunta a este
    servidor desde Internet y el certificado no lo cubre, lo emite o lo amplía. Así un servidor recién
    conectado, o un dominio nuevo del panel, queda con HTTPS y autoconfiguración sin pulsar nada.

    Solo pide a Let's Encrypt nombres que ya resuelven aquí (los fallidos cuentan para su límite)."""
    import ipaddress

    try:
        ip = servidor()["ip_correo"]
    except ErrorDns:
        return {"accion": "nada", "motivo": "sin IP del servidor (Zonas DNS → Ajustes)"}
    if not ipaddress.ip_address(ip).is_global:
        return {"accion": "nada", "motivo": f"la IP del correo ({ip}) no es pública todavía"}
    host, principal = _principal()
    apuntan = [n for n in _candidatos(host, principal) if _apunta(n, ip)]
    if host not in apuntan:
        return {"accion": "nada", "motivo": f"{host} todavía no apunta a {ip} desde Internet"}
    cubiertos = set(estado().get("nombres") or [])
    nuevos = [n for n in apuntan if n not in cubiertos]
    if not nuevos:
        return {"accion": "nada", "motivo": "el certificado ya cubre todos los nombres que apuntan aquí"}
    return dict(emitir(), accion="emitido", nuevos=nuevos)
