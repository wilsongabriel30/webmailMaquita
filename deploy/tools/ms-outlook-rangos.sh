#!/bin/bash
# ms-outlook-rangos.sh — Mantiene el conjunto nftables «nube_microsoft» con los rangos
# publicados por Microsoft para el tráfico de cliente POP3/IMAP4/SMTP (categoría Exchange
# «Allow», id 2 de https://endpoints.office.com). Son las direcciones desde las que la nube
# de Microsoft se conecta a servidores de correo ajenos cuando alguien añade su cuenta al
# Outlook nuevo (nuevo Outlook para Windows, Outlook.com, Outlook para móvil).
#
# Sin esta excepción, el filtro por país (paises_permitidos, solo Ecuador) descarta esas
# conexiones y el Outlook nuevo no descubre la configuración ni logra sincronizar.
# El conjunto solo se acepta en 443 (autodescubrimiento), 143/993 (IMAP) y 465/587 (envío);
# la autenticación sigue exigiendo contraseña de aplicación (política D-5) y fail2ban sigue activo.
set -euo pipefail
LOG="/var/log/geoip-webmail.log"
URL="https://endpoints.office.com/endpoints/worldwide?clientrequestid=8f9e2a1c-7d34-4b6f-9c21-5a3e7b0d4c18"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

if ! curl -sf -m 60 "$URL" -o "$TMP"; then
    echo "$(date '+%F %T'): WARN no se pudo consultar endpoints.office.com (se conserva lo previo)" >> "$LOG"
    exit 0
fi

RANGOS="$(python3 - "$TMP" <<'PY'
import ipaddress, json, sys

datos = json.load(open(sys.argv[1]))
redes = set()
for e in datos:
    if e.get("serviceArea") != "Exchange" or e.get("category") != "Allow":
        continue
    puertos = {p.strip() for p in (e.get("tcpPorts") or "").split(",")}
    if not puertos & {"143", "993", "995", "587"}:
        continue
    for red in e.get("ips", []):
        if ":" in red:
            continue
        try:
            redes.add(str(ipaddress.ip_network(red)))
        except ValueError:
            pass
# Salvaguarda: la lista de Microsoft nunca ha bajado de 8 rangos; si llega recortada, no se aplica.
print("\n".join(sorted(redes)) if len(redes) >= 8 else "")
PY
)"

if [ -z "$RANGOS" ]; then
    echo "$(date '+%F %T'): WARN lista de Microsoft vacía o incompleta (se conserva lo previo)" >> "$LOG"
    exit 0
fi

/usr/sbin/nft list set inet filter nube_microsoft >/dev/null 2>&1 || \
    /usr/sbin/nft add set inet filter nube_microsoft '{ type ipv4_addr; flags interval; }'
/usr/sbin/nft flush set inet filter nube_microsoft
while read -r cidr; do
    [ -n "$cidr" ] && /usr/sbin/nft add element inet filter nube_microsoft "{ $cidr }" 2>/dev/null
done <<< "$RANGOS"

/usr/sbin/nft list ruleset > /etc/nftables.conf
N=$(wc -l <<< "$RANGOS")
echo "$(date '+%F %T'): nube_microsoft actualizado — rangos=$N" >> "$LOG"
logger "Rangos de la nube de Microsoft (Outlook nuevo) actualizados: $N"
