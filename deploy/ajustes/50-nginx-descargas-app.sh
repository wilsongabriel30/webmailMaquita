#!/usr/bin/env bash
# Instaladores de las apps (2026-10-20): ruta /webmail/descargas/ para publicar el APK de Android de la
# organización (deploy/webmail/nginx/descargas-app.conf). Las instalaciones anteriores no la tenían y esa
# dirección devolvía el index.html del webmail. Si el servidor ya sirve esa ruta por su cuenta, no se toca.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
HOST="$(postconf -h myhostname 2>/dev/null || true)"
VHOST="/etc/nginx/sites-available/${HOST}"
SNIPPET=/etc/nginx/snippets/descargas-app.conf
ORIGEN="$APP_DIR/deploy/webmail/nginx/descargas-app.conf"
if [ -z "$HOST" ] || [ ! -f "$VHOST" ]; then echo "Sin cambios: no hay sitio del correo (${VHOST})."; exit 0; fi
if grep -qs "include snippets/descargas-app.conf;" "$VHOST" && cmp -s "$ORIGEN" "$SNIPPET"; then
  echo "Sin cambios: la ruta de descargas ya está."; exit 0
fi
if ! grep -qs "include snippets/descargas-app.conf;" "$VHOST" \
    && grep -rqs "location \^~ /webmail/descargas/" /etc/nginx/sites-enabled/ /etc/nginx/snippets/; then
  echo "Sin cambios: este servidor ya sirve /webmail/descargas/ con su propia configuración."; exit 0
fi
echo "Pendiente: ruta /webmail/descargas/ (instaladores de las apps) en ${VHOST}"
[ "${1:-}" = "--simular" ] && exit 0
install -d -m 755 "$APP_DIR/descargas-app"
[ -f "$SNIPPET" ] && cp "$SNIPPET" "$SNIPPET.bak.$(date +%Y%m%d%H%M%S)"
install -m 644 "$ORIGEN" "$SNIPPET"
if ! grep -qs "include snippets/descargas-app.conf;" "$VHOST"; then
  cp "$VHOST" "$VHOST.bak.$(date +%Y%m%d%H%M%S)"
  # Antes del bloque del webmail (la location ^~ gana igual, pero así queda junto a él).
  sed -i '0,/^\(\s*\)location \/webmail\/ {/s//\1include snippets\/descargas-app.conf;\n\n&/' "$VHOST"
fi
if ! nginx -t >/dev/null 2>&1; then
  ultimo="$(ls -t "$VHOST".bak.* 2>/dev/null | head -1)"; [ -n "$ultimo" ] && cp "$ultimo" "$VHOST"
  echo "nginx rechazó el cambio: se dejó el sitio del correo como estaba." >&2; exit 1
fi
systemctl reload nginx
echo "Listo: ruta de descargas activa (publicar en $APP_DIR/descargas-app/)."
