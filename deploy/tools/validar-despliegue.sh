#!/bin/bash
# validar-despliegue.sh — valida que cada feature del correo funciona DE VERDAD,
# no solo que está instalada. Pensado para correr en el servidor tras instalar.
# Salida: [OK] / [WARN] / [FALLO] por check + resumen. exit = nº de fallos.
#
# Uso: sudo bash validar-despliegue.sh
DB="${MAILDB:-maildb}"
WEBMAIL="${WEBMAIL_URL:-http://127.0.0.1:8000}"
PSQL="sudo -u postgres psql -d $DB -tAc"
PASS=0; FAIL=0; WARN=0
ok(){   printf '  \033[32m[OK]\033[0m    %s\n' "$*"; PASS=$((PASS+1)); }
bad(){  printf '  \033[31m[FALLO]\033[0m %s\n' "$*"; FAIL=$((FAIL+1)); }
warn(){ printf '  \033[33m[WARN]\033[0m  %s\n' "$*"; WARN=$((WARN+1)); }
hdr(){  printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
[ "$(id -u)" -eq 0 ] || { echo "ejecutar como root (sudo)"; exit 2; }

hdr "Servicios"
for s in postfix dovecot rspamd redis-server nginx clamav-daemon maquita-webmail maquita-admin fail2ban; do
  [ "$(systemctl is-active "$s" 2>/dev/null)" = active ] && ok "$s activo" || bad "$s NO activo"
done

hdr "Puertos en escucha"
for p in 25 465 587 143 993 443; do
  ss -ltn 2>/dev/null | grep -q ":$p " && ok "puerto $p" || bad "puerto $p cerrado"
done

hdr "Postfix — AUTH deshabilitado en el 25 (anti fuerza bruta SASL)"
if timeout 6 bash -c "printf 'EHLO t\r\nQUIT\r\n' | openssl s_client -connect 127.0.0.1:25 -starttls smtp -quiet 2>/dev/null | grep -qi '250.*AUTH'"; then
  bad "el puerto 25 ANUNCIA AUTH (poner smtpd_sasl_auth_enable=no global)"
else ok "el puerto 25 no anuncia AUTH"; fi

hdr "Auditoría — captura de verdad (no solo instalada)"
A=$($PSQL "SELECT count(*) FROM audit_log" 2>/dev/null)
curl -s -o /dev/null -X POST "$WEBMAIL/api/auth/login" -H 'Content-Type: application/json' --data '{"username":"validador@local","password":"x"}' 2>/dev/null
sleep 2
B=$($PSQL "SELECT count(*) FROM audit_log" 2>/dev/null)
if [ -n "$B" ] && [ "${B:-0}" -gt "${A:-0}" ]; then ok "audit_log captura eventos ($A → $B)"; else bad "audit_log NO crece — auditoría dormida"; fi

hdr "Viaje imposible (risky_login)"
EN=$($PSQL "SELECT enabled FROM risky_login_config WHERE id=1" 2>/dev/null)
LE=$($PSQL "SELECT count(*) FROM login_events" 2>/dev/null)
[ "$EN" = t ] && ok "risky_login habilitado" || warn "risky_login deshabilitado"
if [ "${LE:-0}" -gt 0 ]; then
  EXT=$($PSQL "SELECT count(*) FROM login_events WHERE is_internal=false" 2>/dev/null)
  ok "login_events poblando ($LE; externos=$EXT)"
  [ "${EXT:-0}" -eq 0 ] && warn "0 logins externos: ¿está aplicando real_ip en nginx? (ver deploy/hardening/nginx)"
else warn "login_events vacío — sin tráfico o real_ip no configurado"; fi

hdr "fail2ban"
fail2ban-client -t >/dev/null 2>&1 && ok "configuración válida" || bad "configuración inválida (fail2ban-client -t)"
grep -q '^backend\s*=\s*systemd' /etc/fail2ban/jail.local 2>/dev/null && ok "backend journald (apto Debian 13)" || warn "backend no es systemd — en Debian 13 no leerá logs"

hdr "DLP (prevención de fuga de datos)"
DK=$($PSQL "SELECT count(*) FROM dlp_keywords" 2>/dev/null)
if [ "${DK:-0}" -gt 0 ]; then ok "DLP con $DK reglas/keywords"; else warn "DLP SIN reglas — no detecta nada (cargar set inicial)"; fi
DV=$($PSQL "SELECT count(*) FROM dlp_violations" 2>/dev/null); ok "violaciones DLP registradas: ${DV:-0}"

hdr "Safe Links (reescritura de URLs entrantes)"
SC=$($PSQL "SELECT enabled FROM safelinks_config LIMIT 1" 2>/dev/null)
[ "$SC" = t ] && ok "Safe Links habilitado" || warn "Safe Links deshabilitado"
[ -f /opt/maquita-webmail/backend/app/safelinks/inbound_rewriter.py ] && ok "reescritor de inbound presente" || warn "reescritor no encontrado"

hdr "MFA / TOTP"
code=$(curl -s -o /dev/null -w '%{http_code}' "$WEBMAIL/api/auth/totp/status" 2>/dev/null)
[ "$code" = 401 ] || [ "$code" = 200 ] && ok "endpoint TOTP responde ($code)" || bad "endpoint TOTP no responde ($code)"
TC=$($PSQL "SELECT count(*) FROM user_totp" 2>/dev/null); ok "usuarios con 2FA activo: ${TC:-0}"

hdr "Redis / Valkey"
RU=$(grep -oE '^REDIS_URL=.*' /opt/maquita-webmail/backend/.env 2>/dev/null | cut -d= -f2-)
if [ -n "$RU" ]; then PONG=$(redis-cli -u "$RU" ping 2>/dev/null); else PONG=$(redis-cli ping 2>/dev/null); fi
echo "$PONG" | grep -q PONG && ok "Redis responde PONG" || bad "Redis no responde (login dará 500)"

hdr "DNS de correo (informativo)"
DOM="${MAIL_DOMAIN:-$(grep -oE '^MAIL_DOMAIN=.*' /opt/maquita-webmail/backend/.env 2>/dev/null | cut -d= -f2)}"
if [ -n "$DOM" ]; then
  dig +short TXT "$DOM" 2>/dev/null | grep -q 'v=spf1' && ok "SPF presente en $DOM" || warn "sin SPF en $DOM"
  dig +short TXT "_dmarc.$DOM" 2>/dev/null | grep -q 'v=DMARC1' && ok "DMARC presente" || warn "sin DMARC en $DOM"
else warn "MAIL_DOMAIN no definido — omito DNS"; fi

printf '\n\033[1mRESUMEN:\033[0m %d OK · %d advertencias · %d fallos\n' "$PASS" "$WARN" "$FAIL"
[ "$FAIL" -eq 0 ] && printf '\033[32mVALIDACIÓN OK\033[0m — el despliegue responde en todo lo crítico\n' \
                  || printf '\033[31mVALIDACIÓN CON FALLOS\033[0m — revisar los [FALLO] de arriba\n'
exit "$FAIL"
