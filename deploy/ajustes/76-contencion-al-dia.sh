#!/usr/bin/env bash
# La contención de cuentas al día (v1.11.2, 22/10/2026).
#
# instalar-proteccion-salida.sh instala maquita-contener, maquita-outbound y maquita-anomalia-salida.py una sola
# vez y nunca los sobrescribe (una vez hubo en un servidor una versión más nueva que la del repositorio). Por eso
# la corrección de la v1.11.1 (maquita-contener cierra las sesiones por sid) no llegaba a los servidores ya
# instalados. Aquí se reemplaza cada uno SOLO si lo instalado es idéntico a una versión anterior del repositorio
# (es decir, nadie lo cambió a mano); si no se reconoce, no se toca y se avisa. Copia previa en
# /var/backups/maquita-webmail/.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESPALDOS=/var/backups/maquita-webmail
PROGRAMAS="maquita-contener maquita-outbound maquita-anomalia-salida.py"
command -v git >/dev/null || { echo "Sin cambios: falta git para reconocer las versiones."; exit 0; }

# ¿El archivo instalado es una versión del repositorio? Compara su suma de git con la de cada versión histórica.
version_conocida() {
  local fuente="$1" instalado="$2" suma c
  suma="$(git hash-object "$instalado")"
  while read -r c; do
    [ "$(git -C "$APP_DIR" rev-parse --verify -q "${c}:${fuente}" 2>/dev/null || true)" = "$suma" ] && return 0
  done < <(git -C "$APP_DIR" log --format=%H -- "$fuente" 2>/dev/null || true)
  return 1
}

pendientes=(); desconocidos=()
for p in $PROGRAMAS; do
  fuente="deploy/tools/$p"; destino="/usr/local/sbin/$p"
  [ -f "$APP_DIR/$fuente" ] && [ -f "$destino" ] || continue
  cmp -s "$APP_DIR/$fuente" "$destino" && continue
  if version_conocida "$fuente" "$destino"; then pendientes+=("$p"); else desconocidos+=("$p"); fi
done
aviso=""
[ "${#desconocidos[@]}" -eq 0 ] || aviso=" Distintos del repositorio y con cambios a mano (no se tocan; compárelos con deploy/tools/): ${desconocidos[*]}."
[ "${#pendientes[@]}" -gt 0 ] || { echo "Sin cambios: la contención de cuentas ya está al día.${aviso}"; exit 0; }
echo "Pendiente: versión nueva de ${pendientes[*]}.${aviso}"
[ "${1:-}" = "--simular" ] && exit 0

mkdir -p "$RESPALDOS" && chmod 700 "$RESPALDOS"
for p in "${pendientes[@]}"; do
  cp -a "/usr/local/sbin/$p" "$RESPALDOS/$p.ajuste-76-$(date +%Y%m%d%H%M%S)"
  install -m 750 "$APP_DIR/deploy/tools/$p" "/usr/local/sbin/$p"
done
echo "Listo: ${pendientes[*]} al día (copia anterior en $RESPALDOS).${aviso}"
