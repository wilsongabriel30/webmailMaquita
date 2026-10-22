#!/usr/bin/env bash
# maquita-sudo en módulos (v1.11.3, 22/10/2026): los validadores pasan a /usr/local/lib/maquita-sudo/ y el programa
# solo los carga de allí (de root y sin escritura para otros). Instala el programa y sus módulos si falta algo o es
# distinto del repositorio, con deploy/sudoers/instalar.sh (primero los módulos, después el programa).
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
S="$APP_DIR/deploy/sudoers"
LIB=/usr/local/lib/maquita-sudo
[ -f /usr/local/sbin/maquita-sudo ] || { echo "Sin cambios: este servidor no usa maquita-sudo."; exit 0; }

pendiente=""
cmp -s "$S/maquita-sudo" /usr/local/sbin/maquita-sudo || pendiente="el programa"
for f in "$S"/lib/*.py; do
  cmp -s "$f" "$LIB/$(basename "$f")" || { pendiente="${pendiente:+$pendiente y }sus validadores"; break; }
done
[ -n "$pendiente" ] || { echo "Sin cambios: maquita-sudo y sus validadores ya están al día."; exit 0; }
echo "Pendiente: maquita-sudo en módulos ($pendiente)."
[ "${1:-}" = "--simular" ] && exit 0

mkdir -p /var/backups/maquita-webmail && chmod 700 /var/backups/maquita-webmail
cp -a /usr/local/sbin/maquita-sudo "/var/backups/maquita-webmail/maquita-sudo.ajuste-78-$(date +%Y%m%d%H%M%S)"
bash "$S/instalar.sh"
# Comprobación: una orden que el panel usa siempre tiene que pasar la validación.
if ! SUDO_USER=maquita-admin python3 -I -c 'import sys,importlib.machinery as m,importlib.util as u
l=m.SourceFileLoader("ms","/usr/local/sbin/maquita-sudo"); s=u.spec_from_loader("ms",l); x=u.module_from_spec(s); l.exec_module(x)
x.autorizar("maquita-admin","maquita-actualizar",["estado"])' >/dev/null 2>&1; then
  echo "Error: maquita-sudo nuevo no valida; se vuelve al anterior." >&2
  cp -a "$(ls -t /var/backups/maquita-webmail/maquita-sudo.ajuste-78-* | head -1)" /usr/local/sbin/maquita-sudo
  exit 1
fi
echo "Listo: maquita-sudo en módulos ($LIB)."
