#!/usr/bin/env bash
# Certificado provisional para los vhosts de nginx cuyo certificado de Let's Encrypt aún no existe.
#
# En una instalación nueva el certificado se emite DESPUÉS (emitir-certificado.sh necesita el DNS
# publicado), pero las plantillas ya apuntan a /etc/letsencrypt/live/<nombre>/. Con un solo archivo
# que falte, «nginx -t» falla y nginx no arranca en 443 (aviso de Andes, 21/10/2026: servidor
# llamado hosting.<dominio> en lugar de mail.<dominio>). Aquí cada ruta de certificado que no
# existe pasa al certificado de prueba del sistema (snakeoil); certbot --nginx la cambia después
# por el certificado real. Las rutas que sí existen no se tocan.
#
# Uso: certificado-provisional.sh <vhost> [<vhost>...]
#      certificado-provisional.sh --todos        todos los de /etc/nginx/sites-enabled
set -uo pipefail
CERT="${MAQUITA_CERT_PROVISIONAL:-/etc/ssl/certs/ssl-cert-snakeoil.pem}"
LLAVE="${MAQUITA_LLAVE_PROVISIONAL:-/etc/ssl/private/ssl-cert-snakeoil.key}"

if [ ! -e "$CERT" ] || [ ! -e "$LLAVE" ]; then
  command -v make-ssl-cert >/dev/null 2>&1 && make-ssl-cert generate-default-snakeoil --force-overwrite >/dev/null 2>&1
fi
[ -e "$CERT" ] && [ -e "$LLAVE" ] || { echo "AVISO: no hay certificado de prueba (paquete ssl-cert)." >&2; exit 1; }

if [ "${1:-}" = "--todos" ]; then
  set -- /etc/nginx/sites-enabled/*
fi

cambiados=0
for vhost in "$@"; do
  real="$(readlink -f "$vhost")"
  [ -f "$real" ] || continue
  rutas="$(grep -oE '^\s*ssl_certificate(_key)?\s+/etc/letsencrypt/live/[^;[:space:]]+' "$real" | awk '{print $2}' | sort -u)"
  for ruta in $rutas; do
    [ -e "$ruta" ] && continue
    case "$ruta" in
      */privkey.pem) nueva="$LLAVE" ;;
      *) nueva="$CERT" ;;
    esac
    sed -i "s|${ruta}|${nueva}|g" "$real"
    echo "  certificado provisional en $(basename "$real"): falta ${ruta}"
    cambiados=$((cambiados + 1))
  done
done
[ "$cambiados" -eq 0 ] || echo "  Cuando el DNS apunte aquí: bash deploy/webmail/tls/emitir-certificado.sh <dominio>"
exit 0
