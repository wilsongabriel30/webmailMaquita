#!/usr/bin/env bash
# Permisos de los .env de las aplicaciones (2026-10-21). instalar.sh dejaba backend/.env con 644: la
# clave de la base del correo y los secretos del webmail quedaban a la vista de cualquier usuario del
# sistema, también de los usuarios de los sitios web (sus tareas cron y aplicaciones propias no tienen
# open_basedir). Ahora: backend/.env 640 root:www-data (lo lee el webmail) y a los demás .env se les
# quitan los permisos de «otros». No cambia el contenido ni el dueño de lo que ya está cerrado.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

abiertos=()
for f in "$APP_DIR/backend/.env" "$APP_DIR/admin-panel/backend/.env" "$APP_DIR/almacen/.env" \
         "$APP_DIR/chat-service/.env" /etc/maquita-mail/*.env; do
  [ -f "$f" ] || continue
  case "$f" in /etc/maquita-mail/organizacion.env) continue ;; esac  # no lleva secretos y lo leen los guiones
  [ $(( 0$(stat -c '%a' "$f") & 07 )) -eq 0 ] || abiertos+=("$f")
done
env_correo="$APP_DIR/backend/.env"
grupo_mal=0
if [ -f "$env_correo" ] && [ "$(stat -c '%G' "$env_correo")" = root ] && id www-data >/dev/null 2>&1; then grupo_mal=1; fi

if [ "${#abiertos[@]}" -eq 0 ] && [ "$grupo_mal" = 0 ]; then
  echo "Sin cambios: ningún .env queda a la vista de otros usuarios."; exit 0
fi
echo "Pendiente: cerrar ${abiertos[*]:-}$( [ "$grupo_mal" = 1 ] && echo " (backend/.env al grupo www-data)")"
[ "${1:-}" = "--simular" ] && exit 0

for f in "${abiertos[@]}"; do chmod o-rwx "$f"; done
if [ -f "$env_correo" ]; then
  [ "$grupo_mal" = 1 ] && chgrp www-data "$env_correo"
  chmod 640 "$env_correo"
fi
# El webmail tiene que seguir leyéndolo: se comprueba antes de dar el ajuste por bueno.
if [ -f "$env_correo" ] && id www-data >/dev/null 2>&1 && ! runuser -u www-data -- test -r "$env_correo"; then
  echo "Error: el webmail (www-data) ya no puede leer $env_correo." >&2; exit 1
fi
echo "Listo: .env cerrados a otros usuarios."
