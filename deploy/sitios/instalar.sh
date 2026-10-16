#!/usr/bin/env bash
# Sitios web del servidor (sección «Sitios web» del panel): PHP-FPM, MariaDB, FTP seguro, SFTP
# encerrado y WP-CLI. Idempotente. Se llama con:  sudo bash deploy/webmail/instalar-app.sh sitios
#
# Todo es software libre: PHP (licencia PHP), MariaDB (GPLv2), vsftpd (GPLv2), OpenSSH (BSD),
# WP-CLI (MIT). WordPress y Joomla (GPLv2+) no se instalan aquí: los descarga el panel en cada
# sitio, de su origen oficial y verificados, cuando se elige la aplicación.
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
WP_CLI_VERSION="${WP_CLI_VERSION:-2.12.0}"
PASV_MIN=40000
PASV_MAX=40100

[ "$EUID" -eq 0 ] || { echo -e "${RED}Ejecutar como root.${NC}"; exit 1; }

echo -e "${GREEN}[1/7] Paquetes (PHP-FPM, MariaDB, vsftpd)...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq php-fpm php-cli php-mysql php-xml php-mbstring php-curl php-zip php-gd \
    php-intl php-bcmath php-imagick mariadb-server vsftpd unzip ssl-cert >/dev/null
PHP_VER="$(ls /etc/php | sort -V | tail -1)"
systemctl enable mariadb "php${PHP_VER}-fpm" >/dev/null 2>&1
systemctl start mariadb
# Cada sitio tiene su propio pool. El «www» que trae Debian no lo usa nadie, pero PHP-FPM no
# arranca sin ningún pool: se sustituye por uno mínimo bajo demanda (sin procesos en reposo).
POOLS="/etc/php/${PHP_VER}/fpm/pool.d"
if [ -f "${POOLS}/www.conf" ]; then
    mv "${POOLS}/www.conf" "${POOLS}/www.conf.desactivado"
fi
cat > "${POOLS}/00-reserva.conf" <<'EOF'
; Pool mínimo para que PHP-FPM arranque aunque no haya sitios. Ningún vhost lo usa.
[reserva]
user = www-data
group = www-data
listen = /run/php/reserva.sock
listen.owner = root
listen.group = root
listen.mode = 0600
pm = ondemand
pm.max_children = 1
pm.process_idle_timeout = 10s
EOF
systemctl reset-failed "php${PHP_VER}-fpm" 2>/dev/null || true
systemctl restart "php${PHP_VER}-fpm"

echo -e "${GREEN}[2/7] Grupo y carpetas...${NC}"
getent group sitios >/dev/null || groupadd --system sitios
install -d -m 755 -o root -g root /srv/sitios
install -d -m 700 -o root -g root /srv/sitios-papelera /etc/maquita-sitios
install -d -m 755 /var/www/certbot
touch /etc/vsftpd.sitios && chmod 644 /etc/vsftpd.sitios

echo -e "${GREEN}[3/7] WP-CLI ${WP_CLI_VERSION} (verificado con su SHA-512 oficial)...${NC}"
if ! /usr/local/bin/wp --allow-root --version 2>/dev/null | grep -q "${WP_CLI_VERSION}"; then
    TMP="$(mktemp -d)"
    BASE="https://github.com/wp-cli/wp-cli/releases/download/v${WP_CLI_VERSION}/wp-cli-${WP_CLI_VERSION}.phar"
    curl -fsSL -o "${TMP}/wp.phar" "${BASE}"
    curl -fsSL -o "${TMP}/wp.phar.sha512" "${BASE}.sha512"
    ESPERADO="$(awk '{print $1}' "${TMP}/wp.phar.sha512")"
    REAL="$(sha512sum "${TMP}/wp.phar" | awk '{print $1}')"
    [ -n "${ESPERADO}" ] && [ "${ESPERADO}" = "${REAL}" ] || { echo -e "${RED}WP-CLI no coincide con su suma oficial. Cancelado.${NC}"; rm -rf "${TMP}"; exit 1; }
    install -m 755 "${TMP}/wp.phar" /usr/local/bin/wp
    rm -rf "${TMP}"
fi

echo -e "${GREEN}[4/7] FTP seguro (vsftpd, solo con cifrado, encerrado en la carpeta del sitio)...${NC}"
if [ -f /etc/vsftpd.conf ] && [ ! -f /etc/vsftpd.conf.original ]; then cp /etc/vsftpd.conf /etc/vsftpd.conf.original; fi
CERT=/etc/ssl/certs/ssl-cert-snakeoil.pem; LLAVE=/etc/ssl/private/ssl-cert-snakeoil.key
MAIL_HOST="$(grep -E '^MAIL_HOST=' "${APP_DIR}/backend/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)"
[ -n "${MAIL_HOST}" ] || MAIL_HOST="$(hostname -f 2>/dev/null || true)"
if [ -n "${MAIL_HOST}" ] && [ -e "/etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem" ]; then
    CERT="/etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem"; LLAVE="/etc/letsencrypt/live/${MAIL_HOST}/privkey.pem"
fi
cat > /etc/vsftpd.conf <<EOF
# Generado por deploy/sitios/instalar.sh. FTP de los sitios web: solo cuentas de la lista
# /etc/vsftpd.sitios (las activa el panel), solo con TLS y encerradas en la carpeta del sitio.
listen=YES
listen_ipv6=NO
anonymous_enable=NO
local_enable=YES
write_enable=YES
local_umask=027
chroot_local_user=YES
allow_writeable_chroot=NO
userlist_enable=YES
userlist_deny=NO
userlist_file=/etc/vsftpd.sitios
pam_service_name=vsftpd-sitios
secure_chroot_dir=/var/run/vsftpd/empty
hide_ids=YES
ftpd_banner=FTP
ssl_enable=YES
allow_anon_ssl=NO
force_local_logins_ssl=YES
force_local_data_ssl=YES
ssl_tlsv1=NO
ssl_sslv2=NO
ssl_sslv3=NO
require_ssl_reuse=NO
ssl_ciphers=HIGH
rsa_cert_file=${CERT}
rsa_private_key_file=${LLAVE}
pasv_enable=YES
pasv_min_port=${PASV_MIN}
pasv_max_port=${PASV_MAX}
xferlog_enable=YES
xferlog_std_format=NO
log_ftp_protocol=NO
max_per_ip=5
EOF
# PAM propio: las cuentas de los sitios no tienen shell válida, y el PAM de vsftpd de Debian
# exige una (pam_shells). Este no la pide, pero sí exige estar en el grupo «sitios».
cat > /etc/pam.d/vsftpd-sitios <<'EOF'
auth     required pam_succeed_if.so user ingroup sitios
auth     required pam_unix.so
account  required pam_unix.so
session  required pam_loginuid.so
EOF
systemctl enable vsftpd >/dev/null 2>&1
systemctl restart vsftpd

echo -e "${GREEN}[5/7] SFTP encerrado para el grupo «sitios» (sin shell)...${NC}"
# Va al FINAL de sshd_config, no en sshd_config.d/: ese directorio se incluye al principio y un
# «Match» allí se tragaría las directivas globales que vienen detrás.
SSHD=/etc/ssh/sshd_config
[ -f "${SSHD}.antes-sitios" ] || cp "${SSHD}" "${SSHD}.antes-sitios"
sed -i '/^# >>> sitios-web (maquita-sitios)/,/^# <<< sitios-web/d' "${SSHD}"
cat >> "${SSHD}" <<'EOF'
# >>> sitios-web (maquita-sitios): cuentas de los sitios, solo SFTP encerrado en su carpeta
Match Group sitios
    ChrootDirectory %h
    ForceCommand internal-sftp -u 0027
    PasswordAuthentication yes
    AllowTcpForwarding no
    AllowAgentForwarding no
    X11Forwarding no
    PermitTunnel no
    PermitTTY no
# <<< sitios-web
EOF
if sshd -t; then
    systemctl reload ssh 2>/dev/null || systemctl reload sshd
else
    cp "${SSHD}.antes-sitios" "${SSHD}"
    echo -e "${YELLOW}sshd no aceptó la configuración de SFTP: se dejó como estaba (el FTP seguro sigue disponible).${NC}"
fi

echo -e "${GREEN}[6/7] Ayudante del panel y permisos...${NC}"
install -d -m 755 /usr/local/lib/maquita-sitios
install -m 644 "${SELF}"/lib/*.py /usr/local/lib/maquita-sitios/
install -m 755 "${SELF}/maquita-sitios" /usr/local/sbin/maquita-sitios
# El envoltorio sudo del panel conoce maquita-sitios desde esta versión: reinstalarlo.
install -m 755 "${APP_DIR}/deploy/sudoers/maquita-sudo" /usr/local/sbin/maquita-sudo
# fail2ban: intentos fallidos de FTP.
if [ -d /etc/fail2ban/jail.d ]; then
    cat > /etc/fail2ban/jail.d/sitios-ftp.local <<'EOF'
[vsftpd]
enabled = true
backend = auto
logpath = /var/log/vsftpd.log
maxretry = 5
EOF
    systemctl reload fail2ban 2>/dev/null || true
fi

echo -e "${GREEN}[7/7] Comprobación...${NC}"
/usr/local/sbin/maquita-sitios estado
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow 21/tcp >/dev/null; ufw allow ${PASV_MIN}:${PASV_MAX}/tcp >/dev/null
fi
echo -e "${GREEN}Listo.${NC} En el panel: Hospedaje → Sitios web."
echo "  Si el servidor está detrás de NAT, abre/redirige TCP 21 y ${PASV_MIN}-${PASV_MAX} para el FTP."
