#!/usr/bin/env bash
# Seguridad del correo y de la web traída del servidor de correo en producción (2026-10-20): rechazo de remitentes con
# metacaracteres de shell (Postfix), regla anti «../» que ya no bloquea nombres con «..», Referrer-Policy
# por ruta (nginx), escaneo semanal de ClamAV y cron de la cuarentena diferida. Toda la lógica, con
# respaldo y vuelta atrás si postfix o nginx la rechazan, vive en deploy/hardening/seguridad-correo-web/.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
exec bash "$APP_DIR/deploy/hardening/seguridad-correo-web/aplicar.sh" "$@"
