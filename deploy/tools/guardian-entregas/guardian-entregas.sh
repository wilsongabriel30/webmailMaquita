#!/bin/bash
# Guardian de entregas — detecta correos que no logran salir ANTES de que reboten.
# Motivo: incidente 2026-07-28 en Zimbra (smtp_helo_timeout=15s) — correos que se
# quedaron 5 dias reintentando y rebotaron sin que nadie se enterara.
# Ejecutado por guardian-entregas.timer cada 30 min.

DESTINO_AVISO="gestiontecnologia@maquita.com.ec"
HORAS_AVISO=6                 # avisar si un mensaje lleva mas de N horas en cola
HORAS_SILENCIO=12             # no repetir el mismo aviso antes de N horas
LOG=/var/log/guardian-entregas.log
ESTADO_DIR=/var/lib/maquita-admin
ESTADO="$ESTADO_DIR/entregas-en-riesgo.json"
SELLO=/var/lib/maquita-admin/.guardian-ultimo-aviso

mkdir -p "$ESTADO_DIR"
ahora=$(date +%s)
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

# --- 1. cola actual: mensajes y su antiguedad ---
cola=$(mktemp); postqueue -p > "$cola" 2>/dev/null
total=$(grep -cE '^[0-9A-F]{8,}' "$cola")
viejos=0; detalle=""
while read -r qid resto; do
  [ -z "$qid" ] && continue
  fecha=$(echo "$resto" | awk '{print $2,$3,$4,$5}')
  ts=$(date -d "$fecha" +%s 2>/dev/null) || continue
  horas=$(( (ahora - ts) / 3600 ))
  if [ "$horas" -ge "$HORAS_AVISO" ]; then
    viejos=$((viejos+1))
    razon=$(grep -A2 "^$qid" "$cola" | grep -oE '\(.*\)' | head -1 | cut -c1-120)
    dest=$(grep -A3 "^$qid" "$cola" | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+' | tail -1)
    detalle="${detalle}  - ${qid} | ${horas}h en cola | ${dest} | ${razon}\n"
  fi
done < <(grep -E '^[0-9A-F]{8,}' "$cola" | sed 's/[*!]//')

# --- 2. patrones de fallo repetidos en el log reciente (ultimas 2h) ---
desde=$(date -d '2 hours ago' '+%b %e %H:' | sed 's/  / /')
patrones=$(grep -h "$(date '+%b %e')" /var/log/mail.log 2>/dev/null | \
  grep -E 'initial server greeting|Connection timed out|status=deferred' | \
  grep -oE 'relay=[^ ,]+' | sort | uniq -c | sort -rn | head -5)

# --- 3. estado para el panel ---
{
  echo "{"
  echo "  \"actualizado\": \"$(date '+%F %T')\","
  echo "  \"en_cola\": $total,"
  echo "  \"atascados_mas_${HORAS_AVISO}h\": $viejos,"
  echo "  \"destinos_con_fallos\": \"$(echo "$patrones" | tr '\n' ';' | sed 's/"/ /g')\""
  echo "}"
} > "$ESTADO"

# --- 4. aviso (con silencio para no repetir) ---
if [ "$viejos" -gt 0 ]; then
  ultimo=0; [ -f "$SELLO" ] && ultimo=$(cat "$SELLO")
  if [ $(( (ahora - ultimo) / 3600 )) -ge "$HORAS_SILENCIO" ]; then
    {
      echo "Subject: [Guardian de entregas] $viejos correo(s) llevan mas de ${HORAS_AVISO}h sin poder salir"
      echo "To: $DESTINO_AVISO"
      echo "Content-Type: text/plain; charset=utf-8"
      echo
      echo "El servidor de correo tiene $viejos mensaje(s) atascados en la cola de salida."
      echo "Si no se resuelven, Postfix los devolvera al remitente al agotar el plazo de reintentos."
      echo
      echo "Mensajes afectados:"
      echo -e "$detalle"
      echo "Destinos con mas fallos recientes:"
      echo "$patrones"
      echo
      echo "Que revisar:"
      echo " - Si el error dice 'initial server greeting', el destino tarda en saludar:"
      echo "   comprobar 'postconf smtp_helo_timeout' (debe ser 120s o mas)."
      echo " - Reintentar desde el panel de administracion (seccion Cola) o con: postqueue -f"
      echo
      echo "-- Guardian de entregas (VM130)"
    } | /usr/sbin/sendmail -t
    echo "$ahora" > "$SELLO"
    log "AVISO enviado a $DESTINO_AVISO: $viejos mensajes atascados (>${HORAS_AVISO}h)"
  else
    log "$viejos mensajes atascados (aviso silenciado, ultimo hace $(( (ahora-ultimo)/3600 ))h)"
  fi
else
  log "OK: $total en cola, ninguno supera ${HORAS_AVISO}h"
fi
rm -f "$cola"
