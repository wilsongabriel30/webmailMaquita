#!/usr/bin/env bash
# instalar-app.sh — agrega/actualiza UNA Aplicacion del Drive (bi | pdf) en un despliegue
# YA montado, reutilizando los bloques 16-17 de instalar.sh. Idempotente: reusa la config
# existente (SECRET_KEY y credenciales de BD del backend); no regenera secretos.
#
# Uso:  sudo bash deploy/webmail/instalar-app.sh <bi|pdf>
set -e
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

APP="${1:-}"
case "$APP" in bi|pdf) ;; *) echo "uso: $0 <bi|pdf>"; exit 2 ;; esac

# Raiz del repo (este script vive en deploy/webmail/)
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
BACKEND_ENV="${APP_DIR}/backend/.env"
[ -f "${BACKEND_ENV}" ] || { echo -e "${RED}No encuentro ${BACKEND_ENV}. Instala primero el webmail (instalar.sh).${NC}"; exit 1; }

# Reusar la configuracion existente (no regenerar nada)
SECRET="$(grep -E '^SECRET_KEY=' "${BACKEND_ENV}" | head -1 | cut -d= -f2-)"
DBURL="$(grep -E '^DATABASE_URL=' "${BACKEND_ENV}" | head -1 | cut -d= -f2-)"
DB_PASS="$(printf '%s' "${DBURL}" | sed -E 's#.*://[^:]+:([^@]+)@.*#\1#')"
MAIL_HOST="$(grep -E '^MAIL_HOST=' "${BACKEND_ENV}" | head -1 | cut -d= -f2-)"
[ -n "${MAIL_HOST}" ] || MAIL_HOST="tu-servidor"
[ -n "${SECRET}" ] || { echo -e "${RED}No pude leer SECRET_KEY de ${BACKEND_ENV}.${NC}"; exit 1; }

mkdir -p /etc/nginx/snippets/maquita-apps

if [ "${APP}" = "bi" ]; then
  echo -e "${GREEN}Instalando/actualizando Tableros/BI...${NC}"
  if ! grep -q sse4_2 /proc/cpuinfo; then
    echo -e "  ${YELLOW}AVISO: CPU sin x86-64-v2 (sse4_2); NumPy 2.x no arrancara. En Proxmox: qm set <vmid> --cpu host.${NC}"
  fi
  D="${APP_DIR}/almacen/aplicaciones/bi"
  [ -d "${D}/venv" ] || python3 -m venv "${D}/venv"
  "${D}/venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
  "${D}/venv/bin/pip" install -q -r "${D}/requirements.txt"
  [ -f "${D}/.env" ] || cat > "${D}/.env" <<BIENV
WEBMAIL_SECRET_KEY=${SECRET}
REDIS_URL=redis://127.0.0.1:6379/0
ALMACEN_INTERNAL_URL=http://127.0.0.1:8788
BIENV
  cp "${D}/deploy/nginx-bi.conf" /etc/nginx/snippets/maquita-apps/bi.conf
  cp "${D}/deploy/maquita-bi.service" /etc/systemd/system/
  systemctl daemon-reload && systemctl enable maquita-bi >/dev/null 2>&1 || true
  systemctl restart maquita-bi
  URL="https://${MAIL_HOST}/tableros/"
else
  echo -e "${GREEN}Instalando/actualizando el Editor de PDF (dependencias pesadas: puede tardar)...${NC}"
  D="${APP_DIR}/almacen/aplicaciones/pdf_editor"
  apt-get install -y --no-install-recommends libglib2.0-0 libgl1 tesseract-ocr >/dev/null 2>&1 || true
  sudo -u postgres psql -c "CREATE DATABASE herramientas OWNER mailserver;" 2>/dev/null || true
  [ -d "${D}/venv" ] || python3 -m venv "${D}/venv"
  "${D}/venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
  "${D}/venv/bin/pip" install -q -r "${D}/requirements.txt"
  mkdir -p /var/lib/maquita-pdf-editor/uploads /var/lib/maquita-pdf-editor/logs
  [ -f "${D}/.env" ] || cat > "${D}/.env" <<PDFENV
WEBMAIL_SECRET_KEY=${SECRET}
HERRAMIENTAS_DATABASE_URI=postgresql://mailserver:${DB_PASS}@127.0.0.1:5432/herramientas
REDIS_URL=redis://127.0.0.1:6379/0
ALMACEN_INTERNAL_URL=http://127.0.0.1:8788
PDF_UPLOADS_DIR=/var/lib/maquita-pdf-editor/uploads
PDF_LOGS_DIR=/var/lib/maquita-pdf-editor/logs
PDFENV
  "${D}/venv/bin/python" "${D}/crear_tablas.py" 2>/dev/null || true
  "${D}/venv/bin/python" "${D}/interfaces/web/verificar_render.py" \
    || { echo -e "  ${RED}ERROR: el Editor de PDF no renderiza (falta base.html o estaticos).${NC}"; exit 1; }
  cp "${D}/deploy/nginx-pdf-editor.conf" /etc/nginx/snippets/maquita-apps/pdf-editor.conf
  cp "${D}/deploy/maquita-pdf-editor.service" /etc/systemd/system/
  systemctl daemon-reload && systemctl enable maquita-pdf-editor >/dev/null 2>&1 || true
  systemctl restart maquita-pdf-editor
  URL="https://${MAIL_HOST}/herramientas/editor-pdf/"
fi

# El server 443 debe incluir los snippets de las apps
if ! grep -rq 'maquita-apps' /etc/nginx/sites-enabled/ 2>/dev/null; then
  echo -e "  ${YELLOW}AVISO: el server 443 no incluye snippets/maquita-apps/. Agrega dentro del server{} de tu sitio:${NC}"
  echo -e "  ${YELLOW}    include /etc/nginx/snippets/maquita-apps/*.conf;${NC}"
fi

nginx -t && systemctl reload nginx
echo -e "${GREEN}Listo: ${URL}${NC}"
