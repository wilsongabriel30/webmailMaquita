#!/usr/bin/env bash
# Actualizaciones manuales por defecto (08/11/2026): instalar una versión es decisión de cada
# organización, que puede tener sus propios ajustes y querer revisarlos antes. La pasada nocturna
# sigue buscando y anuncia la versión en el panel; solo instala si la organización activa la
# casilla «Instalar automáticamente por la noche».
# Este ajuste pasa a manual UNA SOLA VEZ los servidores instalados antes con el automático activado
# (marca /etc/maquita-actualizar/.manual-por-defecto). Si después alguien vuelve a activar el
# automático en el panel, se respeta: el ajuste no lo toca más.
set -euo pipefail
CONF=/etc/maquita-actualizar/config.json
MARCA=/etc/maquita-actualizar/.manual-por-defecto
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
[ -f "$CONF" ] || { echo "Sin cambios: este servidor no tiene el actualizador instalado."; exit 0; }
[ -f "$MARCA" ] && { echo "Sin cambios: el modo manual por defecto ya se aplicó (lo que haya en el panel es decisión de la organización)."; exit 0; }
if ! python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("automatico", False) else 1)' "$CONF"; then
  [ "$SIMULAR" = 1 ] || touch "$MARCA"
  echo "Sin cambios: la actualización ya era manual."; exit 0
fi
if [ "$SIMULAR" = 1 ]; then echo "Pendiente: pasar la actualización automática a manual (se instala desde el panel)."; exit 0; fi
cp -p "$CONF" "$CONF.bak.$(date +%Y%m%d-%H%M%S)"
python3 - "$CONF" <<'PY'
import json, sys
p = sys.argv[1]
c = json.load(open(p)); c["automatico"] = False
json.dump(c, open(p, "w"), indent=2, ensure_ascii=False)
PY
touch "$MARCA"
echo "Listo: la actualización pasa a manual; las versiones nuevas se anuncian en el panel y se instalan con «Instalar ahora»."
