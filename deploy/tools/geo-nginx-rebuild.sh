#!/usr/bin/env bash
# geo-nginx-rebuild.sh — lista de nginx para el filtro por país del puerto 443.
#
# El filtro por país del 443 se hace en nginx y no en el cortafuegos (12/11/2026): así el webmail
# sigue cerrado fuera de los países permitidos, pero quedan abiertas a todo el mundo las rutas que
# deben estarlo — entre servidores (/api/federacion/: recuperación y reacciones), el enlace seguro
# (/api/safelink) y /.well-known/. IMAP, envío y demás puertos siguen en el cortafuegos.
#
# La lista sale de los MISMOS conjuntos del cortafuegos (una sola fuente de verdad):
#   paises_permitidos   países habilitados en el panel + redes propias
#   nube_microsoft*     Outlook nuevo y su autodescubrimiento (ya pasaban antes del filtro)
# Sin esos conjuntos (instalación sin filtro por país) la lista deja pasar a todos.
# Si la lista nueva no valida en nginx, se conserva la anterior.
#
# Uso: geo-nginx-rebuild.sh   (como root; lo llama geoip-rebuild.sh y un cron cada 10 minutos)
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "geo-nginx-rebuild.sh: hay que ejecutarlo como root" >&2; exit 2; }
DESTINO=/etc/nginx/geo/paises_permitidos.conf
CONVERSOR="$(dirname "$(readlink -f "$0")")/geo-nginx-lista.py"
[ -f "$CONVERSOR" ] || CONVERSOR=/usr/local/sbin/geo-nginx-lista.py
mkdir -p "$(dirname "$DESTINO")"
TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT
for conjunto in paises_permitidos nube_microsoft nube_microsoft_web; do
    nft -j list set inet filter "$conjunto" 2>/dev/null || true
done | python3 "$CONVERSOR" > "$TMP"
N="$(grep -c ' 1;$' "$TMP" || true)"
if [ -f "$DESTINO" ] && cmp -s "$TMP" "$DESTINO"; then echo "lista de nginx sin cambios ($N redes)"; exit 0; fi
[ -f "$DESTINO" ] && cp -p "$DESTINO" "$DESTINO.anterior"
install -m 644 "$TMP" "$DESTINO"
if ! command -v nginx >/dev/null 2>&1; then echo "lista de nginx escrita ($N redes); nginx no está instalado aún"; exit 0; fi
if nginx -t >/dev/null 2>&1; then
    nginx -s reload 2>/dev/null || systemctl reload nginx 2>/dev/null || true
    echo "lista de nginx actualizada: $N redes"
else
    if [ -f "$DESTINO.anterior" ]; then cp -p "$DESTINO.anterior" "$DESTINO"; fi
    echo "nginx no validó con la lista nueva: se conserva la anterior" >&2; exit 1
fi
