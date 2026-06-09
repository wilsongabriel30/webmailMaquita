#!/bin/bash
# ===========================================================================
# deploy-webmail.sh — Script de deploy seguro para Maquita Webmail
# ===========================================================================
# IMPORTANTE: Este script es la ÚNICA forma autorizada de desplegar el
# frontend del webmail. NUNCA hacer rm -rf /opt/maquita-webmail/www/*
# manualmente, ya que la estructura de directorios es:
#
#   /opt/maquita-webmail/www/webmail/   ← Frontend React (SPA)
#
# Nginx sirve desde root=/opt/maquita-webmail/www con location /webmail/
# por lo que los archivos DEBEN estar en el subdirectorio /webmail/.
#
# Uso: bash /opt/maquita-webmail/deploy-webmail.sh
# ===========================================================================

set -euo pipefail

# --- Rutas (NO CAMBIAR sin actualizar nginx) ---
WEBMAIL_DIR="/opt/maquita-webmail"
FRONTEND_DIR="${WEBMAIL_DIR}/frontend"
DIST_DIR="${FRONTEND_DIR}/dist"
WWW_DIR="${WEBMAIL_DIR}/www"
DEPLOY_TARGET="${WWW_DIR}/webmail"  # ← Nginx espera archivos aquí
BACKEND_SERVICE="maquita-webmail"
BACKUP_DIR="${WEBMAIL_DIR}/deploy-backups"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== Deploy Maquita Webmail ===${NC}"
echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"

# --- Paso 1: Build ---
echo -e "\n${YELLOW}[1/5] Building frontend...${NC}"
cd "${FRONTEND_DIR}"
npm run build 2>&1 | tail -5

# --- Paso 2: Verificar que el build generó archivos ---
if [ ! -f "${DIST_DIR}/index.html" ]; then
    echo -e "${RED}ERROR: Build falló — no existe ${DIST_DIR}/index.html${NC}"
    exit 1
fi
FILE_COUNT=$(find "${DIST_DIR}" -type f | wc -l)
echo -e "${GREEN}Build OK: ${FILE_COUNT} archivos generados${NC}"

# --- Paso 2.5: GUARDIA de integridad del bundle (anti "X is not defined") ---
# Detecta referencias usadas pero no definidas (tree-shaking roto) ANTES de
# tocar produccion. Esto evito que un bundle roto rompa el correo para todos.
echo -e "\n${YELLOW}[2.5/5] Verificando integridad del bundle...${NC}"
if ! node "${FRONTEND_DIR}/scripts/check-bundle.mjs" "${DIST_DIR}/assets"; then
    echo -e "${RED}ERROR: El bundle contiene referencias indefinidas.${NC}"
    echo -e "${RED}Deploy ABORTADO — produccion queda INTACTA.${NC}"
    exit 1
fi

# --- Paso 3: Backup del deploy actual ---
echo -e "\n${YELLOW}[2/5] Backup del deploy actual...${NC}"
mkdir -p "${BACKUP_DIR}"
TIMESTAMP=$(date '+%Y%m%d-%H%M%S')
if [ -d "${DEPLOY_TARGET}" ]; then
    tar czf "${BACKUP_DIR}/webmail-${TIMESTAMP}.tar.gz" -C "${WWW_DIR}" webmail/
    echo -e "${GREEN}Backup: ${BACKUP_DIR}/webmail-${TIMESTAMP}.tar.gz${NC}"
    # Mantener solo los últimos 5 backups
    ls -t "${BACKUP_DIR}"/webmail-*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
else
    echo "No hay deploy anterior para respaldar"
fi

# --- Paso 4: Deploy (NUNCA tocar www/ raíz, solo www/webmail/) ---
echo -e "\n${YELLOW}[3/5] Desplegando en ${DEPLOY_TARGET}...${NC}"
# CRÍTICO: Solo borrar el contenido de www/webmail/, NUNCA www/ completo
rm -rf "${DEPLOY_TARGET}"
mkdir -p "${DEPLOY_TARGET}"
cp -r "${DIST_DIR}/"* "${DEPLOY_TARGET}/"
# Recrear symlink de downloads (directorio persistente fuera del deploy)
ln -sf /opt/maquita-webmail/downloads "${DEPLOY_TARGET}/downloads"

# Verificación post-deploy
if [ ! -f "${DEPLOY_TARGET}/index.html" ]; then
    echo -e "${RED}ERROR CRÍTICO: Deploy falló — restaurando backup...${NC}"
    rm -rf "${DEPLOY_TARGET}"
    mkdir -p "${DEPLOY_TARGET}"
    tar xzf "${BACKUP_DIR}/webmail-${TIMESTAMP}.tar.gz" -C "${WWW_DIR}"
    echo -e "${YELLOW}Backup restaurado${NC}"
    exit 1
fi

DEPLOYED_COUNT=$(find "${DEPLOY_TARGET}" -type f | wc -l)
echo -e "${GREEN}Deploy OK: ${DEPLOYED_COUNT} archivos en ${DEPLOY_TARGET}${NC}"

# --- Paso 5: Restart backend ---
echo -e "\n${YELLOW}[4/5] Reiniciando backend...${NC}"
systemctl restart "${BACKEND_SERVICE}"
sleep 2

if systemctl is-active --quiet "${BACKEND_SERVICE}"; then
    echo -e "${GREEN}Backend activo${NC}"
else
    echo -e "${RED}ERROR: Backend no arrancó — revisar: journalctl -u ${BACKEND_SERVICE}${NC}"
    exit 1
fi

# --- Paso 6: Verificación final ---
echo -e "\n${YELLOW}[5/5] Verificación...${NC}"
HTTP_CODE=$(curl -sk -L -o /dev/null -w '%{http_code}' https://mail.example.org/webmail/)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}Webmail respondiendo: HTTP ${HTTP_CODE}${NC}"
else
    echo -e "${RED}ALERTA: Webmail respondió HTTP ${HTTP_CODE} — verificar manualmente${NC}"
    echo "Backup disponible en: ${BACKUP_DIR}/webmail-${TIMESTAMP}.tar.gz"
    echo "Para restaurar: tar xzf ${BACKUP_DIR}/webmail-${TIMESTAMP}.tar.gz -C ${WWW_DIR}"
    exit 1
fi

echo -e "\n${GREEN}=== Deploy completado exitosamente ===${NC}"
echo "URL: https://mail.example.org/webmail/"
