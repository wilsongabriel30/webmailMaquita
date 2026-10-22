#!/usr/bin/env bash
# Respaldos del servidor con restic (sección «Respaldos» del panel). Idempotente.
# Se llama con:  sudo bash deploy/webmail/instalar-app.sh respaldos
#
# restic (BSD-2) desde Debian. Crea la clave de recuperación (/etc/maquita-respaldos/clave) y una clave SSH
# para un destino SFTP; el repositorio local en /var/backups/maquita-respaldos/repo; y el temporizador nocturno
# (02:30, antes de las actualizaciones de las 03:30). Las claves se ven en el panel para guardarlas FUERA.
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
[ "$EUID" -eq 0 ] || { echo -e "${RED}Ejecutar como root.${NC}"; exit 1; }

echo -e "${GREEN}[1/4] restic y rsync...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq restic rsync >/dev/null

echo -e "${GREEN}[2/4] Ayudante y claves...${NC}"
install -d -m 755 /usr/local/lib/maquita-respaldos
install -m 644 "${SELF}"/lib/*.py /usr/local/lib/maquita-respaldos/
install -m 755 "${SELF}/maquita-respaldos" /usr/local/sbin/maquita-respaldos
bash "${APP_DIR}/deploy/sudoers/instalar.sh"  # maquita-sudo y sus validadores (/usr/local/lib/maquita-sudo)
install -d -m 700 /etc/maquita-respaldos /var/backups/maquita-respaldos /var/cache/maquita-respaldos
install -d -m 755 /var/lib/maquita-respaldos
[ -s /etc/maquita-respaldos/clave ] || ( umask 077; openssl rand -base64 33 | tr -d '\n' > /etc/maquita-respaldos/clave )
[ -f /etc/maquita-respaldos/id_ed25519 ] || ssh-keygen -q -t ed25519 -N "" -C "respaldos@$(hostname -f)" -f /etc/maquita-respaldos/id_ed25519
[ -f /etc/maquita-respaldos/config.json ] || echo '{"automatico": true, "conservar": {"diarios": 7, "semanales": 4, "mensuales": 6}, "destino": {"tipo": "ninguno", "url": ""}}' > /etc/maquita-respaldos/config.json
chmod 600 /etc/maquita-respaldos/config.json

echo -e "${GREEN}[3/4] Repositorio local y temporizador nocturno...${NC}"
[ -f /var/backups/maquita-respaldos/repo/config ] || RESTIC_PASSWORD_FILE=/etc/maquita-respaldos/clave restic --repo /var/backups/maquita-respaldos/repo init >/dev/null
cat > /etc/systemd/system/maquita-respaldos.service <<'UNIT'
[Unit]
Description=Respaldo nocturno del servidor (restic)
After=postgresql.service mariadb.service

[Service]
Type=oneshot
Nice=10
IOSchedulingClass=idle
ExecStart=/usr/local/sbin/maquita-respaldos automatico
TimeoutStartSec=12h
UNIT
cat > /etc/systemd/system/maquita-respaldos.timer <<'UNIT'
[Unit]
Description=Respaldo del servidor cada noche (02:30)

[Timer]
OnCalendar=*-*-* 02:30:00
RandomizedDelaySec=20min
Persistent=true

[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now maquita-respaldos.timer >/dev/null
# El respaldo anterior (deploy/webmail/backup, tar cifrado con GPG) queda como estaba si se usa.

echo -e "${GREEN}[4/4] Comprobación...${NC}"
/usr/local/sbin/maquita-respaldos estado | head -c 300; echo
echo -e "${GREEN}Listo.${NC} Panel → Protección → Respaldos. Guarde FUERA del servidor la clave de recuperación."
