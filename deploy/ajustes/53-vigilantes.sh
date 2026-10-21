#!/usr/bin/env bash
# Vigilantes del correo (2026-10-20): los que corrían solo en el servidor de producción y no
# llegaban a las instalaciones nuevas. Avisan si el correo deja de entrar a los buzones, si se cae
# un servicio o el webmail (y lo levantan), si el milter deja pasar el correo sin inspección, si la
# configuración del panel se desalinea, si hay señales de intrusión, y vigilan cola, disco y
# certificado. Detalle: deploy/vigilantes/README.md. Las versiones propias de un servidor no se pisan.
set -euo pipefail
export APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
[ -x "$(command -v postconf)" ] || { echo "Sin cambios: este servidor no tiene Postfix."; exit 0; }
bash "$APP_DIR/deploy/vigilantes/instalar.sh" "$@"
