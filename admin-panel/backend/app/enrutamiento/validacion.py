"""Validación del enrutamiento de correo de un dominio. Sin base de datos ni FastAPI: se prueba sola.

Lo que protege:
- que el servidor no quede como relé abierto: el dominio es exacto (sin comodines), la lista de
  destinatarios solo admite direcciones de ESE dominio y, si se pide verificación, no puede estar vacía;
- que no haya bucles: el destino de un reenvío no puede ser este mismo servidor, ni una dirección de
  bucle local, sin especificar, multidifusión o reservada.
"""

import ipaddress
import re

MODOS = ("respaldo", "reenvio")
MAX_DESTINATARIOS = 5000
_ETIQUETA = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
_NOMBRE = re.compile(rf"{_ETIQUETA}(?:\.{_ETIQUETA})+")
_LOCAL = re.compile(r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*")


class ErrorEnrutamiento(ValueError):
    pass


def dominio_valido(valor) -> str:
    dominio = str(valor or "").strip().lower().rstrip(".")
    if len(dominio) > 253 or not _NOMBRE.fullmatch(dominio):
        raise ErrorEnrutamiento("Dominio inválido")
    return dominio


def destino_valido(valor, propios: set[str]) -> str:
    """Nombre de servidor o dirección IP del servidor que recibe el reenvío."""
    texto = str(valor or "").strip().lower().rstrip(".")
    if texto.startswith("[") and texto.endswith("]"):
        texto = texto[1:-1]
    if not texto:
        raise ErrorEnrutamiento("Indique el servidor de destino")
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        ip = None
    if ip is not None:
        if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_reserved or ip.is_link_local:
            raise ErrorEnrutamiento("El destino no puede ser una dirección local, sin especificar o reservada")
        return ip.compressed
    if len(texto) > 253 or not _NOMBRE.fullmatch(texto):
        raise ErrorEnrutamiento("El servidor de destino debe ser un nombre (mx.example.org) o una dirección IP")
    if texto == "localhost" or texto.endswith(".localhost") or texto in propios:
        raise ErrorEnrutamiento("El destino es este mismo servidor: el correo daría vueltas sin llegar")
    return texto


def puerto_valido(valor) -> int:
    if valor is None or valor == "":
        return 25
    if isinstance(valor, bool) or not re.fullmatch(r"[0-9]{1,5}", str(valor)):
        raise ErrorEnrutamiento("Puerto inválido")
    puerto = int(valor)
    if not 1 <= puerto <= 65535:
        raise ErrorEnrutamiento("Puerto inválido")
    return puerto


def destinatarios_validos(valor, dominio: str) -> list[str]:
    if isinstance(valor, str):
        valor = re.split(r"[\s,;]+", valor)
    if not isinstance(valor, list):
        raise ErrorEnrutamiento("La lista de destinatarios no es válida")
    lista = []
    for d in valor:
        d = str(d or "").strip().lower()
        if not d:
            continue
        local, arroba, suyo = d.rpartition("@")
        if not arroba or suyo != dominio:
            raise ErrorEnrutamiento(f"«{d[:80]}» no es una dirección de {dominio}")
        if len(local) > 64 or not _LOCAL.fullmatch(local):
            raise ErrorEnrutamiento(f"«{d[:80]}» no es una dirección válida")
        if d not in lista:
            lista.append(d)
    if len(lista) > MAX_DESTINATARIOS:
        raise ErrorEnrutamiento(f"Demasiados destinatarios (máximo {MAX_DESTINATARIOS})")
    return lista


def _booleano(datos: dict, clave: str, defecto: bool) -> bool:
    valor = datos.get(clave, defecto)
    if not isinstance(valor, bool):
        raise ErrorEnrutamiento(f"«{clave}» debe ser verdadero o falso")
    return valor


def normalizar(dominio: str, datos, propios: set[str] = frozenset()) -> dict:
    """Configuración lista para guardar, o ErrorEnrutamiento con el motivo."""
    if not isinstance(datos, dict):
        raise ErrorEnrutamiento("Datos inválidos")
    dominio = dominio_valido(dominio)
    modo = datos.get("modo")
    if modo not in MODOS:
        raise ErrorEnrutamiento("Modo inválido: «respaldo» (MX de respaldo) o «reenvio» (reenvío a otro servidor)")
    config = {
        "dominio": dominio, "modo": modo, "destino_host": None, "destino_puerto": None,
        "tls_obligatorio": _booleano(datos, "tls_obligatorio", False),
        "verificar_destinatarios": _booleano(datos, "verificar_destinatarios", False),
        "activo": _booleano(datos, "activo", True),
        "destinatarios": destinatarios_validos(datos.get("destinatarios") or [], dominio),
    }
    if modo == "reenvio":
        config["destino_host"] = destino_valido(datos.get("destino_host"), {p.lower() for p in propios})
        config["destino_puerto"] = puerto_valido(datos.get("destino_puerto"))
    elif config["tls_obligatorio"]:
        raise ErrorEnrutamiento("El TLS obligatorio solo se aplica al reenvío a un servidor fijo")
    if config["verificar_destinatarios"] and not config["destinatarios"]:
        raise ErrorEnrutamiento("Con la verificación activa hace falta al menos un destinatario válido")
    return config


def siguiente_salto(config: dict) -> str | None:
    """Lo que Postfix usará como transporte (el mismo texto que arma pgsql-enrutamiento-transporte.cf)."""
    if config["modo"] != "reenvio":
        return None
    return f"smtp:[{config['destino_host']}]:{config['destino_puerto']}"
