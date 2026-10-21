#!/usr/bin/env bash
# Datos de la organización (2026-10-21). instalar.sh no creaba /etc/maquita-mail/organizacion.env
# (aviso de Andes): en los servidores instalados así, los avisos de cuota y de los vigilantes
# salen hacia direcciones de ejemplo y no le llegan a nadie. Este ajuste lo crea con el dominio y
# el servidor de backend/.env. Si el archivo ya existe no lo toca: es de la organización.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV="$APP_DIR/backend/.env"
DESTINO="${ORG_FICHERO:-/etc/maquita-mail/organizacion.env}"

[ -e "$DESTINO" ] && { echo "Sin cambios: $DESTINO ya existe."; exit 0; }
[ -r "$ENV" ] || { echo "Sin cambios: no hay $ENV (no es un servidor de correo instalado)."; exit 0; }
# Sin la clave, grep sale con 1: con pipefail eso cortaría el ajuste (los .env anteriores a la v1.9 no tienen MAIL_HOST).
dominio="$({ grep -E '^MAIL_DOMAIN=' "$ENV" || true; } | head -1 | cut -d= -f2- | tr -d '"' | tr 'A-Z' 'a-z')"
servidor="$({ grep -E '^MAIL_HOST=' "$ENV" || true; } | head -1 | cut -d= -f2- | tr -d '"' | tr 'A-Z' 'a-z')"
[ -n "$servidor" ] || servidor="$(postconf -h myhostname 2>/dev/null || hostname -f)"
[ -n "$dominio" ] || { echo "Sin cambios: backend/.env no dice el dominio (MAIL_DOMAIN)."; exit 0; }

if [ "${1:-}" = "--simular" ]; then
  bash "$APP_DIR/deploy/webmail/configs/crear-organizacion-env.sh" --simular "$dominio" "$servidor"
else
  bash "$APP_DIR/deploy/webmail/configs/crear-organizacion-env.sh" "$dominio" "$servidor"
fi
