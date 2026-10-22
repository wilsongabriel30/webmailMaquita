#!/usr/bin/env bash
# Recolector de los tableros de seguridad del panel general (Seguridad → Tableros, v1.11).
# Lo llaman el instalador (deploy/webmail/instalar.sh) y el ajuste 64 (servidores ya instalados).
# Contrato de los ajustes: con --simular solo informa; sin argumentos aplica. Idempotente.
#   · tablas seg_* (migrations/2026-10-21-tableros-seguridad.sql), como el usuario de la aplicación;
#   · maxminddb en el entorno del panel (país de cada IP con la base GeoIP local);
#   · maquita-seguridad-recolector.service + .timer (cada 5 minutos) y la rotación de /var/log/maquita.
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "$SELF/../.." && pwd)}"
PANEL="$APP_DIR/admin-panel/backend"
ENV_PANEL="$PANEL/.env"
MIGRACION="$APP_DIR/migrations/2026-10-21-tableros-seguridad.sql"
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)." >&2; exit 2; }
[ -f "$ENV_PANEL" ] && [ -x "$PANEL/venv/bin/python" ] || { echo "Sin cambios: el panel general no está instalado en $PANEL."; exit 0; }

valor() { grep -E "^$1=" "$ENV_PANEL" | head -1 | cut -d= -f2-; }
export PGHOST="$(valor DB_HOST)" PGPORT="$(valor DB_PORT)" PGDATABASE="$(valor DB_NAME)" PGUSER="$(valor DB_USER)" PGPASSWORD="$(valor DB_PASS)"
: "${PGHOST:=localhost}" "${PGPORT:=5432}" "${PGDATABASE:=maildb}" "${PGUSER:=mailserver}"

pendiente=()
tablas="$(psql -Atqc "SELECT to_regclass('public.seg_config') IS NOT NULL" 2>/dev/null || echo error)"
case "$tablas" in
    t) ;;
    f) pendiente+=("tablas de los tableros") ;;
    *) echo "Error: no se pudo consultar la base $PGDATABASE como $PGUSER." >&2; exit 1 ;;
esac
"$PANEL/venv/bin/python" -c "import maxminddb" 2>/dev/null || pendiente+=("maxminddb en el entorno del panel")

unidad() { sed "s#/opt/maquita-webmail#$APP_DIR#g" "$SELF/systemd/$1"; }
for u in maquita-seguridad-recolector.service maquita-seguridad-recolector.timer; do
    unidad "$u" | cmp -s - "/etc/systemd/system/$u" || pendiente+=("$u")
done
cmp -s "$SELF/logrotate-maquita" /etc/logrotate.d/maquita || pendiente+=("rotación de /var/log/maquita")
systemctl is-enabled -q maquita-seguridad-recolector.timer 2>/dev/null || pendiente+=("activar el temporizador")

if [ "${#pendiente[@]}" -eq 0 ]; then
    echo "Sin cambios: el recolector de los tableros de seguridad ya está instalado y activo."
    exit 0
fi
echo "Pendiente: ${pendiente[*]}."
[ "$SIMULAR" = 1 ] && exit 0

if [ "$tablas" = f ]; then
    psql -v ON_ERROR_STOP=1 -q -f "$MIGRACION" >/dev/null
fi
"$PANEL/venv/bin/python" -c "import maxminddb" 2>/dev/null \
    || "$PANEL/venv/bin/pip" install -q --disable-pip-version-check "maxminddb==3.1.1"
for u in maquita-seguridad-recolector.service maquita-seguridad-recolector.timer; do
    unidad "$u" > "/etc/systemd/system/$u"
    chmod 644 "/etc/systemd/system/$u"
done
install -m 644 "$SELF/logrotate-maquita" /etc/logrotate.d/maquita
install -d -m 750 -o root -g adm /var/log/maquita
systemctl daemon-reload
systemctl enable --now maquita-seguridad-recolector.timer >/dev/null 2>&1
fuentes="$(cd "$PANEL" && ./venv/bin/python -m app.seguridad.recolector --comprobar 2>/dev/null || echo '{}')"
echo "Listo: recolector de los tableros de seguridad activo (cada 5 minutos). Fuentes: $fuentes"
