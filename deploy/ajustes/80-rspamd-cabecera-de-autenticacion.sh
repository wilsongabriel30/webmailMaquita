#!/usr/bin/env bash
# rspamd añade la cabecera «Authentication-Results» a cada correo que entra (11/11/2026).
#
# La recuperación de correo entre servidores (docs/RECUPERACION-ENTRE-SERVIDORES.md) solo retira un
# correo que ESTE servidor autenticó al recibirlo (DKIM/DMARC del dominio remitente), y lo sabe por su
# propia cabecera Authentication-Results. Las instalaciones hechas con el instalador no la añadían
# (no existía local.d/milter_headers.conf): sin ella, toda petición de otro servidor se rechaza.
# Este ajuste activa la rutina «authentication-results» de milter_headers, respetando lo que ya haya
# en «use». Respalda el archivo, valida con «rspamadm configtest» y vuelve atrás si falla.
set -euo pipefail
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
CONF=/etc/rspamd/local.d/milter_headers.conf

command -v rspamadm >/dev/null 2>&1 || { echo "Sin cambios: este servidor no tiene rspamd."; exit 0; }
if [ -f "$CONF" ] && grep -Eq '^[[:space:]]*use[[:space:]]*=.*authentication-results' "$CONF"; then
    echo "Sin cambios: rspamd ya añade Authentication-Results."; exit 0
fi
if [ "$SIMULAR" = 1 ]; then
    echo "Pendiente: activar la cabecera Authentication-Results en $CONF."; exit 0
fi

RESPALDO=""
if [ -f "$CONF" ]; then
    RESPALDO="$CONF.antes-ajuste80.$(date +%Y%m%d%H%M%S)"
    cp -p "$CONF" "$RESPALDO"
fi
if [ -f "$CONF" ] && grep -Eq '^[[:space:]]*use[[:space:]]*=[[:space:]]*\[.*\][[:space:]]*;' "$CONF"; then
    # Ya hay una lista «use» en una línea: se le añade la rutina sin tocar las demás.
    sed -i -E '0,/^([[:space:]]*use[[:space:]]*=[[:space:]]*\[)(.*)\][[:space:]]*;/s//\1\2, "authentication-results"];/' "$CONF"
    sed -i -E 's/\[[[:space:]]*,[[:space:]]*"authentication-results"\]/["authentication-results"]/' "$CONF"
elif [ -f "$CONF" ] && grep -Eq '^[[:space:]]*use[[:space:]]*=' "$CONF"; then
    echo "No se reconoce el formato de «use» en $CONF: añada \"authentication-results\" a mano." >&2
    exit 1
else
    printf '%s\n' '# Añadido por deploy/ajustes/80-rspamd-cabecera-de-autenticacion.sh' \
        'use = ["authentication-results"];' >> "$CONF"
fi
chmod 644 "$CONF"

if ! rspamadm configtest >/dev/null 2>&1; then
    if [ -n "$RESPALDO" ]; then cp -p "$RESPALDO" "$CONF"; else rm -f "$CONF"; fi
    echo "rspamd rechazó la configuración: se dejó como estaba." >&2
    exit 1
fi
systemctl reload rspamd 2>/dev/null || systemctl restart rspamd
echo "Listo: rspamd añade Authentication-Results a los correos que entran."
