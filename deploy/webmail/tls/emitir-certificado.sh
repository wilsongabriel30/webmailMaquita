#!/usr/bin/env bash
# Emite el certificado TLS del correo con TODOS los nombres de cliente que
# realmente apuntan a este servidor, y activa la autoconfiguracion. Resuelve el
# problema #15 (reporte externo): los clientes que autoconfiguran probando el
# DOMINIO PELADO (dominio.tld:993) recibian un certificado equivocado porque el
# cert solo cubria mail.dominio.tld, y no habia autoconfig que evitara el intento.
#
# Uso:  emitir-certificado.sh dominio.tld [correo-admin]
#       DOMINIOS_EXTRA="otro.tld tercero.org" emitir-certificado.sh dominio.tld
#       (otros dominios de correo del mismo servidor: se añaden mail./autoconfig./autodiscover.
#        de cada uno si ya apuntan aquí; Outlook y los celulares los necesitan en el certificado)
#
# - Resuelve cada nombre candidato contra un resolver PUBLICO (no el local, que
#   puede tener vista interna / split-horizon) y solo pide al cert los nombres
#   cuyo A apunta a la IP publica de este servidor (certbot no falla por nombres
#   que no existen o apuntan a otro lado).
# - Fija el nombre del linaje con --cert-name para que la ruta del cert sea
#   siempre /etc/letsencrypt/live/mail.dominio.tld/ (aunque el apex vaya primero).
# - Tras emitir, sirve el XML de autoconfiguracion (Thunderbird/Evolution) sobre
#   el cert nuevo, para que los clientes ya no adivinen el dominio pelado.
set -euo pipefail

DOMINIO="${1:?Uso: emitir-certificado.sh dominio.tld [correo-admin]}"
EMAIL="${2:-admin@${DOMINIO}}"
MAIL_HOST="mail.${DOMINIO}"
BASE_AUTOCONFIG="$(cd "$(dirname "$0")/../autoconfig" 2>/dev/null && pwd || true)"

IP_PUB="$(curl -fsS4 https://api.ipify.org 2>/dev/null || curl -fsS4 https://ifconfig.me 2>/dev/null || true)"
[ -z "${IP_PUB}" ] && { echo "ERROR: no pude determinar la IP publica de este servidor."; exit 1; }
echo "IP publica de este servidor: ${IP_PUB}"

resolver_publico() {
  local n="$1"
  if command -v dig >/dev/null 2>&1; then
    dig +short +time=3 +tries=1 A "$n" @1.1.1.1 2>/dev/null | grep -E '^[0-9.]+$' || true
  else
    getent ahostsv4 "$n" 2>/dev/null | awk '{print $1}' | sort -u || true
  fi
}
command -v dig >/dev/null 2>&1 || echo "AVISO: 'dig' no esta instalado; uso el resolver local (puede tener vista interna)."

CANDIDATOS=(
  "${DOMINIO}"                 # apex: clientes que adivinan el dominio pelado (#15)
  "${MAIL_HOST}"
  "imap.${DOMINIO}"
  "smtp.${DOMINIO}"
  "pop3.${DOMINIO}"
  "autoconfig.${DOMINIO}"      # Thunderbird / Evolution
  "autodiscover.${DOMINIO}"    # Outlook / ActiveSync
)
for extra in ${DOMINIOS_EXTRA:-}; do
  CANDIDATOS+=("mail.${extra}" "autoconfig.${extra}" "autodiscover.${extra}")
done

ARGS=()
INCLUIDOS=()
for n in "${CANDIDATOS[@]}"; do
  ips="$(resolver_publico "$n")"
  if echo "${ips}" | grep -qx "${IP_PUB}"; then
    ARGS+=("-d" "$n"); INCLUIDOS+=("$n")
    echo "  [+] ${n} -> ${IP_PUB} (incluido)"
  else
    echo "  [-] ${n} -> ${ips:-sin registro A} (omitido: no apunta a este servidor)"
  fi
done

if [ "${#INCLUIDOS[@]}" -eq 0 ]; then
  echo "ERROR: ningun nombre apunta a este servidor. Publica los registros A y reintenta."
  exit 1
fi

echo ""
echo "Emitiendo certificado (linaje: ${MAIL_HOST}) para: ${INCLUIDOS[*]}"
# --reuse-key y --key-type ecdsa son OBLIGATORIOS (15/10/2026): sin ellos certbot genera clave nueva,
# deja la renovacion sin reuse_key y el TLSA de DANE (_25._tcp.${MAIL_HOST}) deja de coincidir.
# Asi paso el 07/09/2026 con este mismo script: ~5 semanas de DANE roto sin que nadie lo viera.
certbot --nginx --non-interactive --agree-tos -m "${EMAIL}" \
  --cert-name "${MAIL_HOST}" --keep-until-expiring --expand \
  --reuse-key --key-type ecdsa "${ARGS[@]}"

# --- Comprobacion DANE: la clave que presenta el puerto 25 debe estar en el TLSA publicado ---
# Solo si el servidor tiene la biblioteca DANE y su linaje es el que se acaba de emitir.
DANE_LIB="${DANE_LIB:-/usr/local/lib/maquita-dane.sh}"
if [ -f "${DANE_LIB}" ] && ( source "${DANE_LIB}"; [ "${DANE_LINAJE:-}" = "/etc/letsencrypt/live/${MAIL_HOST}" ] ); then
  source "${DANE_LIB}"
  systemctl reload postfix
  sleep 2
  if ! dane_publicada "$(dane_huella_puerto25)" "$(dane_publicadas)"; then
    echo ""
    echo "##########################################################################"
    echo "ERROR GRAVE: la clave del certificado NO coincide con el TLSA de DANE."
    echo "Los servidores que validan DANE dejaran de entregar correo. Revisar YA:"
    echo "  /usr/local/bin/vigila-dane.sh ; tail /var/log/vigila-dane.log"
    echo "##########################################################################"
    exit 1
  fi
  echo "DANE: la clave del puerto 25 coincide con el TLSA publicado."
fi

# --- Autoconfiguracion (Thunderbird/Evolution) sobre el cert nuevo ---
if [ -n "${BASE_AUTOCONFIG}" ] && [ -f "${BASE_AUTOCONFIG}/config-v1.1.xml.plantilla" ]; then
  mkdir -p /var/www/autoconfig/mail
  sed -e "s/__DOMINIO__/${DOMINIO}/g" -e "s/__MAIL_HOST__/${MAIL_HOST}/g" \
    "${BASE_AUTOCONFIG}/config-v1.1.xml.plantilla" > /var/www/autoconfig/mail/config-v1.1.xml
  if printf '%s\n' "${INCLUIDOS[@]}" | grep -qx "autoconfig.${DOMINIO}"; then
    sed -e "s/__DOMINIO__/${DOMINIO}/g" -e "s/__MAIL_HOST__/${MAIL_HOST}/g" \
      "${BASE_AUTOCONFIG}/nginx-autoconfig.conf.plantilla" \
      > "/etc/nginx/sites-available/autoconfig-${DOMINIO}.conf"
    ln -sf "/etc/nginx/sites-available/autoconfig-${DOMINIO}.conf" \
      "/etc/nginx/sites-enabled/autoconfig-${DOMINIO}.conf"
    if nginx -t 2>/dev/null; then
      systemctl reload nginx
      echo "Autoconfig activo: https://autoconfig.${DOMINIO}/mail/config-v1.1.xml"
    else
      rm -f "/etc/nginx/sites-enabled/autoconfig-${DOMINIO}.conf"
      echo "AVISO: 'nginx -t' fallo; NO se activo autoconfig (revisa la config manualmente)."
    fi
  else
    echo "AVISO: autoconfig.${DOMINIO} no apunta aqui; el XML quedo listo pero no se publico el vhost."
  fi
fi

echo ""
echo "Listo. Verifica:  certbot certificates"
echo "Autodiscover de Outlook: lo sirve el backend en autodiscover.${DOMINIO}; ActiveSync con deploy/z-push/."
