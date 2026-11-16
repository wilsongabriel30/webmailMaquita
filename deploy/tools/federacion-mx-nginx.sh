#!/bin/bash
# federacion-mx-nginx.sh — que los nombres del MX atiendan /api/federacion/ sin redirigir.
#
# Para instalaciones donde el MX no se llama igual que el correo web (ver
# deploy/webmail/nginx/federacion-mx.conf y docs/RECUPERACION-ENTRE-SERVIDORES.md).
#
# Uso:  sudo bash federacion-mx-nginx.sh [--simular] [--certificado NOMBRE] mx1.ejemplo.org [mx2.ejemplo.org ...]
#
# El certificado debe existir ya y cubrir TODOS los nombres indicados (no se emite aquí: en un servidor
# con DANE, emitir con una clave nueva deja de recibir correo). Por defecto se usa el de
# /etc/letsencrypt/live/<primer nombre>/. Idempotente; respalda lo que reemplaza y, si nginx no valida,
# restaura lo anterior.
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
PLANTILLA="${PLANTILLA:-$AQUI/../webmail/nginx/federacion-mx.conf}"
DESTINO="${DESTINO:-/etc/nginx/sites-available/federacion-mx}"
ENLACE="${ENLACE:-/etc/nginx/sites-enabled/federacion-mx}"
RESPALDOS="${RESPALDOS:-/etc/nginx/respaldos}"
DIR_CERT="${DIR_CERT:-/etc/letsencrypt/live}"

SIMULAR=0; CERT=""; NOMBRES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --simular) SIMULAR=1 ;;
    --certificado) CERT="${2:-}"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    -*) echo "Opción desconocida: $1" >&2; exit 2 ;;
    *) NOMBRES+=("$1") ;;
  esac
  shift
done
[ "${#NOMBRES[@]}" -gt 0 ] || { echo "Indique al menos un nombre de MX. Ver --help." >&2; exit 2; }
for n in "${NOMBRES[@]}"; do
  [[ "$n" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ && "$n" == *.* ]] || { echo "Nombre no válido: $n" >&2; exit 2; }
done
CERT="${CERT:-${NOMBRES[0]}}"
[[ "$CERT" =~ ^[A-Za-z0-9.-]+$ ]] || { echo "Nombre de certificado no válido: $CERT" >&2; exit 2; }

PEM="$DIR_CERT/$CERT/fullchain.pem"
if [ ! -s "$PEM" ]; then
  echo "No existe el certificado $PEM." >&2
  echo "Emítalo primero para: ${NOMBRES[*]} (con la misma clave si el servidor publica DANE) y repita." >&2
  exit 1
fi
# El certificado tiene que nombrar cada MX: si no, los demás servidores rechazan la conexión.
SAN="$(openssl x509 -in "$PEM" -noout -ext subjectAltName 2>/dev/null | tr ',' '\n' | sed -n 's/^ *DNS://p')"
for n in "${NOMBRES[@]}"; do
  cubierto=0; n="${n,,}"
  while IFS= read -r s; do
    [ -n "$s" ] || continue
    s="${s,,}"
    if [ "$s" = "$n" ]; then cubierto=1; fi
    # Comodín: «*.ejemplo.org» cubre un solo nivel (mail.ejemplo.org, no a.mail.ejemplo.org).
    if [[ "$s" == \*.* ]] && [ "${n#*.}" = "${s:2}" ]; then cubierto=1; fi
  done <<<"$SAN"
  [ "$cubierto" = 1 ] || { echo "El certificado $CERT no cubre $n. Añada ese nombre al certificado y repita." >&2; exit 1; }
done

NUEVO="$(sed -e "s/__NOMBRES_MX__/${NOMBRES[*]}/g" -e "s/__CERTIFICADO__/$CERT/g" "$PLANTILLA")"
if [ -f "$DESTINO" ] && [ "$NUEVO" = "$(cat "$DESTINO")" ] && [ -e "$ENLACE" ]; then
  echo "Sin cambios: ${NOMBRES[*]} ya atienden /api/federacion/."; exit 0
fi
if [ "$SIMULAR" = 1 ]; then
  echo "Se escribiría $DESTINO para: ${NOMBRES[*]} (certificado $CERT)."; exit 0
fi

mkdir -p "$RESPALDOS"
RESPALDO=""
if [ -f "$DESTINO" ]; then RESPALDO="$RESPALDOS/federacion-mx.$(date +%Y%m%d-%H%M%S)"; cp -p "$DESTINO" "$RESPALDO"; fi
printf '%s\n' "$NUEVO" > "$DESTINO"
[ -x "$AQUI/nginx-http2-compatible.sh" ] && bash "$AQUI/nginx-http2-compatible.sh" "$DESTINO" || true
ln -sf "$DESTINO" "$ENLACE"
if ! nginx -t >/dev/null 2>&1; then
  if [ -n "$RESPALDO" ]; then cp -p "$RESPALDO" "$DESTINO"; else rm -f "$DESTINO" "$ENLACE"; fi
  echo "nginx no valida la configuración nueva: se dejó como estaba. Revise con «nginx -t»." >&2
  exit 1
fi
systemctl reload nginx
echo "Hecho: ${NOMBRES[*]} atienden /api/federacion/ con el certificado $CERT."
echo "Compruebe desde fuera: curl -si https://${NOMBRES[0]}/api/federacion/v1/recuperacion  (debe dar 200, no 301)"
