#!/usr/bin/env bash
# CPU y memoria por sitio (v1.11): temporizador sitios-recursos cada 5 minutos (maquita-sitios recursos-recoger), su
# carpeta de datos y los módulos de maquita-sitios que lo hacen. Solo en servidores con sitios web; en los demás no
# toca nada. La lógica (qué falta y cómo se instala) vive en deploy/sitios/recursos/instalar.sh, idempotente.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INSTALADOR="$APP_DIR/deploy/sitios/recursos/instalar.sh"
[ -f "$INSTALADOR" ] || { echo "Sin cambios: esta versión no trae la medición de CPU y memoria ($INSTALADOR)."; exit 0; }
if [ "${1:-}" = "--simular" ]; then
  exec bash "$INSTALADOR" --pendiente
fi
exec bash "$INSTALADOR"
