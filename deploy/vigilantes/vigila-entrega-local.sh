#!/bin/bash
# maquita-vigilantes (repo)
# ============================================================================
# vigila-entrega-local — avisa si el correo deja de ENTRAR a los buzones (LMTP).
# Lección de un incidente real (21/09/2026): LMTP caía con «signal 11» y un buzón pasó casi
# 3 días sin recibir; el chequeo general solo avisaba con más de 100 diferidos y nada saltó.
# Mira los últimos VENTANA_MIN minutos del registro del correo y la cola de Postfix:
#   · cualquier caída del proceso LMTP (signal / Fatal / Panic)
#   · ≥ UMBRAL_DIFERIDOS entregas locales diferidas (relay …[private/dovecot-lmtp])
#   · ≥ UMBRAL_COLA mensajes en cola cuyo motivo es la entrega local
# Avisa al empezar, recuerda cada hora mientras dure y avisa al recuperarse.
# NO usa aviso-limitado: es crítico y no debe silenciarse por el tope diario. Sale por sendmail
# (la salida no pasa por LMTP). Conviene que ORG_CORREOS_AVISOS incluya una dirección EXTERNA,
# para que el aviso llegue aunque el buzón de TI esté en este mismo servidor.
# Cron: /etc/cron.d/vigila-entrega-local · Registro: /var/log/vigila-entrega-local.log
# ============================================================================
set -u
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
. /usr/local/lib/maquita-vigilantes/lib-avisos.sh
VENTANA_MIN=10
UMBRAL_DIFERIDOS=3
UMBRAL_COLA=3
RECORDAR_SEG=3600
EST=/var/lib/vigila-entrega-local; mkdir -p "$EST"
LOG=/var/log/vigila-entrega-local.log
SERVIDOR=$(vig_servidor)

RECIENTE=$(vig_registro_correo "$VENTANA_MIN")
CAIDAS=$(echo "$RECIENTE" | grep -E "lmtp" | grep -c -E "killed with signal|Fatal:|Panic:")
DIFERIDOS=$(echo "$RECIENTE" | grep "status=deferred" | grep -c -E "dovecot-lmtp|private/dovecot")
COLA=$(postqueue -j 2>/dev/null | grep -c -E "dovecot-lmtp|private/dovecot")

MAL=0
[ "$CAIDAS" -gt 0 ] && MAL=1
[ "$DIFERIDOS" -ge "$UMBRAL_DIFERIDOS" ] && MAL=1
[ "$COLA" -ge "$UMBRAL_COLA" ] && MAL=1
DETALLE="Últimos $VENTANA_MIN min: caídas de LMTP=$CAIDAS, entregas locales diferidas=$DIFERIDOS. En cola por entrega local: $COLA."

enviar() {
    local destinos
    destinos=$(vig_destinos)
    echo "$2" | vig_enviar "$1" "$destinos"
    echo "$(date '+%F %T') AVISO a $destinos (rc=$?): $1" >> "$LOG"
}

AHORA=$(date +%s)
DESDE_MAL=$(cat "$EST/desde" 2>/dev/null || echo 0)
ULTIMO=$(cat "$EST/ultimo_aviso" 2>/dev/null || echo 0)

if [ "$MAL" -eq 1 ]; then
    [ "$DESDE_MAL" -eq 0 ] && { DESDE_MAL=$AHORA; echo "$AHORA" > "$EST/desde"; }
    if [ $((AHORA - ULTIMO)) -ge "$RECORDAR_SEG" ]; then
        MIN=$(( (AHORA - DESDE_MAL) / 60 ))
        enviar "[CRÍTICO] El correo no está entrando a los buzones ($SERVIDOR)" \
"$DETALLE
Lleva al menos $MIN min. Los remitentes no reciben rebote todavía (el correo espera en cola),
pero los buzones no reciben nada mientras dure.

Revisar:
  journalctl -t postfix/lmtp --since '-30 min' | grep -E 'signal|Fatal|Panic' | tail
  postqueue -p | head -40
  journalctl -u dovecot --since '-30 min' | tail -40
Tras corregir: postqueue -f"
        echo "$AHORA" > "$EST/ultimo_aviso"
    fi
    echo "$(date '+%F %T') MAL $DETALLE" >> "$LOG"
else
    if [ "$DESDE_MAL" -ne 0 ]; then
        if [ "$ULTIMO" -ge "$DESDE_MAL" ]; then
            MIN=$(( (AHORA - DESDE_MAL) / 60 ))
            enviar "[OK] El correo vuelve a entrar a los buzones ($SERVIDOR)" \
"La entrega local se normalizó tras unos $MIN min. $DETALLE
Comprobar que la cola se vació: postqueue -p | tail -1"
        fi
        rm -f "$EST/desde" "$EST/ultimo_aviso"
    fi
fi
exit 0
