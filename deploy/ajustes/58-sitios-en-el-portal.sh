#!/usr/bin/env bash
# «Mi sitio web» en el portal de dominio (v1.9): intermediario maquita-sitios-portal, su socket, la carpeta de
# subidas del portal, la tabla de cuotas pd_cuotas_sitio y la ruta /api/sitios (512 MB) en el nginx del portal.
# Solo en servidores que tienen a la vez los sitios web y el portal de dominio; en los demás no toca nada.
# Toda la lógica (qué falta, respaldo del sitio de nginx y vuelta atrás si nginx lo rechaza) vive en
# deploy/sitios/portal/instalar.sh, que es idempotente.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INSTALADOR="$APP_DIR/deploy/sitios/portal/instalar.sh"
[ -f "$INSTALADOR" ] || { echo "Sin cambios: esta versión no trae el intermediario ($INSTALADOR)."; exit 0; }
if [ "${1:-}" = "--simular" ]; then
  exec bash "$INSTALADOR" --pendiente
fi
exec bash "$INSTALADOR"
