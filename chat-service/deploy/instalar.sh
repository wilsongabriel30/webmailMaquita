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
ejemplo=""
for clave in DATABASE_URL USERS_DB_URL CHAT_JWT_SECRET CHAT_SSO_SECRET CHAT_SESSION_KEY NOTIF_SECRET CHAT_REDIS_URL; do
    valor="$(grep -E "^${clave}=" "$DESTINO/.env" | head -1 | cut -d= -f2-)"
    if [ -z "$valor" ]; then
        faltan="$faltan $clave"
    # Los marcadores del ejemplo NO son configuración: dejarlos pasar habilitaba el servicio
    # contra una base inexistente y el fallo aparecía mucho después.
    elif printf '%s' "$valor" | grep -qE "USUARIO|SERVIDOR|BASE_DEL_CHAT|BASE_DE_USUARIOS|ejemplo\.org|CAMBIAME|<.*>"; then
        ejemplo="$ejemplo $clave"
    fi
done
if [ -n "$faltan" ] || [ -n "$ejemplo" ]; then
    [ -n "$faltan" ] && echo "   FALTAN por rellenar:$faltan"
    [ -n "$ejemplo" ] && echo "   SIGUEN CON EL VALOR DE EJEMPLO:$ejemplo"
    echo "   Rellena el .env y vuelve a ejecutar este guion."
    exit 1
fi
echo "   completa"

echo "== 4b/6 Las bases responden y las tablas existen =="
_url() { grep -E "^${1}=" "$DESTINO/.env" | head -1 | cut -d= -f2-; }
if ! "$DESTINO/venv/bin/python3" - "$(_url DATABASE_URL)" "$(_url USERS_DB_URL)" <<'PY'
import sys
import psycopg2

chat, usuarios = sys.argv[1], sys.argv[2]
try:
    with psycopg2.connect(chat) as c, c.cursor() as cur:
        cur.execute("SELECT to_regclass('public.chat_conversations') IS NOT NULL")
        if not cur.fetchone()[0]:
            print("   La base del chat responde pero NO tiene las tablas.")
            print("   Ejecuta:  venv/bin/python3 migrar_chat.py")
            sys.exit(1)
except Exception as e:
    print("   No se pudo conectar a la base del chat (DATABASE_URL): %s" % type(e).__name__)
    sys.exit(1)
try:
    with psycopg2.connect(usuarios) as c, c.cursor() as cur:
        cur.execute("SELECT to_regclass('public.usuarios') IS NOT NULL")
        if not cur.fetchone()[0]:
            print("   La base de personas responde pero no tiene `usuarios`.")
            print("   Ejecuta:  venv/bin/python3 sincronizar_usuarios.py")
            sys.exit(1)
        cur.execute("SELECT count(*) FROM usuarios WHERE active = true")
        n = cur.fetchone()[0]
        print("   personas activas en el directorio: %d" % n)
        if n == 0:
            print("   AVISO: el chat no reconocerá a nadie hasta que haya personas.")
except Exception as e:
    print("   No se pudo conectar a la base de personas (USERS_DB_URL): %s" % type(e).__name__)
    sys.exit(1)
print("   bases correctas")
PY
then
    echo "   Corrige lo anterior y vuelve a ejecutar este guion."
    exit 1
fi

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
