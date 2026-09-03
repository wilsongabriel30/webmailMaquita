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
for s in postfix dovecot rspamd nginx clamav-daemon maquita-webmail maquita-admin maquita-milter fail2ban; do
  [ "$(systemctl is-active "$s" 2>/dev/null)" = active ] && ok "$s activo" || bad "$s NO activo"
done
# Redis o Valkey (cualquiera sirve)
systemctl is-active redis-server valkey valkey-server 2>/dev/null | grep -q active && ok "redis/valkey activo" || bad "redis/valkey NO activo"

hdr "Puertos en escucha"
for p in 25 465 587 143 993; do
  ss -ltn 2>/dev/null | grep -q ":$p " && ok "puerto $p" || bad "puerto $p cerrado"
done
ss -ltn 2>/dev/null | grep -q ":443 " && ok "puerto 443" || warn "puerto 443 no escucha local (¿HTTPS/proxy en otro host? OK si aplica)"

hdr "TLS/SNI del correo — cert correcto por cada nombre (config automatica movil)"
# La config automatica de Gmail/Outlook prueba el dominio PELADO y los subdominios; cada uno
# debe recibir un cert VALIDO para ese nombre (SNI). Un cert equivocado = "certificado no valido"
# en el primer contacto del usuario. (#15)
DOM="$(postconf -h mydomain 2>/dev/null)"
if [ -n "$DOM" ]; then
  for name in "$DOM" "mail.$DOM" "imap.$DOM" "smtp.$DOM"; do
    out="$(printf 'QUIT\r\n' | timeout 8 openssl s_client -connect 127.0.0.1:465 -servername "$name" -verify_hostname "$name" 2>&1)"
    if echo "$out" | grep -q "Verify return code: 0"; then
      ok "TLS/SNI 465 valido para $name"
    else
      warn "TLS/SNI 465: el cert NO valida para $name (la config automatica de moviles fallara; incluye $name en los SAN + SNI/local_name) [#15]"
    fi
  done
else
  warn "no pude leer 'postconf -h mydomain' para probar TLS/SNI"
fi
# Error-fantasma del mapa SNI mal construido (postmap sin -F) — solo vive en mail.log. (#14)
if tail -400 /var/log/mail.log 2>/dev/null | grep -qiE 'malformed BASE64|map lookup problem|SSL_accept error'; then
  bad "mail.log con errores de TLS/SNI (malformed BASE64 / lookup problem). Si usas tls_server_sni_maps: reconstruye vmail_sni con 'postmap -F' y REINICIA postfix (reload NO basta). [#14]"
else
  ok "mail.log sin errores de TLS/SNI (malformed BASE64/lookup)"
fi

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
DEN=$($PSQL "SELECT enabled FROM dlp_config WHERE id=1" 2>/dev/null)
[ "$DEN" = t ] && ok "DLP habilitado (detectores cédula/RUC/Luhn/IBAN/cuenta activos)" || bad "DLP deshabilitado (aplicar deploy/seeds/dlp-seed.sql)"
DK=$($PSQL "SELECT count(*) FROM dlp_keywords" 2>/dev/null)
[ "${DK:-0}" -gt 0 ] && ok "$DK palabras clave cargadas" || warn "sin keywords (los detectores de patrón igual funcionan; ver dlp-seed.sql)"
DV=$($PSQL "SELECT count(*) FROM dlp_violations" 2>/dev/null); ok "violaciones DLP registradas: ${DV:-0}"

hdr "Safe Links (reescritura de URLs entrantes)"
SC=$($PSQL "SELECT enabled FROM safelinks_config LIMIT 1" 2>/dev/null)
[ "$SC" = t ] && ok "Safe Links habilitado" || warn "Safe Links deshabilitado"
[ -f /opt/maquita-webmail/backend/app/safelinks/inbound_rewriter.py ] && ok "reescritor de inbound presente" || warn "reescritor no encontrado"

hdr "Anti-phishing - clasificador de contenido"
CLF=$(cd /opt/maquita-webmail/backend && venv/bin/python3 -c "from app.safelinks import classifier as c; print(c.score_message(sender='Soporte TI <admin@x.com>', subject='Cuenta suspendida - accion urgente', body='Estimado cliente, verifique su contrasena de inmediato: <a href=\"http://evil-site.ru/login\">https://www.portal-seguro.com</a>')['label'])" 2>/dev/null)
[ "$CLF" = phishing ] && ok "clasificador detecta phishing en la muestra" || bad "clasificador no funciona (revisar safelinks/classifier.py; dio: ${CLF:-vacio})"
EXTK=$(grep -oE '^PHISH_CLASSIFIER_KIND=.+' /opt/maquita-webmail/backend/.env 2>/dev/null | cut -d= -f2-)
EXTU=$(grep -oE '^PHISH_CLASSIFIER_URL=.+' /opt/maquita-webmail/backend/.env 2>/dev/null | cut -d= -f2-)
if [ -n "$EXTK" ] || [ -n "$EXTU" ]; then ok "capa externa configurada (${EXTK:-contrato})"; else warn "capa externa no configurada (solo heuristica local; OK al instalar)"; fi

hdr "MFA / TOTP"
code=$(curl -s -o /dev/null -w '%{http_code}' "$WEBMAIL/api/auth/totp/status" 2>/dev/null)
[ "$code" = 401 ] || [ "$code" = 200 ] && ok "endpoint TOTP responde ($code)" || bad "endpoint TOTP no responde ($code)"
TC=$($PSQL "SELECT count(*) FROM user_totp" 2>/dev/null); ok "usuarios con 2FA activo: ${TC:-0}"

hdr "Redis / Valkey"
RU=$(grep -oE '^REDIS_URL=.*' /opt/maquita-webmail/backend/.env 2>/dev/null | cut -d= -f2-)
RPASS=$(printf '%s' "$RU" | sed -E 's#redis://[^:]*:([^@]*)@.*#\1#')
if [ -n "$RPASS" ] && [ "$RPASS" != "$RU" ]; then
  PONG=$(redis-cli -a "$RPASS" --no-auth-warning ping 2>/dev/null)
else PONG=$(redis-cli ping 2>/dev/null); fi
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

# --- IA enchufable (WARN, no falla la validacion) ---
echo ""
echo "[IA] Probando IA configurada (opcional)..."
if bash /opt/maquita-webmail/deploy/webmail/probar-ia.sh 2>&1 | sed 's/^/    /'; then :; else
  echo "    WARN: la IA no respondio (no critico: las funciones de IA se degradan, el correo sigue)."
fi
