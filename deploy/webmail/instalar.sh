#!/bin/bash
# ============================================================
# Instalador — Fundación Maquita Webmail (instalación NATIVA)
# Debian 12/13 o Ubuntu 22.04+ · Ejecutar como root.
# Deja un servidor de correo + webmail FUNCIONAL de extremo a extremo:
# PostgreSQL, Redis, Postfix, Dovecot, nginx, backend y frontend.
# Variables opcionales no interactivas:  DOMAIN=... MAIL_HOST=... bash instalar.sh
# ============================================================

set -e

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
APP_DIR=/opt/maquita-webmail
CFG="${APP_DIR}/deploy/webmail/configs"

# Si algo falla, indica el paso en vez de abortar en silencio
trap 'echo -e "\n${RED}✗ La instalación se detuvo (línea ${LINENO}). Revisa el último paso [N/14] mostrado arriba y el error inmediatamente anterior.${NC}"' ERR

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║    Fundación Maquita Webmail — Instalador        ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Ejecutar como root (sudo bash instalar.sh)${NC}"; exit 1
fi

# --- Dominio (interactivo o por variable de entorno) ---
if [ -z "$DOMAIN" ]; then
    read -p "Tu dominio de correo (ej: miempresa.com): " DOMAIN
fi
MAIL_HOST=${MAIL_HOST:-mail.${DOMAIN}}
echo -e "${YELLOW}Dominio: ${DOMAIN}  ·  Servidor: ${MAIL_HOST}${NC}"
if [ -z "$ASSUME_YES" ]; then
    read -p "¿Correcto? (s/n): " CONFIRM
    [ "$CONFIRM" != "s" ] && { echo "Cancelado."; exit 0; }
fi

# --- 1. Paquetes base ---
echo -e "\n${GREEN}[1/14] Instalando paquetes base...${NC}"
apt update && apt install -y \
    curl wget git sudo ufw openssl \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    redis-server \
    nginx certbot python3-certbot-nginx \
    postfix postfix-pgsql \
    dovecot-core dovecot-imapd dovecot-pop3d dovecot-lmtpd dovecot-pgsql \
    dovecot-sieve dovecot-managesieved \
    ssl-cert rspamd

# --- 2. Node.js 20 ---
echo -e "\n${GREEN}[2/14] Instalando Node.js 20...${NC}"
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs
fi
echo "Node $(node -v), NPM $(npm -v)"

# --- 3. PostgreSQL: usuario + base de datos ---
echo -e "\n${GREEN}[3/14] Configurando PostgreSQL...${NC}"
DB_PASS=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)
sudo -u postgres psql -c "CREATE USER mailserver WITH PASSWORD '${DB_PASS}';" 2>/dev/null \
    || sudo -u postgres psql -c "ALTER USER mailserver WITH PASSWORD '${DB_PASS}';"
sudo -u postgres psql -c "CREATE DATABASE maildb OWNER mailserver;" 2>/dev/null || true
sudo -u postgres psql -d maildb -c "GRANT ALL ON SCHEMA public TO mailserver;" 2>/dev/null || true

# --- 4. Redis / Valkey ---
# En Debian 13 (trixie), redis-server arrastra Valkey (fork de Redis) que toma el
# puerto 6379 y usa /etc/valkey/valkey.conf. Detectamos cuál está presente.
echo -e "\n${GREEN}[4/14] Configurando Redis/Valkey...${NC}"
REDIS_PASS=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)
if systemctl list-unit-files | grep -q '^valkey-server'; then
    RCONF=/etc/valkey/valkey.conf; RSVC=valkey-server
else
    RCONF=/etc/redis/redis.conf;   RSVC=redis-server
fi
sed -i "s/^# *requirepass .*/requirepass ${REDIS_PASS}/; s/^requirepass .*/requirepass ${REDIS_PASS}/" "$RCONF"
systemctl restart "$RSVC"
echo "  Servicio de caché activo: ${RSVC}"

# --- 5. Usuario vmail (uid/gid 5000, igual que Dovecot) ---
echo -e "\n${GREEN}[5/14] Creando usuario vmail (uid 5000)...${NC}"
groupadd -g 5000 vmail 2>/dev/null || true
useradd -u 5000 -g vmail -d /var/vmail -s /usr/sbin/nologin -m vmail 2>/dev/null || true
mkdir -p /var/vmail && chown -R vmail:vmail /var/vmail

# --- 6. Código de la aplicación ---
echo -e "\n${GREEN}[6/14] Obteniendo Maquita Webmail...${NC}"
if [ ! -d "${APP_DIR}/backend" ]; then
    git clone https://github.com/wilsongabriel30/webmailMaquita.git "${APP_DIR}"
fi
CFG="${APP_DIR}/deploy/webmail/configs"

# --- 7. Migraciones (esquema de correo + cumplimiento) ---
echo -e "\n${GREEN}[7/14] Aplicando migraciones (esquema de correo + app)...${NC}"
for f in "${APP_DIR}"/migrations/*.sql; do
    echo "  → $(basename "$f")"
    PGPASSWORD="${DB_PASS}" psql -h localhost -U mailserver -d maildb -f "$f" >/dev/null
done

# --- 8. Backend (.env + entorno virtual) ---
echo -e "\n${GREEN}[8/14] Configurando backend...${NC}"
cd "${APP_DIR}/backend"
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt
SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ADMIN_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
MASTER_PASS=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)
cat > .env << ENVEOF
DATABASE_URL=postgresql://mailserver:${DB_PASS}@localhost:5432/maildb
REDIS_URL=redis://:${REDIS_PASS}@localhost:6379/0
SECRET_KEY=${SECRET}
ADMIN_JWT_SECRET=${ADMIN_SECRET}
MASTER_PASSWORD=${MASTER_PASS}
IMAP_HOST=127.0.0.1
IMAP_PORT=143
SMTP_HOST=127.0.0.1
SMTP_PORT=587
SIEVE_HOST=127.0.0.1
SIEVE_PORT=4190
MAIL_DOMAIN=${DOMAIN}
COOKIE_DOMAIN=${MAIL_HOST}
CORS_ORIGINS=https://${MAIL_HOST}
ENVEOF

# --- 9. Frontend (compilar) ---
echo -e "\n${GREEN}[9/14] Compilando frontend...${NC}"
cd "${APP_DIR}/frontend"
npm ci --quiet && npx vite build
mkdir -p "${APP_DIR}/www" && ln -sf "${APP_DIR}/frontend/dist" "${APP_DIR}/www/webmail"
[ -f public/sw.js ] && cp public/sw.js dist/sw.js || true

# --- 10. Dovecot (buzones virtuales SQL + usuario maestro 'admin') ---
echo -e "\n${GREEN}[10/14] Configurando Dovecot...${NC}"
[ -f /etc/dovecot/dovecot.conf ] && cp /etc/dovecot/dovecot.conf "/etc/dovecot/dovecot.conf.bak.$(date +%Y%m%d%H%M%S)"
sed "s|__DB_PASS__|${DB_PASS}|g" "${CFG}/dovecot.conf" > /etc/dovecot/dovecot.conf
# Asegurar certificado snakeoil para que Dovecot arranque con TLS
[ -e /etc/dovecot/private/dovecot.pem ] || ln -sf /etc/ssl/certs/ssl-cert-snakeoil.pem /etc/dovecot/private/dovecot.pem
[ -e /etc/dovecot/private/dovecot.key ] || ln -sf /etc/ssl/private/ssl-cert-snakeoil.key /etc/dovecot/private/dovecot.key
# Usuario maestro 'admin' con la MASTER_PASSWORD del backend
MASTER_HASH=$(doveadm pw -s SHA512-CRYPT -p "${MASTER_PASS}")
echo "admin:${MASTER_HASH}" > /etc/dovecot/master-users
# El proceso auth de Dovecot 2.4 corre como usuario 'dovecot' (no root): debe poder
# leer el archivo. root:root 600 daria "internal auth failure" al abrir buzones.
chown root:dovecot /etc/dovecot/master-users
chmod 640 /etc/dovecot/master-users
doveconf -n >/dev/null && echo "  Dovecot: sintaxis OK"
systemctl restart dovecot

# --- 11. Postfix (SMTP + entrega LMTP a Dovecot) ---
echo -e "\n${GREEN}[11/14] Configurando Postfix...${NC}"
mkdir -p /etc/postfix/pgsql
for m in "${CFG}"/postfix-pgsql/*.cf; do
    sed "s|__DB_PASS__|${DB_PASS}|g" "$m" > "/etc/postfix/pgsql/$(basename "$m")"
done
chmod 640 /etc/postfix/pgsql/*.cf; chgrp postfix /etc/postfix/pgsql/*.cf
postconf -e \
  "myhostname = ${MAIL_HOST}" \
  "mydomain = ${DOMAIN}" \
  "myorigin = \$mydomain" \
  "virtual_mailbox_base = /var/vmail" \
  "virtual_uid_maps = static:5000" \
  "virtual_gid_maps = static:5000" \
  "virtual_minimum_uid = 5000" \
  "virtual_mailbox_domains = pgsql:/etc/postfix/pgsql/pgsql-virtual-domains.cf" \
  "virtual_mailbox_maps = pgsql:/etc/postfix/pgsql/pgsql-virtual-mailbox.cf" \
  "virtual_alias_maps = pgsql:/etc/postfix/pgsql/pgsql-virtual-aliases.cf" \
  "virtual_transport = lmtp:unix:private/dovecot-lmtp" \
  "smtpd_sasl_type = dovecot" \
  "smtpd_sasl_path = private/auth" \
  "smtpd_sasl_auth_enable = yes" \
  "smtpd_sender_login_maps = pgsql:/etc/postfix/pgsql/pgsql-sender-login-maps.cf"
# Servicio submission (587) con SASL
if ! grep -qE "^submission[[:space:]]+inet" /etc/postfix/master.cf; then
cat >> /etc/postfix/master.cf <<'EOF'
submission inet n       -       y       -       -       smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=may
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_client_restrictions=permit_sasl_authenticated,reject
  -o smtpd_recipient_restrictions=permit_sasl_authenticated,reject
EOF
fi
postfix check && echo "  Postfix: configuración OK"
systemctl restart postfix

# --- 12. Servicios (systemd + nginx) ---
echo -e "\n${GREEN}[12/14] Configurando servicios web...${NC}"
cp "${APP_DIR}/deploy/webmail/systemd/maquita-webmail.service" /etc/systemd/system/
systemctl daemon-reload && systemctl enable maquita-webmail
NGINX_CONF="/etc/nginx/sites-available/${MAIL_HOST}"
cp "${APP_DIR}/deploy/webmail/nginx/webmail.conf" "${NGINX_CONF}"
sed -i "s/mail\.tudominio\.com/${MAIL_HOST}/g; s/tudominio\.com/${DOMAIN}/g" "${NGINX_CONF}"
# El certificado de Let's Encrypt aun NO existe (certbot es un paso posterior).
# Arrancar con el certificado snakeoil para que nginx valide y sirva desde ya;
# 'certbot --nginx' reemplazara estas rutas por el certificado real.
sed -i "s|/etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem|/etc/ssl/certs/ssl-cert-snakeoil.pem|; s|/etc/letsencrypt/live/${MAIL_HOST}/privkey.pem|/etc/ssl/private/ssl-cert-snakeoil.key|" "${NGINX_CONF}"
ln -sf "${NGINX_CONF}" /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default   # evita conflicto con el server_name por defecto
mkdir -p /var/log/webmail /var/www/certbot
chown www-data:www-data /var/log/webmail

# --- 13. Buzón de demostración ---
echo -e "\n${GREEN}[13/14] Creando buzón de demostración...${NC}"
DEMO_PASS=$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | head -c 14)
DEMO_HASH=$(doveadm pw -s SHA512-CRYPT -p "${DEMO_PASS}")
sudo -u postgres psql -d maildb >/dev/null <<SQL
INSERT INTO domain(domain,description) VALUES('${DOMAIN}','dominio principal')
  ON CONFLICT (domain) DO NOTHING;
INSERT INTO mailbox(username,password,name,maildir,local_part,domain,active)
  VALUES('demo@${DOMAIN}','${DEMO_HASH}','Demo','${DOMAIN}/demo/','demo','${DOMAIN}',true)
  ON CONFLICT (username) DO UPDATE SET password=EXCLUDED.password;
SQL

# --- 14. Iniciar + verificar ---
echo -e "\n${GREEN}[14/14] Iniciando y verificando...${NC}"
systemctl restart maquita-webmail
nginx -t && systemctl reload nginx
sleep 3
HEALTH=$(curl -s http://127.0.0.1:8000/api/health 2>/dev/null || echo "sin respuesta")
AUTH_DEMO=$(doveadm auth test "demo@${DOMAIN}" "${DEMO_PASS}" 2>&1 | grep -c "auth succeeded" || true)
AUTH_MASTER=$(doveadm auth test "demo@${DOMAIN}*admin" "${MASTER_PASS}" 2>&1 | grep -c "auth succeeded" || true)

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ¡Instalación completada!                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}VERIFICACIÓN:${NC}"
echo "  Backend /api/health : ${HEALTH}"
echo "  Login buzón demo    : $([ "$AUTH_DEMO" = "1" ] && echo OK || echo FALLO)"
echo "  Login usuario maestro: $([ "$AUTH_MASTER" = "1" ] && echo OK || echo FALLO)"
echo ""
echo -e "${YELLOW}BUZÓN DE PRUEBA:${NC}"
echo "  Usuario:  demo@${DOMAIN}"
echo "  Clave:    ${DEMO_PASS}"
echo ""
echo -e "${YELLOW}CREDENCIALES GENERADAS (guardar en lugar seguro):${NC}"
echo "  DB password:      ${DB_PASS}"
echo "  Redis password:   ${REDIS_PASS}"
echo "  Master password:  ${MASTER_PASS}"
echo ""
echo -e "${YELLOW}PASOS FINALES (los únicos manuales):${NC}"
echo "  1. DNS:  A ${MAIL_HOST} → IP del servidor · MX ${DOMAIN} → ${MAIL_HOST} (10) · TXT ${DOMAIN} → v=spf1 mx a ~all"
echo "  2. Certificado TLS:  certbot --nginx -d ${MAIL_HOST}"
echo "  3. Entra a:  https://${MAIL_HOST}/webmail/  con demo@${DOMAIN}"
echo ""
