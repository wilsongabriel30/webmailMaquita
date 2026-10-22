#!/usr/bin/env bash
# v1.11 «Para desarrolladores» en servidores ya instalados (sitios web): usuarios de bases con permisos, cortafuegos
# de aplicaciones web por sitio (OWASP CRS: modo, paranoia, exclusiones y registro de bloqueos de cada sitio), claves
# SSH de las cuentas SFTP y fichas de API del portal.
#
# Qué hace (solo lo que falte):
#   - ayudante maquita-sitios y sus módulos, maquita-sudo y los módulos del cortafuegos del proyecto al día;
#   - perfiles del cortafuegos de aplicación (/etc/nginx/sitios-waf/perfil-*.conf), carpetas de reglas y registros
#     por sitio, logrotate, y los vhosts regenerados para que cada sitio cargue sus propias reglas;
#   - sshd: «AuthorizedKeysFile /etc/ssh/claves-sitios/%u» en el bloque «Match Group sitios» (sshd -t antes);
#   - tabla pd_fichas_api del portal de dominio (si el portal está y su base es local).
# Respaldo de todo lo que toca en /var/backups/maquita-sitios/ajuste-71-<fecha>.tar.gz; si `nginx -t` o `sshd -t`
# rechazan el cambio, se restaura lo anterior. Las reglas de WordPress, Joomla y el catálogo no cambian.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
S="$APP_DIR/deploy/sitios"
LIB=/usr/local/lib/maquita-sitios
WAF=/etc/nginx/sitios-waf
SSHD=/etc/ssh/sshd_config
LINEA_CLAVES="    AuthorizedKeysFile /etc/ssh/claves-sitios/%u"
RESPALDOS=/var/backups/maquita-sitios
ENTORNO_PORTAL=/etc/maquita-mail/panel-dominio.env
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1

[ -x /usr/local/sbin/maquita-sitios ] || { echo "Sin cambios: este servidor no tiene los sitios web."; exit 0; }
[ -f "$S/lib/waf_sitio.py" ] || { echo "Sin cambios: esta versión no trae las funciones v1.11 ($S/lib/waf_sitio.py)."; exit 0; }

modulos_al_dia() {
  local f
  for f in "$S"/lib/*.py; do cmp -s "$f" "$LIB/$(basename "$f")" || return 1; done
  for f in "$S"/lib/apps/*.py; do cmp -s "$f" "$LIB/apps/$(basename "$f")" || return 1; done
  cmp -s "$S/maquita-sitios" /usr/local/sbin/maquita-sitios && cmp -s "$APP_DIR/deploy/sudoers/maquita-sudo" /usr/local/sbin/maquita-sudo
}

perfiles_al_dia() {
  local app
  for app in general wordpress joomla aplicacion; do
    cmp -s "$S/nginx/waf-${app}.conf" "$WAF/${app}.conf" && cmp -s "$S/nginx/waf-perfil-${app}.conf" "$WAF/perfil-${app}.conf" || return 1
  done
  cmp -s "$S/nginx/logrotate-sitios-waf" /etc/logrotate.d/sitios-waf && [ -d /etc/maquita-sitios/waf ] && [ -d /var/log/nginx/sitios-waf ]
}

vhosts_sin_reglas_propias() {
  # Sitios cuyo vhost aún carga las reglas comunes (/etc/nginx/sitios-waf/<perfil>.conf) en vez de las suyas.
  grep -ls "modsecurity_rules_file /etc/nginx/sitios-waf/" /etc/nginx/sites-available/sitio-*.conf 2>/dev/null | head -1
}

sshd_al_dia() {
  ! grep -q "^# >>> sitios-web (maquita-sitios)" "$SSHD" 2>/dev/null || \
    sed -n '/^# >>> sitios-web (maquita-sitios)/,/^# <<< sitios-web/p' "$SSHD" | grep -qxF "$LINEA_CLAVES"
}

cortafuegos_al_dia() {
  [ -d /usr/local/lib/maquita-cortafuegos ] || return 0
  local f
  for f in "$APP_DIR"/deploy/cortafuegos/lib/*.py; do cmp -s "$f" "/usr/local/lib/maquita-cortafuegos/$(basename "$f")" || return 1; done
}

bd_portal_local() {
  [ -f "$ENTORNO_PORTAL" ] || return 1
  local host
  host="$(grep -E '^PD_DB_HOST=' "$ENTORNO_PORTAL" | tail -1 | cut -d= -f2- | tr -d "\"'" || true)"
  [ -z "$host" ] || [ "$host" = "127.0.0.1" ] || [ "$host" = "localhost" ] || [ "$host" = "::1" ]
}

nombre_bd_portal() {
  local n
  n="$(grep -E '^PD_DB_NAME=' "$ENTORNO_PORTAL" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"'" || true)"
  echo "${n:-maildb}"
}

tabla_fichas() {
  runuser -u postgres -- psql -X -At -d "$(nombre_bd_portal)" -c "SELECT to_regclass('pd_fichas_api') IS NOT NULL" 2>/dev/null | grep -qx t
}

falta=()
modulos_al_dia || falta+=("ayudante de sitios y maquita-sudo")
perfiles_al_dia || falta+=("perfiles del cortafuegos de aplicación ($WAF/perfil-*.conf)")
[ -z "$(vhosts_sin_reglas_propias)" ] || falta+=("vhosts con las reglas propias de cada sitio")
sshd_al_dia || falta+=("claves SSH en sshd (AuthorizedKeysFile)")
cortafuegos_al_dia || falta+=("módulos del cortafuegos del proyecto")
if bd_portal_local && ! tabla_fichas; then falta+=("tabla pd_fichas_api del portal"); fi

if [ "${#falta[@]}" -eq 0 ]; then echo "Sin cambios: bases, cortafuegos de aplicaciones y claves SSH ya están al día."; exit 0; fi
echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')."
[ "$SIMULAR" = 1 ] && exit 0

# --- Respaldo de todo lo que se va a tocar ---
install -d -m 700 "$RESPALDOS"
RESPALDO="$RESPALDOS/ajuste-71-$(date +%Y%m%d%H%M%S).tar.gz"
tar -czf "$RESPALDO" --ignore-failed-read -P "$LIB" /usr/local/sbin/maquita-sitios /usr/local/sbin/maquita-sudo "$WAF" \
  "$SSHD" $(ls /etc/nginx/sites-available/sitio-*.conf 2>/dev/null) $([ -d /etc/maquita-sitios/waf ] && echo /etc/maquita-sitios/waf) \
  $([ -d /usr/local/lib/maquita-cortafuegos ] && echo /usr/local/lib/maquita-cortafuegos) 2>/dev/null || true

restaurar() {
  echo "Error: $1. Se restaura lo anterior desde $RESPALDO." >&2
  rm -f /etc/nginx/sites-available/sitio-*.conf.tmp
  tar -xzf "$RESPALDO" -P
  nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
  exit 1
}

# --- Ayudante, maquita-sudo y cortafuegos del proyecto ---
install -d -m 755 "$LIB" "$LIB/apps"
install -m 644 "$S"/lib/*.py "$LIB/"
install -m 644 "$S"/lib/apps/*.py "$LIB/apps/"
install -m 755 "$S/maquita-sitios" /usr/local/sbin/maquita-sitios
bash "$APP_DIR/deploy/sudoers/instalar.sh"  # maquita-sudo y sus validadores (/usr/local/lib/maquita-sudo)
if [ -d /usr/local/lib/maquita-cortafuegos ]; then
  install -m 644 "$APP_DIR"/deploy/cortafuegos/lib/*.py /usr/local/lib/maquita-cortafuegos/
fi

# --- Cortafuegos de aplicación: perfiles, carpetas, registro y vhosts con las reglas de cada sitio ---
install -d -m 755 "$WAF" /etc/maquita-sitios/waf
install -d -m 750 -o www-data -g adm /var/log/nginx/sitios-waf
for app in general wordpress joomla aplicacion; do
  install -m 644 "$S/nginx/waf-${app}.conf" "$WAF/${app}.conf"
  install -m 644 "$S/nginx/waf-perfil-${app}.conf" "$WAF/perfil-${app}.conf"
done
install -m 644 "$S/nginx/logrotate-sitios-waf" /etc/logrotate.d/sitios-waf
# «regenerar» reescribe los vhosts y recarga nginx solo si `nginx -t` los acepta.
/usr/local/sbin/maquita-sitios regenerar >/dev/null 2>&1 || restaurar "nginx no aceptó los vhosts regenerados"
nginx -t >/dev/null 2>&1 || restaurar "nginx -t falla tras regenerar"

# --- sshd: claves de los sitios fuera del encierro, de root ---
install -d -m 755 -o root -g root /etc/ssh/claves-sitios
if ! sshd_al_dia; then
  sed -i "/^# >>> sitios-web (maquita-sitios)/,/^# <<< sitios-web/{
    /^    AuthorizedKeysFile /d
    /^    PubkeyAuthentication /d
    /^    # Claves SSH que se añaden/d
    s|^    PasswordAuthentication yes\$|    PasswordAuthentication yes\n    # Claves SSH que se añaden desde el panel o el portal: archivos de root fuera del encierro.\n    PubkeyAuthentication yes\n$LINEA_CLAVES|
  }" "$SSHD"
  if sshd -t 2>/dev/null; then
    systemctl reload ssh 2>/dev/null || systemctl reload sshd
  else
    tar -xzf "$RESPALDO" -P "$SSHD"
    echo "Aviso: sshd no aceptó AuthorizedKeysFile; se dejó como estaba (el SFTP con contraseña sigue igual)." >&2
  fi
fi

# --- Fichas de API del portal ---
if bd_portal_local && ! tabla_fichas; then
  runuser -u postgres -- psql -X -q -v ON_ERROR_STOP=1 -d "$(nombre_bd_portal)" \
    -f "$APP_DIR/panel-dominio/deploy/esquema-5-fichas-api.sql" -f "$APP_DIR/panel-dominio/deploy/permisos-5-fichas-api.sql" >/dev/null \
    || echo "Aviso: no se pudo crear pd_fichas_api; aplique a mano esquema-5-fichas-api.sql y permisos-5-fichas-api.sql." >&2
elif [ -f "$ENTORNO_PORTAL" ] && ! bd_portal_local; then
  echo "Aviso: la base del portal no está en este equipo. Aplique en ella esquema-5-fichas-api.sql y permisos-5-fichas-api.sql."
fi

echo "Listo: usuarios de bases, cortafuegos de aplicaciones por sitio y claves SSH preparados (respaldo: $RESPALDO)."
