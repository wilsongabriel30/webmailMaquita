#!/usr/bin/env bash
# Instala maquita-sudo y sus validadores (/usr/local/lib/maquita-sudo/). Lo llaman todos los instaladores que lo
# necesitan. Primero los módulos y después el programa: un maquita-sudo nuevo sin sus módulos no deja pasar nada.
# Carpeta y archivos de root y sin escritura para otros: maquita-sudo lo comprueba antes de cargarlos.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LIB=/usr/local/lib/maquita-sudo
install -d -m 755 -o root -g root "$LIB"
install -m 644 -o root -g root "$DIR"/lib/*.py "$LIB"/
# Módulos de una versión anterior que ya no existen en esta.
for f in "$LIB"/*.py; do
  [ -e "$DIR/lib/$(basename "$f")" ] || rm -f "$f"
done
rm -rf "$LIB/__pycache__"
install -m 755 -o root -g root "$DIR/maquita-sudo" /usr/local/sbin/maquita-sudo
