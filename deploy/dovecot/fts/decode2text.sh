#!/bin/bash
# Decodificador de adjuntos del índice de texto completo (servicio maquita-decode2text de Dovecot).
# Se instala en /usr/local/lib/maquita-fts/decode2text.sh; Dovecot lo ejecuta como el usuario sin
# privilegios «maquita-fts» (sin acceso a los buzones: solo recibe el adjunto por la entrada estándar).
#
# Aquí solo se ponen los límites del sistema; el trabajo lo hace decodificador/decodificar.py:
#  - memoria virtual, tiempo de CPU y tamaño de archivo (ulimit), sin volcados de memoria;
#  - tiempo real máximo (timeout) y prioridad baja de CPU y disco (nice, ionice);
#  - entorno vacío y carpeta temporal propia (0700).
# Los valores salen de /etc/maquita-fts/decodificador.conf (MEMORIA_MB, TIEMPO_TOTAL_S); si no, los de
# abajo. Nunca ejecuta macros ni el contenido del adjunto.
set -u
CONF=/etc/maquita-fts/decodificador.conf
LIB=/usr/local/lib/maquita-fts
MEMORIA_MB=1024
TIEMPO_TOTAL_S=60
if [ -r "$CONF" ]; then
  # Se leen solo enteros con nombre conocido: el archivo no se ejecuta («source» lo haría).
  v=$(grep -E '^MEMORIA_MB=[0-9]{2,5}$' "$CONF" | tail -n1 | cut -d= -f2) && [ -n "$v" ] && MEMORIA_MB=$v
  v=$(grep -E '^TIEMPO_TOTAL_S=[0-9]{1,3}$' "$CONF" | tail -n1 | cut -d= -f2) && [ -n "$v" ] && TIEMPO_TOTAL_S=$v
fi
[ "$MEMORIA_MB" -le 4096 ] || MEMORIA_MB=4096
[ "$TIEMPO_TOTAL_S" -le 300 ] || TIEMPO_TOTAL_S=300

umask 077
ulimit -c 0
ulimit -v $((MEMORIA_MB * 1024))
ulimit -t "$TIEMPO_TOTAL_S"
ulimit -f $((1300 * 1024)) # KiB: entrada (≤200 MB) + descomprimido (≤1 GB) como mucho

TMPDIR=/var/lib/maquita-fts/tmp
[ -d "$TMPDIR" ] && [ -w "$TMPDIR" ] || TMPDIR=/tmp
exec env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR="$TMPDIR" HOME=/nonexistent \
  timeout -k 5 "$TIEMPO_TOTAL_S" nice -n 10 ionice -c3 \
  /usr/bin/python3 -I "$LIB/decodificar.py" "$@"
