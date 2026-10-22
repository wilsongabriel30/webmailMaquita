#!/usr/bin/env bash
# Instala o pone al día el portal de administradores de dominio (puerto 8444) en un servidor de correo
# ya instalado con deploy/webmail/instalar.sh. Hace lo que describe panel-dominio/README.md:
# usuario del sistema, entorno de Python, tablas y permisos, rol de base propio, servicio y nginx.
# Si el servidor tiene sitios web, instala también su intermediario (deploy/sitios/portal).
# Idempotente: no cambia la clave del rol ni pisa un nginx del portal que ya exista.
#
# Uso: sudo bash panel-dominio/deploy/instalar.sh            (o instalar-app.sh portal-dominio)
#      PD_NOMBRE=portal.example.org  nombre del servidor en el vhost (por defecto MAIL_HOST de backend/.env)
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)." >&2; exit 2; }
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
BACK="${APP_DIR}/panel-dominio/backend"
ENV_CORREO="${APP_DIR}/backend/.env"
ENTORNO=/etc/maquita-mail/panel-dominio.env
UNIDAD=/etc/systemd/system/maquita-panel-dominio.service
VHOST=/etc/nginx/sites-available/panel-dominio
MARCA="${APP_DIR}/uploads/branding/empresas"

[ -r "$ENV_CORREO" ] || { echo "No hay ${ENV_CORREO}: instale antes el correo (deploy/webmail/instalar.sh)." >&2; exit 1; }
valor() { { grep -E "^$1=" "$ENV_CORREO" || true; } | head -1 | cut -d= -f2- | tr -d '"'; }
DOMINIO="$(valor MAIL_DOMAIN)"
NOMBRE="${PD_NOMBRE:-$(valor MAIL_HOST)}"
[ -n "$NOMBRE" ] || NOMBRE="$(postconf -h myhostname 2>/dev/null || true)"
[ -n "$NOMBRE" ] || NOMBRE="mail.${DOMINIO}"
[[ "$NOMBRE" =~ ^[a-z0-9.-]+\.[a-z]{2,63}$ ]] || { echo "Nombre de servidor no válido: $NOMBRE" >&2; exit 1; }

# Base de datos: las tablas pd_ son del dueño de la base del correo (el panel general las administra).
URL="$(valor DATABASE_URL)"
DUENO="$(sed -E 's|^[a-z+]+://([^:]+):.*|\1|' <<<"$URL")"
CLAVE_DUENO="$(sed -E 's|^[a-z+]+://[^:]+:([^@]*)@.*|\1|' <<<"$URL")"
BASE="$(sed -E 's|.*/([A-Za-z0-9_]+)(\?.*)?$|\1|' <<<"$URL")"
[ -n "$DUENO" ] && [ -n "$BASE" ] || { echo "No se entiende DATABASE_URL de backend/.env." >&2; exit 1; }
como_dueno() { PGPASSWORD="$CLAVE_DUENO" psql -X -q -v ON_ERROR_STOP=1 -h localhost -U "$DUENO" -d "$BASE" "$@"; }

echo "== Portal de dominio para ${NOMBRE} (base ${BASE}) =="

# 1. Usuario del sistema y grupo de la carpeta de logos (compartida con el panel general y el webmail).
id maquita-dominio >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin maquita-dominio
getent group maquita-marca >/dev/null || groupadd --system maquita-marca
usermod -aG maquita-marca maquita-dominio
id maquita-admin >/dev/null 2>&1 && usermod -aG maquita-marca maquita-admin
install -d -g maquita-marca -m 2775 "$MARCA"
chgrp -R maquita-marca "$MARCA"

# 2. Entorno de Python.
[ -x "${BACK}/venv/bin/python" ] || python3 -m venv "${BACK}/venv"
"${BACK}/venv/bin/pip" install -q --upgrade pip
"${BACK}/venv/bin/pip" install -q -r "${BACK}/requirements.txt"

# 3. Rol propio del portal (la clave se genera una vez y solo la lee root) y tablas con sus permisos.
install -d -m 755 /etc/maquita-mail
if [ ! -s "$ENTORNO" ]; then
  install -m 600 /dev/null "$ENTORNO"
  printf 'PD_DB_PASS=%s\n' "$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)" > "$ENTORNO"
fi
CLAVE_PD="$(grep -E '^PD_DB_PASS=' "$ENTORNO" | cut -d= -f2-)"
existe_rol="$(sudo -u postgres psql -X -tAc "SELECT 1 FROM pg_roles WHERE rolname='panel_dominio'")"
if [ "$existe_rol" != 1 ]; then
  sudo -u postgres psql -X -q -v ON_ERROR_STOP=1 -v clave="$CLAVE_PD" <<'SQL'
CREATE ROLE panel_dominio LOGIN PASSWORD :'clave';
SQL
fi
sudo -u postgres psql -X -q -v ON_ERROR_STOP=1 -v base="$BASE" <<'SQL'
GRANT CONNECT ON DATABASE :"base" TO panel_dominio;
SQL
for f in esquema.sql esquema-2-autonomia.sql esquema-4-sitios.sql esquema-5-soporte.sql esquema-5-fichas-api.sql; do
  [ -f "${SELF}/$f" ] && como_dueno -f "${SELF}/$f"
done
for f in permisos.sql permisos-2-autonomia.sql permisos-3-multicuenta.sql permisos-4-sitios.sql permisos-5-soporte.sql permisos-5-enrutamiento.sql permisos-5-fichas-api.sql; do
  [ -f "${SELF}/$f" ] || continue
  como_dueno -f "${SELF}/$f" || echo "  Aviso: ${f} no se aplicó entero (falta alguna tabla de una sección no instalada)."
done

# 4. Servicio.
if ! cmp -s "${SELF}/maquita-panel-dominio.service" "$UNIDAD"; then
  install -m 644 "${SELF}/maquita-panel-dominio.service" "$UNIDAD"
  systemctl daemon-reload
fi
systemctl enable -q maquita-panel-dominio
systemctl restart maquita-panel-dominio

# 5. nginx: el proxy común y el vhost del puerto 8444 (si ya existe, es del servidor: no se pisa).
install -m 644 "${SELF}/panel-dominio-proxy.conf" /etc/nginx/snippets/panel-dominio-proxy.conf
if [ ! -e "$VHOST" ]; then
  sed -e "s/correo\.ejemplo\.org/${NOMBRE}/g" "${SELF}/nginx-panel-dominio.conf" > "$VHOST"
  ln -sf "$VHOST" /etc/nginx/sites-enabled/panel-dominio
  bash "${APP_DIR}/deploy/webmail/nginx/certificado-provisional.sh" "$VHOST" || true
fi
nginx -t >/dev/null 2>&1 || { echo "Error: nginx rechaza la configuración (nginx -t)." >&2; nginx -t; exit 1; }
systemctl reload nginx

# 6. Sitios web desde el portal, si el servidor los tiene.
if [ -x /usr/local/sbin/maquita-sitios ]; then
  bash "${APP_DIR}/deploy/sitios/portal/instalar.sh"
  # v1.11: rutas públicas del gancho de git y del DNS dinámico, que atiende este portal.
  bash "${APP_DIR}/deploy/sitios/publico/instalar.sh" \
    || echo "Aviso: no se pudieron publicar las rutas del gancho y del DNS dinámico (deploy/sitios/publico/instalar.sh)." >&2
fi

# 7. Órdenes de consola del panel (vale de entrada del superadmin y vale de soporte del portal).
bash "${APP_DIR}/deploy/panel/instalar.sh"

for _ in $(seq 1 15); do
  curl -fsS -m 3 http://127.0.0.1:8003/api/salud >/dev/null 2>&1 && break
  sleep 2
done
curl -fsS -m 3 http://127.0.0.1:8003/api/salud >/dev/null 2>&1 \
  || { echo "Error: el portal no responde en 127.0.0.1:8003 (journalctl -u maquita-panel-dominio)." >&2; exit 1; }
echo "Listo: portal de dominio en https://${NOMBRE}:8444/ — los administradores se crean en el panel general"
echo "       (Administración → Administradores de dominio). Abra el puerto 8444 solo a quien deba llegar."
