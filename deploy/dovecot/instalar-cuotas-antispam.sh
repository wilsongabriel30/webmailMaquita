#!/usr/bin/env bash
# Instala las piezas de cuotas y aprendizaje del antispam (no recarga Dovecot):
#   /etc/dovecot/maquita.d/cuotas-y-antispam.conf   ← deploy/dovecot/cuotas-y-antispam.conf
#   «!include_try /etc/dovecot/maquita.d/*.conf» al final de dovecot.conf, si aún no está
#   /var/vmail/sieve/report-{spam,ham}.sieve         ← filtros IMAPSieve (compilados con sievec)
#   /var/vmail/sieve/pipe-bin/learn-{spam,ham}.sh    ← llaman a rspamc
#   /usr/local/sbin/rspamd-reentrenar-ham.sh + maquita-reentrenar-ham.timer (mensual)
# La usan deploy/webmail/instalar.sh (instalación nueva) y deploy/ajustes/51-* (servidores ya instalados).
# Uso: instalar-cuotas-antispam.sh <APP_DIR>
set -euo pipefail
APP_DIR="${1:?uso: $0 <APP_DIR>}"
D="$APP_DIR/deploy/dovecot"; RS="$APP_DIR/deploy/rspamd"
CONF=/etc/dovecot/dovecot.conf
INCLUDE='!include_try /etc/dovecot/maquita.d/*.conf'

install -d -o root -g dovecot -m 755 /etc/dovecot/maquita.d
install -o root -g dovecot -m 644 "$D/cuotas-y-antispam.conf" /etc/dovecot/maquita.d/cuotas-y-antispam.conf
grep -qxF "$INCLUDE" "$CONF" || printf '\n# ---- Piezas opcionales del repositorio (deploy/dovecot) ----\n%s\n' "$INCLUDE" >> "$CONF"

# sievec compila con la configuración vigente: necesita ya las extensiones pipe e imapsieve (include).
install -d -o vmail -g vmail -m 755 /var/vmail/sieve /var/vmail/sieve/pipe-bin
for s in report-spam report-ham; do
  install -o vmail -g vmail -m 644 "$D/$s.sieve" "/var/vmail/sieve/$s.sieve"
  sudo -u vmail sievec "/var/vmail/sieve/$s.sieve"
done
for p in learn-spam learn-ham; do install -o vmail -g vmail -m 755 "$D/pipe-bin/$p.sh" "/var/vmail/sieve/pipe-bin/$p.sh"; done

install -m 755 "$RS/reentrenar-ham.sh" /usr/local/sbin/rspamd-reentrenar-ham.sh
install -m 644 "$RS/maquita-reentrenar-ham.service" "$RS/maquita-reentrenar-ham.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now maquita-reentrenar-ham.timer >/dev/null 2>&1 || true
