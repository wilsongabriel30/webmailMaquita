#!/usr/bin/env bash
# Prueba T-40: un reinicio del backend del correo NO debe invalidar sesiones ni dar 502.
# 1) Abre la sesión de pruebas y comprueba /api/auth/me = 200.
# 2) Lanza una sonda (cada 0,4 s) contra la API, reinicia el backend principal y cuenta los códigos.
# 3) Vuelve a probar el MISMO token tras el reinicio: debe seguir 200.
# Corre en el propio servidor del correo (reinicia maquita-webmail: unos segundos de reconexión).
# Uso: HUMO_URL=https://mail.example.org bash prueba-reinicio-sesion.sh [cuenta]
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="${HUMO_BACKEND:-/opt/maquita-webmail/backend}"
[ -f /etc/maquita-humo.env ] && . /etc/maquita-humo.env
URL="${HUMO_URL:?Falta HUMO_URL, p. ej. https://mail.example.org}"
T="$("$BACKEND/venv/bin/python" "$DIR/sesion_prueba.py" ${1:+"$1"} 2>/dev/null | tail -1)"
[ -n "$T" ] || { echo "no se pudo abrir la sesión de pruebas"; exit 2; }
SONDA="$(mktemp)"; trap 'rm -f "$SONDA"' EXIT
ANTES=$(curl -s -o /dev/null -w "%{http_code}" -b "access_token=$T" "$URL/api/auth/me")
echo "sesión antes del reinicio: HTTP $ANTES"
( for _ in $(seq 1 60); do curl -s -o /dev/null -w "%{http_code}\n" -m 10 "$URL/api/auth/oidc/enabled" >> "$SONDA"; sleep 0.4; done ) &
sleep 3
systemctl restart maquita-webmail
wait
DESPUES=$(curl -s -o /dev/null -w "%{http_code}" -b "access_token=$T" "$URL/api/auth/me")
echo "sesión DESPUÉS del reinicio (mismo token): HTTP $DESPUES"
echo "códigos de la API durante el reinicio:"; sort "$SONDA" | uniq -c
MALOS=$(grep -cv "^200$" "$SONDA")
if [ "$ANTES" = 200 ] && [ "$DESPUES" = 200 ] && [ "$MALOS" = 0 ]; then
  echo "RESULTADO: OK (sesión intacta, sin cortes)"
else
  echo "RESULTADO: FALLO"; exit 1
fi
