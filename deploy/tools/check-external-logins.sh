#!/bin/bash
# check-external-logins.sh — Alerta si hay 0 accesos EXTERNOS (IMAP/POP) en las ultimas N horas.
# Detecta el caso "nadie puede configurar el correo en el celular/Outlook" SIN esperar reclamos
# (en el incidente de migracion hubo 0 logins externos por 4 dias y nadie lo noto).
# Externo = login Dovecot con rip distinto de 127.0.0.1/::1 (el webmail entra desde localhost).
# Uso: check-external-logins.sh [horas]   (default 24)
ALERT_EMAIL="${ALERT_EMAIL:-gestiontecnologia@maquita.org}"
HOURS="${1:-24}"
HOSTNAME=$(hostname)

EXT=$(python3 - "$HOURS" <<'PY'
import re, sys, datetime
hours = int(sys.argv[1])
LOGS = ["/var/log/mail.log", "/var/log/mail.log.1"]
RE = re.compile(r'^(\S+)\s.*?(imap|pop3)-login: Logged in: user=<([^>]+)>.*?rip=([0-9a-fA-F:.]+)')
INTERNAL = {"127.0.0.1", "::1", ""}
now = datetime.datetime.now().astimezone()
cutoff = now - datetime.timedelta(hours=hours)
ext = 0
for p in LOGS:
    try:
        f = open(p, errors="ignore")
    except FileNotFoundError:
        continue
    with f:
        for line in f:
            m = RE.match(line)
            if not m:
                continue
            ts, proto, user, rip = m.groups()
            try:
                t = datetime.datetime.fromisoformat(ts)
            except ValueError:
                continue
            if t < cutoff:
                continue
            if rip not in INTERNAL:
                ext += 1
print(ext)
PY
)

if [ "${EXT:-0}" -eq 0 ] 2>/dev/null; then
    printf 'ALERTA en %s: 0 accesos EXTERNOS IMAP/POP en las ultimas %s horas.\n\nPosible fallo de configuracion de clientes (celular/Outlook/Thunderbird) — el mismo patron del\nincidente de migracion (nadie pudo configurar IMAP por dias). Revisar:\n  - Autenticacion Dovecot / claves de usuarios.\n  - La tarjeta "Configurar mi correo" del webmail (Ajustes).\n  - Panel admin -> "Accesos externos".\n' "$HOSTNAME" "$HOURS" \
        | mail -s "ALERTA: 0 accesos externos al correo ($HOSTNAME)" "$ALERT_EMAIL" 2>/dev/null
    echo "$(date '+%Y-%m-%d %H:%M:%S'): ALERTA 0 accesos externos en ${HOURS}h" >> /var/log/mail-external-logins.log
fi
