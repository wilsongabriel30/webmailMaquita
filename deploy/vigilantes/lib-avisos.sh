# maquita-vigilantes (repo) — funciones comunes de los vigilantes del servidor de correo.
# Se carga con «. /usr/local/lib/maquita-vigilantes/lib-avisos.sh». Sin datos propios: a quién avisar
# y con qué remitente sale del servidor, en este orden:
#   1. /etc/maquita-mail/organizacion.env  (ORG_CORREOS_AVISOS, ORG_REMITENTE_AVISOS)
#   2. el panel: outbound_anomaly_config.notify_admin (maildb)
#   3. postmaster@<dominio del correo> (en las instalaciones nuevas es un alias del buzón de TI)
# shellcheck shell=bash

[ -r /etc/maquita-mail/organizacion.env ] && . /etc/maquita-mail/organizacion.env

vig_dominio() { postconf -h mydomain 2>/dev/null || hostname -d; }
vig_servidor() { postconf -h myhostname 2>/dev/null || hostname -f 2>/dev/null || hostname; }

vig_destinos() {
    local d="${ORG_CORREOS_AVISOS:-}"
    if [ -z "$d" ] && command -v psql >/dev/null 2>&1; then
        d=$(sudo -u postgres psql -d maildb -Atc \
            "SELECT notify_admin FROM outbound_anomaly_config WHERE id = 1" 2>/dev/null | head -1)
    fi
    [ -n "$d" ] || d="postmaster@$(vig_dominio)"
    echo "$d" | tr ',' ' ' | xargs
}

vig_remitente() { echo "${ORG_REMITENTE_AVISOS:-postmaster@$(vig_dominio)}"; }

# Registro del correo de los últimos N minutos, con o sin /var/log/mail.log (las instalaciones
# nuevas solo tienen el diario de systemd). Formato de cada línea: «AAAA-MM-DDTHH:MM:SS … mensaje».
vig_registro_correo() {
    local min="$1"
    if [ -s /var/log/mail.log ]; then
        local desde
        desde=$(date -d "-$min min" '+%Y-%m-%dT%H:%M:%S')
        tail -n 40000 /var/log/mail.log | awk -v d="$desde" 'substr($1,1,19) >= d'
    else
        journalctl --since "-$min min" -o short-iso --no-pager -q \
            -t postfix/lmtp -t postfix/qmgr -t postfix/smtp -t postfix/smtpd -t postfix/error \
            -t dovecot 2>/dev/null
    fi
}

# Envío de un aviso por sendmail (no depende del webmail ni de LMTP).
# vig_enviar "asunto" "destinos" < cuerpo
vig_enviar() {
    local asunto="$1" destinos="$2" remitente servidor
    remitente=$(vig_remitente); servidor=$(vig_servidor)
    {
        echo "From: Vigilantes $servidor <$remitente>"
        echo "To: ${destinos// /, }"
        echo "Subject: $asunto"
        echo "Content-Type: text/plain; charset=UTF-8"
        echo "Auto-Submitted: auto-generated"
        echo
        cat
        echo
        echo "Servidor: $servidor · $(date '+%F %T')"
    } | /usr/sbin/sendmail -t -f "$remitente"
}
