#!/bin/bash
# ============================================================
# Instalador — Fundación Maquita Webmail
# Ejecutar como root en Debian 12/13 o Ubuntu 22.04+
# ============================================================

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║    Fundación Maquita Webmail — Instalador        ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Ejecutar como root (sudo bash instalar.sh)${NC}"
    exit 1
fi

# --- Preguntar dominio ---
read -p "Tu dominio de correo (ej: miempresa.com): " DOMAIN
read -p "Hostname del servidor de correo (ej: mail.${DOMAIN}): " MAIL_HOST
MAIL_HOST=${MAIL_HOST:-mail.${DOMAIN}}

echo ""
echo -e "${YELLOW}Dominio: ${DOMAIN}${NC}"
echo -e "${YELLOW}Servidor: ${MAIL_HOST}${NC}"
echo ""
read -p "¿Correcto? (s/n): " CONFIRM
if [ "$CONFIRM" != "s" ]; then echo "Cancelado."; exit 0; fi

# --- 1. Paquetes base ---
echo -e "\n${GREEN}[1/10] Instalando paquetes base...${NC}"
apt update && apt install -y \
    curl wget git sudo ufw \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    redis-server \
    nginx certbot python3-certbot-nginx \
    postfix postfix-pgsql \
    dovecot-core dovecot-imapd dovecot-lmtpd dovecot-pgsql \
    dovecot-sieve dovecot-managesieved \
    rspamd

# --- 2. Node.js ---
echo -e "\n${GREEN}[2/10] Instalando Node.js 20...${NC}"
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs
fi
echo "Node $(node -v), NPM $(npm -v)"

# --- 3. PostgreSQL ---
echo -e "\n${GREEN}[3/10] Configurando PostgreSQL...${NC}"
DB_PASS=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)
sudo -u postgres psql -c "CREATE USER mailserver WITH PASSWORD '${DB_PASS}';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE maildb OWNER mailserver;" 2>/dev/null || true
sudo -u postgres psql -d maildb -c "GRANT ALL ON SCHEMA public TO mailserver;" 2>/dev/null || true
echo -e "${GREEN}DB password: ${DB_PASS} (guardar en lugar seguro)${NC}"

# --- 4. Redis ---
echo -e "\n${GREEN}[4/10] Configurando Redis...${NC}"
REDIS_PASS=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)
sed -i "s/^# requirepass .*/requirepass ${REDIS_PASS}/" /etc/redis/redis.conf
sed -i "s/^requirepass .*/requirepass ${REDIS_PASS}/" /etc/redis/redis.conf
systemctl restart redis-server

# --- 5. Usuario vmail ---
echo -e "\n${GREEN}[5/10] Creando usuario vmail...${NC}"
groupadd -g 150 vmail 2>/dev/null || true
useradd -u 150 -g vmail -d /var/vmail -s /usr/sbin/nologin -m vmail 2>/dev/null || true
mkdir -p /var/vmail
chown -R vmail:vmail /var/vmail

# --- 6. Clonar repositorio ---
echo -e "\n${GREEN}[6/10] Instalando Maquita Webmail...${NC}"
if [ ! -d /opt/maquita-webmail ]; then
    git clone https://github.com/wilsongabriel30/webmailMaquita.git /opt/maquita-webmail
else
    echo "  Ya existe /opt/maquita-webmail, actualizando..."
    cd /opt/maquita-webmail && git pull origin main 2>/dev/null || true
fi

# --- 7. Backend ---
echo -e "\n${GREEN}[7/10] Configurando backend...${NC}"
cd /opt/maquita-webmail/backend
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt

SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ADMIN_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(16))")
MASTER_PASS=$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9!@#' | head -c 16)

cat > .env << ENVEOF
DATABASE_URL=postgresql://mailserver:${DB_PASS}@localhost:5432/maildb
REDIS_URL=redis://:${REDIS_PASS}@localhost:6379/0
SECRET_KEY=${SECRET}
IMAP_HOST=127.0.0.1
IMAP_PORT=143
SMTP_HOST=127.0.0.1
SMTP_PORT=587
SIEVE_HOST=127.0.0.1
SIEVE_PORT=4190
MAIL_DOMAIN=${DOMAIN}
COOKIE_DOMAIN=${MAIL_HOST}
CORS_ORIGINS=https://${MAIL_HOST}
MASTER_PASSWORD=${MASTER_PASS}
ADMIN_JWT_SECRET=${ADMIN_SECRET}
ENVEOF
echo -e "${GREEN}  .env generado con credenciales únicas${NC}"

# --- 8. Frontend ---
echo -e "\n${GREEN}[8/10] Compilando frontend...${NC}"
cd /opt/maquita-webmail/frontend

# Ajustar base URL si es diferente
sed -i "s|base: '/webmail/'|base: '/webmail/'|" vite.config.ts

npm ci --quiet
npx vite build

mkdir -p /opt/maquita-webmail/www
ln -sf /opt/maquita-webmail/frontend/dist /opt/maquita-webmail/www/webmail

# Copiar Service Worker
if [ -f /opt/maquita-webmail/frontend/public/sw.js ]; then
    cp /opt/maquita-webmail/frontend/public/sw.js /opt/maquita-webmail/frontend/dist/sw.js
fi

# --- 9. Servicios ---
echo -e "\n${GREEN}[9/10] Configurando servicios...${NC}"

# Systemd
cp /opt/maquita-webmail/deploy/webmail/systemd/maquita-webmail.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable maquita-webmail

# Nginx
NGINX_CONF="/etc/nginx/sites-available/${MAIL_HOST}"
cp /opt/maquita-webmail/deploy/webmail/nginx/webmail.conf "${NGINX_CONF}"
sed -i "s/tudominio\.com/${DOMAIN}/g" "${NGINX_CONF}"
sed -i "s/mail\.tudominio\.com/${MAIL_HOST}/g" "${NGINX_CONF}"
ln -sf "${NGINX_CONF}" /etc/nginx/sites-enabled/

# Crear directorios de logs
mkdir -p /var/log/webmail /var/www/certbot
chown www-data:www-data /var/log/webmail

# --- 10. Iniciar ---
echo -e "\n${GREEN}[10/10] Iniciando servicios...${NC}"
systemctl restart maquita-webmail
nginx -t && systemctl reload nginx

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ¡Instalación completada!                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}CREDENCIALES GENERADAS (guardar en lugar seguro):${NC}"
echo "  DB password:     ${DB_PASS}"
echo "  Redis password:  ${REDIS_PASS}"
echo "  Master password: ${MASTER_PASS}"
echo "  Secret key:      ${SECRET}"
echo ""
echo -e "${YELLOW}PASOS PENDIENTES:${NC}"
echo ""
echo "1. Configurar DNS:"
echo "   A     ${MAIL_HOST}  →  IP_DE_ESTE_SERVIDOR"
echo "   MX    ${DOMAIN}     →  ${MAIL_HOST} (prioridad 10)"
echo "   TXT   ${DOMAIN}     →  v=spf1 mx a ~all"
echo ""
echo "2. Obtener certificado SSL:"
echo "   certbot --nginx -d ${MAIL_HOST}"
echo ""
echo "3. Configurar Postfix y Dovecot:"
echo "   Ver README.md secciones 5 y 6"
echo ""
echo "4. Crear primer buzón:"
echo "   doveadm pw -s BLF-CRYPT  (para generar hash)"
echo "   Ver README.md sección 14"
echo ""
echo "5. Acceder:"
echo "   https://${MAIL_HOST}/webmail/"
echo ""
echo "6. Verificar salud:"
echo "   curl http://127.0.0.1:8000/api/health"
echo ""
