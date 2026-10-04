#!/bin/bash
# geoip-country.sh enable|disable <cc> | list — abre o cierra un país para el webmail.
# Lo usan el panel de administración (a través de maquita-sudo) y el administrador por consola.
#
# El cambio se guarda en la base y se aplica al cortafuegos. Si aplicar falla, el cambio de la
# base SE DESHACE: el panel nunca muestra un país abierto que el cortafuegos sigue cerrando.
# Sin credenciales: la base sale de DATABASE_URL.
set -euo pipefail
ACTION="${1:-}"; CC="$(printf '%s' "${2:-}" | tr 'A-Z' 'a-z')"
ENV_BACKEND=/opt/maquita-webmail/backend/.env
ENV_ORG=/etc/maquita-mail/organizacion.env
REBUILD="$(dirname "$(readlink -f "$0")")/geoip-rebuild.sh"
valor() { grep -E "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'" || true; }
DSN="$(valor "$ENV_BACKEND" DATABASE_URL | sed -E 's#^postgresql\+[a-z0-9]+://#postgresql://#')"
[ -n "$DSN" ] || { echo "geoip-country.sh: sin DATABASE_URL en $ENV_BACKEND" >&2; exit 1; }
BASE="$(valor "$ENV_ORG" ORG_PAIS_BASE | tr 'A-Z' 'a-z')"; [[ "$BASE" =~ ^[a-z]{2}$ ]] || BASE=ec
QUIEN="$(printf '%s' "${SUDO_USER:-consola}" | tr -cd 'A-Za-z0-9._@-' | cut -c1-60)"
sql() { psql "$DSN" -X -tA -v ON_ERROR_STOP=1 "$@"; }

case "$ACTION" in
  list)
    sql -c "SELECT code||' '||name||' '||enabled FROM geo_webmail_countries ORDER BY code"
    ;;
  enable|disable)
    [[ "$CC" =~ ^[a-z]{2}$ ]] || { echo "código de país inválido (ISO-2, p. ej. es)" >&2; exit 1; }
    [ "$(id -u)" -eq 0 ] || { echo "geoip-country.sh: hay que ejecutarlo como root" >&2; exit 2; }
    if [ "$ACTION" = disable ] && [ "$CC" = "$BASE" ]; then
      echo "el país base ($BASE) no se puede cerrar" >&2; exit 1
    fi
    EN=$([ "$ACTION" = enable ] && echo true || echo false)
    ANTES="$(sql -v c="$CC" <<<"SELECT enabled FROM geo_webmail_countries WHERE code = :'c'")"
    sql -v c="$CC" -v e="$EN" -v q="$QUIEN" >/dev/null <<<"INSERT INTO geo_webmail_countries (code, name, enabled, updated_by)
        VALUES (:'c', upper(:'c'), :'e'::boolean, :'q')
        ON CONFLICT (code) DO UPDATE SET enabled = :'e'::boolean, updated_at = now(), updated_by = :'q'"
    if ! "$REBUILD"; then
      # No se pudo aplicar: la base vuelve a como estaba.
      if [ -z "$ANTES" ]; then sql -v c="$CC" >/dev/null <<<"DELETE FROM geo_webmail_countries WHERE code = :'c'"
      else sql -v c="$CC" -v e="$ANTES" >/dev/null <<<"UPDATE geo_webmail_countries SET enabled = :'e'::boolean WHERE code = :'c'"; fi
      echo "no se pudo aplicar el cambio al cortafuegos; el país $CC queda como estaba" >&2
      exit 1
    fi
    echo "país $CC -> $ACTION OK"
    ;;
  *) echo "uso: geoip-country.sh enable|disable <cc> | list" >&2; exit 1 ;;
esac
