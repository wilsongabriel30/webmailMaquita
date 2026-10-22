"""Líneas de registro → eventos simples (flujo de correo e inicios de sesión).

Funciones puras: reciben texto y devuelven eventos; no leen archivos ni tocan la base. Así se prueban
con líneas sintéticas y el recolector solo se ocupa de leer de dónde toque (archivo o diario).

Formatos que se entienden:
  · syslog clásico      «Oct 21 10:30:01 host postfix/smtpd[123]: …»
  · ISO (rsyslog nuevo) «2026-10-21T10:30:01.123456-05:00 host dovecot: …»
  · journalctl -o short-iso «2026-10-21T10:30:01-0500 host postfix/qmgr[9]: …»
  · nginx «combined» del acceso de ActiveSync (/var/log/nginx/activesync-access.log).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from urllib.parse import parse_qs, unquote, urlsplit

SERVICIOS = ("webmail", "imap", "pop3", "smtp", "activesync", "panel")


@dataclass(frozen=True)
class EventoCorreo:
    momento: datetime
    tipo: str  # recibido | enviado | rebotado | diferido | rechazado | rechazado_filtro


@dataclass(frozen=True)
class EventoAcceso:
    momento: datetime
    servicio: str
    resultado: str  # ok | fallo
    cuenta: str = ""
    ip: str = ""
    veces: int = 1
    pais: str = field(default="", compare=False)


_RE_LINEA = re.compile(
    r"(?P<fecha>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"
    r"|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
    r"\s+\S+\s+(?P<prog>[^\s\[:]+)(?:\[\d+\])?:\s(?P<msg>.*)"
)
_MESES = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
_RE_FECHA_SYSLOG = re.compile(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})")
_RE_DESFASE = re.compile(r"(.*[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)([+-])(\d{2}):?(\d{2})")

# Postfix
_RE_ENTREGA = re.compile(r"[0-9A-Za-z]+: to=<[^>]*>,(?: orig_to=<[^>]*>,)? relay=([^,]+),.*?\bstatus=(\w+)")
_RE_SASL_OK = re.compile(r"[0-9A-Za-z]+: client=[^\[\s]*\[([^\]]+)\](?::\d+)?, sasl_method=[^,]+, sasl_username=([^\s,]+)")
_RE_SASL_FALLO = re.compile(r"warning: [^\[\s]*\[([^\]]+)\](?::\d+)?: SASL \S+ authentication failed:(.*)")
_RE_SASL_USUARIO = re.compile(r"sasl_username=([^\s,]+)")
# Dovecot
_RE_DOVECOT_LOGIN = re.compile(r"(imap|pop3)-login: (?:Info: )?Login: user=<([^>]*)>")
_RE_DOVECOT_FALLO = re.compile(r"(imap|pop3)-login: .*\(auth failed, (\d+) attempts?")
_RE_USER = re.compile(r"\buser=<([^>]*)>")
_RE_RIP = re.compile(r"\brip=([0-9A-Fa-f:.]+)")
# nginx combined
_RE_NGINX = re.compile(r'(\S+) \S+ (\S+) \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d{3}) .*')
_RE_FECHA_NGINX = re.compile(r"(\d{2})/([A-Z][a-z]{2})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})")
_RE_IP = re.compile(r"[0-9A-Fa-f:.]{2,45}")


def _cuenta(texto: str) -> str:
    c = (texto or "").strip().strip("<>").lower()
    return c[:255]


def _ip(texto: str) -> str:
    t = (texto or "").strip()
    return t if _RE_IP.fullmatch(t) else ""


def fecha_registro(texto: str, ahora: datetime, zona: tzinfo) -> datetime | None:
    """Fecha de la cabecera de una línea. El formato syslog clásico no trae año ni zona: se toma la
    zona del servidor y el año de «ahora» (o el anterior si la fecha quedaría en el futuro: enero
    leyendo líneas de diciembre)."""
    m = _RE_FECHA_SYSLOG.fullmatch(texto)
    if m:
        mes = _MESES.get(m.group(1))
        if not mes:
            return None
        try:
            f = datetime(ahora.year, mes, int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), tzinfo=zona)
        except ValueError:
            return None
        if f > ahora + timedelta(days=1):
            f = f.replace(year=ahora.year - 1)
        return f
    t = texto.replace("Z", "+00:00")
    d = _RE_DESFASE.fullmatch(t)
    if d:
        t = f"{d.group(1)}{d.group(2)}{d.group(3)}:{d.group(4)}"
    try:
        f = datetime.fromisoformat(t)
    except ValueError:
        return None
    return f if f.tzinfo else f.replace(tzinfo=zona)


def _es_local(relay: str) -> bool:
    r = relay.lower()
    return "127.0.0.1" in r or "[::1]" in r or r.startswith("localhost")


def analizar_linea(linea: str, ahora: datetime, zona: tzinfo) -> list:
    """Una línea de syslog o del diario → lista (casi siempre vacía o de un elemento) de eventos."""
    m = _RE_LINEA.fullmatch(linea.rstrip("\r\n"))
    if not m:
        return []
    prog, msg = m.group("prog"), m.group("msg")
    es_postfix = prog.startswith("postfix")
    if not es_postfix and not prog.startswith("dovecot"):
        return []
    momento = fecha_registro(m.group("fecha"), ahora, zona)
    if momento is None:
        return []
    if es_postfix:
        return _postfix(prog, msg, momento)
    return _dovecot(msg, momento)


def _postfix(prog: str, msg: str, momento: datetime) -> list:
    if "NOQUEUE: reject:" in msg:
        return [EventoCorreo(momento, "rechazado")]
    if "milter-reject:" in msg:
        return [EventoCorreo(momento, "rechazado_filtro")]
    e = _RE_ENTREGA.search(msg)
    if e:
        relay, estado = e.group(1), e.group(2)
        if estado == "bounced":
            return [EventoCorreo(momento, "rebotado")]
        if estado == "deferred":
            return [EventoCorreo(momento, "diferido")]
        if estado != "sent":
            return []
        agente = prog.rsplit("/", 1)[-1]
        if agente in ("lmtp", "virtual", "local", "pipe") or "lmtp" in relay or "dovecot" in relay:
            return [EventoCorreo(momento, "recibido")]
        if agente == "smtp" and not _es_local(relay):
            return [EventoCorreo(momento, "enviado")]
        return []
    s = _RE_SASL_OK.search(msg)
    if s:
        return [EventoAcceso(momento, "smtp", "ok", _cuenta(s.group(2)), _ip(s.group(1)))]
    f = _RE_SASL_FALLO.search(msg)
    if f:
        u = _RE_SASL_USUARIO.search(f.group(2))
        return [EventoAcceso(momento, "smtp", "fallo", _cuenta(u.group(1)) if u else "", _ip(f.group(1)))]
    return []


def _dovecot(msg: str, momento: datetime) -> list:
    ok = _RE_DOVECOT_LOGIN.search(msg)
    if ok:
        rip = _RE_RIP.search(msg)
        return [EventoAcceso(momento, ok.group(1), "ok", _cuenta(ok.group(2)), _ip(rip.group(1)) if rip else "")]
    fallo = _RE_DOVECOT_FALLO.search(msg)
    if fallo:
        u, rip = _RE_USER.search(msg), _RE_RIP.search(msg)
        veces = max(1, min(int(fallo.group(2)), 100))
        return [EventoAcceso(momento, fallo.group(1), "fallo", _cuenta(u.group(1)) if u else "",
                             _ip(rip.group(1)) if rip else "", veces)]
    return []


def analizar_activesync(linea: str) -> list:
    """Línea del registro de acceso de nginx para /Microsoft-Server-ActiveSync.

    Correcto: respuesta 2xx con usuario. Fallo: 401/403 CON usuario (la primera petición de cada
    teléfono llega sin credenciales y recibe 401: eso es el saludo normal, no un fallo)."""
    m = _RE_NGINX.fullmatch(linea.rstrip("\r\n"))
    if not m:
        return []
    ip, usuario, fecha, metodo, ruta, codigo = m.groups()
    if "microsoft-server-activesync" not in ruta.lower() or metodo == "OPTIONS":
        return []
    f = _RE_FECHA_NGINX.fullmatch(fecha)
    if not f or f.group(2) not in _MESES:
        return []
    desfase = timedelta(hours=int(f.group(8)), minutes=int(f.group(9))) * (1 if f.group(7) == "+" else -1)
    try:
        momento = datetime(int(f.group(3)), _MESES[f.group(2)], int(f.group(1)), int(f.group(4)),
                           int(f.group(5)), int(f.group(6)), tzinfo=timezone(desfase))
    except ValueError:
        return []
    cuenta = "" if usuario == "-" else _cuenta(unquote(usuario))
    if not cuenta:
        cuenta = _cuenta((parse_qs(urlsplit(ruta).query).get("User") or [""])[0])
    codigo = int(codigo)
    if 200 <= codigo < 300 and cuenta:
        return [EventoAcceso(momento, "activesync", "ok", cuenta, _ip(ip))]
    if codigo in (401, 403) and usuario != "-":
        return [EventoAcceso(momento, "activesync", "fallo", cuenta, _ip(ip))]
    return []


# Acciones de la auditoría que cuentan como inicio de sesión.
ACCIONES_WEBMAIL = {"login_success": "ok", "login_failed": "fallo", "login_blocked": "fallo"}
ACCIONES_PANEL = {"login": "ok", "login_failed": "fallo"}


def evento_auditoria(servicio: str, accion: str, cuenta: str, ip: str, momento: datetime) -> EventoAcceso | None:
    """Fila de user_activity_log (webmail) o admin_audit (panel) → evento de acceso."""
    tabla = ACCIONES_WEBMAIL if servicio == "webmail" else ACCIONES_PANEL
    resultado = tabla.get(accion)
    if not resultado or momento is None:
        return None
    c = _cuenta(cuenta)
    if c.startswith("("):  # «(login_attempt)»: el webmail no sabe con qué cuenta se intentó
        c = ""
    return EventoAcceso(momento, servicio, resultado, c, _ip(str(ip or "")))
