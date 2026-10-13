#!/usr/bin/env bash
# Ajustes del servidor que no viajan con la aplicación (Postfix, Dovecot…): los que corregimos en
# producción y cualquier instalación anterior necesita también. Un ajuste por archivo, en orden
# (NN-nombre.sh); todos son idempotentes y respaldan lo que tocan.
#
# Uso:  sudo bash deploy/ajustes/aplicar-ajustes.sh            # solo muestra qué falta (no toca nada)
#       sudo bash deploy/ajustes/aplicar-ajustes.sh --aplicar  # aplica lo que falte
#
# Para añadir un ajuste nuevo: copiar uno existente con el número siguiente. Contrato: con
# --simular solo informa; sin argumentos aplica. Imprime «Sin cambios: …», «Pendiente: …» o
# «Listo: …» y sale con 0 si todo fue bien.
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
APLICAR=0; [ "${1:-}" = "--aplicar" ] && APLICAR=1
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)." >&2; exit 2; }

fallos=0; pendientes=0
for a in "$DIR"/[0-9][0-9]-*.sh; do
  nombre="$(basename "$a" .sh)"
  printf '\n\033[1m== %s ==\033[0m\n' "$nombre"
  if [ "$APLICAR" = 1 ]; then salida="$(bash "$a" 2>&1)"; rc=$?
  else salida="$(bash "$a" --simular 2>&1)"; rc=$?; fi
  printf '%s\n' "$salida" | sed 's/^/  /'
  [ "$rc" -eq 0 ] || { fallos=$((fallos+1)); printf '  \033[31m[FALLO]\033[0m (código %s)\n' "$rc"; }
  grep -q '^Pendiente' <<<"$salida" && pendientes=$((pendientes+1))
done

echo
if [ "$fallos" -gt 0 ]; then
  echo "Terminó con $fallos ajuste(s) en error: revisa el mensaje de cada uno."
elif [ "$APLICAR" = 0 ] && [ "$pendientes" -gt 0 ]; then
  echo "$pendientes ajuste(s) pendientes. Para aplicarlos: sudo bash $0 --aplicar"
elif [ "$APLICAR" = 0 ]; then
  echo "El servidor ya tiene todos los ajustes."
elif [ "$pendientes" -eq 0 ]; then
  echo "Sin cambios: el servidor ya tenía todos los ajustes."
else
  echo "Ajustes aplicados."
fi
exit "$fallos"
