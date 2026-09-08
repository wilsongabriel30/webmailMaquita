#!/bin/bash
# Instala el servicio de chat en su propia máquina. Idempotente: se puede repetir.
#
# Qué hace: usuario del servicio, entorno de Python, dependencias, `.env` a partir del
# ejemplo, unidad de systemd y comprobaciones. NO toca nginx ni la base: eso va aparte y
# está explicado en docs/CHAT-INSTALACION.md.
set -euo pipefail

DESTINO="${DESTINO:-/opt/maquita-webmail/chat-service}"
USUARIO="${USUARIO:-maquita-chat}"

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta como root."; exit 1; }
[ -f "$DESTINO/app_chat.py" ] || { echo "No encuentro el código en $DESTINO."; exit 1; }

echo "== 1/6 Usuario del servicio =="
id "$USUARIO" >/dev/null 2>&1 || useradd --system --home-dir "$DESTINO" --shell /usr/sbin/nologin "$USUARIO"
echo "   $USUARIO"

echo "== 2/6 Entorno de Python =="
[ -d "$DESTINO/venv" ] || python3 -m venv "$DESTINO/venv"
"$DESTINO/venv/bin/pip" install --quiet --upgrade pip
"$DESTINO/venv/bin/pip" install --quiet -r "$DESTINO/requirements.txt"
echo "   dependencias instaladas"

echo "== 3/6 Configuración =="
if [ ! -f "$DESTINO/.env" ]; then
    cp "$DESTINO/deploy/env.example" "$DESTINO/.env"
    echo "   creado $DESTINO/.env a partir del ejemplo: RELLÉNALO ANTES DE SEGUIR"
    echo "   los secretos se generan con: openssl rand -hex 32   (uno distinto para cada uno)"
else
    echo "   ya existe $DESTINO/.env (no se toca)"
fi
chown -R "$USUARIO:$USUARIO" "$DESTINO"
chmod 600 "$DESTINO/.env"

echo "== 4/6 Comprobación de la configuración mínima =="
faltan=""
for clave in DATABASE_URL USERS_DB_URL CHAT_JWT_SECRET CHAT_SSO_SECRET CHAT_SESSION_KEY NOTIF_SECRET CHAT_REDIS_URL; do
    valor="$(grep -E "^${clave}=" "$DESTINO/.env" | head -1 | cut -d= -f2-)"
    [ -n "$valor" ] || faltan="$faltan $clave"
done
if [ -n "$faltan" ]; then
    echo "   FALTAN por rellenar:$faltan"
    echo "   Rellena el .env y vuelve a ejecutar este guion."
    exit 1
fi
echo "   completa"

echo "== 5/6 Unidad de systemd =="
install -m 644 "$DESTINO/deploy/maquita-chat.service" /etc/systemd/system/maquita-chat.service
sed -i "s|/opt/maquita-webmail/chat-service|$DESTINO|g; s|^User=.*|User=$USUARIO|; s|^Group=.*|Group=$USUARIO|" \
    /etc/systemd/system/maquita-chat.service
systemctl daemon-reload
systemctl enable --now maquita-chat
sleep 4

echo "== 6/6 Comprobación =="
systemctl is-active --quiet maquita-chat || { echo "   el servicio NO arrancó:"; journalctl -u maquita-chat -n 20 --no-pager; exit 1; }
puerto="$(grep -E '^CHAT_PORT=' "$DESTINO/.env" | cut -d= -f2- || true)"
puerto="${puerto:-8790}"
codigo="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$puerto/healthz" || true)"
echo "   servicio activo, /healthz responde $codigo (debe ser 200)"
echo
echo "Falta publicarlo en nginx (deploy/nginx-chat-*.conf) y comprobar la puerta:"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' https://<tu-dominio>/sso/entrar   # 401 sin vale, correcto"
