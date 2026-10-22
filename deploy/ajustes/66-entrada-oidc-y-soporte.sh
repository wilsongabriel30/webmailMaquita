#!/usr/bin/env bash
# Entrada por OpenID Connect al panel general y entrada de soporte al portal de dominio (2026-10-21).
# En servidores ya instalados deja:
#   1. las órdenes de consola maquita-panel (vale-entrada) y maquita-panel-dominio (vale-soporte);
#   2. las tablas del panel (admin_oidc_config, admin_oidc_flujos, admin_vales_entrada), si la
#      actualización no aplicó todavía migrations/2026-10-21-entrada-oidc-y-vales.sql;
#   3. con el portal de dominio instalado, sus tablas y permisos de soporte (esquema-5 y permisos-5).
# No reinicia servicios: el código nuevo lo ponen en marcha maquita-actualizar o el despliegue.
# Detalle: docs/ENTRADA-OIDC-Y-SOPORTE.md
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
ENV_PANEL="${APP_DIR}/admin-panel/backend/.env"
ENV_CORREO="${APP_DIR}/backend/.env"
ENV_PORTAL=/etc/maquita-mail/panel-dominio.env
MIGRACION="${APP_DIR}/migrations/2026-10-21-entrada-oidc-y-vales.sql"
SQL_PORTAL="${APP_DIR}/panel-dominio/deploy"
INSTALADOR="${APP_DIR}/deploy/panel/instalar.sh"

[ -f "$INSTALADOR" ] || { echo "Sin cambios: esta versión no trae las órdenes de consola del panel ($INSTALADOR)."; exit 0; }
[ -f "$ENV_PANEL" ] || { echo "Sin cambios: este servidor no tiene el panel general ($ENV_PANEL)."; exit 0; }

valor() { { grep -E "^$2=" "$1" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | tr -d "\"'"; }
BASE="$(valor "$ENV_PANEL" DB_NAME)"; BASE="${BASE:-maildb}"
HOST_BD="$(valor "$ENV_PANEL" DB_HOST)"; HOST_BD="${HOST_BD:-localhost}"
bd_local() { [ "$HOST_BD" = "localhost" ] || [ "$HOST_BD" = "127.0.0.1" ] || [ "$HOST_BD" = "::1" ]; }
consulta() { runuser -u postgres -- psql -X -At -d "$BASE" -c "$1" 2>/dev/null || true; }
como_panel() {
  PGPASSWORD="$(valor "$ENV_PANEL" DB_PASS)" psql -X -q -v ON_ERROR_STOP=1 -h "$HOST_BD" \
    -p "$(valor "$ENV_PANEL" DB_PORT | grep -E '^[0-9]+$' || echo 5432)" -U "$(valor "$ENV_PANEL" DB_USER)" -d "$BASE" "$@"
}
# Las tablas pd_ son del dueño de la base del correo (DATABASE_URL), como en panel-dominio/deploy/instalar.sh.
como_dueno() {
  local url dueno clave
  url="$(valor "$ENV_CORREO" DATABASE_URL)"
  dueno="$(sed -E 's|^[a-z+]+://([^:]+):.*|\1|' <<<"$url")"
  clave="$(sed -E 's|^[a-z+]+://[^:]+:([^@]*)@.*|\1|' <<<"$url")"
  PGPASSWORD="$clave" psql -X -q -v ON_ERROR_STOP=1 -h localhost -U "$dueno" -d "$BASE" "$@"
}
portal_instalado() { [ -f "$ENV_PORTAL" ] && [ "$(consulta "SELECT to_regclass('pd_admins') IS NOT NULL")" = t ]; }
portal_al_dia() {
  [ "$(consulta "SELECT to_regclass('pd_vales_soporte') IS NOT NULL AND to_regclass('pd_sesiones_soporte') IS NOT NULL")" = t ] &&
  [ "$(consulta "SELECT has_table_privilege('panel_dominio', 'pd_sesiones_soporte', 'INSERT') AND has_table_privilege('panel_dominio', 'pd_vales_soporte', 'SELECT')")" = t ]
}

# --- Qué falta ---
falta=()
salida_cli="$(bash "$INSTALADOR" --pendiente)"
grep -q '^Pendiente' <<<"$salida_cli" && falta+=("órdenes de consola")
if bd_local; then
  [ "$(consulta "SELECT to_regclass('admin_vales_entrada') IS NOT NULL AND to_regclass('admin_oidc_config') IS NOT NULL")" = t ] \
    || falta+=("tablas de entrada del panel")
  if portal_instalado && ! portal_al_dia; then falta+=("tablas y permisos de soporte del portal"); fi
fi

if [ "${#falta[@]}" -eq 0 ]; then
  bd_local || echo "Aviso: la base está en otro equipo ($HOST_BD): aplique allí la migración y esquema-5/permisos-5-soporte.sql."
  echo "Sin cambios: la entrada OIDC y la de soporte ya están instaladas."; exit 0
fi
echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')."
[ "$SIMULAR" = 1 ] && exit 0

# --- Aplicar ---
bash "$INSTALADOR" >/dev/null
if bd_local; then
  if [ "$(consulta "SELECT to_regclass('admin_vales_entrada') IS NOT NULL AND to_regclass('admin_oidc_config') IS NOT NULL")" != t ]; then
    como_panel -f "$MIGRACION" >/dev/null || { echo "Error: no se pudo aplicar $MIGRACION como el usuario del panel." >&2; exit 1; }
  fi
  if portal_instalado && ! portal_al_dia; then
    como_dueno -f "${SQL_PORTAL}/esquema-5-soporte.sql" -f "${SQL_PORTAL}/permisos-5-soporte.sql" >/dev/null \
      || { echo "Error: no se pudieron crear las tablas de soporte del portal (esquema-5/permisos-5-soporte.sql)." >&2; exit 1; }
  fi
fi
echo "Listo: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')."
