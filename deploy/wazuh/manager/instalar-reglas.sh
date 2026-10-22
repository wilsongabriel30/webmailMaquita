#!/usr/bin/env bash
# Decodificadores y reglas de Maquita en un MANAGER de Wazuh (docs/WAZUH.md). Se ejecuta en el
# manager, no en el servidor de correo. Idempotente; respalda lo que reemplaza y vuelve atrás si
# Wazuh no acepta la configuración nueva.
#
# Uso (en el manager):  sudo bash instalar-reglas.sh [--simular]
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)"
OSSEC="${WAZUH_RAIZ:-/var/ossec}"
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)." >&2; exit 2; }
[ -x "$OSSEC/bin/wazuh-analysisd" ] || { echo "Aquí no hay un manager de Wazuh ($OSSEC/bin/wazuh-analysisd)." >&2; exit 1; }

FECHA=$(date +%Y%m%d%H%M%S)
pendientes=()
for par in "decoders/maquita_decoders.xml:etc/decoders/maquita_decoders.xml" "rules/maquita_rules.xml:etc/rules/maquita_rules.xml"; do
    src="$SELF/${par%%:*}"; dst="$OSSEC/${par#*:}"
    cmp -s "$src" "$dst" 2>/dev/null || pendientes+=("$src:$dst")
done
if [ "${#pendientes[@]}" -eq 0 ]; then echo "Sin cambios: el manager ya tiene las reglas de Maquita."; exit 0; fi
echo "Pendiente: copiar ${#pendientes[@]} archivo(s) de reglas/decodificadores de Maquita."
[ "$SIMULAR" = 1 ] && exit 0

for p in "${pendientes[@]}"; do
    src="${p%%:*}"; dst="${p#*:}"
    if [ -f "$dst" ]; then cp -p "$dst" "$dst.anterior-$FECHA"; fi
    install -m 660 -o root -g wazuh "$src" "$dst"
done
if ! "$OSSEC/bin/wazuh-analysisd" -t >/dev/null 2>&1; then
    echo "Wazuh no acepta la configuración nueva; se vuelve a la anterior:" >&2
    "$OSSEC/bin/wazuh-analysisd" -t 2>&1 | tail -5 >&2 || true
    for p in "${pendientes[@]}"; do
        dst="${p#*:}"
        if [ -f "$dst.anterior-$FECHA" ]; then mv -f "$dst.anterior-$FECHA" "$dst"; else rm -f "$dst"; fi
    done
    exit 1
fi
systemctl restart wazuh-manager
echo "Listo: reglas de Maquita instaladas (100800-100899) y wazuh-manager reiniciado."
