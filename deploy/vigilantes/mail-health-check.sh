#!/bin/bash
# maquita-vigilantes (repo)
# ============================================================================
# mail-health-check — cada 5 minutos: cola de Postfix, disco de los buzones y vencimiento del
# certificado del correo. Los servicios caídos los avisa (y repara) guardian-web-correo; aquí se
# registran, pero el aviso por correo es solo de cola, disco y certificado: como máximo uno cada
# 6 h y por el canal con tope diario (aviso-limitado). Registro: /var/log/mail-health.log
# ============================================================================
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
. /usr/local/lib/maquita-vigilantes/lib-avisos.sh
SERVIDOR=$(vig_servidor)
ERRORS=""

for svc in postfix dovecot rspamd redis-server postgresql clamav-daemon nginx maquita-webmail; do
    systemctl list-unit-files "$svc.service" --no-legend 2>/dev/null | grep -q . || continue
    systemctl is-active --quiet "$svc" 2>/dev/null || ERRORS="${ERRORS}CRITICO: $svc NO ESTA ACTIVO\n"
done

QUEUE_SIZE=$(find /var/spool/postfix/deferred -type f 2>/dev/null | wc -l)
[ "$QUEUE_SIZE" -gt 100 ] && ERRORS="${ERRORS}ALERTA: Cola de Postfix tiene $QUEUE_SIZE mensajes en deferred\n"

DISK_USAGE=$(df /var/vmail 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
[ -n "$DISK_USAGE" ] && [ "$DISK_USAGE" -gt 85 ] && ERRORS="${ERRORS}ALERTA: Disco /var/vmail al ${DISK_USAGE}%\n"

CERT_FIN=$(echo | openssl s_client -servername "$SERVIDOR" -connect 127.0.0.1:993 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$CERT_FIN" ]; then
    DAYS_LEFT=$(( ($(date -d "$CERT_FIN" +%s) - $(date +%s)) / 86400 ))
    [ "$DAYS_LEFT" -lt 30 ] && ERRORS="${ERRORS}ALERTA: Certificado del correo ($SERVIDOR) expira en $DAYS_LEFT dias\n"
fi

if [ -n "$ERRORS" ]; then
    echo -e "$(date): PROBLEMAS DETECTADOS en $SERVIDOR:\n$ERRORS" >> /var/log/mail-health.log
    AVISAR=$(echo -e "$ERRORS" | grep -v "NO ESTA ACTIVO" | sed "/^$/d")
    ULT=/var/lib/guardian-web-correo/mail-health-ultimo; mkdir -p /var/lib/guardian-web-correo
    if [ -n "$AVISAR" ] && [ $(( $(date +%s) - $(cat $ULT 2>/dev/null || echo 0) )) -ge 21600 ]; then
        echo -e "Problemas detectados en $SERVIDOR:\n\n$AVISAR" | /usr/local/sbin/aviso-limitado "ALERTA: Problemas en $SERVIDOR"
        date +%s > $ULT
    fi
else
    echo "$(date): Todo OK. Cola: $QUEUE_SIZE. Disco: ${DISK_USAGE}%" >> /var/log/mail-health.log
fi
