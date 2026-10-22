#!/usr/bin/env bash
# Despliegue desde git de los sitios PHP y DNS dinámico (v1.11): git, rsync y ssh-keygen; carpetas de root de los
# secretos (ganchos y fichas del DNS dinámico); y, con el portal de dominio, las rutas públicas /git-despliegue/ y
# /nic/update en el nginx del correo con su límite de peticiones (respaldo en /var/backups/maquita-sitios-publico y
# vuelta atrás si nginx las rechaza). Solo en servidores con sitios web. La lógica vive en
# deploy/sitios/publico/instalar.sh, idempotente.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INSTALADOR="$APP_DIR/deploy/sitios/publico/instalar.sh"
[ -f "$INSTALADOR" ] || { echo "Sin cambios: esta versión no trae el despliegue desde git ni el DNS dinámico ($INSTALADOR)."; exit 0; }
if [ "${1:-}" = "--simular" ]; then
  exec bash "$INSTALADOR" --pendiente
fi
exec bash "$INSTALADOR"
