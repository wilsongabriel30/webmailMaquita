#!/usr/bin/env bash
# Seguridad del correo y de la web traída de producción (20/10/2026). Idempotente y con respaldo:
#   1. Postfix: rechaza remitentes con metacaracteres de shell (reject_sender_injection.regexp).
#   2. nginx: la regla anti «../» solo bloquea segmentos «..» reales (antes daba 403 a adjuntos
#      como «BODA..pdf») y la Referrer-Policy por ruta (no-referrer en enlaces públicos del Almacén).
#   3. ClamAV: escaneo semanal del sistema (sin los buzones; el correo entrante ya se analiza).
#   4. Cuarentena diferida: cron del reconciliador (milter/reconciliar_cuarentena.py).
# Uso: aplicar.sh [--simular] [--sin-recargar]   (el instalador usa --sin-recargar: recarga él)
# Si postfix o nginx rechazan el cambio, se restaura lo anterior y sale con error.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
ORIGEN="$APP_DIR/deploy/hardening/seguridad-correo-web"
SIMULAR=0; RECARGAR=1
for a in "$@"; do case "$a" in --simular) SIMULAR=1 ;; --sin-recargar) RECARGAR=0 ;; esac; done
FECHA="$(date +%Y%m%d%H%M%S)"
pendientes=(); hechos=()

# --- 1. Postfix ------------------------------------------------------------------------------
REGEXP=/etc/postfix/reject_sender_injection.regexp
REGLA="check_sender_access regexp:$REGEXP"
# Si el servidor ya tiene su propio archivo de reglas, se respeta: solo se instala si falta.
postfix_pendiente() {
  command -v postconf >/dev/null || return 1
  [ -f "$REGEXP" ] || return 0
  ! postconf -h smtpd_sender_restrictions | grep -qF "$REGLA"
}
if postfix_pendiente; then pendientes+=("Postfix: rechazo de remitentes con metacaracteres de shell"); fi

# --- 2. nginx --------------------------------------------------------------------------------
HOST="$(postconf -h myhostname 2>/dev/null || true)"
VHOST="/etc/nginx/sites-available/${HOST}"
MAPA=/etc/nginx/conf.d/maquita-politica-referer.conf
REGEX_NUEVA='(?:^|/|%2f|%5c)(?:\.|%2e)(?:\.|%2e)(?:/|\?|%2f|%5c|$)'
nginx_traversal() { [ -f "$VHOST" ] && grep -qE 'request_uri ~\* "\\\.\\\." ?\)' "$VHOST"; }
mapa_ajeno() { grep -rlsE '^[[:space:]]*map[[:space:]].*\$politica_referer' /etc/nginx/ 2>/dev/null | grep -v -e "$MAPA" -e '\.bak' | grep -q .; }
nginx_referer() {
  [ -f "$VHOST" ] && grep -q 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;' "$VHOST" && ! mapa_ajeno
}
nginx_traversal && pendientes+=("nginx: la regla anti «../» ya no bloquea nombres con «..» (p. ej. BODA..pdf)")
nginx_referer && pendientes+=("nginx: Referrer-Policy por ruta (no-referrer en enlaces públicos)")

# --- 3 y 4. Tareas programadas -----------------------------------------------------------------
# Un servidor con su propio escaneo semanal (p. ej. /etc/cron.d/clamav-weekly) no recibe otro.
clamav_pendiente() {
  command -v clamscan >/dev/null || return 1
  [ -f /etc/cron.d/clamav-weekly ] && return 1
  [ -f /etc/cron.d/clamav-semanal ] && cmp -s "$ORIGEN/clamav-semanal.sh" /usr/local/sbin/clamav-semanal.sh && return 1
  return 0
}
cuarentena_pendiente() {
  [ -f "$APP_DIR/milter/reconciliar_cuarentena.py" ] || return 1
  grep -rlsF "reconciliar_cuarentena.py" /etc/cron.d/ | grep -q . && return 1
  return 0
}
clamav_pendiente && pendientes+=("ClamAV: escaneo semanal del sistema (viernes 00:00, sin los buzones)")
cuarentena_pendiente && pendientes+=("Cuarentena diferida: reconciliador cada 7 minutos")

if [ "${#pendientes[@]}" -eq 0 ]; then echo "Sin cambios: la seguridad del correo y de la web ya está al día."; exit 0; fi
for p in "${pendientes[@]}"; do echo "Pendiente: $p"; done
[ "$SIMULAR" = 1 ] && exit 0

# --- Aplicar -----------------------------------------------------------------------------------
if postfix_pendiente; then
  cp -p /etc/postfix/main.cf "/etc/postfix/main.cf.bak.$FECHA"
  [ -f "$REGEXP" ] || install -m 644 "$ORIGEN/reject_sender_injection.regexp" "$REGEXP"
  actual="$(postconf -h smtpd_sender_restrictions)"
  if ! grep -qF "$REGLA" <<<"$actual"; then
    postconf -e "smtpd_sender_restrictions = $REGLA${actual:+, $actual}"
  fi
  if ! postfix check >/dev/null 2>&1; then
    cp -p "/etc/postfix/main.cf.bak.$FECHA" /etc/postfix/main.cf
    echo "postfix check rechazó el cambio: se dejó main.cf como estaba." >&2; exit 1
  fi
  [ "$RECARGAR" = 1 ] && systemctl is-active -q postfix && postfix reload >/dev/null 2>&1
  hechos+=("Postfix")
fi

if nginx_traversal || nginx_referer; then
  cp -p "$VHOST" "$VHOST.bak.$FECHA"
  mapa_nuevo=0
  if nginx_referer; then
    [ -f "$MAPA" ] || mapa_nuevo=1
    install -m 644 "$ORIGEN/politica-referer.conf" "$MAPA"
    sed -i 's|add_header Referrer-Policy "strict-origin-when-cross-origin" always;|add_header Referrer-Policy $politica_referer always;|' "$VHOST"
  fi
  if nginx_traversal; then
    REGEX="$REGEX_NUEVA" python3 - "$VHOST" <<'PY'
import os, re, sys
ruta = sys.argv[1]
texto = open(ruta, encoding="utf-8").read()
nueva = os.environ["REGEX"]
texto = re.sub(r'request_uri ~\* "\\\.\\\." ?\)', lambda m: f'request_uri ~* "{nueva}")', texto)
open(ruta, "w", encoding="utf-8").write(texto)
PY
  fi
  if ! nginx -t >/dev/null 2>&1; then
    cp -p "$VHOST.bak.$FECHA" "$VHOST"; [ "$mapa_nuevo" = 1 ] && rm -f "$MAPA"
    echo "nginx rechazó el cambio: se dejó el sitio del correo como estaba." >&2; exit 1
  fi
  [ "$RECARGAR" = 1 ] && systemctl is-active -q nginx && systemctl reload nginx
  hechos+=("nginx")
fi

if clamav_pendiente; then
  install -m 755 "$ORIGEN/clamav-semanal.sh" /usr/local/sbin/clamav-semanal.sh
  install -m 644 "$ORIGEN/cron-clamav-semanal" /etc/cron.d/clamav-semanal
  hechos+=("ClamAV semanal")
fi
if cuarentena_pendiente; then
  install -m 644 "$ORIGEN/cron-reconciliar-cuarentena" /etc/cron.d/maquita-reconciliar-cuarentena
  hechos+=("cuarentena diferida")
fi
echo "Listo: ${hechos[*]}."
