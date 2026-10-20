#!/bin/bash
# Sección «activesync» (instalar-app.sh activesync): Exchange ActiveSync con Z-Push para Outlook (clásico,
# nuevo y de celular), el correo del iPhone y Android: correo, calendario y contactos, configurados solos por
# autodiscover. Instala Docker si falta, Z-Push en contenedor (deploy/z-push/instalar.sh) y activa la ruta
# /Microsoft-Server-ActiveSync en el sitio del correo. Mientras no esté instalado, el autodiscover no la anuncia.
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
[ "$EUID" -eq 0 ] || { echo -e "${RED}Ejecutar como root${NC}"; exit 1; }
AQUI="$(cd "$(dirname "$0")" && pwd)"
ENV_BACKEND="$(cd "$AQUI/../.." && pwd)/backend/.env"
HOST_CORREO="$(postconf -h myhostname)"
DOMINIO="${DOMAIN:-$(grep -oP '^MAIL_DOMAIN=\K.*' "$ENV_BACKEND" 2>/dev/null || echo "${HOST_CORREO#mail.}")}"
VHOST="/etc/nginx/sites-available/${HOST_CORREO}"
[ -f "$VHOST" ] || { echo -e "${RED}No está el sitio del correo ($VHOST): instala antes el webmail${NC}"; exit 1; }

if ! command -v docker >/dev/null; then
    echo -e "${GREEN}Instalando Docker (paquete de Debian)...${NC}"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io >/dev/null
    systemctl enable --now docker >/dev/null
fi
MAIL_HOST="$HOST_CORREO" bash "$AQUI/instalar.sh" "$DOMINIO"

# El sitio del correo trae el include comentado: se activa (una sola vez, con copia previa).
if grep -q "^\s*# include snippets/maquita-apps/activesync.conf;" "$VHOST"; then
    cp "$VHOST" "$VHOST.bak.$(date +%Y%m%d%H%M%S)"
    sed -i 's|^\(\s*\)# include snippets/maquita-apps/activesync.conf;|\1include snippets/maquita-apps/activesync.conf;|' "$VHOST"
fi
if ! nginx -t >/dev/null 2>&1; then
    echo -e "${RED}nginx rechaza la configuración: se deja el sitio del correo como estaba${NC}"
    ultimo=$(ls -t "$VHOST".bak.* 2>/dev/null | head -1); [ -n "$ultimo" ] && cp "$ultimo" "$VHOST"
    exit 1
fi
systemctl reload nginx
sleep 2
CODIGO=$(curl -sk -o /dev/null -w '%{http_code}' -X OPTIONS "https://${HOST_CORREO}/Microsoft-Server-ActiveSync" --resolve "${HOST_CORREO}:443:127.0.0.1" || echo 000)
[ "$CODIGO" = "401" ] || { echo -e "${RED}ActiveSync no responde como se espera (HTTP $CODIGO): docker logs zpush${NC}"; exit 1; }
echo -e "${GREEN}ActiveSync listo${NC} en https://${HOST_CORREO}/Microsoft-Server-ActiveSync (el autodiscover ya lo anuncia)."
