#!/bin/bash
# sync-blacklist-mikrotik.sh
# Empuja las IPs atacantes de correo detectadas en VM130 (blacklist-ips.txt +
# baneos de fail2ban) hacia la address-list "blacklist_mail" del MikroTik
# el MikroTik del borde, que las dropea en el borde (raw prerouting) antes
# de llegar a VM130. Idempotente: solo añade las que faltan.
# Creado 2026-06-15 — blindaje correo con feedback del banco de pruebas.
set -uo pipefail

KEY=/root/.ssh/mikrotik_sync
MT_USER=CHANGEME_MT_USER          # usuario dedicado del router (NO admin)
MT_HOST=CHANGEME_MIKROTIK_HOST    # IP del router, ej: 192.0.2.1
LIST=blacklist_mail
BLACKLIST_FILE=/etc/mailserver/blacklist-ips.txt
LOG=/var/log/sync-blacklist-mikrotik.log
SSH="ssh -i $KEY -o ConnectTimeout=8 -o StrictHostKeyChecking=no -o PreferredAuthentications=publickey ${MT_USER}@${MT_HOST}"

ts(){ date '+%Y-%m-%d %H:%M:%S'; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# 1) IPs/CIDR candidatas: blacklist curada + fail2ban (jails de correo y ssh).
#    Se EXCLUYEN rangos privados/loopback por seguridad (nunca banear internos).
{
  grep -oE '^[0-9]{1,3}(\.[0-9]{1,3}){3}(/[0-9]{1,2})?' "$BLACKLIST_FILE" 2>/dev/null
  for j in postfix-sasl dovecot recidive sshd; do
    fail2ban-client status "$j" 2>/dev/null | sed -n 's/.*Banned IP list:[[:space:]]*//p'
  done | tr ' ' '\n' | grep -oE '^[0-9]{1,3}(\.[0-9]{1,3}){3}$'
} | grep -vE '^(10\.|127\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|169\.254\.)   # + añadí tu LAN si usa IPs públicas (ej 203\.0\.113\.)' \
  | sort -u > "$TMP/local"

# 2) IPs ya presentes en el MikroTik
$SSH "/ip firewall address-list print without-paging where list=$LIST" 2>/dev/null \
  | grep -oE '[0-9]{1,3}(\.[0-9]{1,3}){3}(/[0-9]{1,2})?' | sort -u > "$TMP/remote"

# 3) Diferencia: las que faltan por añadir
comm -23 "$TMP/local" "$TMP/remote" > "$TMP/new"
N=$(grep -c . "$TMP/new" || true)

if [ "$N" -eq 0 ]; then
  echo "$(ts) sincronizado, sin cambios ($(grep -c . "$TMP/local") IPs en lista local)" >> "$LOG"
  exit 0
fi

# 4) Añadir en lotes (un solo SSH por lote de 50) para eficiencia
SENT=0
: > "$TMP/batch"
while read -r ip; do
  [ -z "$ip" ] && continue
  printf ':do {/ip firewall address-list add list=%s address=%s comment="auto-sync VM130"} on-error={};' "$LIST" "$ip" >> "$TMP/batch"
  SENT=$((SENT+1))
  if [ $((SENT % 50)) -eq 0 ]; then
    $SSH "$(cat "$TMP/batch")" >/dev/null 2>&1
    : > "$TMP/batch"
  fi
done < "$TMP/new"
[ -s "$TMP/batch" ] && $SSH "$(cat "$TMP/batch")" >/dev/null 2>&1

echo "$(ts) añadidas $N IPs nuevas a $LIST en MikroTik" >> "$LOG"
