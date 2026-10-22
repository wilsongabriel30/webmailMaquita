#!/usr/bin/env bash
# Crea /etc/maquita-mail/organizacion.env con los datos de la instalación, si todavía no existe.
#
# Lo leen el correo, el panel, el filtro, los avisos de cuota y los vigilantes. Sin él todos usan
# los valores de ejemplo del código (example.org), que no funcionan: los avisos no le llegan a
# nadie (aviso de Andes, 21/10/2026: instalar.sh no lo creaba y lo escribieron a mano).
# NUNCA lo sobrescribe: si ya existe, es de la organización.
#
# Uso: crear-organizacion-env.sh <dominio> <servidor de correo> [correo de avisos]
#      (--simular: solo dice si falta)
set -euo pipefail
SIMULAR=0; [ "${1:-}" = "--simular" ] && { SIMULAR=1; shift; }
DOMINIO="${1:?Uso: crear-organizacion-env.sh <dominio> <servidor> [correo de avisos]}"
SERVIDOR="${2:?Falta el nombre del servidor de correo}"
AVISOS="${3:-postmaster@${DOMINIO}}"
DESTINO="${ORG_FICHERO:-/etc/maquita-mail/organizacion.env}"

[[ "$DOMINIO" =~ ^[a-z0-9.-]+\.[a-z]{2,63}$ ]] || { echo "Dominio no válido: $DOMINIO" >&2; exit 1; }
[[ "$SERVIDOR" =~ ^[a-z0-9.-]+\.[a-z]{2,63}$ ]] || { echo "Servidor no válido: $SERVIDOR" >&2; exit 1; }
[[ "$AVISOS" =~ ^[A-Za-z0-9._%+-]+@[a-z0-9.-]+$ ]] || { echo "Correo de avisos no válido: $AVISOS" >&2; exit 1; }

if [ -e "$DESTINO" ]; then echo "Sin cambios: $DESTINO ya existe."; exit 0; fi
echo "Pendiente: crear $DESTINO para ${DOMINIO}"
[ "$SIMULAR" = 1 ] && exit 0

install -d -m 755 "$(dirname "$DESTINO")"
umask 022
cat > "$DESTINO" <<EOF
# Datos de la organización (lo creó la instalación el $(date +%Y-%m-%d); revísalo y complétalo).
# Explicación de cada valor: deploy/webmail/configs/organizacion.env.ejemplo
ORG_DOMINIO=${DOMINIO}
ORG_DOMINIOS="${DOMINIO}"
# Redes propias en CIDR, además de las privadas (un inicio de sesión desde ellas no es de riesgo).
ORG_REDES=""
ORG_URL_CORREO=https://${SERVIDOR}
ORG_URL_PANEL=https://${SERVIDOR}:8443
# A quién avisa el sistema cuando algo falla (buzones al 95 %, vigilantes…), separados por espacios.
ORG_CORREOS_AVISOS="${AVISOS}"
ORG_REMITENTE_AVISOS=postmaster@${DOMINIO}
# Detrás de un proxy (docs/PROXY-CONFIABLE.md; después, el ajuste 75): IP o redes que fail2ban nunca banea,
# el proxy de confianza y cómo pasa la IP real (proxy_protocol o cabecera).
#FAIL2BAN_IGNORAR=""
#PROXY_CONFIABLE=""
#PROXY_MODO=proxy_protocol
EOF
chmod 644 "$DESTINO"
echo "Listo: $DESTINO creado. Revisa ORG_CORREOS_AVISOS y ORG_REDES."
