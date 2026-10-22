#!/usr/bin/env bash
# Las Aplicaciones del Drive usan el mismo Redis que el correo (v1.11.1, 22/10/2026).
#
# instalar-app.sh escribía REDIS_URL=redis://127.0.0.1:6379/0 en el .env del Editor de PDF y de los Tableros.
# En un servidor con Redis protegido por contraseña, la aplicación no puede leer la sesión del webmail y
# responde 401 a quien la tiene abierta. Aquí se copia el REDIS_URL de backend/.env a esas aplicaciones, solo si
# es distinto, con copia previa del .env en /var/backups/maquita-webmail/ y reinicio de esa aplicación.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
BACKEND_ENV="${APP_DIR}/backend/.env"
RESPALDOS=/var/backups/maquita-webmail

REDIS="$(grep -E '^REDIS_URL=' "$BACKEND_ENV" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
[ -n "$REDIS" ] || { echo "Sin cambios: backend/.env no define REDIS_URL."; exit 0; }

pendientes=()
for app in pdf_editor bi; do
  env_app="${APP_DIR}/almacen/aplicaciones/${app}/.env"
  [ -f "$env_app" ] || continue
  actual="$(grep -E '^REDIS_URL=' "$env_app" | head -1 | cut -d= -f2- | tr -d '"' || true)"
  [ "$actual" = "$REDIS" ] || pendientes+=("$app")
done
[ "${#pendientes[@]}" -gt 0 ] || { echo "Sin cambios: las Aplicaciones del Drive ya usan el Redis del correo (o no están instaladas)."; exit 0; }
echo "Pendiente: el Redis del correo en ${pendientes[*]}."
[ "${1:-}" = "--simular" ] && exit 0

mkdir -p "$RESPALDOS" && chmod 700 "$RESPALDOS"
for app in "${pendientes[@]}"; do
  env_app="${APP_DIR}/almacen/aplicaciones/${app}/.env"
  cp -a "$env_app" "${RESPALDOS}/${app}.env.ajuste-74-$(date +%Y%m%d%H%M%S)"
  grep -v -E '^REDIS_URL=' "$env_app" > "${env_app}.nuevo" || true
  printf 'REDIS_URL=%s\n' "$REDIS" >> "${env_app}.nuevo"
  chmod --reference="$env_app" "${env_app}.nuevo"
  chown --reference="$env_app" "${env_app}.nuevo"
  mv "${env_app}.nuevo" "$env_app"
  servicio="maquita-${app//_/-}"
  systemctl is-enabled -q "$servicio" 2>/dev/null && systemctl restart "$servicio"
done
echo "Listo: ${pendientes[*]} usan el Redis del correo (copia del .env en ${RESPALDOS})."
