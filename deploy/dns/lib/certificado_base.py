"""Piezas comunes de los certificados del correo: nombre del servidor, dominio principal, modo y certbot.

Lo usan el certificado del servidor (certificado.py) y los certificados por dominio de cliente
(certificado_dominios.py, certificado_sni.py).

REGLA DANE: toda petición a certbot pasa por pedir(), que siempre lleva «--reuse-key --key-type ecdsa».
La clave del linaje del servidor no cambia nunca en una renovación ni al ampliar o reducir sus nombres:
si cambiara, los registros TLSA publicados dejarían de coincidir y los servidores que validan DANE
dejarían de entregar el correo de todos los dominios. Los linajes por dominio usan lo mismo, por si sus
dueños publican TLSA más adelante. Aquí no se borra ningún linaje.
"""

import os
import re
import shutil
import time

import comprobar
import zona as Z
from comun import ErrorDns, ejecutar

WEBROOT = "/var/www/certbot"
LIVE = "/etc/letsencrypt/live"
SNAKEOIL = ("/etc/ssl/certs/ssl-cert-snakeoil.pem", "/etc/ssl/private/ssl-cert-snakeoil.key")
MODOS = ("compartido", "por-dominio")
RE_HOST = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class ErrorConfiguracion(ErrorDns):
    """Falta o sobra algo en la configuración del servidor: reintentar cada media hora no lo arregla."""


def fichero_org():
    return os.getenv("ORG_FICHERO", "/etc/maquita-mail/organizacion.env")


def org(clave, defecto=""):
    """Valor de /etc/maquita-mail/organizacion.env (CLAVE=valor, con o sin comillas)."""
    try:
        with open(fichero_org(), encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea.startswith(clave + "="):
                    return linea.split("=", 1)[1].split(" #", 1)[0].strip().strip("\"'") or defecto
    except OSError:
        pass
    return defecto


def modo():
    """«compartido» (por defecto: un certificado para todos los dominios) o «por-dominio» (hospedaje)."""
    valor = org("CERTIFICADO_MODO", "compartido").lower()
    if valor not in MODOS:
        raise ErrorConfiguracion(f"CERTIFICADO_MODO={valor} no es válido en {fichero_org()}: use «compartido» o «por-dominio»")
    return valor


def dominio_principal(host, zonas=None):
    """Dominio de la organización que administra el servidor (correo de contacto de Let's Encrypt).

    En orden: mail.<dominio> (lo de siempre, para no cambiar nada a quien ya funciona); ORG_DOMINIO de
    organizacion.env; la zona más corta de este servidor que contiene el nombre; el nombre sin su
    primera etiqueta (hosting.example.org → example.org)."""
    if host.startswith("mail."):
        return host[len("mail."):]
    declarado = org("ORG_DOMINIO").lower().rstrip(".")
    if RE_HOST.match(declarado):
        return declarado
    if zonas is None:
        zonas = [z["zona"] for z in Z.listar()]
    contienen = sorted((z for z in zonas if host == z or host.endswith("." + z)), key=len)
    if contienen:
        return contienen[0]
    return host.split(".", 1)[1]


def principal():
    """(nombre del servidor, dominio principal). El nombre del servidor es el linaje del certificado del
    servidor y su nombre principal, tal cual (mail.<dominio>, hosting.<dominio>, correo.<dominio>…)."""
    try:
        host = ejecutar(["postconf", "-h", "myhostname"]).strip().lower().rstrip(".")
    except ErrorDns as e:
        raise ErrorConfiguracion(f"no se pudo leer el nombre del servidor de correo ({e})")
    if not RE_HOST.match(host) or host.count(".") < 2:
        raise ErrorConfiguracion(f"el nombre del servidor de correo ({host or 'vacío'}) no es un nombre completo "
                                 "del tipo servidor.dominio.tld (postconf myhostname, MAIL_HOST)")
    return host, dominio_principal(host)


def rutas(linaje):
    vivo = f"{LIVE}/{linaje}"
    return f"{vivo}/fullchain.pem", f"{vivo}/privkey.pem"


def existe(linaje):
    cadena, llave = rutas(linaje)
    return os.path.exists(cadena) and os.path.exists(llave)


def leer_certificado(linaje):
    """{"nombres": [...], "vence": "..."} del certificado vigente del linaje, o None si no existe."""
    pem = f"{LIVE}/{linaje}/cert.pem"
    if not os.path.exists(pem):
        return None
    salida = ejecutar(["openssl", "x509", "-in", pem, "-noout", "-enddate", "-ext", "subjectAltName"])
    nombres = sorted(re.findall(r"DNS:([^,\s]+)", salida))
    vence = next((l.split("=", 1)[1] for l in salida.splitlines() if l.startswith("notAfter=")), "")
    return {"nombres": nombres, "vence": vence}


def apunta(nombre, ip):
    respuesta, _ = comprobar._consultar(nombre, "A")
    return bool(respuesta) and ip in respuesta


def pedir(linaje, nombres, correo):
    """Emite, amplía o reduce el linaje con validación webroot. Nunca cambia la clave (ver REGLA DANE)."""
    os.makedirs(WEBROOT, exist_ok=True)
    args = ["certbot", "certonly", "--webroot", "-w", WEBROOT, "--non-interactive", "--agree-tos",
            "-m", correo, "--cert-name", linaje, "--expand", "--keep-until-expiring",
            # --reuse-key: la clave no cambia en cada renovación ni al cambiar los nombres (DANE/TLSA).
            "--reuse-key", "--key-type", "ecdsa"]
    for n in nombres:
        args += ["-d", n]
    ejecutar(args, tiempo=600)


def respaldar(ruta, carpeta=None):
    """Copia con fecha junto al archivo, o en «carpeta» (los de nginx van a /etc/nginx/respaldos/)."""
    if os.path.exists(ruta):
        destino = ruta
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
            destino = os.path.join(carpeta, os.path.basename(ruta))
        shutil.copy2(ruta, f"{destino}.bak.{time.strftime('%Y%m%d%H%M%S')}")


def reemplazar(ruta, cambios):
    with open(ruta) as f:
        texto = f.read()
    nuevo = texto
    for viejo, nuevo_valor in cambios:
        nuevo = nuevo.replace(viejo, nuevo_valor)
    if nuevo != texto:
        respaldar(ruta)
        with open(ruta, "w") as f:
            f.write(nuevo)
        return True
    return False
