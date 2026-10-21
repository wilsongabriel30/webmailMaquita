#!/usr/bin/env bash
# Aviso de cuota del buzón. Lo ejecuta el servicio «quota-warning» de Dovecot (como vmail) en el momento
# exacto en que un buzón cruza el 85 % o el 95 % de su cuota (avisos-cuota.conf).
#   Uso: maquita-aviso-cuota <porcentaje> <usuario>
#   - 85: correo al usuario con los pasos para liberar espacio.
#   - 95: lo mismo, como urgente, y una nota a Tecnología (ORG_CORREOS_AVISOS de organizacion.env).
# Como mucho un aviso por buzón y umbral cada 7 días: al borrar y volver a recibir, el buzón puede
# cruzar el umbral varias veces. El correo se entrega con dovecot-lda y quota_enforce=no para que
# llegue aunque el buzón esté casi lleno.
set -uo pipefail
PCT="${1:-}"; USUARIO="${2:-}"
[[ "$PCT" =~ ^[0-9]{1,3}$ ]] || exit 0
[[ "$USUARIO" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+$ ]] || exit 0

ORG="${MAQUITA_ORG_ENV:-/etc/maquita-mail/organizacion.env}"
# shellcheck source=/dev/null
[ -r "$ORG" ] && . "$ORG"
REMITENTE="${ORG_REMITENTE_AVISOS:-postmaster@${USUARIO#*@}}"
TI="${ORG_CORREOS_AVISOS:-}"
URL="${ORG_URL_CORREO:-}"
ESTADO="${MAQUITA_AVISO_CUOTA_DIR:-/var/lib/maquita-aviso-cuota}"
LDA="${MAQUITA_LDA:-/usr/lib/dovecot/dovecot-lda}"
SENDMAIL="${MAQUITA_SENDMAIL:-/usr/sbin/sendmail}"
DOVEADM="${MAQUITA_DOVEADM:-/usr/bin/doveadm}"  # el servicio de Dovecot no hereda PATH

mkdir -p "$ESTADO" 2>/dev/null
sello="$ESTADO/$(printf '%s' "$USUARIO" | tr -c 'A-Za-z0-9@._-' '_').$PCT"
[ -n "$(find "$sello" -mmin -10080 2>/dev/null)" ] && exit 0
touch "$sello" 2>/dev/null

# «12,3 GB de 15 GB» o «180 MB de 196 MB» (la cuota de Dovecot cuenta en KiB); vacío si doveadm no responde.
uso="$("$DOVEADM" -f tab quota get -u "$USUARIO" 2>/dev/null | awk -F'\t' '
  $2=="STORAGE" && $4 ~ /^[0-9]+$/ {
    if ($4 >= 1048576) printf "%.1f GB de %.0f GB", $3/1048576, $4/1048576
    else if ($4 >= 1024) printf "%.0f MB de %.0f MB", $3/1024, $4/1024
    else printf "%d KB de %d KB", $3, $4
    exit }' | tr . ,)"
detalle="${uso:+ ($uso)}"

asunto_b64() { printf '=?UTF-8?B?%s?=' "$(printf '%s' "$1" | base64 -w0)"; }
cabeceras() {  # $1 = destinatario, $2 = asunto
  printf 'From: %s\nTo: %s\nSubject: %s\nDate: %s\nMessage-ID: <aviso-cuota.%s.%s@%s>\n' \
    "$REMITENTE" "$1" "$(asunto_b64 "$2")" "$(LC_ALL=C date -R)" "$(date +%s)" "$$" "${USUARIO#*@}"
  printf 'Auto-Submitted: auto-generated\nMIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n\n'
}

if [ "$PCT" -ge 95 ]; then
  asunto="URGENTE: su buzón está al $PCT % y pronto dejará de recibir correo"
  inicio="Su buzón $USUARIO está al $PCT % de su espacio$detalle. Le queda muy poco: libere espacio hoy."
else
  asunto="Su buzón está al $PCT %: libere espacio"
  inicio="Su buzón $USUARIO ha llegado al $PCT % de su espacio$detalle."
fi

{
  cabeceras "$USUARIO" "$asunto"
  cat <<EOF
Estimado/a usuario/a:

$inicio

Cuando llegue al 100 %, dejará de recibir correos nuevos y quienes le escriban recibirán un rechazo.

Para liberar espacio:
1. Vacíe la «Papelera» y la carpeta «Spam» (correo no deseado).
2. Busque los correos con adjuntos grandes y elimine los que ya no necesite. Si un adjunto es
   importante, guárdelo antes en la nube institucional o en su equipo.
3. Elimine boletines, publicidad, notificaciones automáticas y conversaciones antiguas que ya no le sirvan.
4. Revise la carpeta «Enviados»: también ocupa espacio.
5. Al terminar, vacíe otra vez la «Papelera»: mientras los correos sigan ahí, ocupan espacio.

Si por su trabajo necesita conservar todo y requiere más espacio, escriba a Tecnología${TI:+ ($TI)}.
${URL:+
Correo web: $URL
}
Este es un mensaje automático del servidor de correo; no hace falta responderlo.
EOF
} | "$LDA" -d "$USUARIO" -o quota_enforce=no -f "$REMITENTE" 2>/dev/null

if [ "$PCT" -ge 95 ] && [ -n "$TI" ]; then
  {
    cabeceras "$TI" "Buzón al $PCT %: $USUARIO"
    printf 'El buzón %s cruzó el %s %% de su cuota%s.\nSe le envió el aviso con los pasos para liberar espacio.\nAl 100 %% rechazará el correo nuevo.\n' \
      "$USUARIO" "$PCT" "$detalle"
  } | "$SENDMAIL" -f "$REMITENTE" -- $TI
fi
exit 0
