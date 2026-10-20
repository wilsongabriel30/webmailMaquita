#!/bin/bash
# Escaneo SEMANAL de ClamAV del sistema (/). Lo lanza /etc/cron.d/clamav-semanal el viernes a las 00:00.
# timeout 48 h: si no termina, se corta el domingo 00:00 (TERM, y KILL 2 min después si resiste).
# flock evita que se solapen dos semanas; nice/ionice = mínima prioridad de CPU y disco.
#
# Se excluye /var/vmail (los buzones): en un servidor grande escanearlo entero tardaba más de
# 11 horas y saturaba justo el disco del que Dovecot sirve el correo (el webmail se volvía
# lentísimo en plena jornada; ionice -c3 no basta con algunos planificadores de disco).
# El correo NO queda sin protección: el entrante se analiza en tiempo real con rspamd + clamd
# (/etc/rspamd/local.d/antivirus.conf). Para repasar el histórico, lanzar un escaneo puntual de
# /var/vmail un fin de semana.
install -d -m 755 /var/log/clamav
/usr/bin/flock -n /var/lock/clamav-semanal.lock -c \
  'timeout --signal=TERM --kill-after=2m 48h nice -n 19 ionice -c3 clamscan -r --infected --exclude-dir=^/sys --exclude-dir=^/proc --exclude-dir=^/dev --exclude-dir=^/run --exclude-dir=^/var/vmail --exclude-dir=^/root/cuarentena-malware / > /var/log/clamav/escaneo-semanal-$(date +%F).log 2>&1' \
  || logger -t clamav-semanal "Escaneo semanal: omitido (otro en curso), cortado a las 48 h o con hallazgos (ver /var/log/clamav)"
# Conservar solo los últimos 8 registros.
ls -1t /var/log/clamav/escaneo-semanal-*.log 2>/dev/null | tail -n +9 | xargs -r rm -f
