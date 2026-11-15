"""Datos comunes de las pruebas de humo: a qué servidor y con qué cuentas se prueba.

Todo sale de variables de entorno (o de /etc/maquita-humo.env, si existe), para que las mismas
pruebas sirvan en cualquier instalación:

  HUMO_URL           dirección del correo, p. ej. https://mail.example.org   (obligatoria)
  HUMO_CUENTA        cuenta de pruebas que abre la sesión                    (test@<dominio>)
  HUMO_DESTINO       destinatario de los correos de prueba                    (= HUMO_CUENTA)
  HUMO_PERSONA       segunda cuenta (tareas y reuniones entre dos personas)   (= HUMO_DESTINO)
  HUMO_CONVERSACION  id de una conversación del chat de la cuenta de pruebas  (1)
  HUMO_UID_CORREO    UID de un correo de la bandeja de entrada de la cuenta    (1)
  HUMO_CONECTAR      (opcional) a dónde conectarse de verdad, p. ej. https://127.0.0.1 — para servidores
                     detrás de un proxy, donde la dirección pública no responde desde el propio servidor.
                     Se envía el nombre de HUMO_URL en la cabecera Host y no se valida el certificado.
"""

import os
import sys
from urllib.parse import urlparse


def _leer_archivo(ruta="/etc/maquita-humo.env"):
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    clave, valor = linea.split("=", 1)
                    os.environ.setdefault(clave.strip(), valor.strip().strip("\"'"))
    except OSError:
        pass


_leer_archivo()
BASE = os.environ.get("HUMO_URL", "").rstrip("/")
if not BASE.startswith("https://"):
    sys.exit("Falta HUMO_URL (p. ej. HUMO_URL=https://mail.example.org) o en /etc/maquita-humo.env")
HOST = urlparse(BASE).hostname
_DOMINIO = HOST.split(".", 1)[1] if HOST.count(".") >= 2 else HOST
CUENTA = os.environ.get("HUMO_CUENTA", f"test@{_DOMINIO}")
DESTINO = os.environ.get("HUMO_DESTINO", CUENTA)
PERSONA = os.environ.get("HUMO_PERSONA", DESTINO)
CONVERSACION = os.environ.get("HUMO_CONVERSACION", "1")
UID_CORREO = os.environ.get("HUMO_UID_CORREO", "1")
CONECTAR = os.environ.get("HUMO_CONECTAR", "").rstrip("/")


def abrir(peticion_ruta, metodo="GET", datos=None, cabeceras=None, tiempo=25):
    """Abre BASE + ruta; con HUMO_CONECTAR va a esa dirección con el nombre público en Host."""
    import ssl
    import urllib.request

    destino = (CONECTAR or BASE) + peticion_ruta
    r = urllib.request.Request(destino, data=datos, method=metodo)
    for clave, valor in (cabeceras or {}).items():
        r.add_header(clave, valor)
    contexto = None
    if CONECTAR:
        r.add_header("Host", HOST)
        if CONECTAR.startswith("https://"):
            contexto = ssl.create_default_context()
            contexto.check_hostname = False
            contexto.verify_mode = ssl.CERT_NONE
    return urllib.request.urlopen(r, timeout=tiempo, context=contexto)
