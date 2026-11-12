#!/usr/bin/env bash
# Dovecot respeta la lista de cuentas «solo webmail» (12/11/2026).
#
# En las cuentas de la tabla auth_cuentas_solo_web la contraseña principal no sirve por IMAP, POP3
# ni SMTP desde fuera del propio servidor (docs: panel de administración → Cuentas solo webmail).
# Las instalaciones anteriores tienen la consulta del passdb sin esa condición: este ajuste la añade.
# Respalda el archivo, valida con «doveconf» y vuelve atrás si falla. Recarga sin cortar sesiones.
set -euo pipefail
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
BASE_DATOS="${DB_NAME:-maildb}"

command -v doveconf >/dev/null 2>&1 || { echo "Sin cambios: este servidor no tiene Dovecot."; exit 0; }
CONF="$(grep -rl "contrasenas_aplicacion_obligatorias" /etc/dovecot --include='*.conf' --include='*.ext' 2>/dev/null | head -1 || true)"
[ -n "$CONF" ] || { echo "Sin cambios: no se encontró la consulta de contraseñas de Dovecot."; exit 0; }
if grep -q "auth_cuentas_solo_web" "$CONF"; then
    echo "Sin cambios: Dovecot ya respeta las cuentas solo webmail."; exit 0
fi
VIEJA="OR NOT EXISTS (SELECT 1 FROM auth_politica WHERE clave = 'contrasenas_aplicacion_obligatorias' AND valor = 'true'))"
grep -qF "$VIEJA" "$CONF" || { echo "No se reconoce la consulta en $CONF: ajústela a mano (ver deploy/webmail/configs/dovecot.conf)." >&2; exit 1; }
# Sin la tabla, la consulta fallaría y NADIE podría entrar: se comprueba antes de tocar nada.
if [ "$(sudo -u postgres psql -d "$BASE_DATOS" -Atc "SELECT to_regclass('auth_cuentas_solo_web') IS NOT NULL" 2>/dev/null)" != "t" ]; then
    echo "Pendiente: falta la tabla auth_cuentas_solo_web (aplique migrations/2026-11-12-cuentas-solo-webmail.sql)."; exit 0
fi
if [ "$SIMULAR" = 1 ]; then
    echo "Pendiente: añadir las cuentas solo webmail a la consulta de $CONF."; exit 0
fi

RESPALDO="$CONF.antes-ajuste81.$(date +%Y%m%d%H%M%S)"
cp -p "$CONF" "$RESPALDO"
NUEVA="OR (NOT EXISTS (SELECT 1 FROM auth_politica WHERE clave = 'contrasenas_aplicacion_obligatorias' AND valor = 'true') AND NOT EXISTS (SELECT 1 FROM auth_cuentas_solo_web WHERE username = '%{user}')))"
python3 - "$CONF" "$VIEJA" "$NUEVA" <<'PY'
import sys
ruta, vieja, nueva = sys.argv[1:4]
texto = open(ruta, encoding="utf-8").read()
assert texto.count(vieja) == 1
open(ruta, "w", encoding="utf-8").write(texto.replace(vieja, nueva))
PY
if ! doveconf -n >/dev/null 2>&1; then
    cp -p "$RESPALDO" "$CONF"
    echo "La configuración no validó: se restauró $CONF." >&2
    exit 1
fi
doveadm reload
echo "Hecho: Dovecot respeta las cuentas solo webmail (respaldo en $RESPALDO)."
