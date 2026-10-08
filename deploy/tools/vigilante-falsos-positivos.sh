#!/bin/bash
# vigilante-falsos-positivos — 08/10/2026. Lo instala deploy/webmail/instalar.sh (cron 07:10).
# Avisa por aviso-limitado; si no existe, define AVISO=<programa que lea el cuerpo por stdin y reciba el asunto>.
# Regla de la casa: no se pierde ni un correo importante en «no deseado». Cada mañana revisa lo que entró a
# Junk en las últimas 24 h en todos los buzones activos y, si el remitente es alguien a quien ESE buzón ya
# le ha escrito (está en sus Enviados), lo devuelve a la bandeja de entrada, lo enseña al filtro como
# legítimo y lo informa a TI (por aviso-limitado). Lo demás solo se cuenta en el informe.
# Uso: vigilante-falsos-positivos [--solo-informe]   (sin mover nada)
# Registro: /var/log/vigilante-falsos-positivos.log
set -u
LOG=/var/log/vigilante-falsos-positivos.log
SOLO_INFORME=0; [ "${1:-}" = "--solo-informe" ] && SOLO_INFORME=1
DESDE=${DESDE:-1d}
informe=""; total_junk=0; devueltos=0; buzones=0
for u in $(sudo -u postgres psql -d maildb -tAc "select username from mailbox where active order by username"); do
  uids=$(doveadm search -u "$u" mailbox Junk since "$DESDE" 2>/dev/null | awk '{print $2}')
  [ -z "$uids" ] && continue
  buzones=$((buzones+1))
  for uid in $uids; do
    total_junk=$((total_junk+1))
    de=$(doveadm fetch -u "$u" hdr.from mailbox Junk uid "$uid" 2>/dev/null | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+' | head -1 | tr 'A-Z' 'a-z')
    [ -z "$de" ] && continue
    # ¿Este buzón le ha escrito antes a ese remitente? (Enviados = correspondencia real)
    conocido=0
    for mb in Sent Enviados "Sent Items"; do
      if doveadm search -u "$u" mailbox "$mb" to "$de" 2>/dev/null | grep -q .; then conocido=1; break; fi
    done
    [ $conocido -eq 1 ] || continue
    asunto=$(doveadm fetch -u "$u" hdr.subject mailbox Junk uid "$uid" 2>/dev/null | sed -n 's/^hdr.subject: //p' | head -1 | cut -c1-80)
    if [ $SOLO_INFORME -eq 0 ]; then
      doveadm fetch -u "$u" text mailbox Junk uid "$uid" 2>/dev/null | sed 1d | rspamc learn_ham >/dev/null 2>&1
      doveadm move -u "$u" INBOX mailbox Junk uid "$uid" >/dev/null 2>&1 && devueltos=$((devueltos+1))
    fi
    informe="$informe
  · $u ← $de — «$asunto»"
    echo "$(date '+%F %T') $u <- $de | $asunto | $( [ $SOLO_INFORME -eq 1 ] && echo solo-informe || echo devuelto )" >> $LOG
  done
done
resumen="Últimas 24 h: $total_junk correos en no deseado en $buzones buzones. Devueltos a la bandeja de entrada por venir de un remitente conocido (el buzón ya le había escrito): $devueltos."
echo "$(date '+%F %T') RESUMEN $resumen" >> $LOG
if [ -n "$informe" ] || [ $SOLO_INFORME -eq 1 ]; then
  printf '%s\n%s\n\nCriterio: solo se devuelve lo que viene de alguien a quien ese buzón ya escribió. Para remitentes nuevos, la persona debe usar «No es spam»; para repetidos molestos, «Bloquear remitente».\nRegistro: %s\n' "$resumen" "$informe" "$LOG" | "${AVISO:-/usr/local/sbin/aviso-limitado}" "Correo: falsos positivos devueltos ($devueltos)"
fi
