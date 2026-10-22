#!/usr/bin/env bash
# El webmail es el servidor por defecto de nginx (v1.11.1, reportado por Andes, 22/10/2026).
#
# Sin «default_server», nginx atiende las peticiones con un nombre desconocido (la IP, o el nombre del equipo
# cuando no es mail.<dominio>) con el PRIMER server{} que carga, y los vhosts de los sitios de los clientes
# se cargan antes que el del webmail por orden alfabético: https://<servidor>/webmail/ acababa en el sitio
# de un cliente (301) y deploy-webmail.sh revertía la actualización. Aquí se marca el vhost del webmail como
# servidor por defecto en IPv4 (80 y 443), solo si nadie lo es ya. Copia previa, «nginx -t» y vuelta atrás.
set -euo pipefail
command -v nginx >/dev/null || { echo "Sin cambios: nginx no está instalado."; exit 0; }
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
ENV_BACKEND="${APP_DIR}/backend/.env"

# ¿Hay ya un servidor por defecto en IPv4 para el puerto indicado?
# Sin «grep -q» en tubería: con pipefail, el SIGPIPE de «nginx -T» haría creer que no lo hay.
tiene_defecto() {
  [ -n "$(nginx -T 2>/dev/null | grep -E "^[[:space:]]*listen[[:space:]]+(0\.0\.0\.0:|\*:)?$1([[:space:]][^;]*)?[[:space:]]default_server" || true)" ]
}

# El vhost del webmail: el de MAIL_HOST o, si no, el que sirve /webmail/ en 443.
vhost_webmail() {
  local host
  host="$(grep -E '^MAIL_HOST=' "$ENV_BACKEND" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)"
  if [ -n "$host" ] && [ -f "/etc/nginx/sites-available/${host}" ]; then
    echo "/etc/nginx/sites-available/${host}"; return
  fi
  local f
  for f in /etc/nginx/sites-enabled/*; do
    [ -f "$f" ] || continue
    if grep -Eq '^[[:space:]]*location[[:space:]]+(\^~[[:space:]]+)?/webmail' "$f" && grep -Eq '^[[:space:]]*listen[[:space:]]+443' "$f"; then
      readlink -f "$f"; return
    fi
  done
}

pendientes=()
tiene_defecto 443 || pendientes+=(443)
tiene_defecto 80 || pendientes+=(80)
[ "${#pendientes[@]}" -gt 0 ] || { echo "Sin cambios: nginx ya tiene servidor por defecto en 80 y 443."; exit 0; }

ARCHIVO="$(vhost_webmail || true)"
[ -n "$ARCHIVO" ] && [ -f "$ARCHIVO" ] || { echo "Sin cambios: no encuentro el vhost del webmail (MAIL_HOST en backend/.env)."; exit 0; }
echo "Pendiente: el webmail como servidor por defecto de nginx en ${pendientes[*]} (${ARCHIVO})."
[ "${1:-}" = "--simular" ] && exit 0

mkdir -p /etc/nginx/respaldos
RESPALDO="/etc/nginx/respaldos/$(basename "$ARCHIVO").ajuste-73-$(date +%Y%m%d%H%M%S)"
cp -a "$ARCHIVO" "$RESPALDO"
for puerto in "${pendientes[@]}"; do
  # Solo la primera línea «listen <puerto>…;» de IPv4 del archivo (no las de [::]).
  grep -Eq "^[[:space:]]*listen[[:space:]]+(0\.0\.0\.0:)?${puerto}\b[^;]*default_server" "$ARCHIVO" && continue
  sed -E -i "0,/^([[:space:]]*listen[[:space:]]+(0\.0\.0\.0:)?${puerto}\b[^;]*);/s//\1 default_server;/" "$ARCHIVO"
done
if ! nginx -t >/dev/null 2>&1; then
  cp -a "$RESPALDO" "$ARCHIVO"
  echo "Error: nginx rechazó el cambio; se dejó como estaba (copia en $RESPALDO)." >&2
  exit 1
fi
systemctl reload nginx
echo "Listo: el webmail es el servidor por defecto de nginx en ${pendientes[*]} (copia en $RESPALDO)."
