"""Llamadas a maquita-sitios y maquita-dns, con el validador de maquita-sudo como segunda barrera.

El intermediario ya decide qué orden y qué argumentos salen de cada petición; aun así, antes de ejecutar,
los argumentos pasan por validar_sitios / validar_dns del envoltorio sudo del panel general (el mismo
archivo instalado, cargado como módulo). Si el envoltorio no los admitiría, aquí tampoco se ejecutan.
"""

import importlib.machinery
import importlib.util
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys

import rutas
from errores import ErrorPortal

_sudo = None
_registro = None


def registro():
    """Syslog (auth) con la marca MAQUITA_SITIOS_PORTAL; sin /dev/log (pruebas), a stderr."""
    global _registro
    if _registro is None:
        _registro = logging.getLogger("maquita-sitios-portal")
        try:
            h = logging.handlers.SysLogHandler(address="/dev/log", facility=logging.handlers.SysLogHandler.LOG_AUTH)
        except OSError:
            h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("maquita-sitios-portal: %(message)s"))
        _registro.addHandler(h)
        _registro.setLevel(logging.INFO)
    return _registro


def _envoltorio():
    global _sudo
    if _sudo is None:
        if not os.path.isfile(rutas.MAQUITA_SUDO):
            raise ErrorPortal(503, "Los sitios web no están instalados en este servidor")
        cargador = importlib.machinery.SourceFileLoader("maquita_sudo_portal", rutas.MAQUITA_SUDO)
        spec = importlib.util.spec_from_loader("maquita_sudo_portal", cargador)
        modulo = importlib.util.module_from_spec(spec)
        cargador.exec_module(modulo)
        _sudo = modulo
    return _sudo


def validar(programa, args):
    """Devuelve los argumentos si el envoltorio sudo los admitiría; si no, 400."""
    ms = _envoltorio()
    if any(not isinstance(a, str) or not a or len(a) > 40000 or re.search(r"[\x00-\x1f\x7f]", a) for a in args):
        raise ErrorPortal(400, "Datos no válidos")
    try:
        return (ms.validar_sitios if programa == "maquita-sitios" else ms.validar_dns)(list(args))
    except ms.Rechazo:
        raise ErrorPortal(400, "Datos no válidos")


def _correr(orden, tiempo):
    return subprocess.run(orden, capture_output=True, text=True, timeout=tiempo, cwd="/",
                          env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"})


def ejecutar(programa, args, tiempo=300):
    """Ejecuta el ayudante (como root, con entorno limpio) y devuelve su JSON. {"error"} ⇒ 400."""
    binario = rutas.MAQUITA_SITIOS if programa == "maquita-sitios" else rutas.MAQUITA_DNS
    validados = validar(programa, args)
    if not os.path.isfile(binario):
        if programa == "maquita-sitios":
            raise ErrorPortal(503, "Los sitios web no están instalados en este servidor")
        raise ErrorPortal(503, "Las zonas DNS no se gestionan en este servidor")
    try:
        r = _correr([binario] + validados, tiempo)
    except subprocess.TimeoutExpired:
        raise ErrorPortal(503, "La operación tardó demasiado; revise el estado del sitio en unos minutos")
    try:
        datos = json.loads((r.stdout or "").strip() or "null")
    except ValueError:
        datos = None
    if isinstance(datos, dict) and datos.get("error"):
        raise ErrorPortal(400, str(datos["error"])[:400])
    if r.returncode != 0 or datos is None:
        registro().warning("MAQUITA_SITIOS_PORTAL fallo %s %s: %s", programa, validados[:1],
                           (r.stderr or "").strip()[-300:])
        raise ErrorPortal(503, "Fallo interno del ayudante (ver registro del sistema)")
    return datos
