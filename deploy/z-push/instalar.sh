#!/bin/bash
# ============================================
# Instalador de Z-Push (ActiveSync)
# Para Fundación Maquita Webmail
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Instalador Z-Push para Fundación Maquita Webmail ===${NC}"
echo ""

# Verificar root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Ejecutar como root (sudo)${NC}"
    exit 1
fi

# Detectar versión de PHP
if command -v php &>/dev/null; then
    PHP_VERSION=$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')
    echo -e "${GREEN}✓ PHP detectado: ${PHP_VERSION}${NC}"
else
    echo -e "${YELLOW}PHP no encontrado. Instalando...${NC}"
    apt update
    apt install -y php-fpm
    PHP_VERSION=$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')
fi

# Verificar versión mínima
PHP_MAJOR=$(echo $PHP_VERSION | cut -d. -f1)
if [ "$PHP_MAJOR" -lt 8 ]; then
    echo -e "${RED}Error: Se requiere PHP 8.0+. Tienes PHP ${PHP_VERSION}${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Paso 1/6: Instalando extensiones PHP...${NC}"
apt update
apt install -y \
    php${PHP_VERSION}-imap \
    php${PHP_VERSION}-curl \
    php${PHP_VERSION}-xml \
    php${PHP_VERSION}-mbstring \
    php${PHP_VERSION}-intl \
    php${PHP_VERSION}-soap \
    php${PHP_VERSION}-xsl \
    libawl-php 2>/dev/null || \
apt install -y \
    php-imap \
    php-curl \
    php-xml \
    php-mbstring \
    php-intl \
    php-soap \
    php-xsl \
    libawl-php
echo -e "${GREEN}✓ Extensiones PHP instaladas${NC}"

echo ""
echo -e "${YELLOW}Paso 2/6: Descargando Z-Push...${NC}"
if [ -d /opt/z-push ]; then
    echo -e "${YELLOW}  /opt/z-push ya existe, actualizando...${NC}"
    cd /opt/z-push && git pull 2>/dev/null || echo "  (no se pudo actualizar, usando existente)"
else
    git clone --depth 1 https://github.com/Z-Hub/Z-Push.git /opt/z-push
fi
chown -R www-data:www-data /opt/z-push
echo -e "${GREEN}✓ Z-Push descargado en /opt/z-push${NC}"

echo ""
echo -e "${YELLOW}Paso 3/6: Creando directorios...${NC}"
mkdir -p /var/lib/z-push /var/log/z-push
chown -R www-data:www-data /var/lib/z-push /var/log/z-push
echo -e "${GREEN}✓ Directorios creados${NC}"

echo ""
echo -e "${YELLOW}Paso 4/6: Copiando configuraciones...${NC}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Solo copiar si no existen (no sobreescribir configs existentes)
for f in config.php; do
    if [ ! -f /opt/z-push/src/$f ] || [ -f /opt/z-push/src/${f}.orig ]; then
        cp "${SCRIPT_DIR}/configs/${f}" /opt/z-push/src/$f
        echo "  Copiado: $f"
    else
        echo "  Ya existe: $f (no sobreescrito)"
    fi
done

cp -n "${SCRIPT_DIR}/configs/backend-imap.php" /opt/z-push/src/backend/imap/config.php 2>/dev/null && echo "  Copiado: backend-imap" || echo "  Ya existe: backend-imap"
cp -n "${SCRIPT_DIR}/configs/backend-caldav.php" /opt/z-push/src/backend/caldav/config.php 2>/dev/null && echo "  Copiado: backend-caldav" || echo "  Ya existe: backend-caldav"
cp -n "${SCRIPT_DIR}/configs/backend-carddav.php" /opt/z-push/src/backend/carddav/config.php 2>/dev/null && echo "  Copiado: backend-carddav" || echo "  Ya existe: backend-carddav"
cp -n "${SCRIPT_DIR}/configs/backend-combined.php" /opt/z-push/src/backend/combined/config.php 2>/dev/null && echo "  Copiado: backend-combined" || echo "  Ya existe: backend-combined"
cp -n "${SCRIPT_DIR}/configs/autodiscover.php" /opt/z-push/src/autodiscover/config.php 2>/dev/null && echo "  Copiado: autodiscover" || echo "  Ya existe: autodiscover"

echo -e "${GREEN}✓ Configuraciones copiadas${NC}"

echo ""
echo -e "${YELLOW}Paso 5/6: Configurando PHP-FPM...${NC}"
# Copiar pool zpush
POOL_DIR="/etc/php/${PHP_VERSION}/fpm/pool.d"
if [ -d "$POOL_DIR" ]; then
    # Ajustar versión de PHP en el socket
    sed "s/php8.4/php${PHP_VERSION}/g" "${SCRIPT_DIR}/php-fpm/zpush.conf" > "${POOL_DIR}/zpush.conf"
    systemctl restart php${PHP_VERSION}-fpm
    echo -e "${GREEN}✓ PHP-FPM configurado (pool zpush)${NC}"
else
    echo -e "${RED}No se encontró ${POOL_DIR}. Configurar PHP-FPM manualmente.${NC}"
fi

echo ""
echo -e "${YELLOW}Paso 6/6: Verificando...${NC}"

# Verificar socket
SOCKET="/run/php/php${PHP_VERSION}-zpush.sock"
if [ -S "$SOCKET" ]; then
    echo -e "${GREEN}✓ Socket PHP-FPM activo: ${SOCKET}${NC}"
else
    echo -e "${RED}✗ Socket no encontrado: ${SOCKET}${NC}"
    echo "  Reintentar: systemctl restart php${PHP_VERSION}-fpm"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Z-Push instalado correctamente${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}PASOS MANUALES PENDIENTES:${NC}"
echo ""
echo "1. Editar las configuraciones con tu dominio:"
echo "   nano /opt/z-push/src/config.php"
echo "   nano /opt/z-push/src/backend/imap/config.php"
echo "   nano /opt/z-push/src/autodiscover/config.php"
echo "   → Cambiar 'mail.example.org' por tu dominio"
echo ""
echo "2. Agregar a tu Nginx (dentro del server block HTTPS):"
echo "   cat ${SCRIPT_DIR}/nginx/activesync.conf"
echo "   → Cambiar 'php8.4' por 'php${PHP_VERSION}'"
echo "   → Luego: nginx -t && systemctl reload nginx"
echo ""
echo "3. Configurar DNS:"
echo "   CNAME: autodiscover.tudominio.com → mail.tudominio.com"
echo ""
echo "4. Probar:"
echo "   curl -s -o /dev/null -w '%{http_code}' https://mail.tudominio.com/Microsoft-Server-ActiveSync"
echo "   (debe devolver 401)"
echo ""
echo "5. Conectar dispositivo móvil:"
echo "   Tipo: Exchange/ActiveSync"
echo "   Servidor: mail.tudominio.com"
echo "   Puerto: 443, SSL/TLS"
echo ""
