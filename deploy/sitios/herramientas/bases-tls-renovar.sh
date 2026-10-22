#!/usr/bin/env bash
# Certificado del servidor para el acceso remoto a las bases (MariaDB y PostgreSQL), copiado del de Let's Encrypt.
# Lo instala el ajuste 72 en /usr/local/sbin/maquita-bases-tls y como gancho de certbot
# (/etc/letsencrypt/renewal-hooks/deploy/maquita-bases-tls): tras cada renovación del certificado del servidor
# vuelve a copiarlo (MariaDB y PostgreSQL no pueden leer /etc/letsencrypt) y les pide recargarlo sin reiniciar.
# No pide ni cambia certificados: solo copia el que ya hay (no toca la clave, así que no afecta a DANE).
#
# Uso: maquita-bases-tls <nombre del servidor>      (certbot lo llama sin argumentos, con RENEWED_LINEAGE)
set -euo pipefail
ESTADO=/etc/maquita-sitios/bases-remoto.json
HOST="${1:-}"
if [ -z "$HOST" ] && [ -f "$ESTADO" ]; then
  HOST="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("host") or "")' "$ESTADO" 2>/dev/null || true)"
fi
[[ "$HOST" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$ ]] || { echo "maquita-bases-tls: nombre del servidor no válido" >&2; exit 2; }
ORIGEN="/etc/letsencrypt/live/$HOST"
# Con certbot: solo cuando se renovó ESTE certificado.
if [ -n "${RENEWED_LINEAGE:-}" ] && [ "$(readlink -f "$RENEWED_LINEAGE")" != "$(readlink -f "$ORIGEN")" ]; then
  exit 0
fi
[ -s "$ORIGEN/fullchain.pem" ] && [ -s "$ORIGEN/privkey.pem" ] || { echo "maquita-bases-tls: falta el certificado en $ORIGEN" >&2; exit 1; }

copiar() {  # copiar <carpeta> <usuario>
  local carpeta="$1" usuario="$2"
  getent passwd "$usuario" >/dev/null || return 0
  install -d -m 750 -o root -g "$usuario" "$carpeta"
  install -m 644 -o root -g "$usuario" "$ORIGEN/fullchain.pem" "$carpeta/fullchain.pem"
  install -m 640 -o root -g "$usuario" "$ORIGEN/privkey.pem" "$carpeta/privkey.pem"
}

if [ -d /etc/mysql ]; then
  copiar /etc/mysql/ssl-maquita mysql
  # MariaDB 10.4 o posterior recarga el certificado sin reiniciar.
  mariadb --protocol=socket -u root -e "FLUSH SSL" 2>/dev/null || true
fi
if [ -d /etc/postgresql ]; then
  copiar /etc/postgresql/ssl-maquita postgres
  runuser -u postgres -- psql -X -q -c "SELECT pg_reload_conf();" >/dev/null 2>&1 || true
fi
echo "maquita-bases-tls: certificado de $HOST copiado para las bases."
