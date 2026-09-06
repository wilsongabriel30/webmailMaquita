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
# Uso:
#   bash deploy-webmail.sh                  → build + deploy + reinicia backend
#   bash deploy-webmail.sh --solo-frontend  → build + deploy SIN tocar el backend
#     (para cambios solo de React/HTML/CSS: el reinicio del backend corta el
#      correo ~30 segundos a los usuarios conectados y no hace falta)
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
# T-35: cada publicación renueva la caché del service worker (arranque sin red con la portada vigente)
npm run build 2>&1 | tail -5

# Marca y version de cache del service worker.
#
# Se aplican sobre dist/ DESPUES de construir, nunca sobre public/sw.js. Antes se
# hacia sobre el fuente y cada publicacion dejaba el arbol de trabajo sucio: el
# fichero versionado quedaba modificado con la fecha, y esa suciedad se acababa
# colando en un commit o se perdia en un git checkout. Un despliegue no debe
# modificar el codigo fuente. Vite copia public/ a dist/ tal cual, asi que el
# resultado publicado es el mismo.
SW_DIST="${DIST_DIR}/sw.js"
if [ -f "$SW_DIST" ]; then
  NOMBRE_APP="$(sudo -u postgres psql -d maildb -tAc \
    "SELECT value FROM branding_settings WHERE key='app_name'" 2>/dev/null | xargs || true)"
  if [ -n "$NOMBRE_APP" ]; then
    # Prefijo del nombre de cache: minusculas y guiones. NO afecta a los
    # identificadores de IndexedDB del correo ni del chat, que son fijos.
    PREFIJO_CACHE="$(printf '%s' "$NOMBRE_APP" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-|-$//g')"
    sed -i -E "s/^const NOMBRE_APP = \"[^\"]*\";/const NOMBRE_APP = \"${NOMBRE_APP}\";/" "$SW_DIST"
    sed -i -E "s/(const CACHE_NAME = \")[^\"]*(-v)/\1${PREFIJO_CACHE}\2/" "$SW_DIST"
    echo "   Marca inyectada en el service worker: ${NOMBRE_APP} (cache: ${PREFIJO_CACHE}-v…)"
  fi
  sed -i -E "s/(const CACHE_NAME = \"[^\"]*-v)[0-9A-Za-z-]*(\")/\1$(date +%Y%m%d%H%M)\2/" "$SW_DIST"
  echo "   Version de cache renovada en dist/sw.js (el fuente no se toca)"
fi

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
# Conservar assets con hash de deploys anteriores (pestañas abiertas siguen
# pidiendo chunks viejos; sin esto ven \"Failed to fetch dynamically imported module\").
OLD_ASSETS=""
if [ -d "${DEPLOY_TARGET}/assets" ]; then
    OLD_ASSETS=$(mktemp -d)
    cp -r "${DEPLOY_TARGET}/assets/." "${OLD_ASSETS}/"
fi
# CRÍTICO: Solo borrar el contenido de www/webmail/, NUNCA www/ completo
rm -rf "${DEPLOY_TARGET}"
mkdir -p "${DEPLOY_TARGET}"
cp -r "${DIST_DIR}/"* "${DEPLOY_TARGET}/"
# Restaurar assets anteriores SIN pisar los nuevos (hash único = sin colisiones)
if [ -n "${OLD_ASSETS}" ] && [ -d "${OLD_ASSETS}" ]; then
    cp -rn "${OLD_ASSETS}/." "${DEPLOY_TARGET}/assets/" 2>/dev/null || true
    rm -rf "${OLD_ASSETS}"
    # Purgar assets con más de 14 días (huérfanos de deploys muy viejos)
    find "${DEPLOY_TARGET}/assets" -type f -mtime +14 -delete 2>/dev/null || true
fi
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

# --- Paso 5: Restart backend (omitido con --solo-frontend) ---
if [[ "${1:-}" == "--solo-frontend" ]]; then
    echo -e "\n${YELLOW}[4/5] Backend NO reiniciado (--solo-frontend)${NC}"
    if systemctl is-active --quiet "${BACKEND_SERVICE}"; then
        echo -e "${GREEN}Backend sigue activo, sin corte para los usuarios${NC}"
    else
        echo -e "${RED}AVISO: el backend está caído — revisar: journalctl -u ${BACKEND_SERVICE}${NC}"
    fi
else
echo -e "\n${YELLOW}[4/5] Reiniciando backend...${NC}"
systemctl restart "${BACKEND_SERVICE}"
sleep 2

if systemctl is-active --quiet "${BACKEND_SERVICE}"; then
    echo -e "${GREEN}Backend activo${NC}"
else
    echo -e "${RED}ERROR: Backend no arrancó — revisar: journalctl -u ${BACKEND_SERVICE}${NC}"
    exit 1
fi
fi

# --- Paso 6: Verificación final ---
echo -e "\n${YELLOW}[5/5] Verificación...${NC}"
HTTP_CODE=$(curl -sk -L -o /dev/null -w '%{http_code}' https://mail.maquita.org/webmail/)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}Webmail respondiendo: HTTP ${HTTP_CODE}${NC}"
else
    echo -e "${RED}ALERTA: Webmail respondió HTTP ${HTTP_CODE} — verificar manualmente${NC}"
    echo "Backup disponible en: ${BACKUP_DIR}/webmail-${TIMESTAMP}.tar.gz"
    echo "Para restaurar: tar xzf ${BACKUP_DIR}/webmail-${TIMESTAMP}.tar.gz -C ${WWW_DIR}"
    exit 1
fi

# --- Paso 7: EL CANDADO (T-29) — pruebas de humo obligatorias tras desplegar ---
if [ "${SIN_CANDADO:-0}" != "1" ] && [ -x /usr/local/bin/candado ]; then
    echo -e "\n${YELLOW}[candado] pruebas de humo en modo app...${NC}"
    if /usr/local/bin/candado ${CANDADO_ALCANCE:-todo}; then
        echo -e "${GREEN}Candado en verde: el despliegue queda confirmado.${NC}"
    else
        echo -e "${RED}CANDADO EN ROJO tras el despliegue.${NC}"
        echo "Regla T-29: se arregla o se revierte; no se deja pasar."
        echo "Respaldo para revertir: ${BACKUP_DIR}/webmail-${TIMESTAMP}.tar.gz"
        exit 1
    fi
fi

echo -e "\n${GREEN}=== Deploy completado exitosamente ===${NC}"
echo "URL: https://mail.maquita.org/webmail/"
