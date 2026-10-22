#!/usr/bin/env bash
# CPU y memoria por sitio (v1.11): el temporizador sitios-recursos (cada 5 minutos, maquita-sitios recursos-recoger),
# su carpeta de datos y los módulos de maquita-sitios que lo hacen (si este servidor aún no los tiene). Idempotente.
#
# Uso:  sudo bash deploy/sitios/recursos/instalar.sh              instala o actualiza
#       sudo bash deploy/sitios/recursos/instalar.sh --pendiente  solo dice qué falta (no toca nada)
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)"
SITIOS="$(cd "${SELF}/.." && pwd)"
APP_DIR="$(cd "${SITIOS}/../.." && pwd)"
LIB=/usr/local/lib/maquita-sitios
BIN=/usr/local/sbin/maquita-sitios
UNIDADES=/etc/systemd/system
DATOS=/var/lib/maquita-sitios/recursos
PENDIENTE=0; [ "${1:-}" = "--pendiente" ] && PENDIENTE=1

[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)." >&2; exit 2; }
[ -x "$BIN" ] || { echo "Sin cambios: este servidor no tiene los sitios web (maquita-sitios)."; exit 0; }

# --- Qué falta ---
falta=()
for m in recursos.py ordenes_v111.py; do
  cmp -s "${SITIOS}/lib/$m" "${LIB}/$m" || falta+=("módulo $m")
done
grep -q "ordenes_v111" "$BIN" || falta+=("programa maquita-sitios con las órdenes de la v1.11")
for u in sitios-recursos.service sitios-recursos.timer; do
  cmp -s "${SELF}/$u" "${UNIDADES}/$u" || falta+=("unidad $u")
done
systemctl is-enabled --quiet sitios-recursos.timer 2>/dev/null || falta+=("temporizador activo")
[ "$(stat -c '%U %a' "$DATOS" 2>/dev/null)" = "root 700" ] || falta+=("carpeta $DATOS")

if [ "${#falta[@]}" -eq 0 ]; then echo "Sin cambios: la medición de CPU y memoria de los sitios ya está al día."; exit 0; fi
echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')"
[ "$PENDIENTE" = 1 ] && exit 0

# --- Programa y módulos (los mismos que instala deploy/sitios/instalar.sh) y validador de maquita-sudo ---
install -d -m 755 "$LIB"
install -m 644 "${SITIOS}"/lib/*.py "$LIB/"
install -m 755 "${SITIOS}/maquita-sitios" "$BIN"
install -m 755 "${APP_DIR}/deploy/sudoers/maquita-sudo" /usr/local/sbin/maquita-sudo

# --- Carpeta de datos y temporizador ---
install -d -m 755 /var/lib/maquita-sitios
install -d -m 700 "$DATOS"
for u in sitios-recursos.service sitios-recursos.timer; do
  install -m 644 "${SELF}/$u" "${UNIDADES}/$u"
done
systemctl daemon-reload
systemctl enable --now sitios-recursos.timer >/dev/null 2>&1
# Una primera lectura ya: la siguiente, a los 5 minutos, da la primera CPU.
"$BIN" recursos-recoger >/dev/null || { echo "Error: maquita-sitios recursos-recoger falló (journalctl -u sitios-recursos)." >&2; exit 1; }
echo "Listo: CPU y memoria de los sitios cada 5 minutos (temporizador sitios-recursos, datos en $DATOS)."
