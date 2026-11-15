#!/usr/bin/env bash
# Con ActiveSync instalado, nginx escucha en la IP del puente de Docker (vhost radicale-zpush). Tras
# reiniciar el servidor, nginx podía arrancar antes que Docker y fallar con «bind() ... failed (99)»,
# dejando caído todo lo web hasta levantarlo a mano (informe de Andes, 15/11/2026).
# Este ajuste hace que nginx arranque después de Docker y reintente si falla. Solo actúa donde
# existe ese vhost; no reinicia ni recarga nginx (el cambio vale desde el siguiente arranque).
set -euo pipefail
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
AQUI="$(cd "$(dirname "$0")" && pwd)"; RAIZ="$(cd "$AQUI/../.." && pwd)"
ORIGEN="$RAIZ/deploy/z-push/systemd/nginx-despues-de-docker.conf"
DESTINO=/etc/systemd/system/nginx.service.d/despues-de-docker.conf

[ -e /etc/nginx/sites-enabled/radicale-zpush ] || { echo "Sin cambios: este servidor no tiene el vhost radicale-zpush (ActiveSync)."; exit 0; }
[ -f "$ORIGEN" ] || { echo "Falta $ORIGEN en el repositorio." >&2; exit 1; }
if cmp -s "$ORIGEN" "$DESTINO" 2>/dev/null; then echo "Sin cambios: nginx ya arranca después de Docker."; exit 0; fi
if [ "$SIMULAR" = 1 ]; then echo "Pendiente: hacer que nginx arranque después de Docker ($DESTINO)."; exit 0; fi
install -d -m 755 "$(dirname "$DESTINO")"
[ -f "$DESTINO" ] && cp -p "$DESTINO" "$DESTINO.bak.$(date +%Y%m%d-%H%M%S)"
install -m 644 "$ORIGEN" "$DESTINO"
systemctl daemon-reload
echo "Hecho: nginx arranca después de Docker y reintenta si falla (vale desde el próximo arranque)."
