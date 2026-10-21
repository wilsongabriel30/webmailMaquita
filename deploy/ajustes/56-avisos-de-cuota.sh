#!/usr/bin/env bash
# Avisos de cuota del buzón (2026-10-21). Con las cuotas ya aplicadas (ajuste 51), un buzón lleno rechaza el
# correo sin que nadie lo vea venir. Este ajuste instala deploy/dovecot/avisos-cuota: al cruzar el 85 % el
# usuario recibe un correo con los pasos para liberar espacio; al 95 %, uno urgente y Tecnología una nota.
# Valida con doveconf -n antes de recargar; si falla, deja todo como estaba.
# No toca servidores sin cuotas ni los que ya tienen avisos de cuota propios.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
D="$APP_DIR/deploy/dovecot/avisos-cuota"
CONF=/etc/dovecot/dovecot.conf
NUESTRO=/etc/dovecot/maquita.d/avisos-cuota.conf
SCRIPT=/usr/local/bin/maquita-aviso-cuota

[ -f "$CONF" ] || { echo "Sin cambios: no hay $CONF."; exit 0; }
actual="$(doveconf -n 2>/dev/null)" || { echo "Sin cambios: la configuración actual de Dovecot no valida (doveconf -n); no se toca."; exit 0; }
grep -qE '^quota[ "]' <<<"$actual" || { echo "Sin cambios: este servidor no aplica cuotas (ajuste 51)."; exit 0; }
if [ ! -e "$NUESTRO" ] && grep -qE '^\s+(quota_)?warning ' <<<"$actual"; then
  echo "Sin cambios: este servidor ya tiene avisos de cuota propios."; exit 0
fi

falta=()
cmp -s "$D/aviso-cuota.sh" "$SCRIPT" 2>/dev/null || falta+=("guion de aviso ($SCRIPT)")
[ "$(bash "$D/instalar.sh" --mostrar)" = "$(cat "$NUESTRO" 2>/dev/null)" ] || falta+=("avisos al 85 % y al 95 % ($NUESTRO)")
if [ "${#falta[@]}" -eq 0 ]; then echo "Sin cambios: los avisos de cuota ya están activos."; exit 0; fi

echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')"
[ "${1:-}" = "--simular" ] && exit 0

respaldo="$CONF.bak.$(date +%Y%m%d%H%M%S)"
cp -p "$CONF" "$respaldo"
previo=""; [ -e "$NUESTRO" ] && { previo="$NUESTRO.bak.$(date +%Y%m%d%H%M%S)"; cp -p "$NUESTRO" "$previo"; }
deshacer() {
  cp -p "$respaldo" "$CONF"
  if [ -n "$previo" ]; then cp -p "$previo" "$NUESTRO"; else rm -f "$NUESTRO"; fi
  echo "Error: $1. Configuración de Dovecot restaurada." >&2; exit 1
}

bash "$D/instalar.sh" || deshacer "no se pudieron instalar los avisos"
salida="$(doveconf -n 2>&1 >/dev/null)" || deshacer "doveconf rechaza la configuración: ${salida:0:300}"
doveadm reload 2>/dev/null || systemctl reload-or-restart dovecot
echo "Listo: avisos de cuota al 85 % y al 95 % activos (respaldo: $respaldo)."
