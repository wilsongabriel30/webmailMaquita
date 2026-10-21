#!/usr/bin/env bash
# Cuotas de buzón y aprendizaje del antispam (2026-10-20). Las instalaciones anteriores guardaban la cuota
# de cada buzón en la tabla mailbox pero Dovecot no la aplicaba (ni el plugin quota estaba activo), y
# mover un correo a «Junk» o sacarlo de ahí no le enseñaba nada a Rspamd. Este ajuste:
#   - añade quota_storage_size (bytes de la columna quota) a la consulta del userdb SQL de dovecot.conf;
#   - instala deploy/dovecot/cuotas-y-antispam.conf en /etc/dovecot/maquita.d/ (incluido desde dovecot.conf),
#     los filtros IMAPSieve, los programas que llaman a rspamc y el reentrenamiento mensual.
# Valida con doveconf -n antes de recargar; si falla, deja dovecot.conf como estaba.
# No toca servidores que ya configuran cuotas por su cuenta (p. ej. con conf.d/90-quota.conf).
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CONF=/etc/dovecot/dovecot.conf
NUESTRO=/etc/dovecot/maquita.d/cuotas-y-antispam.conf
INCLUDE='!include_try /etc/dovecot/maquita.d/*.conf'
ANCLA="5000 AS gid FROM mailbox WHERE username = '%{user}' AND active = true"
CAMPO="5000 AS gid, CASE WHEN quota > 0 THEN quota::text END AS quota_storage_size FROM mailbox WHERE username = '%{user}' AND active = true"

[ -f "$CONF" ] || { echo "Sin cambios: no hay $CONF."; exit 0; }
actual="$(doveconf -n 2>/dev/null)" || { echo "Sin cambios: la configuración actual de Dovecot no valida (doveconf -n); no se toca."; exit 0; }
if [ ! -e "$NUESTRO" ] && grep -qE '^quota[ "]' <<<"$actual"; then
  echo "Sin cambios: este servidor ya configura cuotas por su cuenta (revisar a mano si hace falta)."; exit 0
fi

falta=()
cmp -s "$APP_DIR/deploy/dovecot/cuotas-y-antispam.conf" "$NUESTRO" 2>/dev/null || falta+=("configuración de cuotas y antispam")
grep -qxF "$INCLUDE" "$CONF" || falta+=("incluir maquita.d en dovecot.conf")
grep -q 'quota_storage_size' "$CONF" || falta+=("cuota del buzón en el userdb")
for f in /var/vmail/sieve/report-spam.svbin /var/vmail/sieve/report-ham.svbin \
         /var/vmail/sieve/pipe-bin/learn-spam.sh /var/vmail/sieve/pipe-bin/learn-ham.sh \
         /etc/systemd/system/maquita-reentrenar-ham.timer; do
  [ -e "$f" ] || { falta+=("filtros de aprendizaje y reentrenamiento"); break; }
done
if [ "${#falta[@]}" -eq 0 ]; then echo "Sin cambios: cuotas y aprendizaje del antispam ya activos."; exit 0; fi
if ! grep -q 'quota_storage_size' "$CONF" && ! grep -qF "$ANCLA" "$CONF"; then
  echo "Sin cambios: la consulta del userdb de $CONF no es la del repositorio; añadir quota_storage_size a mano."; exit 0
fi

echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')"
[ "${1:-}" = "--simular" ] && exit 0

respaldo="$CONF.bak.$(date +%Y%m%d%H%M%S)"
cp -p "$CONF" "$respaldo"
deshacer() { cp -p "$respaldo" "$CONF"; rm -f "$NUESTRO"; echo "Error: $1. dovecot.conf restaurado desde $respaldo." >&2; exit 1; }

grep -q 'quota_storage_size' "$CONF" || sed -i "s|$ANCLA|$CAMPO|" "$CONF"
bash "$APP_DIR/deploy/dovecot/instalar-cuotas-antispam.sh" "$APP_DIR" || deshacer "no se pudieron instalar las piezas"
salida="$(doveconf -n 2>&1 >/dev/null)" || deshacer "doveconf rechaza la configuración: ${salida:0:300}"
doveadm reload 2>/dev/null || systemctl reload-or-restart dovecot
echo "Listo: cuotas aplicadas por Dovecot y aprendizaje del antispam activo (respaldo: $respaldo)."
