"""Salud de accesos externos (IMAP/POP) — observabilidad del panel admin.

Externo = login Dovecot con rip distinto de localhost (el webmail entra desde 127.0.0.1).
0 accesos externos durante horas hábiles indica que los clientes (celular/Outlook) no pueden
conectar — el patrón del incidente de migración. Lectura del log (www-data está en grupo adm).
"""

import datetime
import re

_LOGS = ["/var/log/mail.log", "/var/log/mail.log.1"]
_RE = re.compile(
    r"^(\S+)\s.*?(imap|pop3)-login: Logged in: user=<([^>]+)>.*?rip=([0-9a-fA-F:.]+)"
)
_INTERNAL = {"127.0.0.1", "::1", ""}


def login_health(hours: int = 24) -> dict:
    now = datetime.datetime.now().astimezone()
    cutoff = now - datetime.timedelta(hours=hours)
    external = 0
    internal = 0
    by_protocol = {"imap": 0, "pop3": 0}
    last_external = None
    last_ts = None

    for path in _LOGS:
        try:
            fh = open(path, errors="ignore")
        except FileNotFoundError:
            continue
        with fh:
            for line in fh:
                m = _RE.match(line)
                if not m:
                    continue
                ts_s, proto, user, rip = m.groups()
                try:
                    ts = datetime.datetime.fromisoformat(ts_s)
                except ValueError:
                    continue
                if ts < cutoff:
                    continue
                if rip in _INTERNAL:
                    internal += 1
                else:
                    external += 1
                    by_protocol[proto] = by_protocol.get(proto, 0) + 1
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
                        last_external = {
                            "user": user,
                            "ip": rip,
                            "time": ts.isoformat(),
                        }

    return {
        "window_hours": hours,
        "external_count": external,
        "internal_count": internal,
        "by_protocol": by_protocol,
        "last_external": last_external,
        "ok": external > 0,
        "note": "0 accesos externos puede indicar que los clientes (celular/Outlook) no logran conectar.",
    }
