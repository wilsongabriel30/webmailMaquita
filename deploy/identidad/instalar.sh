#!/usr/bin/env bash
# Identidad de la institución: ayudante que aplica nombre, logo y textos en todo el servidor
# (panel → Personalización → «Aplicar en todo»). Idempotente.
# Se llama con:  sudo bash deploy/webmail/instalar-app.sh identidad   (también lo hace instalar.sh)
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
[ "$EUID" -eq 0 ] || { echo "Ejecutar como root."; exit 1; }
install -m 755 "${SELF}/maquita-identidad" /usr/local/sbin/maquita-identidad
install -m 755 "${APP_DIR}/deploy/sudoers/maquita-sudo" /usr/local/sbin/maquita-sudo
echo "Identidad: listo (panel → Personalización → «Aplicar en todo»)."
