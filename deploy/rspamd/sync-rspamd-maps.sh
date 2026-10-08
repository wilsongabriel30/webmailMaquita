#!/bin/bash
# sync-rspamd-maps.sh — genera los mapas que usa deploy/rspamd/maquita-antispoof.lua:
#   /etc/rspamd/local.d/maps/local_domains.map      dominios propios (tabla «domain» del panel)
#   /etc/rspamd/maquita_impersonation_terms.map     marcas y roles protegidos (panel + roles_protegidos.map)
# Sin este mapa, la regla MAQ_DISPNAME_SPOOF (+6) manda a no deseado el correo legítimo de cualquier
# dominio de la casa que no esté en la lista (reportado por una instalación externa el 08/10/2026).
# Idempotente; corre cada 10 minutos por cron (deploy/rspamd/cron-sync-rspamd-maps). Sin credenciales
# en el código: lee DATABASE_URL del .env del backend.
set -uo pipefail
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
ENV_FILE="${ENV_FILE:-$APP_DIR/backend/.env}"
ROLES="${ROLES:-$APP_DIR/deploy/rspamd/maps/roles_protegidos.map}"
TERMS=/etc/rspamd/maquita_impersonation_terms.map
DOMS=/etc/rspamd/local.d/maps/local_domains.map

DB_URL=$(grep -E '^DATABASE_URL=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
[ -z "$DB_URL" ] && { echo "sync-rspamd-maps: sin DATABASE_URL en $ENV_FILE" >&2; exit 1; }
# psql entiende postgresql://; se quita el sufijo del driver (postgresql+asyncpg://)
DB_URL=$(echo "$DB_URL" | sed -E 's#^postgres(ql)?\+[a-z0-9]+://#postgresql://#')
Q() { psql "$DB_URL" -tAc "$1" 2>/dev/null; }

T=$(mktemp)
Q "SELECT unnest(impersonation_terms) FROM security_config WHERE id=1;" | tr '[:upper:]' '[:lower:]' | sed 's/^ *//;s/ *$//' | grep -v '^$' >> "$T"
[ -f "$ROLES" ] && grep -vE '^\s*#|^\s*$' "$ROLES" | tr '[:upper:]' '[:lower:]' >> "$T"
if [ -s "$T" ]; then sort -u "$T" > "$TERMS"; chmod 644 "$TERMS"; fi
rm -f "$T"

D=$(mktemp)
Q "SELECT lower(domain) FROM domain WHERE active;" | sed 's/^ *//;s/ *$//' | grep -v '^$' | sort -u > "$D"
if [ -s "$D" ]; then mkdir -p "$(dirname "$DOMS")"; cp "$D" "$DOMS"; chmod 644 "$DOMS"; fi
rm -f "$D"
