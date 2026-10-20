#!/usr/bin/env bash
# Chat institucional EN LA MISMA MÁQUINA que el correo (modo integrado, mismo origen). Idempotente.
# Se llama con:  sudo bash deploy/webmail/instalar-app.sh chat
#
# Para el chat en su propia máquina (como en una instalación grande) está docs/CHAT-INSTALACION.md.
# Aquí todo queda hecho y cableado sin preguntas:
#   - base «chat» propia y rol «chat»; las personas son los buzones del correo: un rol de SOLO LECTURA
#     («chat_lector», solo la tabla mailbox) y un temporizador que las copia cada 2 minutos;
#   - .env del chat con secretos propios (la sesión la firma el correo: CHAT_JWT_SECRET = SECRET_KEY);
#   - el correo conoce al chat (CHAT_SSO_SECRET, NOTIF_SECRET y CHAT_INTERNAL_URL en su .env);
#   - nginx: /chat/, /api/chat/, /socket.io/ y estáticos del chat en el vhost del correo (127.0.0.1:8790).
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
CHAT="${APP_DIR}/chat-service"
ENV_CORREO="${APP_DIR}/backend/.env"
ENV_CHAT="${CHAT}/.env"
[ "$EUID" -eq 0 ] || { echo -e "${RED}Ejecutar como root.${NC}"; exit 1; }
[ -f "$ENV_CORREO" ] || { echo -e "${RED}Primero el correo (deploy/webmail/instalar.sh).${NC}"; exit 1; }

valor() { grep -E "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2-; }
SECRET_KEY="$(valor SECRET_KEY "$ENV_CORREO")"
DOMINIO="$(valor MAIL_DOMAIN "$ENV_CORREO")"
MAIL_HOST="${MAIL_HOST:-mail.${DOMINIO}}"
REDIS_CLAVE="$(valor REDIS_URL "$ENV_CORREO" | sed -nE 's#^redis://:([^@]+)@.*#\1#p')"
[ -n "$SECRET_KEY" ] && [ -n "$DOMINIO" ] || { echo -e "${RED}Faltan SECRET_KEY o MAIL_DOMAIN en ${ENV_CORREO}.${NC}"; exit 1; }
sql() { runuser -u postgres -- psql -q -v ON_ERROR_STOP=1 "$@"; }

echo -e "${GREEN}[1/6] Bases de datos...${NC}"
if [ -f "$ENV_CHAT" ]; then
    CLAVE_CHAT="$(valor DATABASE_URL "$ENV_CHAT" | sed -nE 's#^postgresql://chat:([^@]+)@.*#\1#p')"
    CLAVE_LECTOR="$(cat /etc/maquita-chat/lector 2>/dev/null || true)"
fi
CLAVE_CHAT="${CLAVE_CHAT:-$(openssl rand -hex 24)}"
CLAVE_LECTOR="${CLAVE_LECTOR:-$(openssl rand -hex 24)}"
sql -d postgres <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chat') THEN CREATE ROLE chat LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chat_lector') THEN CREATE ROLE chat_lector LOGIN; END IF;
END \$\$;
ALTER ROLE chat PASSWORD '${CLAVE_CHAT}';
ALTER ROLE chat_lector PASSWORD '${CLAVE_LECTOR}';
SQL
sql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'chat'" | grep -q 1 || sql -d postgres -c "CREATE DATABASE chat OWNER chat ENCODING 'UTF8' TEMPLATE template0;"
# Solo lectura y solo la tabla de buzones del correo.
sql -d maildb -c "GRANT CONNECT ON DATABASE maildb TO chat_lector; GRANT USAGE ON SCHEMA public TO chat_lector; GRANT SELECT ON mailbox TO chat_lector;"
install -d -m 700 /etc/maquita-chat
( umask 077; printf '%s' "$CLAVE_LECTOR" > /etc/maquita-chat/lector )

echo -e "${GREEN}[2/6] Configuración del chat...${NC}"
if [ ! -f "$ENV_CHAT" ]; then
    ( umask 077; cat > "$ENV_CHAT" <<EOF
# Generado por deploy/chat/instalar.sh (chat en la misma máquina que el correo).
DATABASE_URL=postgresql://chat:${CLAVE_CHAT}@127.0.0.1:5432/chat
# Las personas: tabla «usuarios» de la propia base del chat, copiada de los buzones del correo
# cada 2 minutos (maquita-chat-sincronizar.timer).
USERS_DB_URL=postgresql://chat:${CLAVE_CHAT}@127.0.0.1:5432/chat
USE_PGBOUNCER=0
CHAT_JWT_SECRET=${SECRET_KEY}
CHAT_SSO_SECRET=$(openssl rand -hex 32)
CHAT_SESSION_KEY=$(openssl rand -hex 32)
NOTIF_SECRET=$(openssl rand -hex 32)
DOMINIOS_EQUIVALENTES=${DOMINIO}
CHAT_SESION_CENTRAL=1
CHAT_REVALIDAR_SESION_SEG=300
CHAT_SESION_EXTERNA_MAX_SEG=43200
CORREO_URL_API=http://127.0.0.1:8000
CHAT_BIND=127.0.0.1
CHAT_PORT=8790
CHAT_URL_PUBLICA=https://${MAIL_HOST}
CHAT_CORS_ORIGENES=https://${MAIL_HOST}
CHAT_REDIS_URL=redis://:${REDIS_CLAVE}@127.0.0.1:6379/3
EOF
    )
    echo "   creado ${ENV_CHAT}"
else
    # La sesión la firma el correo: si su SECRET_KEY cambió, el chat rechazaría a todos.
    sed -i "s#^CHAT_JWT_SECRET=.*#CHAT_JWT_SECRET=${SECRET_KEY}#" "$ENV_CHAT"
    echo "   ${ENV_CHAT} ya existía (se conserva; CHAT_JWT_SECRET al día)"
fi

echo -e "${GREEN}[3/6] Entorno, tablas y personas...${NC}"
[ -d "${CHAT}/venv" ] || python3 -m venv "${CHAT}/venv"
"${CHAT}/venv/bin/pip" install --quiet --disable-pip-version-check -r "${CHAT}/requirements.txt"
( cd "$CHAT" && set -a && . "$ENV_CHAT" && set +a && venv/bin/python3 migrar_chat.py >/dev/null )
cat > /usr/local/sbin/maquita-chat-sincronizar <<EOF
#!/bin/sh
# Copia los buzones del correo al directorio de personas del chat (lo lanza maquita-chat-sincronizar.timer).
set -a; . ${ENV_CHAT}; set +a
USERS_DB_URL="postgresql://chat_lector:\$(cat /etc/maquita-chat/lector)@127.0.0.1:5432/maildb" exec ${CHAT}/venv/bin/python3 ${CHAT}/sincronizar_usuarios.py
EOF
chmod 700 /usr/local/sbin/maquita-chat-sincronizar
/usr/local/sbin/maquita-chat-sincronizar | tail -2
cat > /etc/systemd/system/maquita-chat-sincronizar.service <<'EOF'
[Unit]
Description=Directorio del chat: copia los buzones del correo
After=postgresql.service

[Service]
Type=oneshot
WorkingDirectory=/opt/maquita-webmail/chat-service
ExecStart=/usr/local/sbin/maquita-chat-sincronizar
EOF
sed -i "s#/opt/maquita-webmail/chat-service#${CHAT}#" /etc/systemd/system/maquita-chat-sincronizar.service
cat > /etc/systemd/system/maquita-chat-sincronizar.timer <<'EOF'
[Unit]
Description=Directorio del chat al día con los buzones (cada 2 minutos)

[Timer]
OnBootSec=1min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now maquita-chat-sincronizar.timer >/dev/null

echo -e "${GREEN}[4/6] Servicio del chat...${NC}"
bash "${CHAT}/deploy/instalar.sh" | grep -E "^==|personas|responde|NO|FALTAN|SIGUEN" || true
systemctl is-active -q maquita-chat || { echo -e "${RED}El chat no arrancó (journalctl -u maquita-chat).${NC}"; exit 1; }

echo -e "${GREEN}[5/6] El correo conoce al chat...${NC}"
cambio=0
for clave in CHAT_SSO_SECRET NOTIF_SECRET; do
    v="$(valor "$clave" "$ENV_CHAT")"
    if [ "$(valor "$clave" "$ENV_CORREO")" != "$v" ]; then
        sed -i "/^${clave}=/d" "$ENV_CORREO"; echo "${clave}=${v}" >> "$ENV_CORREO"; cambio=1
    fi
done
grep -q '^CHAT_INTERNAL_URL=' "$ENV_CORREO" || { echo "CHAT_INTERNAL_URL=http://127.0.0.1:8790" >> "$ENV_CORREO"; cambio=1; }
[ "$cambio" = 1 ] && systemctl restart maquita-webmail && echo "   correo reiniciado con la configuración del chat" || echo "   ya estaba"

echo -e "${GREEN}[6/6] nginx (mismo origen que el correo)...${NC}"
install -d /etc/nginx/snippets/maquita-apps
sed 's#10\.0\.0\.10:8790#127.0.0.1:8790#g; s#^\# Sustituir 10.0.0.10 por la máquina del chat.#\# Chat en esta misma máquina (deploy/chat/instalar.sh).#' \
    "${CHAT}/deploy/nginx-chat-consumidor.conf" > /etc/nginx/snippets/maquita-apps/chat.conf
nginx -t 2>&1 | tail -1 && systemctl reload nginx
sleep 2
echo "   /healthz: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8790/healthz)   /chat/entrar sin vale: $(curl -sk -o /dev/null -w '%{http_code}' --resolve "${MAIL_HOST}:443:127.0.0.1" "https://${MAIL_HOST}/chat/entrar")"
echo -e "${GREEN}Listo.${NC} El chat aparece en el webmail (burbuja y sección Chat)."
