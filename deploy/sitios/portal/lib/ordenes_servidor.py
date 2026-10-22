"""Información del servidor y CPU y memoria de un sitio, desde el portal (v1.11).

«servidor-info» reúne lo que un cliente necesita para configurar sus programas (FTP, correo, DNS) y saber qué
le ofrece el servidor: versiones de PHP instaladas, rutas de sus sitios, IP compartida, servidores de nombres
de SUS dominios, cuotas, puertos de FTP y SFTP y servidores de correo. Nada sensible: ni otros dominios ni
sitios, ni direcciones internas, ni versiones de programas que no le hagan falta.
"""

import glob
import os
import re

import alcance
import ayudantes
import cuotas
import rutas
import sesion
from errores import ErrorPortal
from ordenes_sitios import sitios

RE_VERSION = re.compile(r"[578]\.[0-9]")
# Los de serie de cada sitio (deploy/sitios/lib/plantillas.py y propias_servicio.py).
LIMITES_PHP = {"memoria_mb": 256, "subida_mb": 64, "formulario_mb": 64, "tiempo_s": 120, "procesos": 6}
LIMITES_APP = {"memoria_mb": 768, "cpu_por_ciento": 150, "tareas": 256}


def recursos(ctx):
    return sitios("recursos", ctx.sitio, tiempo=60)


def _leer(ruta, tope=200000):
    try:
        with open(ruta, errors="replace") as f:
            return f.read(tope)
    except OSError:
        return None


def _vsftpd():
    texto = _leer(rutas.VSFTPD)
    if texto is None:
        return None
    valores = {}
    for linea in texto.splitlines():
        clave, _, valor = linea.strip().partition("=")
        if clave and not clave.startswith("#"):
            valores[clave.strip()] = valor.strip()
    puerto = valores.get("listen_port", "21")
    datos = {"puerto": int(puerto) if puerto.isdigit() else 21, "cifrado": valores.get("ssl_enable", "NO").upper() == "YES"}
    if valores.get("pasv_min_port", "").isdigit() and valores.get("pasv_max_port", "").isdigit():
        datos["pasivos"] = f"{valores['pasv_min_port']}-{valores['pasv_max_port']}"
    return datos


def _sftp():
    """Puerto de SSH (el primero que fija sshd, como hace él: sshd_config.d va incluido al principio)."""
    for ruta in sorted(glob.glob(os.path.join(rutas.SSHD_D, "*.conf"))) + [rutas.SSHD]:
        for linea in (_leer(ruta) or "").splitlines():
            partes = linea.split("#", 1)[0].split()
            if len(partes) == 2 and partes[0].lower() == "port" and partes[1].isdigit():
                return int(partes[1])
    return 22


def _php():
    datos = {"instaladas": [], "de_serie": None, "notas": {}}
    base = (_leer(rutas.PHP_BASE, 20) or "").strip()
    if RE_VERSION.fullmatch(base):
        datos["de_serie"] = base
    try:
        estado = sitios("php-estado", tiempo=120)
    except ErrorPortal:
        return datos
    instaladas = [v for v in estado.get("instaladas") or [] if isinstance(v, str) and RE_VERSION.fullmatch(v)]
    notas = estado.get("notas") or {}
    datos.update(instaladas=instaladas, notas={v: str(notas[v])[:200] for v in instaladas if v in notas})
    return datos


def _dns(dominios):
    """IP compartida y servidores de nombres de las zonas de sus dominios que sirve este servidor."""
    if not os.path.isfile(rutas.MAQUITA_DNS):
        return None, {}
    try:
        srv = ayudantes.ejecutar("maquita-dns", ["servidor-ver"], tiempo=60) or {}
    except ErrorPortal:
        return None, {}
    nombres = [n.get("nombre") for n in srv.get("ns") or []
               if isinstance(n, dict) and re.fullmatch(r"ns[1-5]", str(n.get("nombre")))]
    por_dominio = {d: [f"{n}.{d}" for n in nombres] for d in dominios
                   if nombres and os.path.isfile(os.path.join(rutas.ZONAS_DNS, f"{d}.json"))}
    return srv.get("ip_web") or srv.get("ip_correo"), por_dominio


def info(ctx):
    dominios = ctx.admin["dominios"]
    servidor = alcance.mail_host()
    ip, servidores_nombres = _dns(dominios)
    guardadas = sesion.cuotas_guardadas(dominios)
    return {
        "servidor": servidor,
        "ip_compartida": ip,
        "servidores_de_nombres": servidores_nombres,
        "php": _php(),
        "limites_php": LIMITES_PHP,
        "limites_aplicaciones": LIMITES_APP,
        "cuotas": {d: cuotas.de(d, guardadas) for d in dominios},
        "rutas": {"sitio": f"{rutas.RAIZ_SITIOS}/<sitio>", "publica": f"{rutas.RAIZ_SITIOS}/<sitio>/publico",
                  "temporal": f"{rutas.RAIZ_SITIOS}/<sitio>/tmp", "registros": f"{rutas.RAIZ_SITIOS}/<sitio>/registros",
                  "por_sftp": "/publico"},
        "ftp": _vsftpd(),
        "sftp": {"puerto": _sftp()},
        "correo": {"servidor": servidor, "imap": {"puerto": 993, "cifrado": "SSL/TLS"},
                   "smtp": [{"puerto": 465, "cifrado": "SSL/TLS"}, {"puerto": 587, "cifrado": "STARTTLS"}],
                   "autenticacion": "dirección de correo completa y su contraseña"},
        "dns_dinamico": "/nic/update",
    }


ORDENES = {
    "recursos": ("sitio", recursos),
    "servidor-info": ("ninguno", info),
}
