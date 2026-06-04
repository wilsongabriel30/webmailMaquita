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
trap 'echo -e "\n${RED}✗ La instalación se detuvo (línea ${LINENO}). Revisa el último paso [N/15] mostrado arriba y el error inmediatamente anterior.${NC}"' ERR

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
echo -e "\n${GREEN}[1/15] Instalando paquetes base...${NC}"
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
echo -e "\n${GREEN}[2/15] Instalando Node.js 20...${NC}"
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs
fi
echo "Node $(node -v), NPM $(npm -v)"

# --- 3. PostgreSQL: usuario + base de datos ---
echo -e "\n${GREEN}[3/15] Configurando PostgreSQL...${NC}"
DB_PASS=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)
sudo -u postgres psql -c "CREATE USER mailserver WITH PASSWORD '${DB_PASS}';" 2>/dev/null \
    || sudo -u postgres psql -c "ALTER USER mailserver WITH PASSWORD '${DB_PASS}';"
sudo -u postgres psql -c "CREATE DATABASE maildb OWNER mailserver;" 2>/dev/null || true
sudo -u postgres psql -d maildb -c "GRANT ALL ON SCHEMA public TO mailserver;" 2>/dev/null || true

# --- 4. Redis / Valkey ---
# En Debian 13 (trixie), redis-server arrastra Valkey (fork de Redis) que toma el
# puerto 6379 y usa /etc/valkey/valkey.conf. Detectamos cuál está presente.
echo -e "\n${GREEN}[4/15] Configurando Redis/Valkey...${NC}"
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
echo -e "\n${GREEN}[5/15] Creando usuario vmail (uid 5000)...${NC}"
groupadd -g 5000 vmail 2>/dev/null || true
useradd -u 5000 -g vmail -d /var/vmail -s /usr/sbin/nologin -m vmail 2>/dev/null || true
mkdir -p /var/vmail && chown -R vmail:vmail /var/vmail

# --- 6. Código de la aplicación ---
echo -e "\n${GREEN}[6/15] Obteniendo Maquita Webmail...${NC}"
if [ ! -d "${APP_DIR}/backend" ]; then
    git clone https://github.com/wilsongabriel30/webmailMaquita.git "${APP_DIR}"
fi
CFG="${APP_DIR}/deploy/webmail/configs"

# --- 7. Esquema de la base de datos (todas las tablas de la app) ---
echo -e "\n${GREEN}[7/15] Aplicando esquema de la base de datos...${NC}"
for f in "${APP_DIR}"/migrations/*.sql; do
    echo "  → $(basename "$f")"
    # ON_ERROR_STOP=0: el esquema usa IF NOT EXISTS; tolera re-ejecución sin abortar
    PGPASSWORD="${DB_PASS}" psql -v ON_ERROR_STOP=0 -h localhost -U mailserver -d maildb -f "$f" >/dev/null 2>&1
done

# --- 8. Backend (.env + entorno virtual) ---
echo -e "\n${GREEN}[8/15] Configurando backend...${NC}"
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
COOKIE_DOMAIN=.${DOMAIN}
CORS_ORIGINS=https://${MAIL_HOST},https://${DOMAIN},https://webmail.${DOMAIN},https://correo.${DOMAIN}
RADICALE_URL=http://127.0.0.1:5232
ENVEOF

# --- 9. Frontend (compilar) ---
echo -e "\n${GREEN}[9/15] Compilando frontend...${NC}"
cd "${APP_DIR}/frontend"
npm ci --quiet && npx vite build
mkdir -p "${APP_DIR}/www" && ln -sf "${APP_DIR}/frontend/dist" "${APP_DIR}/www/webmail"
[ -f public/sw.js ] && cp public/sw.js dist/sw.js || true

# --- 10. Dovecot (buzones virtuales SQL + usuario maestro 'admin') ---
echo -e "\n${GREEN}[10/15] Configurando Dovecot...${NC}"
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
echo -e "\n${GREEN}[11/15] Configurando Postfix...${NC}"
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
# rspamd como milter (procesa y FIRMA el correo) + generación de la clave DKIM
postconf -e \
  "smtpd_milters = inet:localhost:11332" \
  "non_smtpd_milters = inet:localhost:11332" \
  "milter_protocol = 6" \
  "milter_default_action = accept"
mkdir -p /var/lib/rspamd/dkim
rspamadm dkim_keygen -d "${DOMAIN}" -s mail -b 2048 \
  -k "/var/lib/rspamd/dkim/${DOMAIN}.mail.key" > "/tmp/dkim-${DOMAIN}.txt" 2>/dev/null || true
chown _rspamd:_rspamd "/var/lib/rspamd/dkim/${DOMAIN}.mail.key" 2>/dev/null || true
cat > /etc/rspamd/local.d/dkim_signing.conf <<DKIMC
enabled = true;
selector = "mail";
allow_username_mismatch = true;
path = "/var/lib/rspamd/dkim/\$domain.mail.key";
DKIMC
systemctl restart rspamd 2>/dev/null || true
systemctl restart postfix
echo "  DKIM generado (registro DNS en /tmp/dkim-${DOMAIN}.txt)"

# --- 12. Servicios (systemd + nginx) ---
echo -e "\n${GREEN}[12/15] Configurando servicios web...${NC}"
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
# MTA-STS: política de TLS obligatorio en tránsito (sube la nota de entregabilidad)
STS_ID=$(date +%Y%m%d%H%M%S)
mkdir -p /var/www/mta-sts/.well-known
cat > /var/www/mta-sts/.well-known/mta-sts.txt <<MTASTS
version: STSv1
mode: enforce
mx: ${MAIL_HOST}
max_age: 604800
MTASTS
cat > "/etc/nginx/sites-available/mta-sts.${DOMAIN}" <<MTANGINX
server {
    listen 80;
    server_name mta-sts.${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}
server {
    listen 443 ssl;
    server_name mta-sts.${DOMAIN};
    ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;
    location = /.well-known/mta-sts.txt {
        default_type text/plain;
        alias /var/www/mta-sts/.well-known/mta-sts.txt;
    }
    location / { return 404; }
}
MTANGINX
ln -sf "/etc/nginx/sites-available/mta-sts.${DOMAIN}" /etc/nginx/sites-enabled/
echo "  MTA-STS preparado (política servida en mta-sts.${DOMAIN})"
# Radicale: backend CalDAV/CardDAV del calendario y los contactos (puerto 5232)
mkdir -p /etc/radicale /var/lib/radicale/collections
cp "${CFG}/radicale.config" /etc/radicale/config
chown -R www-data:www-data /var/lib/radicale
cp "${APP_DIR}/deploy/webmail/configs/radicale.service" /etc/systemd/system/radicale.service
systemctl daemon-reload && systemctl enable --now radicale 2>/dev/null
echo "  Radicale (calendario/contactos) configurado en :5232"

# --- 13. Buzón de demostración (dominio FALSO + clave genérica para el 1er ingreso) ---
echo -e "\n${GREEN}[13/15] Creando buzón de demostración...${NC}"
# Clave genérica y conocida SOLO para el primer ingreso. El instalador avisa cambiarla.
CLAVE_GENERICA="Cambiar2026"
DEMO_DOM="ejemplo.local"
DEMO_HASH=$(doveadm pw -s SHA512-CRYPT -p "${CLAVE_GENERICA}")
sudo -u postgres psql -d maildb >/dev/null <<SQL
-- Dominio real (para que crees tus buzones cuando configures el DNS)
INSERT INTO domain(domain,description) VALUES('${DOMAIN}','dominio principal')
  ON CONFLICT (domain) DO NOTHING;
-- Dominio FALSO para el buzón de prueba: permite entrar al webmail SIN tener DNS configurado
INSERT INTO domain(domain,description) VALUES('${DEMO_DOM}','dominio de prueba')
  ON CONFLICT (domain) DO NOTHING;
INSERT INTO mailbox(username,password,name,maildir,local_part,domain,active)
  VALUES('demo@${DEMO_DOM}','${DEMO_HASH}','Demostración','${DEMO_DOM}/demo/','demo','${DEMO_DOM}',true)
  ON CONFLICT (username) DO UPDATE SET password=EXCLUDED.password;
-- El buzón demo queda como administrador para poder entrar al panel /admin del webmail
INSERT INTO admin(username,superadmin,active) VALUES('demo@${DEMO_DOM}',true,true)
  ON CONFLICT (username) DO UPDATE SET superadmin=true, active=true;
SQL

# --- 14. Panel de administración avanzado (adminMaquita, puerto 8443) ---
echo -e "\n${GREEN}[14/15] Instalando panel de administración avanzado...${NC}"
# Backend del panel (puerto 8001)
cd "${APP_DIR}/admin-panel/backend"
python3 -m venv venv
./venv/bin/pip install --quiet -r requirements.txt
# JWT_SECRET del panel = ADMIN_JWT_SECRET del webmail (si difieren, impersonate da 403)
cat > .env <<ENVADMIN
DB_HOST=localhost
DB_PORT=5432
DB_NAME=maildb
DB_USER=mailserver
DB_PASS=${DB_PASS}
JWT_SECRET=${ADMIN_SECRET}
RSPAMD_URL=http://localhost:11334
MASTER_PASSWORD=${MASTER_PASS}
ENVADMIN
# Frontend del panel
cd "${APP_DIR}/admin-panel/frontend"
npm ci --quiet && npx vite build
# Servicio systemd
cp "${APP_DIR}/admin-panel/deploy/maquita-admin.service" /etc/systemd/system/
systemctl daemon-reload && systemctl enable maquita-admin && systemctl restart maquita-admin
# nginx :8443 (auth básica + snakeoil hasta certbot)
ADMIN_NGINX="/etc/nginx/sites-available/${MAIL_HOST}-admin"
sed "s/__MAIL_HOST__/${MAIL_HOST}/g" "${APP_DIR}/admin-panel/deploy/nginx-admin.conf" > "${ADMIN_NGINX}"
ln -sf "${ADMIN_NGINX}" /etc/nginx/sites-enabled/
# Credencial de acceso (auth básica de nginx, usuario 'admin') — misma clave genérica
printf "admin:%s\n" "$(openssl passwd -apr1 "${CLAVE_GENERICA}")" > /etc/nginx/.htpasswd_admin
chmod 640 /etc/nginx/.htpasswd_admin; chgrp www-data /etc/nginx/.htpasswd_admin
# Primer usuario del panel (tabla admin_users, hash bcrypt) — misma clave genérica
sleep 3
ADMIN_BHASH=$(./venv/bin/python -c "import bcrypt,sys; print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())" "${CLAVE_GENERICA}" 2>/dev/null) || \
  ADMIN_BHASH=$("${APP_DIR}/admin-panel/backend/venv/bin/python" -c "import bcrypt,sys; print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())" "${CLAVE_GENERICA}")
PGPASSWORD="${DB_PASS}" psql -v ON_ERROR_STOP=0 -h localhost -U mailserver -d maildb >/dev/null 2>&1 <<SQLADMIN
INSERT INTO admin_users(username,password_hash,display_name,role,active)
  VALUES('admin','${ADMIN_BHASH}','Administrador','superadmin',true)
  ON CONFLICT (username) DO UPDATE SET password_hash=EXCLUDED.password_hash, active=true;
SQLADMIN
echo "  Panel de administración: https://${MAIL_HOST}:8443"

# --- 15. Iniciar + verificar ---
echo -e "\n${GREEN}[15/15] Iniciando y verificando...${NC}"
systemctl restart maquita-webmail
nginx -t && systemctl reload nginx
sleep 3
HEALTH=$(curl -s http://127.0.0.1:8000/api/health 2>/dev/null || echo "sin respuesta")
AUTH_DEMO=$(doveadm auth test "demo@${DEMO_DOM}" "${CLAVE_GENERICA}" 2>&1 | grep -c "auth succeeded" || true)
AUTH_MASTER=$(doveadm auth test "demo@${DEMO_DOM}*admin" "${MASTER_PASS}" 2>&1 | grep -c "auth succeeded" || true)

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ¡Instalación completada!                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}VERIFICACIÓN:${NC}"
echo "  Backend /api/health : ${HEALTH}"
echo "  Login buzón demo    : $([ "$AUTH_DEMO" = "1" ] && echo OK || echo FALLO)"
echo "  Login usuario maestro: $([ "$AUTH_MASTER" = "1" ] && echo OK || echo FALLO)"
echo "  Radicale (calendario) : $(curl -s -o /dev/null -w \"%{http_code}\" --max-time 4 http://127.0.0.1:5232/ 2>/dev/null) (000=no responde)"
echo ""
echo -e "${RED}==============================================================${NC}"
echo -e "${RED}  CLAVE DE PRIMER INGRESO (para TODOS los accesos):  ${CLAVE_GENERICA}${NC}"
echo -e "${RED}  >>> CÁMBIALA APENAS ENTRES. Es genérica y conocida. <<<${NC}"
echo -e "${RED}==============================================================${NC}"
echo ""
echo -e "${YELLOW}1) WEBMAIL  (puedes entrar YA, sin necesidad de DNS):${NC}"
echo "     URL:      https://${MAIL_HOST}/webmail/"
echo "     Usuario:  demo@${DEMO_DOM}"
echo "     Clave:    ${CLAVE_GENERICA}      (recuerda cambiarla en Ajustes)"
echo "     Este buzón es ADMINISTRADOR: dentro del webmail tienes el panel /admin"
echo "     (dominios, buzones, alias, auditoría, anti-spam, eDiscovery...)."
echo ""
echo -e "${YELLOW}2) PANEL DE ADMINISTRACIÓN AVANZADO:${NC}"
echo "     URL:      https://${MAIL_HOST}:8443"
echo "     Usuario:  admin"
echo "     Clave:    ${CLAVE_GENERICA}      (sirve para el aviso del navegador y para el panel)"
echo "     (autoresponder, firmas masivas, buzones compartidos, rspamd, firewall)"
echo "     Cámbiala dentro del panel; la del navegador, en /etc/nginx/.htpasswd_admin"
echo ""
echo "  Cuando configures tu dominio real, crea tus buzones desde el panel."
echo "  Hacer admin a otro:  INSERT INTO admin(username,superadmin,active) VALUES('correo@${DOMAIN}',true,true);"
echo ""
echo -e "${YELLOW}CREDENCIALES DE SISTEMA (guárdalas en lugar seguro):${NC}"
echo "  DB password:      ${DB_PASS}"
echo "  Redis password:   ${REDIS_PASS}"
echo "  Master password:  ${MASTER_PASS}"
echo ""
echo -e "${YELLOW}PASOS FINALES — DNS (imprescindible para enviar y recibir correo):${NC}"
echo "  Crea estos registros donde administras tu dominio (tu proveedor de DNS):"
echo ""
echo "  1) A      ${MAIL_HOST}              -> <IP PÚBLICA DE ESTE SERVIDOR>"
echo "  2) MX     ${DOMAIN}                 -> ${MAIL_HOST}   (prioridad 10)"
echo "  3) TXT    ${DOMAIN}                 -> v=spf1 mx ~all        (SPF: autoriza a tu servidor a enviar)"
echo "  4) TXT    _dmarc.${DOMAIN}          -> v=DMARC1; p=quarantine; rua=mailto:postmaster@${DOMAIN}"
echo "  5) TXT    mail._domainkey.${DOMAIN}  -> (DKIM, ya generado; ver abajo)"
echo "  6) PTR (DNS inverso):  <IP> -> ${MAIL_HOST}"
echo "        Lo configura el PROVEEDOR de tu servidor/VPS, no aquí. SIN PTR, Gmail/Outlook"
echo "        rechazan tu correo. Pídeselo a tu proveedor (Hetzner, OVH, DigitalOcean, etc.)."
echo ""
echo "  >> Registro DKIM a publicar (copia el contenido entre comillas en el valor del TXT):"
sed "s/^/     /" "/tmp/dkim-${DOMAIN}.txt" 2>/dev/null || echo "     (no se generó; revisa rspamd)"
echo ""
echo ""
echo "  RECOMENDADO (para 10/10 — MTA-STS ya quedó montado en el servidor):"
echo "    7) A      mta-sts.${DOMAIN}            -> <IP PÚBLICA DE ESTE SERVIDOR>"
echo "    8) TXT    _mta-sts.${DOMAIN}           -> v=STSv1; id=${STS_ID}"
echo "    9) TXT    _smtp._tls.${DOMAIN}         -> v=TLSRPTv1; rua=mailto:postmaster@${DOMAIN}"
echo "       Después de publicar el A:  certbot --nginx -d mta-sts.${DOMAIN}"
echo "       Más (DANE, BIMI, listas negras, 10/10):  docs/ENTREGABILIDAD.md"
echo ""
echo "  Explicación paso a paso de cada registro (para principiantes):  docs/CONFIGURAR-DNS.md"
echo ""
echo -e "${YELLOW}DESPUÉS DEL DNS:${NC}"
echo "  • Certificado TLS (HTTPS):   certbot --nginx -d ${MAIL_HOST}"
echo "  • Webmail:                   https://${MAIL_HOST}/webmail/   (usuario demo@${DOMAIN})"
echo "  • Panel de administración:   https://${MAIL_HOST}:8443"
echo ""
