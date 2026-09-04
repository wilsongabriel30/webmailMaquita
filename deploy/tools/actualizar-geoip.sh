#!/usr/bin/env bash
# Actualiza la base GeoIP LOCAL (DB-IP City Lite) que usa la deteccion de accesos
# sospechosos. Sin cuenta ni clave: el archivo es publico y se publica cada mes.
#
# Reemplaza el archivo solo si lo descargado es una base valida, para no dejar el
# servidor sin geolocalizacion por una descarga a medias.
#
# Uso: actualizar-geoip.sh [destino]   (por defecto /var/lib/GeoIP/dbip-city-lite.mmdb)
set -euo pipefail

DESTINO="${1:-/var/lib/GeoIP/dbip-city-lite.mmdb}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

descargar() {
  local mes="$1"
  curl -sfL --max-time 300 "https://download.db-ip.com/free/dbip-city-lite-${mes}.mmdb.gz" \
       -o "$TMP/base.mmdb.gz"
}

MES="$(date +%Y-%m)"
if ! descargar "$MES"; then
  MES_ANT="$(date -d '1 month ago' +%Y-%m)"
  echo "No hay base de $MES todavia; se intenta la de $MES_ANT"
  descargar "$MES_ANT" || { echo "No se pudo descargar la base GeoIP" >&2; exit 1; }
  MES="$MES_ANT"
fi

gunzip -f "$TMP/base.mmdb.gz"

# Comprobar que es una base legible antes de sustituir la que ya funciona
PY=/opt/maquita-webmail/backend/venv/bin/python3
"$PY" - "$TMP/base.mmdb" <<'PYEOF'
import sys
import maxminddb
r = maxminddb.open_database(sys.argv[1])
assert r.get("8.8.8.8"), "la base descargada no resuelve una IP conocida"
print("base valida:", r.metadata().database_type)
r.close()
PYEOF

mkdir -p "$(dirname "$DESTINO")"
[ -f "$DESTINO" ] && cp -f "$DESTINO" "$DESTINO.anterior"
install -m 644 "$TMP/base.mmdb" "$DESTINO"
echo "Base GeoIP actualizada a $MES en $DESTINO ($(du -h "$DESTINO" | cut -f1))"
echo "Recuerde reiniciar maquita-webmail para que tome la base nueva."
