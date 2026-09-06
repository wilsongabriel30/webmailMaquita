#!/usr/bin/env bash
# Aplica el TLS endurecido de tls-endurecido.cf con postconf -e.
# Idempotente. No toca rutas de certificado ni master.cf.
# Uso:  aplicar-tls.sh [--simular]
set -euo pipefail
CF="$(dirname "$0")/tls-endurecido.cf"
[ -f "$CF" ] || { echo "Falta $CF" >&2; exit 1; }
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1

cambios=0
while IFS= read -r linea; do
  case "$linea" in ''|\#*) continue;; esac
  clave="${linea%%=*}"; clave="${clave// /}"
  valor="${linea#*=}"; valor="${valor# }"
  actual="$(postconf -h "$clave" 2>/dev/null || true)"
  if [ "$actual" = "$valor" ]; then continue; fi
  cambios=$((cambios+1))
  if [ "$SIMULAR" = 1 ]; then
    echo "CAMBIARIA $clave"
    echo "   ahora : ${actual:-(sin definir)}"
    echo "   quedaria: $valor"
  else
    postconf -e "$clave = $valor"
    echo "aplicado: $clave"
  fi
done < "$CF"

if [ "$SIMULAR" = 1 ]; then
  echo "Simulacion: $cambios ajuste(s) pendientes."; exit 0
fi
if [ "$cambios" -gt 0 ]; then
  postfix check && systemctl reload postfix
  echo "Postfix recargado con $cambios ajuste(s)."
else
  echo "Sin cambios: el servidor ya coincide con el repositorio."
fi
