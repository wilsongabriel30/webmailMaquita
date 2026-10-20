#!/usr/bin/env bash
# Webmail (2026-10-20): parada ordenada aprendida en producción. Con la unidad original, un reinicio
# esperaba hasta 90 s a conexiones colgadas y los workers que morían por un fallo nativo no dejaban
# rastro. Se instala como drop-in (no se toca la unidad, que cada servidor puede haber ajustado:
# p. ej. más workers). No reinicia el servicio: rige en el próximo reinicio o actualización.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
UNIDAD=/etc/systemd/system/maquita-webmail.service
DIR_DROP=/etc/systemd/system/maquita-webmail.service.d
DESTINO="$DIR_DROP/50-parada-ordenada.conf"
ORIGEN="$APP_DIR/deploy/webmail/systemd/maquita-webmail.service.d/50-parada-ordenada.conf"
if [ ! -f "$UNIDAD" ]; then echo "Sin cambios: este servidor no tiene el servicio del webmail."; exit 0; fi
if cmp -s "$ORIGEN" "$DESTINO"; then echo "Sin cambios: la parada ordenada ya está."; exit 0; fi
if grep -qs '^KillMode=mixed' "$UNIDAD" && grep -qs 'PYTHONFAULTHANDLER=1' "$UNIDAD" && [ ! -f "$DESTINO" ]; then
  echo "Sin cambios: la unidad del webmail ya trae la parada ordenada."; exit 0
fi
echo "Pendiente: parada ordenada del webmail ($DESTINO)"
[ "${1:-}" = "--simular" ] && exit 0
install -d -m 755 "$DIR_DROP"
[ -f "$DESTINO" ] && cp "$DESTINO" "$DESTINO.bak.$(date +%Y%m%d%H%M%S)"
install -m 644 "$ORIGEN" "$DESTINO"
if ! systemd-analyze verify "$UNIDAD" >/dev/null 2>&1 && systemd-analyze verify "$UNIDAD" 2>&1 | grep -q "50-parada-ordenada"; then
  ultimo="$(ls -t "$DESTINO".bak.* 2>/dev/null | head -1)"
  if [ -n "$ultimo" ]; then cp "$ultimo" "$DESTINO"; else rm -f "$DESTINO"; fi
  systemctl daemon-reload
  echo "systemd rechazó el drop-in: se dejó el webmail como estaba." >&2; exit 1
fi
systemctl daemon-reload
echo "Listo: parada ordenada instalada (rige en el próximo reinicio del webmail)."
