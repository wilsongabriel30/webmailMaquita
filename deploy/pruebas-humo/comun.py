"""Datos comunes de las pruebas de humo: a qué servidor y con qué cuentas se prueba.

Todo sale de variables de entorno (o de /etc/maquita-humo.env, si existe), para que las mismas
pruebas sirvan en cualquier instalación:

  HUMO_URL           dirección del correo, p. ej. https://mail.example.org   (obligatoria)
  HUMO_CUENTA        cuenta de pruebas que abre la sesión                    (test@<dominio>)
  HUMO_DESTINO       destinatario de los correos de prueba                    (= HUMO_CUENTA)
  HUMO_PERSONA       segunda cuenta (tareas y reuniones entre dos personas)   (= HUMO_DESTINO)
  HUMO_CONVERSACION  id de una conversación del chat de la cuenta de pruebas  (1)
  HUMO_UID_CORREO    UID de un correo de la bandeja de entrada de la cuenta    (1)
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
