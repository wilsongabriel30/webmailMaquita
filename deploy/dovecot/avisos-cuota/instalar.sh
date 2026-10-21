#!/usr/bin/env bash
# Instala los avisos de cuota (no recarga Dovecot):
#   /usr/local/bin/maquita-aviso-cuota            ← aviso-cuota.sh
#   /etc/dovecot/maquita.d/avisos-cuota.conf     ← avisos-cuota.conf.plantilla con el nombre de la cuota
#   «!include_try /etc/dovecot/maquita.d/*.conf» al final de dovecot.conf, si aún no está
# Lo usan deploy/webmail/instalar.sh (instalación nueva) y deploy/ajustes/56-* (servidores ya instalados).
# Uso: instalar.sh            instala
#      instalar.sh --mostrar  imprime la configuración que instalaría (para comparar)
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
CONF=/etc/dovecot/dovecot.conf
INCLUDE='!include_try /etc/dovecot/maquita.d/*.conf'

# Nombre de la primera cuota definida: «quota "User quota" {» o «quota count {».
cuota="$(doveconf -n 2>/dev/null | sed -nE 's/^quota "?([^"{]*[^"{ ])"? \{$/\1/p' | head -1)"
[ -n "$cuota" ] || { echo "Dovecot no tiene ninguna cuota definida: no hay a qué poner avisos." >&2; exit 1; }
generada="$(sed "s|@CUOTA@|$cuota|" "$D/avisos-cuota.conf.plantilla")"
[ "${1:-}" = "--mostrar" ] && { printf '%s\n' "$generada"; exit 0; }

install -m 755 "$D/aviso-cuota.sh" /usr/local/bin/maquita-aviso-cuota
install -d -o vmail -g vmail -m 750 /var/lib/maquita-aviso-cuota
install -d -o root -g dovecot -m 755 /etc/dovecot/maquita.d
printf '%s\n' "$generada" > /etc/dovecot/maquita.d/avisos-cuota.conf
chown root:dovecot /etc/dovecot/maquita.d/avisos-cuota.conf; chmod 644 /etc/dovecot/maquita.d/avisos-cuota.conf
grep -qxF "$INCLUDE" "$CONF" || printf '\n# ---- Piezas opcionales del repositorio (deploy/dovecot) ----\n%s\n' "$INCLUDE" >> "$CONF"
