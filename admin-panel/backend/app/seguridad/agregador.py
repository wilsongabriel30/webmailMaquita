"""Eventos → totales por hora (lo que guarda el recolector). Funciones puras, sin base de datos."""

from __future__ import annotations

import ipaddress
from collections import Counter, defaultdict
from datetime import datetime, timezone

from .parseo import EventoAcceso, EventoCorreo

COLUMNAS_FLUJO = ("recibidos", "enviados", "rebotados", "diferidos", "rechazados", "rechazados_filtro")
_TIPO_A_COLUMNA = {"recibido": "recibidos", "enviado": "enviados", "rebotado": "rebotados",
                   "diferido": "diferidos", "rechazado": "rechazados", "rechazado_filtro": "rechazados_filtro"}

# Acciones de Rspamd (/stat) → columna del flujo.
ACCIONES_RSPAMD = {"reject": "spam_rechazado", "add header": "spam_marcado", "rewrite subject": "spam_marcado",
                   "greylist": "spam_aplazado", "soft reject": "spam_aplazado"}


def hora_de(momento: datetime) -> datetime:
    return momento.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def agregar_correo(eventos) -> dict:
    """{hora: Counter(columna → total)}."""
    salida: dict = defaultdict(Counter)
    for e in eventos:
        if isinstance(e, EventoCorreo) and e.tipo in _TIPO_A_COLUMNA:
            salida[hora_de(e.momento)][_TIPO_A_COLUMNA[e.tipo]] += 1
    return dict(salida)


def agregar_accesos(eventos) -> dict:
    """{(hora, servicio, cuenta, ip): {"pais", "ok", "fallos"}}.

    ActiveSync: el teléfono repite la petición cada pocos minutos con la misma clave; un acceso
    correcto cuenta una vez por hora, cuenta e IP (si no, el tablero mediría el sondeo, no los inicios
    de sesión). Los fallos sí cuentan todos."""
    salida: dict = {}
    for e in eventos:
        if not isinstance(e, EventoAcceso):
            continue
        clave = (hora_de(e.momento), e.servicio, e.cuenta, e.ip)
        fila = salida.setdefault(clave, {"pais": e.pais, "ok": 0, "fallos": 0})
        if e.pais and not fila["pais"]:
            fila["pais"] = e.pais
        if e.resultado == "ok":
            fila["ok"] = 1 if e.servicio == "activesync" else fila["ok"] + e.veces
        else:
            fila["fallos"] += e.veces
    return salida


def delta_rspamd(anterior: dict | None, actual: dict | None) -> dict:
    """Diferencia entre dos lecturas de /stat de Rspamd (contadores acumulados desde su arranque).

    Si un contador baja, Rspamd se reinició: lo que cuenta ahora es todo nuevo."""
    if not actual:
        return {}

    def _cifras(stat):
        acciones = (stat or {}).get("actions") or {}
        cifras = Counter({"analizados": int((stat or {}).get("scanned") or 0)})
        for accion, columna in ACCIONES_RSPAMD.items():
            cifras[columna] += int(acciones.get(accion) or 0)
        return cifras

    if anterior is None:
        return {}  # primera lectura: solo sirve de punto de partida
    ahora, antes = _cifras(actual), _cifras(anterior)
    reinicio = ahora["analizados"] < antes["analizados"]
    salida = {}
    for columna, valor in ahora.items():
        d = valor if reinicio else valor - antes.get(columna, 0)
        salida[columna] = max(0, d)
    return salida


def _redes(textos) -> list:
    redes = []
    for t in textos:
        try:
            redes.append(ipaddress.ip_network(t, strict=False))
        except ValueError:
            continue
    return redes


REDES_PASARELA_DEFECTO = ("127.0.0.0/8", "::1/128", "172.17.0.0/16")


def filtro_pasarela(textos=REDES_PASARELA_DEFECTO):
    """Devuelve una función que dice si un evento de IMAP/SMTP viene de una pasarela propia.

    El webmail y ActiveSync (Z-Push, en su contenedor) entran a Dovecot y a Postfix con la clave de
    la persona desde 127.0.0.1 o la red de Docker: esos accesos ya se cuentan en su puerta de entrada
    (webmail, activesync) y contarlos otra vez como IMAP falsearía el tablero."""
    redes = _redes(textos)

    def es_pasarela(e: EventoAcceso) -> bool:
        if e.servicio not in ("imap", "pop3", "smtp") or not e.ip:
            return False
        try:
            ip = ipaddress.ip_address(e.ip)
        except ValueError:
            return False
        return any(ip in r for r in redes if r.version == ip.version)

    return es_pasarela
