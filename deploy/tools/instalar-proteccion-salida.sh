#!/bin/bash
# instalar-proteccion-salida.sh — deja completa la protección de salida (cuenta comprometida).
#
# Sirve para una instalación EXISTENTE que no pasó por esa parte de instalar.sh, y lo llama
# también instalar.sh. Es idempotente: lo que ya está no se pisa, tampoco si difiere del repositorio.
#
#   1. Límite de envío por usuario (rspamd «ratelimit») CON Redis: sin servidores de Redis el
#      módulo se desactiva solo («no servers are specified, disabling module») y nadie lo nota.
#   2. Contención: maquita-contener, maquita-outbound y su sudoers.
#   3. Detector de envío masivo por cron cada 2 minutos y sus tablas.
#
# Uso: sudo bash deploy/tools/instalar-proteccion-salida.sh
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "ejecutar como root (sudo)"; exit 2; }
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
ENV_BACKEND="${MAQUITA_BACKEND_ENV:-/opt/maquita-webmail/backend/.env}"
CFG="${APP_DIR}/deploy/webmail/configs"
paso(){ printf '\n== %s ==\n' "$*"; }
hecho(){ printf '  [hecho]  %s\n' "$*"; }
estaba(){ printf '  [estaba] %s\n' "$*"; }
aviso(){ printf '  [AVISO]  %s\n' "$*"; }

paso "1. Límite de envío por usuario (rspamd ratelimit)"
mkdir -p /etc/rspamd/local.d /etc/rspamd/maps.d
RL=/etc/rspamd/local.d/ratelimit.conf
if [ -f "$RL" ]; then estaba "$RL"; else install -m 640 -g _rspamd "${CFG}/rspamd-ratelimit.conf" "$RL"; hecho "$RL (plantilla)"; fi
MAPA=/etc/rspamd/maps.d/ratelimit_whitelist.map
if [ -f "$MAPA" ]; then estaba "$MAPA"; else install -m 644 "${CFG}/rspamd-ratelimit-whitelist.map" "$MAPA"; hecho "$MAPA"; fi
# Redis: o bien global (local.d/redis.conf con servers), o bien propio del módulo.
if grep -qsE '^\s*servers\s*=' /etc/rspamd/local.d/redis.conf || grep -qE '^\s*servers\s*=' "$RL"; then
  estaba "rspamd ya tiene Redis para el límite de envío"
else
  URL="$(grep -E '^REDIS_URL=' "$ENV_BACKEND" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'" || true)"
  CLAVE="$(printf '%s' "$URL" | sed -nE 's#^redis://[^:@/]*:([^@]*)@.*#\1#p')"
  SERVIDOR="$(printf '%s' "$URL" | sed -nE 's#^redis://([^@]*@)?([^/:]+)(:([0-9]+))?.*#\2:\4#p' | sed 's/:$/:6379/; s/^localhost:/127.0.0.1:/')"
  [ -n "$SERVIDOR" ] || SERVIDOR="127.0.0.1:6379"
  {
    echo ""
    echo "# Redis propio de este módulo (base aparte): sin servidores, rspamd desactiva el límite."
    echo "servers = \"${SERVIDOR}\";"
    echo "db = \"4\";"
    [ -n "$CLAVE" ] && echo "password = \"${CLAVE}\";"
  } >> "$RL"
  chown root:_rspamd "$RL" 2>/dev/null || true; chmod 640 "$RL"
  hecho "Redis configurado para el límite de envío (${SERVIDOR}, base 4)"
fi

paso "2. Contención de cuentas"
# Un ayudante que ya existe NUNCA se sobrescribe, aunque difiera del repositorio: puede ser una
# version mas nueva que la versionada (paso el 03/10/2026 y hubo que reconstruirlo).
for h in maquita-contener maquita-outbound; do
  if [ ! -e "/usr/local/sbin/$h" ]; then install -m 750 "${APP_DIR}/deploy/tools/$h" "/usr/local/sbin/$h"; hecho "/usr/local/sbin/$h"
  elif cmp -s "${APP_DIR}/deploy/tools/$h" "/usr/local/sbin/$h"; then estaba "/usr/local/sbin/$h"
  else estaba "/usr/local/sbin/$h (distinto del repositorio: NO se sobrescribe; compárelo a mano)"; fi
done
if [ -f /etc/sudoers.d/maquita-outbound ]; then estaba "/etc/sudoers.d/maquita-outbound"
else install -m 440 "${CFG}/sudoers-maquita-outbound" /etc/sudoers.d/maquita-outbound; hecho "/etc/sudoers.d/maquita-outbound"; fi
visudo -c >/dev/null 2>&1 || aviso "sudoers no valida: revisar /etc/sudoers.d/maquita-outbound"

paso "3. Detector de envío masivo"
DSN="$(grep -E '^DATABASE_URL=' "$ENV_BACKEND" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'" | sed -E 's#^postgresql\+[a-z0-9]+://#postgresql://#' || true)"
if [ -n "$DSN" ]; then
  if psql "$DSN" -X -q -v ON_ERROR_STOP=1 -f "${APP_DIR}/migrations/2026-10-03-proteccion-salida.sql" >/dev/null 2>&1; then hecho "tablas del detector (migración 2026-10-03-proteccion-salida.sql)"
  else aviso "no se pudo aplicar la migración 2026-10-03-proteccion-salida.sql con el usuario de la aplicación"; fi
else
  aviso "sin DATABASE_URL en $ENV_BACKEND: aplique a mano migrations/2026-10-03-proteccion-salida.sql"
fi
DET=/usr/local/sbin/maquita-anomalia-salida.py
if [ -f "$DET" ] && ! cmp -s "${APP_DIR}/deploy/tools/maquita-anomalia-salida.py" "$DET"; then
  estaba "$DET (distinto del repositorio: NO se sobrescribe; compárelo a mano)"
elif [ -f "$DET" ]; then estaba "$DET"
else install -m 750 "${APP_DIR}/deploy/tools/maquita-anomalia-salida.py" "$DET"; hecho "$DET"; fi
CRON=/etc/cron.d/maquita-anomalia
if [ -f "$CRON" ]; then estaba "$CRON"
else echo "*/2 * * * * root $DET >> /var/log/maquita-anomalia.log 2>&1" > "$CRON"; chmod 644 "$CRON"; hecho "$CRON (cada 2 minutos)"; fi

paso "4. Aplicar y comprobar"
if rspamadm configtest >/dev/null 2>&1; then
  systemctl restart rspamd 2>/dev/null && hecho "rspamd reiniciado" || aviso "no se pudo reiniciar rspamd"
  sleep 4
  if journalctl -u rspamd --since '-1 min' --no-pager 2>/dev/null | cat - /var/log/rspamd/rspamd.log 2>/dev/null | tail -400 | grep -q 'ratelimit.*disabling module'; then
    aviso "rspamd sigue desactivando el límite de envío: revise servers/password en $RL"
  else
    hecho "el límite de envío está activo (rspamd no lo desactiva)"
  fi
else
  aviso "rspamadm configtest falla: NO se reinició rspamd. Revise $RL"
fi
echo
echo "Listo. El umbral, la acción y el correo de aviso se ajustan en el panel → Protección de salida."
