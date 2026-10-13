#!/usr/bin/env bash
# Mapas pgsql con string_agg sin HAVING (2026-10-13): devuelven una fila NULL cuando la dirección
# no existe y Postfix anota «empty lookup result» en cada búsqueda. HAVING count(*) > 0 no cambia
# el resultado de las direcciones que sí existen.
set -euo pipefail
CONF="${POSTFIX_CONF:-/etc/postfix}"
mapas="$(postconf -c "$CONF" -h virtual_alias_maps | tr ', ' '\n\n' | sed -n 's/^\(proxy:\)\{0,1\}pgsql://p')"
afectados=()
for m in $mapas; do
  [ -f "$m" ] || continue
  grep -qiE '^query *=.*string_agg' "$m" && ! grep -qiE '^query *=.*having' "$m" && afectados+=("$m")
done
if [ "${#afectados[@]}" -eq 0 ]; then echo "Sin cambios: ningún mapa con string_agg sin HAVING."; exit 0; fi
printf 'Pendiente: añadir HAVING count(*) > 0 en %s\n' "${afectados[@]}"
[ "${1:-}" = "--simular" ] && exit 0
for m in "${afectados[@]}"; do
  cp -a "$m" "$m.bak.$(date +%Y%m%d_%H%M%S)"
  sed -i -E '/^query *=.*string_agg/I s/[[:space:];]*$/ HAVING count(*) > 0/' "$m"
done
if [ "$CONF" = /etc/postfix ]; then postfix check && postfix reload; fi
echo "Listo: mapas corregidos."
