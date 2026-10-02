"""Datos de la organización que instala el correo: sus dominios, su red, sus direcciones.

El repositorio es público y sirve a cualquiera. Lo que identifica a quien lo instala no va en
el código: va en el servidor, en un fichero de texto, y aquí solo quedan valores de ejemplo.

DE DÓNDE SALE CADA VALOR, por orden
  1. la variable de entorno con ese nombre (el .env del servicio);
  2. el fichero de la organización, /etc/maquita-mail/organizacion.env (o el que diga
     ORG_FICHERO), con líneas CLAVE="valor" que también puede leer un guion de shell;
  3. el valor de ejemplo escrito en el código.

El fichero se lee una vez por proceso. Las listas se separan con espacios o comas.
Este módulo no importa nada del resto de la aplicación: lo usan también guiones sueltos.
(Hay una copia por aplicación —correo, panel, guiones—: si cambias una, cambia las demás.)
"""

import os
import re
from functools import lru_cache

FICHERO = os.environ.get("ORG_FICHERO", "/etc/maquita-mail/organizacion.env")
FICHERO_DOMINIOS = os.environ.get(
    "ORG_FICHERO_DOMINIOS", "/etc/maquita-mail/dominios-propios.txt"
)
_LINEA = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


@lru_cache(maxsize=1)
def _del_fichero() -> dict:
    valores = {}
    try:
        with open(FICHERO, encoding="utf-8") as f:
            for linea in f:
                if linea.lstrip().startswith("#"):
                    continue
                m = _LINEA.match(linea)
                if m:
                    v = m.group(2)
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    valores[m.group(1)] = v
    except OSError:
        pass
    return valores


def valor(clave: str, defecto: str = "") -> str:
    return os.environ.get(clave) or _del_fichero().get(clave) or defecto


def lista(clave: str, defecto: str = "") -> list:
    return [x for x in re.split(r"[\s,;]+", valor(clave, defecto)) if x]


def dominio_principal() -> str:
    return valor("MAIL_DOMAIN", valor("ORG_DOMINIO", "example.org")).lower()


@lru_cache(maxsize=1)
def dominios_propios() -> frozenset:
    """Los dominios de correo de la casa: ORG_DOMINIOS, el fichero de dominios y el principal."""
    dominios = {d.lower() for d in lista("ORG_DOMINIOS")}
    try:
        with open(FICHERO_DOMINIOS, encoding="utf-8") as f:
            dominios |= {
                l.strip().lower()
                for l in f
                if l.strip() and not l.lstrip().startswith("#")
            }
    except OSError:
        pass
    dominios.add(dominio_principal())
    return frozenset(dominios)


def dominios(clave: str) -> frozenset:
    """Una lista concreta de dominios (p. ej. ORG_DOMINIOS_GRUPOS); si no está, todos los propios."""
    return frozenset(d.lower() for d in lista(clave)) or dominios_propios()


def redes_propias() -> list:
    """Redes de la organización en notación CIDR (ORG_REDES)."""
    return lista("ORG_REDES")


def url(clave: str, defecto: str) -> str:
    return valor(clave, defecto).rstrip("/")


def url_correo() -> str:
    """Dirección pública del correo, la que escribe la gente."""
    return url("PUBLIC_BASE_URL", url("ORG_URL_CORREO", "https://mail.example.org"))


def url_intranet() -> str:
    return url("ORG_URL_INTRANET", "https://intranet.example.org")


def url_reuniones() -> str:
    return url(
        "JITSI_BASE_URL", url("ORG_URL_REUNIONES", "https://reuniones.example.org")
    )


def url_identidad() -> str:
    return url("KC_BASE", url("ORG_URL_IDENTIDAD", "https://auth.example.org"))


def servidor(direccion: str) -> str:
    """'https://mail.example.org:8443/x' -> 'mail.example.org'"""
    return re.sub(r"^[a-z]+://", "", direccion, flags=re.I).split("/")[0].split(":")[0]


def remitente(clave: str, nombre: str, local: str) -> str:
    """Remitente de los avisos del sistema: el configurado o «Nombre <local@dominio principal>»."""
    return valor(
        clave,
        (
            f"{nombre} <{local}@{dominio_principal()}>"
            if nombre
            else f"{local}@{dominio_principal()}"
        ),
    )


def correos_de_avisos() -> list:
    """A quién avisa el sistema cuando algo falla (ORG_CORREOS_AVISOS)."""
    return lista("ORG_CORREOS_AVISOS", f"postmaster@{dominio_principal()}")
