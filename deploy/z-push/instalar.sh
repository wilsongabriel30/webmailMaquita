#!/bin/bash
# Z-Push (ActiveSync) en contenedor — instalador/actualizador para Maquita Mail.
# Uso: bash deploy/z-push/instalar.sh [dominio-del-correo]   (p. ej. maquita.org)
#
# Construye la imagen (base oficial actual + apt-get upgrade), escribe las configuraciones en
# /opt/z-push-docker (no dentro de la imagen: se editan sin reconstruir), arranca el contenedor
# «zpush» escuchando solo en 127.0.0.1:9000 (FastCGI) y deja el snippet de nginx. Idempotente:
# volver a ejecutarlo reconstruye la imagen y recrea el contenedor con el estado conservado.
set -euo pipefail
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
[ "$EUID" -eq 0 ] || { echo -e "${RED}Ejecutar como root${NC}"; exit 1; }
command -v docker >/dev/null || { echo -e "${RED}Falta docker (apt install docker.io)${NC}"; exit 1; }

AQUI="$(cd "$(dirname "$0")" && pwd)"
DOMINIO="${1:-${DOMAIN:-}}"
if [ -z "$DOMINIO" ]; then
    DOMINIO=$(grep -o '^MAIL_DOMAIN=.*' /opt/maquita-webmail/backend/.env 2>/dev/null | cut -d= -f2- || true)
fi
[ -n "$DOMINIO" ] || { echo -e "${RED}Indica el dominio: bash instalar.sh midominio.org${NC}"; exit 1; }
HOST_CORREO="${MAIL_HOST:-mail.${DOMINIO}}"
CONF=/opt/z-push-docker
ESTADO=/var/lib/z-push
LOGS=/var/log/z-push

echo -e "${GREEN}[1/5] Construyendo la imagen zpush (base actual + upgrade)...${NC}"
# --network host: en servidores con DNS interno los contenedores de build no resuelven.
docker build --pull --network host -t zpush:latest "$AQUI"

echo -e "${GREEN}[2/5] Configuraciones en ${CONF} (se conservan si ya existen)...${NC}"
mkdir -p "$CONF" "$ESTADO" "$LOGS"
# El fichero de usuarios/dispositivos debe existir con un array PHP serializado: vacío o ausente
# hace fallar LinkUserDevice. Un estado de una instalación nativa antigua (users como carpeta) no vale.
if [ -d "$ESTADO/users" ]; then mv "$ESTADO/users" "$ESTADO/users.nativo-$(date +%Y%m%d)"; fi
[ -s "$ESTADO/users" ] || printf 'a:0:{}' > "$ESTADO/users"
chown -R 33:33 "$ESTADO" "$LOGS"        # www-data dentro del contenedor
for f in config.php backend-imap.php backend-caldav.php backend-carddav.php backend-combined.php autodiscover.php; do
    if [ ! -f "$CONF/$f" ]; then
        sed -e "s/mail\.example\.org/${HOST_CORREO}/g" "$AQUI/configs/$f" > "$CONF/$f"
        echo "  escrito $f"
    else
        echo "  conservado $f"
    fi
done
chmod 640 "$CONF"/*.php && chown root:33 "$CONF"/*.php

echo -e "${GREEN}[3/5] Contenedor zpush...${NC}"
docker rm -f zpush >/dev/null 2>&1 || true
docker run -d --name zpush --restart unless-stopped \
    --add-host host.docker.internal:host-gateway \
    -p 127.0.0.1:9000:9000 \
    -v "$ESTADO":/var/lib/z-push \
    -v "$LOGS":/var/log/z-push \
    -v "$CONF/config.php":/opt/z-push/src/config.php:ro \
    -v "$CONF/backend-imap.php":/opt/z-push/src/backend/imap/config.php:ro \
    -v "$CONF/backend-caldav.php":/opt/z-push/src/backend/caldav/config.php:ro \
    -v "$CONF/backend-carddav.php":/opt/z-push/src/backend/carddav/config.php:ro \
    -v "$CONF/backend-combined.php":/opt/z-push/src/backend/combined/config.php:ro \
    -v "$CONF/autodiscover.php":/opt/z-push/src/autodiscover/config.php:ro \
    zpush:latest >/dev/null
sleep 2
docker ps --format '{{.Names}} {{.Status}}' | grep -q '^zpush Up' || { echo -e "${RED}el contenedor no arrancó: docker logs zpush${NC}"; exit 1; }

echo -e "${GREEN}[4/5] Snippet de nginx...${NC}"
mkdir -p /etc/nginx/snippets/maquita-apps
install -m644 "$AQUI/nginx/activesync.conf" /etc/nginx/snippets/maquita-apps/activesync.conf
if grep -q "maquita-apps/activesync.conf" /etc/nginx/sites-enabled/* 2>/dev/null; then
    nginx -t >/dev/null && systemctl reload nginx && echo "  nginx recargado"
else
    echo -e "  ${YELLOW}Añade dentro del server{} HTTPS del correo:  include snippets/maquita-apps/activesync.conf;${NC}"
    echo -e "  ${YELLOW}y recarga nginx. El autodiscover ya lo sirve el backend (XML y JSON).${NC}"
fi

echo -e "${GREEN}[5/5] Comprobación...${NC}"
CODIGO=$(curl -sk -o /dev/null -w '%{http_code}' -X OPTIONS "https://${HOST_CORREO}/Microsoft-Server-ActiveSync" --resolve "${HOST_CORREO}:443:127.0.0.1" 2>/dev/null || echo 000)
echo "  OPTIONS /Microsoft-Server-ActiveSync -> ${CODIGO} (401 = Z-Push responde y pide credenciales)"
echo "  Z-Push $(docker exec zpush cat /opt/z-push/VERSION 2>/dev/null)"
echo "  Radicale desde el contenedor: $(docker exec zpush php -r '$f=@fsockopen("host.docker.internal",5232,$e,$m,3); echo $f?"ok":"NO (Radicale debe escuchar en 172.17.0.1:5232 y el cortafuegos aceptar docker0 -> 5232/993/465)";')"
echo "  Colecciones de Radicale de todos los buzones:"; /opt/maquita-webmail/almacen/venv/bin/python /opt/maquita-webmail/deploy/tools/radicale-asegurar-colecciones.py --todos 2>/dev/null | tail -1 || true
echo ""
echo "Cuentas en Outlook (clásico y nuevo), Android e iOS: tipo Exchange/ActiveSync, servidor ${HOST_CORREO},"
echo "usuario = correo completo. El nuevo Outlook se configura solo por autodiscover. Ver OPERACION.md."
