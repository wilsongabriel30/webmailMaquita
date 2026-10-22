#!/usr/bin/env bash
# Órdenes de consola del panel: maquita-panel (vale de entrada al panel general, 8443) y
# maquita-panel-dominio (vale de soporte del portal de dominio, 8444). Idempotente.
#
# Uso:  sudo bash deploy/panel/instalar.sh              instala o pone al día
#       sudo bash deploy/panel/instalar.sh --pendiente  solo dice qué falta (no toca nada)
#
# Deja: los dos programas en /usr/local/sbin y su biblioteca en /usr/local/lib/maquita-panel (solo root).
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)"
LIB=/usr/local/lib/maquita-panel
PENDIENTE=0; [ "${1:-}" = "--pendiente" ] && PENDIENTE=1
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)." >&2; exit 2; }

falta=()
for p in maquita-panel maquita-panel-dominio; do
  cmp -s "${SELF}/$p" "/usr/local/sbin/$p" || falta+=("orden $p")
done
diff -qr -x __pycache__ "${SELF}/lib" "$LIB" >/dev/null 2>&1 || falta+=("biblioteca ($LIB)")

if [ "${#falta[@]}" -eq 0 ]; then echo "Sin cambios: las órdenes de consola del panel ya están al día."; exit 0; fi
echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')"
[ "$PENDIENTE" = 1 ] && exit 0

install -d -m 700 "$LIB"
rm -f "$LIB"/*.py
install -m 600 "${SELF}"/lib/*.py "$LIB/"
for p in maquita-panel maquita-panel-dominio; do
  install -m 700 "${SELF}/$p" "/usr/local/sbin/$p"
done
echo "Listo: maquita-panel vale-entrada y maquita-panel-dominio vale-soporte instalados."
