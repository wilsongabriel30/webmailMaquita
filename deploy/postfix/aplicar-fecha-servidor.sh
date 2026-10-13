#!/usr/bin/env bash
# Envíos autenticados con la fecha del servidor (ver fecha_servidor_envio).
# Crea el servicio cleanup_envio y lo asigna a submission (587) y smtps (465).
# Idempotente: se puede correr las veces que haga falta. Respalda master.cf antes de tocarlo.
# Uso:  aplicar-fecha-servidor.sh [--simular]
#       POSTFIX_CONF=/otra/ruta aplicar-fecha-servidor.sh   (ensayar sobre una copia)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
CONF="${POSTFIX_CONF:-/etc/postfix}"
PC=(postconf -c "$CONF")
FILTRO="$CONF/fecha_servidor_envio"
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1

# Los header_checks generales también se aplican a los envíos (van antes que el filtro de la fecha).
generales="$("${PC[@]}" -h header_checks)"
tablas="${generales:+$generales,}regexp:$FILTRO"

pendiente=()
cmp -s "$DIR/fecha_servidor_envio" "$FILTRO" 2>/dev/null || pendiente+=("instalar $FILTRO")
[ -n "$("${PC[@]}" -M cleanup_envio/unix 2>/dev/null)" ] || pendiente+=("crear el servicio cleanup_envio")
[ "$("${PC[@]}" -Ph cleanup_envio/unix/header_checks 2>/dev/null)" = "$tablas" ] || pendiente+=("cleanup_envio: header_checks")
[ "$("${PC[@]}" -Ph cleanup_envio/unix/always_add_missing_headers 2>/dev/null)" = "yes" ] || pendiente+=("cleanup_envio: always_add_missing_headers")
servicios=()
for s in submission smtps; do
  [ -n "$("${PC[@]}" -M "$s/inet" 2>/dev/null)" ] || continue
  servicios+=("$s")
  [ "$("${PC[@]}" -Ph "$s/inet/cleanup_service_name" 2>/dev/null)" = "cleanup_envio" ] || pendiente+=("$s: usar cleanup_envio")
done
[ "${#servicios[@]}" -gt 0 ] || { echo "No hay servicios submission ni smtps en $CONF/master.cf" >&2; exit 1; }

if [ "${#pendiente[@]}" -eq 0 ]; then
  echo "Sin cambios: los envíos autenticados ya salen con la fecha del servidor."; exit 0
fi
printf 'Pendiente: %s\n' "${pendiente[@]}"
[ "$SIMULAR" = 1 ] && exit 0

cp -a "$CONF/master.cf" "$CONF/master.cf.bak.$(date +%Y%m%d_%H%M%S)"
install -m644 "$DIR/fecha_servidor_envio" "$FILTRO"
[ -n "$("${PC[@]}" -M cleanup_envio/unix 2>/dev/null)" ] || \
  "${PC[@]}" -M "cleanup_envio/unix=cleanup_envio unix n - y - 0 cleanup"
"${PC[@]}" -P "cleanup_envio/unix/header_checks=$tablas" \
             "cleanup_envio/unix/always_add_missing_headers=yes"
for s in "${servicios[@]}"; do "${PC[@]}" -P "$s/inet/cleanup_service_name=cleanup_envio"; done

if [ "$CONF" = /etc/postfix ]; then
  postfix check && postfix reload
  echo "Listo: los envíos autenticados salen con la fecha del servidor (Postfix recargado)."
else
  echo "Listo (copia en $CONF; no se recarga Postfix)."
fi
