#!/usr/bin/env bash
# Intermediario de sitios web del portal de dominio (maquita-sitios-portal): «Mi sitio web» en el portal.
# Solo tiene sentido con las dos cosas instaladas: los sitios web (maquita-sitios) y el portal de dominio
# (usuario maquita-dominio). Sin alguna de ellas no hace nada. Idempotente.
#
# Uso:  sudo bash deploy/sitios/portal/instalar.sh              instala o actualiza
#       sudo bash deploy/sitios/portal/instalar.sh --pendiente  solo dice qué falta (no toca nada)
#
# Instala: el programa y sus módulos, el socket y su servicio de systemd, la carpeta de subidas del portal,
# el permiso del portal para escribir en ella, la tabla de cuotas (si la base es local) y, en el sitio de
# nginx del portal, la ruta /api/sitios con su límite de 512 MB (el resto del portal sigue con 64 KB).
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../../.." && pwd)"
LIB=/usr/local/lib/maquita-sitios-portal
BIN=/usr/local/sbin/maquita-sitios-portal
UNIDADES=/etc/systemd/system
SUBIDAS=/var/lib/maquita-sitios/subidas-portal
EXTRA="${UNIDADES}/maquita-panel-dominio.service.d/sitios-web.conf"
ENTORNO=/etc/maquita-mail/panel-dominio.env
CONF_REPO="${APP_DIR}/panel-dominio/deploy/nginx-panel-dominio.conf"
REPO_HERR="${APP_DIR}/deploy/sitios/herramientas/nginx-herramientas.conf"
REPO_RUTAS="${APP_DIR}/deploy/sitios/herramientas/nginx-herramientas-rutas.conf"
SNIP_HERR=/etc/nginx/snippets/herramientas-bd.conf
SNIP_RUTAS=/etc/nginx/snippets/herramientas-bd-rutas.conf
RESPALDOS=/var/backups/maquita-sitios-portal
SQL_DIR="${APP_DIR}/panel-dominio/deploy"
PENDIENTE=0; [ "${1:-}" = "--pendiente" ] && PENDIENTE=1

[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)." >&2; exit 2; }
if [ ! -x /usr/local/sbin/maquita-sitios ] || ! getent passwd maquita-dominio >/dev/null; then
  echo "Sin cambios: hacen falta los sitios web y el portal de dominio a la vez; este servidor no tiene los dos."
  exit 0
fi

drop_in() {
  printf '%s\n' "# Generado por deploy/sitios/portal/instalar.sh: subidas de sitios web del portal." \
    "[Service]" "ReadWritePaths=-${SUBIDAS}"
}

# Sitios de nginx del portal: los que incluyen su proxy (el archivo real, aunque esté enlazado).
vhosts_portal() {
  grep -ls "snippets/panel-dominio-proxy.conf" /etc/nginx/sites-enabled/* 2>/dev/null | while read -r v; do readlink -f "$v"; done | sort -u
}

bloque_nginx() { sed -n '/# >>> sitios web (maquita-sitios-portal)/,/# <<< sitios web/p' "$CONF_REPO"; }

bd_local() {
  local host
  host="$(grep -E '^PD_DB_HOST=' "$ENTORNO" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"'" || true)"
  [ -z "$host" ] || [ "$host" = "127.0.0.1" ] || [ "$host" = "localhost" ] || [ "$host" = "::1" ]
}

nombre_bd() {
  local n
  n="$(grep -E '^PD_DB_NAME=' "$ENTORNO" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"'" || true)"
  echo "${n:-maildb}"
}

tabla_cuotas() {
  runuser -u postgres -- psql -X -At -d "$(nombre_bd)" -c "SELECT to_regclass('pd_cuotas_sitio') IS NOT NULL" 2>/dev/null | grep -qx t
}

# --- Qué falta ---
falta=()
cmp -s "${SELF}/maquita-sitios-portal" "$BIN" || falta+=("programa ($BIN)")
diff -qr -x __pycache__ "${SELF}/lib" "$LIB" >/dev/null 2>&1 || falta+=("módulos ($LIB)")
for u in maquita-sitios-portal.socket maquita-sitios-portal@.service; do
  cmp -s "${SELF}/$u" "${UNIDADES}/$u" || falta+=("unidad $u")
done
systemctl is-active --quiet maquita-sitios-portal.socket 2>/dev/null || falta+=("socket activo")
[ "$(stat -c '%U:%G %a' "$SUBIDAS" 2>/dev/null)" = "maquita-dominio:maquita-dominio 700" ] || falta+=("carpeta de subidas ($SUBIDAS)")
if [ -f "${UNIDADES}/maquita-panel-dominio.service" ]; then
  [ "$(drop_in)" = "$(cat "$EXTRA" 2>/dev/null)" ] || falta+=("permiso del portal sobre sus subidas")
fi
for v in $(vhosts_portal); do
  grep -q "location /api/sitios" "$v" || falta+=("ruta /api/sitios en nginx ($v)")
done
if [ -f "$ENTORNO" ] && bd_local && ! tabla_cuotas; then falta+=("tabla pd_cuotas_sitio"); fi
# «Bases → Entrar» desde el portal: las rutas de phpMyAdmin y Adminer, si el servidor las tiene.
if [ -f "$SNIP_HERR" ]; then
  cmp -s "$REPO_HERR" "$SNIP_HERR" || falta+=("herramientas de bases ($SNIP_HERR)")
  cmp -s "$REPO_RUTAS" "$SNIP_RUTAS" || falta+=("rutas de las herramientas ($SNIP_RUTAS)")
  for v in $(vhosts_portal); do
    grep -q "herramientas-bd-rutas" "$v" || falta+=("herramientas de bases en el portal ($v)")
  done
fi

if [ "${#falta[@]}" -eq 0 ]; then echo "Sin cambios: el intermediario de sitios del portal ya está al día."; exit 0; fi
echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')"
[ "$PENDIENTE" = 1 ] && exit 0

# --- Programa, módulos y unidades ---
install -d -m 755 "$LIB"
rm -f "$LIB"/*.py
install -m 644 "${SELF}"/lib/*.py "$LIB/"
install -m 755 "${SELF}/maquita-sitios-portal" "$BIN"
cambio_unidades=0
for u in maquita-sitios-portal.socket maquita-sitios-portal@.service; do
  cmp -s "${SELF}/$u" "${UNIDADES}/$u" || { install -m 644 "${SELF}/$u" "${UNIDADES}/$u"; cambio_unidades=1; }
done
# El validador que hace de segunda barrera es el maquita-sudo instalado: que sea el de esta versión.
bash "${APP_DIR}/deploy/sudoers/instalar.sh"  # maquita-sudo y sus validadores (/usr/local/lib/maquita-sudo)

# --- Carpeta de subidas (del portal, 0700) y su permiso de escritura en la unidad del portal ---
install -d -m 755 /var/lib/maquita-sitios
install -d -o maquita-dominio -g maquita-dominio -m 700 "$SUBIDAS"
reiniciar_portal=0
if [ -f "${UNIDADES}/maquita-panel-dominio.service" ] && [ "$(drop_in)" != "$(cat "$EXTRA" 2>/dev/null)" ]; then
  install -d -m 755 "$(dirname "$EXTRA")"
  drop_in > "$EXTRA"
  reiniciar_portal=1
fi

systemctl daemon-reload
systemctl enable --now maquita-sitios-portal.socket >/dev/null 2>&1
[ "$cambio_unidades" = 1 ] && systemctl restart maquita-sitios-portal.socket
# ReadWritePaths solo se aplica al arrancar: el portal se reinicia (unos segundos) si cambió.
[ "$reiniciar_portal" = 1 ] && systemctl try-restart maquita-panel-dominio

# --- Tabla de cuotas (solo con la base en este equipo; si no, se indica cómo) ---
if [ -f "$ENTORNO" ] && bd_local; then
  if ! runuser -u postgres -- psql -X -q -v ON_ERROR_STOP=1 -d "$(nombre_bd)" \
      -f "${SQL_DIR}/esquema-4-sitios.sql" -f "${SQL_DIR}/permisos-4-sitios.sql" >/dev/null; then
    echo "Aviso: no se pudo crear pd_cuotas_sitio; aplíquela a mano (panel-dominio/README.md)." >&2
  fi
else
  echo "Aviso: la base del portal no está en este equipo. Aplique en ella esquema-4-sitios.sql y permisos-4-sitios.sql."
fi

# --- Herramientas de bases: rutas compartidas por el panel general y el portal ---
if [ -f "$SNIP_HERR" ]; then
  install -d -m 700 "$RESPALDOS"
  cp -p "$SNIP_HERR" "${RESPALDOS}/herramientas-bd.conf.$(date +%Y%m%d%H%M%S)"
  install -m 644 "$REPO_RUTAS" "$SNIP_RUTAS"
  install -m 644 "$REPO_HERR" "$SNIP_HERR"
fi

# --- nginx: ruta /api/sitios en el sitio del portal (respaldo y vuelta atrás si nginx la rechaza) ---
tocados=()
for v in $(vhosts_portal); do
  if grep -q "location /api/sitios" "$v"; then
    # Portal ya con /api/sitios de una versión anterior: solo falta incluir las herramientas de bases.
    if ! grep -q "herramientas-bd-rutas" "$v" && grep -q "# <<< sitios web" "$v"; then
      install -d -m 700 "$RESPALDOS"
      cp -p "$v" "${RESPALDOS}/$(basename "$v").$(date +%Y%m%d%H%M%S)"
      sed -i 's|^\([ \t]*\)# <<< sitios web|\1include /etc/nginx/snippets/herramientas-bd-rutas*.conf;\n\1# <<< sitios web|' "$v"
      tocados+=("$v")
    fi
    continue
  fi
  grep -qE '^\s*location /api/ \{' "$v" || { echo "Aviso: $v no tiene «location /api/ {»; añada a mano el bloque de sitios web." >&2; continue; }
  install -d -m 700 "$RESPALDOS"
  cp -p "$v" "${RESPALDOS}/$(basename "$v").$(date +%Y%m%d%H%M%S)"
  tmp="$(mktemp)"; bloque_nginx > "$tmp"
  # Antes de la primera «location /api/ {»: nginx elige la location de prefijo más largo, así que el orden
  # no cambia cuál gana; así queda junto a las demás rutas de la API.
  awk -v bloque="$tmp" '!hecho && /^[ \t]*location \/api\/ \{/ { while ((getline l < bloque) > 0) print l; hecho=1 } { print }' "$v" > "$v.nuevo"
  cat "$v.nuevo" > "$v"; rm -f "$v.nuevo" "$tmp"
  tocados+=("$v")
done
if [ "${#tocados[@]}" -gt 0 ]; then
  if ! nginx -t >/dev/null 2>&1; then
    for v in "${tocados[@]}"; do
      ultimo="$(ls -t "${RESPALDOS}/$(basename "$v")".* 2>/dev/null | head -1)"; [ -n "$ultimo" ] && cp -p "$ultimo" "$v"
    done
    ultimo="$(ls -t "${RESPALDOS}"/herramientas-bd.conf.* 2>/dev/null | head -1)"; [ -n "$ultimo" ] && cp -p "$ultimo" "$SNIP_HERR"
    echo "Error: nginx rechazó la ruta /api/sitios; el sitio del portal quedó como estaba." >&2
    exit 1
  fi
  systemctl reload nginx
fi

[ -S /run/maquita-sitios-portal.sock ] || { echo "Error: el socket /run/maquita-sitios-portal.sock no está." >&2; exit 1; }
echo "Listo: intermediario de sitios web del portal activo (/run/maquita-sitios-portal.sock)."
