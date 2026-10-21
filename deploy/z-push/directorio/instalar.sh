#!/bin/bash
# Libreta de la organización (GAL) en ActiveSync: al escribir un destinatario en el teléfono o en
# Outlook aparecen los buzones del propio dominio. Instala la búsqueda BackendSearchMaquita, el
# generador del directorio y su temporizador, y activa SEARCH_PROVIDER en la configuración de Z-Push.
# Idempotente. Solo recrea el contenedor si le falta el montaje de la búsqueda o cambió la config.
#
# Uso: bash deploy/z-push/directorio/instalar.sh [--simular]
set -euo pipefail
[ "$EUID" -eq 0 ] || { echo "Ejecutar como root" >&2; exit 1; }
AQUI="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$AQUI/../../.." && pwd)"
CONF=/opt/z-push-docker
ESTADO=/var/lib/z-push
LOGS=/var/log/z-push
GEN=/usr/local/sbin/maquita-zpush-directorio
MONTAJE=/opt/z-push/src/backend/searchmaquita/searchmaquita.php

docker inspect zpush >/dev/null 2>&1 || { echo "Sin cambios: Z-Push no está instalado."; exit 0; }

pendiente=()
cmp -s "$AQUI/searchmaquita.php" "$CONF/searchmaquita.php" || pendiente+=("búsqueda")
cmp -s "$AQUI/maquita-zpush-directorio" "$GEN" || pendiente+=("generador")
systemctl is-enabled -q maquita-zpush-directorio.timer 2>/dev/null || pendiente+=("temporizador")
grep -qE '^define\("SEARCH_PROVIDER", "BackendSearchMaquita"\);' "$CONF/config.php" || pendiente+=("configuración")
docker inspect zpush --format '{{range .Mounts}}{{.Destination}} {{end}}' | grep -q "$MONTAJE" || pendiente+=("montaje")
# La libreta personal estaba en una ruta de DAViCal (/caldav.php/...), no en la «contacts» de Radicale.
grep -q "caldav.php/%u/addresses" "$CONF/backend-carddav.php" 2>/dev/null && pendiente+=("ruta de contactos")

if [ "${#pendiente[@]}" -eq 0 ]; then
    [ "${1:-}" = "--simular" ] || MAQUITA_APP_DIR="$APP_DIR" "$GEN" >/dev/null
    echo "Sin cambios: la libreta de la organización ya está activa."; exit 0
fi
echo "Pendiente: libreta de la organización (${pendiente[*]})."
[ "${1:-}" = "--simular" ] && exit 0

install -m 640 -o root -g 33 "$AQUI/searchmaquita.php" "$CONF/searchmaquita.php"
install -m 755 "$AQUI/maquita-zpush-directorio" "$GEN"
cat > /etc/systemd/system/maquita-zpush-directorio.service <<EOF
[Unit]
Description=Libreta de la organización para ActiveSync (buzones activos por dominio)

[Service]
Type=oneshot
Environment=MAQUITA_APP_DIR=${APP_DIR}
ExecStart=${GEN}
EOF
cat > /etc/systemd/system/maquita-zpush-directorio.timer <<'EOF'
[Unit]
Description=Libreta de la organización para ActiveSync cada 15 minutos

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
MAQUITA_APP_DIR="$APP_DIR" "$GEN"
systemctl enable -q --now maquita-zpush-directorio.timer

if grep -q "caldav.php/%u/addresses" "$CONF/backend-carddav.php" 2>/dev/null; then
    cp -p "$CONF/backend-carddav.php" "$CONF/backend-carddav.php.bak.$(date +%Y%m%d%H%M%S)"
    sed -i "s|caldav.php/%u/addresses/|%u/contacts/|" "$CONF/backend-carddav.php"
fi
recrear=0
if ! grep -qE '^define\("SEARCH_PROVIDER", "BackendSearchMaquita"\);' "$CONF/config.php"; then
    cp -p "$CONF/config.php" "$CONF/config.php.bak.$(date +%Y%m%d%H%M%S)"
    sed -i -E 's/^define\("SEARCH_PROVIDER", *"[^"]*"\);/define("SEARCH_PROVIDER", "BackendSearchMaquita");/' "$CONF/config.php"
    grep -qE '^define\("SEARCH_PROVIDER", "BackendSearchMaquita"\);' "$CONF/config.php" || \
        echo 'define("SEARCH_PROVIDER", "BackendSearchMaquita");' >> "$CONF/config.php"
    recrear=1
fi
docker inspect zpush --format '{{range .Mounts}}{{.Destination}} {{end}}' | grep -q "$MONTAJE" || recrear=1
if [ "$recrear" = 1 ]; then
    # shellcheck source=../contenedor.sh
    source "$AQUI/../contenedor.sh"
    zpush_arrancar || { echo "Error: el contenedor zpush no arrancó (docker logs zpush)." >&2; exit 1; }
fi
docker exec zpush php -l /opt/z-push/src/backend/searchmaquita/searchmaquita.php >/dev/null || {
    echo "Error: la búsqueda no carga en el contenedor." >&2; exit 1; }
echo "Listo: libreta de la organización activa en ActiveSync."
