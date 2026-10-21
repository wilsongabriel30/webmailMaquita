#!/usr/bin/env bash
# ActiveSync 16.1 en Z-Push (2026-10-21). Las versiones publicadas de Z-Push (2.7.x) llegan a 14.1: los
# borradores del teléfono no se guardaban en el servidor, a diferencia de Zimbra. La imagen se construye
# ahora con un commit fijo de la rama develop (16.1, borradores en IMAP) y con el parche de los contactos
# sin nombre (Radicale exige FN). Si el contenedor nuevo no responde con 16.1, vuelve a la imagen anterior.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
AQUI="$APP_DIR/deploy/z-push"
QUIERO="$(grep -oP '^ARG ZPUSH_VERSION=\K\S+' "$AQUI/Dockerfile")"

docker inspect zpush >/dev/null 2>&1 || { echo "Sin cambios: Z-Push no está instalado."; exit 0; }
TIENE="$(docker exec zpush cat /opt/z-push/VERSION 2>/dev/null || echo desconocida)"
PARCHE="$(docker exec zpush grep -c 'Parche de Maquita' /opt/z-push/src/backend/carddav/carddav.php 2>/dev/null || echo 0)"
if [ "$TIENE" = "$QUIERO" ] && [ "$PARCHE" != 0 ]; then
  echo "Sin cambios: Z-Push ya tiene ActiveSync 16.1 ($QUIERO)."; exit 0
fi
echo "Pendiente: Z-Push $TIENE → $QUIERO (ActiveSync 16.1 y contactos sin nombre)."
[ "${1:-}" = "--simular" ] && exit 0

ANTERIOR="zpush:anterior-$(date +%Y%m%d%H%M%S)"
docker tag zpush:latest "$ANTERIOR"
docker build -q --pull --network host -t zpush:latest "$AQUI" >/dev/null

CONF=/opt/z-push-docker ESTADO=/var/lib/z-push LOGS=/var/log/z-push
# shellcheck source=../z-push/contenedor.sh
source "$AQUI/contenedor.sh"
volver() {
  echo "Error: $1. Vuelvo a la imagen anterior ($ANTERIOR)." >&2
  docker tag "$ANTERIOR" zpush:latest
  zpush_arrancar || true
  exit 1
}
zpush_arrancar || volver "el contenedor nuevo no arrancó"
sleep 3
docker exec zpush sh -c "grep -A8 'supportedASVersions = array' /opt/z-push/src/lib/core/zpush.php | grep -q ASV_161" \
  || volver "Z-Push no trae ActiveSync 16.1"
docker exec zpush php -l /opt/z-push/src/backend/carddav/carddav.php >/dev/null || volver "el parche de contactos no carga"
echo "Listo: Z-Push con ActiveSync 16.1. Imagen anterior guardada como $ANTERIOR."
