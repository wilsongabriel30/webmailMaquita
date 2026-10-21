#!/bin/bash
# Reequilibra el Bayes de Rspamd aprendiendo como LEGÍTIMO el correo que las personas CONSERVAN en su
# bandeja de entrada desde hace más de 3 días (si fuera spam lo habrían movido o borrado). El correo
# enviado ya lo aprende el autoaprendizaje al salir.
# Motivo (servidor de producción, 08/10/2026): con muchos más spam que legítimos aprendidos, Rspamd se negaba a
# aprender («all learn conditions denied») y el Bayes marcaba correo legítimo como spam.
# Lo lanza maquita-reentrenar-ham.timer una vez al mes; también se puede ejecutar a mano.
#   MAX_POR_BUZON (80)  correos por buzón en cada pasada      MAILDB (maildb)  base de datos de buzones
set -uo pipefail
LOG=/var/log/rspamd-reentrenar-ham.log
MAX_POR_BUZON=${MAX_POR_BUZON:-80}
MAILDB=${MAILDB:-maildb}
estado() { rspamc stat 2>/dev/null | grep -E 'BAYES_(SPAM|HAM)' | grep -oE 'learned: [0-9]+' | paste -sd' '; }

echo "$(date '+%F %T') inicio (INBOX, máx. $MAX_POR_BUZON por buzón, entre 90 y 3 días de antigüedad)" >> "$LOG"
echo "   antes: $(estado)" >> "$LOG"
ok=0; ya=0; err=0; n=0
for u in $(sudo -u postgres psql -d "$MAILDB" -tAc "select username from mailbox where active order by username"); do
  uids=$(doveadm search -u "$u" mailbox INBOX since 90d before 3d 2>/dev/null | awk '{print $2}' | tail -n "$MAX_POR_BUZON")
  for uid in $uids; do
    n=$((n+1))
    r=$(doveadm fetch -u "$u" text mailbox INBOX uid "$uid" 2>/dev/null | sed 1d | nice -n 15 rspamc learn_ham 2>/dev/null)
    if grep -q 'success = true' <<<"$r"; then ok=$((ok+1))
    elif grep -qi 'already learned' <<<"$r"; then ya=$((ya+1))
    else err=$((err+1)); fi
  done
done
echo "   después: $(estado)" >> "$LOG"
echo "$(date '+%F %T') fin: $n mensajes, $ok aprendidos, $ya ya conocidos, $err errores" >> "$LOG"
