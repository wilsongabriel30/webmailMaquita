#!/usr/bin/env bash
# Zonas DNS del servidor (secciones «Zonas DNS» y «Nuevo dominio» del panel): BIND 9 autoritativo,
# solo para las zonas propias, sin recursión. Idempotente.
# Se llama con:  sudo bash deploy/webmail/instalar-app.sh dns
#
# BIND 9 (MPL 2.0) desde Debian.
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
[ "$EUID" -eq 0 ] || { echo -e "${RED}Ejecutar como root.${NC}"; exit 1; }

echo -e "${GREEN}[1/4] BIND 9...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq bind9 bind9-dnsutils >/dev/null

echo -e "${GREEN}[2/4] Solo autoritativo (sin recursión, versión oculta, límite de respuestas)...${NC}"
[ -f /etc/bind/named.conf.options.antes-panel ] || cp /etc/bind/named.conf.options /etc/bind/named.conf.options.antes-panel
cat > /etc/bind/named.conf.options <<'EOF'
// Generado por deploy/dns/instalar.sh. Autoritativo solo para las zonas de este servidor.
options {
    directory "/var/cache/bind";
    recursion no;
    allow-recursion { none; };
    allow-transfer { none; };
    allow-query { any; };
    version none;
    hostname none;
    server-id none;
    minimal-responses yes;
    dnssec-validation auto;
    listen-on { any; };
    listen-on-v6 { ::1; };
    // Contra la amplificación (DNS usado como arma para atacar a terceros).
    rate-limit { responses-per-second 10; window 5; };
};
EOF
install -d -m 755 -o root -g bind /etc/bind/zonas
install -d -m 700 /etc/maquita-dns
[ -f /etc/bind/maquita-zonas.conf ] || { echo "// Generado por el panel (Zonas DNS)." > /etc/bind/maquita-zonas.conf; chgrp bind /etc/bind/maquita-zonas.conf; }
grep -q 'maquita-zonas.conf' /etc/bind/named.conf.local || echo 'include "/etc/bind/maquita-zonas.conf";' >> /etc/bind/named.conf.local

echo -e "${GREEN}[3/4] Ayudante del panel...${NC}"
install -d -m 755 /usr/local/lib/maquita-dns
install -m 644 "${SELF}"/lib/*.py /usr/local/lib/maquita-dns/
install -m 755 "${SELF}/maquita-dns" /usr/local/sbin/maquita-dns
install -m 755 "${APP_DIR}/deploy/sudoers/maquita-sudo" /usr/local/sbin/maquita-sudo

echo -e "${GREEN}[4/4] Comprobación...${NC}"
named-checkconf
systemctl enable named >/dev/null 2>&1 || true
systemctl restart named
/usr/local/sbin/maquita-dns estado
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow 53 >/dev/null
fi
echo -e "${GREEN}Listo.${NC} En el panel: Hospedaje → Zonas DNS (primero «Ajustes»: IP pública y servidores de nombres)."
echo "  Si el servidor está detrás de NAT, redirige 53/UDP y 53/TCP de cada IP de los servidores de nombres."
