#!/usr/bin/env bash
# alias_maps sin NIS (2026-10-13): el valor por omisión incluye nis:mail.aliases y llena mail.log
# de «NIS domain name not set» en cada conexión.
set -euo pipefail
CONF="${POSTFIX_CONF:-/etc/postfix}"
actual="$(postconf -c "$CONF" -h alias_maps)"
if ! grep -q 'nis:' <<<"$actual"; then echo "Sin cambios: alias_maps no usa NIS."; exit 0; fi
nuevo="$(tr ',' '\n' <<<"$actual" | sed 's/^ *//' | grep -v '^nis:' | paste -sd, | sed 's/,/, /g')"
echo "Pendiente: alias_maps = ${nuevo} (ahora: ${actual})"
[ "${1:-}" = "--simular" ] && exit 0
cp -a "$CONF/main.cf" "$CONF/main.cf.bak.$(date +%Y%m%d_%H%M%S)"
postconf -c "$CONF" -e "alias_maps = ${nuevo}"
if [ "$CONF" = /etc/postfix ]; then postfix check && postfix reload; fi
echo "Listo: alias_maps sin NIS."
