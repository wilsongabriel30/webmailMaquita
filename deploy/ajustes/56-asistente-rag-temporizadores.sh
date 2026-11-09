#!/usr/bin/env bash
# Asistente «Pregúntale a tu correo» (RAG, 08/11/2026): las dos pasadas que indexan el correo
# corrían solo en el servidor de producción. Este ajuste instala sus unidades de systemd desde
# deploy/systemd/ y activa los temporizadores:
#   - rag-indexacion.timer  (21:00, todo el buzón, incremental)
#   - rag-recientes.timer   (cada 15 min de 06:45 a 20:45, solo lo nuevo de Bandeja de entrada y Enviados)
# Sin dominios habilitados en rag_domains las pasadas terminan al instante («sin dominios RAG
# habilitados»), así que activarlas no cuesta nada. Idempotente: respalda lo que reemplaza.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
[ -x "$APP_DIR/backend/venv/bin/python" ] || { echo "Sin cambios: este servidor no tiene el backend del webmail."; exit 0; }
UNIDADES=(rag-indexacion.service rag-indexacion.timer rag-recientes.service rag-recientes.timer)
pendientes=()
for u in "${UNIDADES[@]}"; do
  origen="$APP_DIR/deploy/systemd/$u"; destino="/etc/systemd/system/$u"
  [ -f "$origen" ] || { echo "Falta $origen en el repositorio." >&2; exit 1; }
  cmp -s "$origen" "$destino" 2>/dev/null || pendientes+=("$u")
done
for t in rag-indexacion.timer rag-recientes.timer; do
  systemctl is-enabled --quiet "$t" 2>/dev/null || pendientes+=("activar $t")
done
if [ "${#pendientes[@]}" -eq 0 ]; then echo "Sin cambios: unidades del asistente instaladas y temporizadores activos."; exit 0; fi
if [ "$SIMULAR" = 1 ]; then echo "Pendiente: ${pendientes[*]}"; exit 0; fi
fecha="$(date +%Y%m%d-%H%M%S)"
for u in "${UNIDADES[@]}"; do
  origen="$APP_DIR/deploy/systemd/$u"; destino="/etc/systemd/system/$u"
  if ! cmp -s "$origen" "$destino" 2>/dev/null; then
    [ -f "$destino" ] && cp -p "$destino" "$destino.bak.$fecha"
    install -m 0644 "$origen" "$destino"
  fi
done
for l in /var/log/rag-indexacion.log /var/log/rag-recientes.log; do touch "$l"; chown www-data "$l"; done
systemctl daemon-reload
systemctl enable --now rag-indexacion.timer rag-recientes.timer >/dev/null
echo "Listo: ${pendientes[*]}"
