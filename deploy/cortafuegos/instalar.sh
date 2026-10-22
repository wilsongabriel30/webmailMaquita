#!/usr/bin/env bash
# Cortafuegos del servidor (sección «Cortafuegos» del panel) sobre iptables. Idempotente.
# Se llama con:  sudo ADMIN_IPS="203.0.113.0/24 198.51.100.7" bash deploy/webmail/instalar-app.sh cortafuegos
#
# ADMIN_IPS: IP o redes desde donde se administra (SSH y panel). Si no se indica, se usan las redes
# privadas y la IP de la sesión SSH desde la que se instala. Luego se cambian desde el panel.
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
[ "$EUID" -eq 0 ] || { echo -e "${RED}Ejecutar como root.${NC}"; exit 1; }

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    echo -e "${RED}ufw está activo: dos programas manejando el cortafuegos se pisan. Desactívelo (ufw disable) y repita.${NC}"
    exit 1
fi

echo -e "${GREEN}[1/3] iptables...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq iptables >/dev/null

echo -e "${GREEN}[2/3] Ayudante del panel y carga al arrancar...${NC}"
install -d -m 755 /usr/local/lib/maquita-cortafuegos
install -m 644 "${SELF}"/lib/*.py /usr/local/lib/maquita-cortafuegos/
install -m 755 "${SELF}/maquita-cortafuegos" /usr/local/sbin/maquita-cortafuegos
bash "${APP_DIR}/deploy/sudoers/instalar.sh"  # maquita-sudo y sus validadores (/usr/local/lib/maquita-sudo)
cat > /etc/systemd/system/maquita-cortafuegos.service <<'EOF'
[Unit]
Description=Cortafuegos del servidor (reglas del panel)
After=network-pre.target
Wants=network-pre.target
Before=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/maquita-cortafuegos cargar

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable maquita-cortafuegos.service >/dev/null 2>&1

echo -e "${GREEN}[3/3] Configuración inicial...${NC}"
ADMIN="${ADMIN_IPS:-}"
if [ -z "${ADMIN}" ]; then
    ADMIN="10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
    [ -n "${SSH_CLIENT:-}" ] && ADMIN="${ADMIN} ${SSH_CLIENT%% *}/32"
fi
# shellcheck disable=SC2086
/usr/local/sbin/maquita-cortafuegos inicial ${ADMIN}
echo -e "${GREEN}Listo.${NC} En el panel: Protección → Cortafuegos. SSH y panel solo desde: ${ADMIN}"
