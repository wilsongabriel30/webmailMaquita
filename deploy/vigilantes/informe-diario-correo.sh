#!/bin/bash
# maquita-vigilantes (repo)
# Informe diario del tráfico de correo del día anterior (pflogsumm), en
# /var/log/informe-diario-correo/AAAAMMDD.log. No envía nada: es para consultar y comparar.
# Lee /var/log/mail.log si existe; si no, el diario de systemd (instalaciones nuevas).
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
command -v pflogsumm >/dev/null 2>&1 || { echo "pflogsumm no está instalado (apt install pflogsumm)"; exit 0; }
DIR=/var/log/informe-diario-correo; mkdir -p "$DIR"
SALIDA="$DIR/$(date -d yesterday +%Y%m%d).log"
if [ -s /var/log/mail.log ]; then
    pflogsumm /var/log/mail.log --problems-first --rej-add-from --verbose-msg-detail -d yesterday > "$SALIDA" 2>&1
else
    journalctl --since yesterday --until today -o short --no-pager -q -t postfix/smtpd -t postfix/smtp \
        -t postfix/qmgr -t postfix/lmtp -t postfix/cleanup -t postfix/submission/smtpd -t postfix/smtps/smtpd \
        -t postfix/bounce -t postfix/error 2>/dev/null \
        | pflogsumm --problems-first --rej-add-from --verbose-msg-detail > "$SALIDA" 2>&1
fi
find "$DIR" -name '*.log' -mtime +90 -delete 2>/dev/null
exit 0
