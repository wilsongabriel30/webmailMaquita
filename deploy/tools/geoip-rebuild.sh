#!/bin/bash
# geoip-rebuild.sh — reconstruye el conjunto nftables «paises_permitidos», que decide desde
# qué países se llega al webmail, IMAP y envío (ver deploy/hardening/nftables/README.md).
#
# La lista de países sale de la base (tabla geo_webmail_countries, enabled = true). Las redes
# internas (privadas, las de ORG_REDES y el propio equipo) SIEMPRE se incluyen: la oficina y
# la VPN nunca se quedan fuera.
#
# El conjunto se cambia en UNA sola transacción de nftables: nunca queda vacío a medias, y si
# algo falla se conserva el anterior. Sin credenciales: la base sale de DATABASE_URL.
#
# Uso: geoip-rebuild.sh            (como root; también por cron semanal)
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "geoip-rebuild.sh: hay que ejecutarlo como root" >&2; exit 2; }
ENV_BACKEND=/opt/maquita-webmail/backend/.env
ENV_ORG=/etc/maquita-mail/organizacion.env
LOG=/var/log/geoip-webmail.log
NFT=/usr/sbin/nft
valor() { grep -E "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'" || true; }

DSN="$(valor "$ENV_BACKEND" DATABASE_URL | sed -E 's#^postgresql\+[a-z0-9]+://#postgresql://#')"
[ -n "$DSN" ] || { echo "geoip-rebuild.sh: sin DATABASE_URL en $ENV_BACKEND" >&2; exit 1; }
BASE="$(valor "$ENV_ORG" ORG_PAIS_BASE | tr 'A-Z' 'a-z')"; [[ "$BASE" =~ ^[a-z]{2}$ ]] || BASE=ec
INTERNAS="127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 $(valor "$ENV_ORG" ORG_REDES | tr ',' ' ')"

CODES="$(psql "$DSN" -X -tAc "SELECT string_agg(code, ' ' ORDER BY code) FROM geo_webmail_countries WHERE enabled" 2>/dev/null || true)"
[ -n "$CODES" ] || CODES="$BASE"   # salvaguarda: nunca dejar el conjunto solo con las redes internas

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
ELEMENTOS="$TMP/elementos"; : > "$ELEMENTOS"
for net in $INTERNAS; do
  [[ "$net" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}(/[0-9]{1,2})?$ ]] && echo "$net" >> "$ELEMENTOS"
done
for c in $CODES; do
  [[ "$c" =~ ^[a-z]{2}$ ]] || continue
  if curl -sf --max-time 60 -o "$TMP/$c.zone" "https://www.ipdeny.com/ipblocks/data/countries/$c.zone" && [ -s "$TMP/$c.zone" ]; then
    grep -E '^[0-9]{1,3}(\.[0-9]{1,3}){3}/[0-9]{1,2}$' "$TMP/$c.zone" >> "$ELEMENTOS"
  elif [ "$c" = "$BASE" ]; then
    # Sin los rangos del país base no se toca nada: reconstruir sin él dejaría fuera a casi todos.
    echo "$(date '+%F %T'): ERROR no se pudo bajar $c.zone (país base); se conserva el conjunto actual" >> "$LOG"
    echo "geoip-rebuild.sh: no se pudieron bajar los rangos del país base ($c); no se cambió nada" >&2
    exit 1
  else
    echo "$(date '+%F %T'): WARN no se pudo bajar $c.zone; ese país queda fuera hasta la próxima reconstrucción" >> "$LOG"
  fi
done

# auto-merge no está activo en el conjunto: se quitan duplicados y los rangos que nft rechace
# por solaparse se descartan probando primero en seco.
sort -u "$ELEMENTOS" -o "$ELEMENTOS"
{
  echo "flush set inet filter paises_permitidos"
  echo "add element inet filter paises_permitidos { $(paste -sd, "$ELEMENTOS") }"
} > "$TMP/cambio.nft"
if ! $NFT -c -f "$TMP/cambio.nft" 2>/dev/null; then
  # Algún rango se solapa con otro: se añaden de uno en uno dentro de la misma transacción lógica
  # (primero en un conjunto de prueba idéntico) para quedarse solo con los que nft acepta.
  : > "$TMP/buenos"
  $NFT add table inet geoip_prueba
  $NFT add set inet geoip_prueba p '{ type ipv4_addr; flags interval; }'
  while read -r cidr; do
    $NFT add element inet geoip_prueba p "{ $cidr }" 2>/dev/null && echo "$cidr" >> "$TMP/buenos"
  done < "$ELEMENTOS"
  $NFT delete table inet geoip_prueba
  {
    echo "flush set inet filter paises_permitidos"
    echo "add element inet filter paises_permitidos { $(paste -sd, "$TMP/buenos") }"
  } > "$TMP/cambio.nft"
fi
$NFT -f "$TMP/cambio.nft"

N="$($NFT list set inet filter paises_permitidos | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(/[0-9]+)?' | wc -l)"
# Persistencia para el arranque. Si este proceso corre confinado y /etc es de solo lectura, no
# es grave: la base es la fuente de verdad y el cron semanal vuelve a escribirlo.
if ! { $NFT list ruleset > /etc/nftables.conf.nuevo && mv /etc/nftables.conf.nuevo /etc/nftables.conf; } 2>/dev/null; then
  rm -f /etc/nftables.conf.nuevo 2>/dev/null || true
  $NFT list ruleset > /etc/nftables.conf 2>/dev/null \
    || echo "$(date '+%F %T'): WARN no se pudo guardar /etc/nftables.conf (se guardará en la próxima reconstrucción como root)" >> "$LOG"
fi
echo "$(date '+%F %T'): rebuild OK — paises=[$CODES] rangos=$N" >> "$LOG"
logger "GeoIP webmail actualizado: paises=[$CODES] rangos=$N" 2>/dev/null || true
echo "conjunto reconstruido: paises=[$CODES] rangos=$N"
