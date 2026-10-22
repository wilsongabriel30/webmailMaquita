#!/usr/bin/env bash
# Actualizaciones del servidor desde el repositorio (sección «Actualizaciones» del panel). Idempotente.
# Se llama con:  sudo bash deploy/webmail/instalar-app.sh actualizar
#
# Deja el ayudante maquita-actualizar, la lista de firmantes de versiones y el temporizador nocturno
# (03:30 más un margen al azar de hasta 45 min, para que no se actualicen todos los servidores a la vez).
# La primera vez el canal es «estable» (etiquetas firmadas) con actualización automática activada.
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
[ "$EUID" -eq 0 ] || { echo -e "${RED}Ejecutar como root.${NC}"; exit 1; }
[ -d "${APP_DIR}/.git" ] || { echo -e "${RED}${APP_DIR} no es un clon de git: el actualizador necesita el repositorio.${NC}"; exit 1; }

echo -e "${GREEN}[1/3] Ayudante y lista de firmantes...${NC}"
install -d -m 755 /usr/local/lib/maquita-actualizar
install -m 644 "${SELF}"/lib/*.py /usr/local/lib/maquita-actualizar/
install -m 644 "${SELF}/vigilados.txt" /usr/local/lib/maquita-actualizar/vigilados.txt
install -m 755 "${SELF}/maquita-actualizar" /usr/local/sbin/maquita-actualizar
bash "${APP_DIR}/deploy/sudoers/instalar.sh"  # maquita-sudo y sus validadores (/usr/local/lib/maquita-sudo)
install -d -m 755 /etc/maquita-actualizar /var/lib/maquita-actualizar
install -m 644 "${SELF}/firmantes" /etc/maquita-actualizar/firmantes
[ -f /etc/maquita-actualizar/config.json ] || echo '{"canal": "estable", "automatico": true}' > /etc/maquita-actualizar/config.json

echo -e "${GREEN}[2/3] Temporizador nocturno...${NC}"
cat > /etc/systemd/system/maquita-actualizar.service <<'UNIT'
[Unit]
Description=Actualización automática del servidor (si está activada en el panel)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/maquita-actualizar automatico
TimeoutStartSec=3h
UNIT
cat > /etc/systemd/system/maquita-actualizar.timer <<'UNIT'
[Unit]
Description=Busca e instala versiones nuevas cada noche

[Timer]
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=45min
Persistent=false

[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now maquita-actualizar.timer >/dev/null

echo -e "${GREEN}[3/3] Comprobación...${NC}"
/usr/local/sbin/maquita-actualizar buscar | head -c 400 || true; echo
echo -e "${GREEN}Listo.${NC} En el panel: Protección → Actualizaciones."
