#!/bin/bash
# aplicar-limites-tamano.sh — Coordina el limite de tamano de adjuntos en TODAS las capas
# desde UNA sola variable de politica: MAX_ATTACHMENT_MB.
#
# Regla:  nginx client_max_body_size >= postfix message_size_limit >= MAX_ATTACHMENT_MB * 1.37
#         (1.37 = inflacion base64 del adjunto dentro del correo)
#
# Uso:  aplicar-limites-tamano.sh [MAX_MB]
#   MAX_MB: tamano maximo de adjunto real en MB (default: $MAX_ATTACHMENT_MB o 25)
#
# Hace:
#   1. Escribe /etc/nginx/snippets/maquita-max-body.conf  (los vhosts -webmail Y proxy frontal-
#      deben incluirlo:  include snippets/maquita-max-body.conf; )
#   2. postconf -e message_size_limit
#   3. Asegura que el usuario del backend lea /var/log/mail.log (grupo adm + ACL) -> fix Errno 13
#   4. nginx -t && reload ; postfix reload
set -euo pipefail
MAX_MB="${1:-${MAX_ATTACHMENT_MB:-25}}"
MSG_MB=$(awk -v m="$MAX_MB" 'BEGIN{ v=m*1.37; printf("%d", (v==int(v))? v : int(v)+1) }')
NGINX_MB=$(( MSG_MB + 3 ))
MSG_BYTES=$(( MSG_MB * 1024 * 1024 ))
SNIP=/etc/nginx/snippets/maquita-max-body.conf
echo "Politica: MAX_ATTACHMENT_MB=${MAX_MB} -> postfix=${MSG_MB}MB (${MSG_BYTES}B)  nginx=${NGINX_MB}m"

if [ -d /etc/nginx ]; then
  mkdir -p /etc/nginx/snippets
  cat > "$SNIP" <<EOSNIP
# Generado por aplicar-limites-tamano.sh — NO editar a mano.
# Derivado de MAX_ATTACHMENT_MB=${MAX_MB} (adjunto real) * 1.37 (base64) + headroom.
client_max_body_size ${NGINX_MB}m;
EOSNIP
  echo "  [nginx] $SNIP -> client_max_body_size ${NGINX_MB}m"
  if nginx -t 2>/dev/null; then systemctl reload nginx 2>/dev/null && echo "  [nginx] reload OK"; else echo "  [nginx] AVISO: 'nginx -t' fallo, NO recargado"; fi
fi

if command -v postconf >/dev/null 2>&1; then
  postconf -e "message_size_limit=${MSG_BYTES}"
  postfix reload 2>/dev/null || systemctl reload postfix 2>/dev/null || true
  echo "  [postfix] message_size_limit=${MSG_BYTES}"
fi

SVC_USER="${SVC_USER:-www-data}"
if id "$SVC_USER" >/dev/null 2>&1 && [ -f /var/log/mail.log ]; then
  if ! id -nG "$SVC_USER" | grep -qw adm; then usermod -aG adm "$SVC_USER" && echo "  [perms] $SVC_USER -> grupo adm (requiere relogin del servicio)"; fi
  setfacl -m u:"$SVC_USER":r /var/log/mail.log 2>/dev/null && echo "  [perms] ACL r mail.log para $SVC_USER" || true
fi
echo "OK."
