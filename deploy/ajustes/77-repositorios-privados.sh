#!/usr/bin/env bash
# Repositorios privados en servidores ya instalados (sitios web): autenticación de git por sitio para el despliegue
# de los sitios PHP y para las aplicaciones propias Node.js, Python y estáticas (clave de despliegue generada,
# clave propia, token o usuario y contraseña; deploy/sitios/lib/git_clave.py y git_credencial.py).
#
# Qué hace (solo lo que falte):
#   - ayudante maquita-sitios y sus módulos (con el validador sudo_git_credencial.py) y maquita-sudo al día;
#   - con el portal de dominio, sus módulos (ordenes_git_credencial.py), con su propio instalador (idempotente).
# No toca vhosts, sitios ni credenciales. Las unidades de las aplicaciones propias ya creadas toman el encierro
# nuevo (la aplicación no ve la carpeta de despliegues) la próxima vez que se pulse «Desplegar».
# Respaldo de lo que sustituye en /var/backups/maquita-sitios/ajuste-77-<fecha>.tar.gz.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
S="$APP_DIR/deploy/sitios"
LIB=/usr/local/lib/maquita-sitios
LIB_PORTAL=/usr/local/lib/maquita-sitios-portal
RESPALDOS=/var/backups/maquita-sitios
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1

[ -x /usr/local/sbin/maquita-sitios ] || { echo "Sin cambios: este servidor no tiene los sitios web."; exit 0; }
[ -f "$S/lib/git_credencial.py" ] || { echo "Sin cambios: esta versión no trae los repositorios privados."; exit 0; }

modulos_al_dia() {
  local f
  for f in "$S"/lib/*.py; do cmp -s "$f" "$LIB/$(basename "$f")" || return 1; done
  cmp -s "$S/maquita-sitios" /usr/local/sbin/maquita-sitios && cmp -s "$APP_DIR/deploy/sudoers/maquita-sudo" /usr/local/sbin/maquita-sudo
}

portal_al_dia() {
  [ -d "$LIB_PORTAL" ] || return 0
  diff -qr -x __pycache__ "$S/portal/lib" "$LIB_PORTAL" >/dev/null 2>&1
}

falta=()
modulos_al_dia || falta+=("ayudante de sitios y maquita-sudo")
portal_al_dia || falta+=("módulos del intermediario del portal ($LIB_PORTAL)")
if [ "${#falta[@]}" -eq 0 ]; then echo "Sin cambios: los repositorios privados ya están preparados."; exit 0; fi
echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')."
[ "$SIMULAR" = 1 ] && exit 0

install -d -m 700 "$RESPALDOS"
RESPALDO="$RESPALDOS/ajuste-77-$(date +%Y%m%d%H%M%S).tar.gz"
tar -czf "$RESPALDO" --ignore-failed-read -P "$LIB" /usr/local/sbin/maquita-sitios /usr/local/sbin/maquita-sudo \
  $([ -d "$LIB_PORTAL" ] && echo "$LIB_PORTAL") 2>/dev/null || true

install -d -m 755 "$LIB"
install -m 644 "$S"/lib/*.py "$LIB/"
install -m 755 "$S/maquita-sitios" /usr/local/sbin/maquita-sitios
bash "$APP_DIR/deploy/sudoers/instalar.sh"  # maquita-sudo y sus validadores (/usr/local/lib/maquita-sudo)
if [ -d "$LIB_PORTAL" ] && ! portal_al_dia; then
  bash "$S/portal/instalar.sh" >/dev/null || echo "Aviso: no se pudo poner al día el intermediario del portal; ejecute $S/portal/instalar.sh." >&2
fi
# El validador nuevo tiene que cargar: si no, las órdenes de autenticación no pasarían por maquita-sudo.
python3 - <<'PY' || { echo "Error: maquita-sudo no carga el validador; se restaura lo anterior ($RESPALDO)." >&2; tar -xzf "$RESPALDO" -P; exit 1; }
import importlib.machinery, importlib.util
cargador = importlib.machinery.SourceFileLoader("maquita_sudo_ajuste", "/usr/local/sbin/maquita-sudo")
modulo = importlib.util.module_from_spec(importlib.util.spec_from_loader("maquita_sudo_ajuste", cargador))
cargador.exec_module(modulo)
modulo.validar_sitios(["git-credencial", "example.org"])
PY
echo "Listo: autenticación de git por sitio (repositorios privados) preparada (respaldo: $RESPALDO)."
