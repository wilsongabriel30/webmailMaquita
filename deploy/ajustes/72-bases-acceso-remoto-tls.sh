#!/usr/bin/env bash
# v1.11: el servidor preparado para el acceso remoto a las bases de los sitios, SOLO con TLS y SOLO por el
# cortafuegos del proyecto (cada puerto se abre después, desde el panel o el portal, para las IP de cada usuario).
#
# Qué hace (solo lo que falte), con el certificado de Let's Encrypt del propio servidor (MAIL_HOST):
#   - copia el certificado para MariaDB y PostgreSQL y deja el gancho de certbot que lo vuelve a copiar al renovarse
#     (maquita-bases-tls; no pide certificados ni toca la clave: no afecta a DANE);
#   - MariaDB: escucha en la red con TLS 1.2 o superior (90-maquita-bases-remoto.cnf). Las cuentas remotas se crean
#     con REQUIRE SSL; root sigue solo por el socket local;
#   - PostgreSQL 16 o posterior: escucha en la red con ssl = on y scram-sha-256, e incluye en pg_hba.conf el archivo
#     de reglas «hostssl» que genera maquita-sitios (include_if_exists);
#   - deja escrito en /etc/maquita-sitios/bases-remoto.json qué motores quedaron listos.
# MariaDB y PostgreSQL se REINICIAN una vez (unos segundos sin bases: correo, panel y sitios esperan).
# No hace nada sin el cortafuegos del proyecto activo: sin él, escuchar en la red abriría los puertos a todo Internet.
# Respaldo en /var/backups/maquita-sitios/ajuste-72-<fecha>.tar.gz; si un motor no arranca, vuelve a lo anterior.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
ESTADO=/etc/maquita-sitios/bases-remoto.json
CNF=/etc/mysql/mariadb.conf.d/90-maquita-bases-remoto.cnf
HBA_SITIOS=/etc/postgresql/maquita-bases-remoto.conf
HOOK=/etc/letsencrypt/renewal-hooks/deploy/maquita-bases-tls
BIN=/usr/local/sbin/maquita-bases-tls
RESPALDOS=/var/backups/maquita-sitios
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1

[ -x /usr/local/sbin/maquita-sitios ] || { echo "Sin cambios: este servidor no tiene los sitios web."; exit 0; }
[ -f "$APP_DIR/deploy/sitios/lib/bases_remoto.py" ] || { echo "Sin cambios: esta versión no trae el acceso remoto a bases."; exit 0; }
if ! iptables -C INPUT -j CORTAFUEGOS >/dev/null 2>&1; then
  echo "Sin cambios: el acceso remoto a bases exige el cortafuegos del proyecto activo (maquita-cortafuegos); sin él no se abre MariaDB ni PostgreSQL a la red."
  exit 0
fi
MAIL_HOST="$(grep -E '^MAIL_HOST=' /opt/maquita-webmail/backend/.env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' " || true)"
[ -n "$MAIL_HOST" ] || MAIL_HOST="$(hostname -f 2>/dev/null || true)"
if [ -z "$MAIL_HOST" ] || [ ! -s "/etc/letsencrypt/live/$MAIL_HOST/fullchain.pem" ]; then
  echo "Sin cambios: no hay certificado de Let's Encrypt de ${MAIL_HOST:-este servidor}; el acceso remoto a bases necesita uno (TLS obligatorio)."
  exit 0
fi

PG_CONF="$(ls -d /etc/postgresql/*/main 2>/dev/null | sort -V | tail -1 || true)"
PG_VERSION="$(basename "$(dirname "$PG_CONF")" 2>/dev/null || echo 0)"
hay_mariadb() { command -v mariadb >/dev/null && [ -d /etc/mysql/mariadb.conf.d ]; }
hay_pg() { [ -n "$PG_CONF" ] && [ "${PG_VERSION%%.*}" -ge 16 ] 2>/dev/null; }

mariadb_listo() { [ -f "$CNF" ] && mariadb --protocol=socket -u root -N -B -e "SHOW GLOBAL VARIABLES LIKE 'have_ssl'" 2>/dev/null | grep -q "YES"; }
pg_listo() {
  [ -f "$PG_CONF/conf.d/90-maquita-bases-remoto.conf" ] && grep -q "maquita-bases-remoto.conf" "$PG_CONF/pg_hba.conf" \
    && [ "$(runuser -u postgres -- psql -X -At -c 'SHOW ssl' 2>/dev/null)" = "on" ]
}
estado_al_dia() {
  [ -f "$ESTADO" ] && python3 - "$ESTADO" "$MAIL_HOST" "$(hay_mariadb && mariadb_listo && echo 1)" "$(hay_pg && pg_listo && echo 1)" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
ok = d.get("host") == sys.argv[2] and d.get("mariadb", {}).get("activo") == (sys.argv[3] == "1") \
    and d.get("postgresql", {}).get("activo") == (sys.argv[4] == "1")
sys.exit(0 if ok else 1)
PY
}

falta=()
cmp -s "$APP_DIR/deploy/sitios/herramientas/bases-tls-renovar.sh" "$BIN" && [ -L "$HOOK" -o -f "$HOOK" ] || falta+=("certificado para las bases y su renovación")
if hay_mariadb && ! mariadb_listo; then falta+=("MariaDB con TLS en la red (se reinicia)"); fi
if hay_pg && ! pg_listo; then falta+=("PostgreSQL ${PG_VERSION} con TLS en la red y pg_hba (se reinicia)"); fi
[ "${#falta[@]}" -gt 0 ] || estado_al_dia || falta+=("estado del acceso remoto ($ESTADO)")

if [ "${#falta[@]}" -eq 0 ]; then echo "Sin cambios: el acceso remoto a bases con TLS ya está preparado."; exit 0; fi
echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')."
[ "$SIMULAR" = 1 ] && exit 0

install -d -m 700 "$RESPALDOS"
RESPALDO="$RESPALDOS/ajuste-72-$(date +%Y%m%d%H%M%S).tar.gz"
tar -czf "$RESPALDO" --ignore-failed-read -P $([ -d /etc/mysql ] && echo /etc/mysql) $([ -n "$PG_CONF" ] && echo "$PG_CONF") \
  $([ -f "$ESTADO" ] && echo "$ESTADO") 2>/dev/null || true

# --- Certificado y su renovación ---
install -m 755 "$APP_DIR/deploy/sitios/herramientas/bases-tls-renovar.sh" "$BIN"
install -d -m 755 "$(dirname "$HOOK")"
ln -sfn "$BIN" "$HOOK"
"$BIN" "$MAIL_HOST" >/dev/null

mariadb_ok=0; pg_ok=0
# --- MariaDB ---
if hay_mariadb; then
  if ! mariadb_listo; then
    cat > "$CNF" <<'EOF'
# Generado por el ajuste 72: acceso remoto a las bases de los sitios, solo con TLS. El cortafuegos del proyecto
# abre el puerto 3306 únicamente para las IP de cada usuario; las cuentas remotas llevan REQUIRE SSL.
[mariadbd]
bind-address = 0.0.0.0
ssl_cert = /etc/mysql/ssl-maquita/fullchain.pem
ssl_key = /etc/mysql/ssl-maquita/privkey.pem
tls_version = TLSv1.2,TLSv1.3
EOF
    chmod 644 "$CNF"
    if ! systemctl restart mariadb || ! mariadb_listo; then
      rm -f "$CNF"; systemctl restart mariadb || true
      echo "Aviso: MariaDB no arrancó con TLS en la red; se dejó como estaba (respaldo: $RESPALDO)." >&2
    fi
  fi
  mariadb_listo && mariadb_ok=1
fi

# --- PostgreSQL ---
if hay_pg; then
  if ! pg_listo; then
    install -d -m 755 "$PG_CONF/conf.d"
    cat > "$PG_CONF/conf.d/90-maquita-bases-remoto.conf" <<'EOF'
# Generado por el ajuste 72: acceso remoto a las bases de los sitios, solo con TLS (hostssl + scram-sha-256).
# El cortafuegos del proyecto abre el puerto 5432 únicamente para las IP de cada usuario.
listen_addresses = '*'
ssl = on
ssl_cert_file = '/etc/postgresql/ssl-maquita/fullchain.pem'
ssl_key_file = '/etc/postgresql/ssl-maquita/privkey.pem'
ssl_min_protocol_version = 'TLSv1.2'
password_encryption = 'scram-sha-256'
EOF
    [ -f "$HBA_SITIOS" ] || { install -m 640 -o postgres -g postgres /dev/null "$HBA_SITIOS"; echo "# Generado por maquita-sitios." > "$HBA_SITIOS"; }
    grep -q "maquita-bases-remoto.conf" "$PG_CONF/pg_hba.conf" || \
      printf '\n# Acceso remoto a las bases de los sitios (solo hostssl, lo genera maquita-sitios).\ninclude_if_exists %s\n' "$HBA_SITIOS" >> "$PG_CONF/pg_hba.conf"
    unidad="postgresql@${PG_VERSION}-main"
    if ! systemctl restart "$unidad" || ! pg_listo; then
      tar -xzf "$RESPALDO" -P "$PG_CONF" 2>/dev/null || true
      rm -f "$PG_CONF/conf.d/90-maquita-bases-remoto.conf"
      systemctl restart "$unidad" || true
      echo "Aviso: PostgreSQL no arrancó con TLS en la red; se dejó como estaba (respaldo: $RESPALDO)." >&2
    fi
  fi
  pg_listo && pg_ok=1
fi

install -d -m 700 /etc/maquita-sitios
python3 - "$ESTADO" "$MAIL_HOST" "$mariadb_ok" "$pg_ok" <<'PY'
import json, os, sys
ruta, host, m, p = sys.argv[1:5]
tmp = ruta + ".tmp"
with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644), "w") as f:
    json.dump({"host": host, "mariadb": {"activo": m == "1"}, "postgresql": {"activo": p == "1"}}, f)
os.replace(tmp, ruta)
PY
if [ "$mariadb_ok" = 0 ] && [ "$pg_ok" = 0 ]; then
  echo "Error: ni MariaDB ni PostgreSQL quedaron preparados para el acceso remoto con TLS." >&2
  exit 1
fi
echo "Listo: acceso remoto a bases con TLS preparado (MariaDB: $([ $mariadb_ok = 1 ] && echo sí || echo no), PostgreSQL: $([ $pg_ok = 1 ] && echo sí || echo no)); los puertos siguen cerrados hasta que se den IP a un usuario."
