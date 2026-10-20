#!/usr/bin/env bash
# Sella la plantilla: borra todo lo que identifica a ESTA máquina para que cada clon nazca distinto,
# sin rastro de quién la preparó, y la apaga. Después, en Proxmox: «Convertir en plantilla».
#
#   bash sellar.sh               (pide confirmación)
#   SIN_APAGAR=1 bash sellar.sh  (pruebas)
#
# Se niega si el correo ya está instalado: una VM configurada NO se clona (repetiría claves DKIM,
# secretos de sesión y contraseñas de las bases en todas las organizaciones).
set -euo pipefail
[ "$EUID" -eq 0 ] || { echo "Ejecutar como root."; exit 1; }
if [ -f /opt/maquita-webmail/backend/.env ] || systemctl list-unit-files maquita-webmail.service 2>/dev/null | grep -q maquita-webmail; then
    echo "Esta VM ya tiene el correo instalado: no se puede sellar como plantilla. Use una VM recién preparada."; exit 1
fi
[ -f /etc/maquita-plantilla/sin-configurar ] || { echo "Falta preparar.sh (no existe /etc/maquita-plantilla/sin-configurar)."; exit 1; }
if [ -t 0 ] && [ -z "${SIN_APAGAR:-}" ]; then
    read -r -p "Se borrarán claves SSH, accesos, historial y registros, y se apagará la VM. ¿Continuar? (s/n): " r
    [ "$r" = "s" ] || exit 0
fi
cd /opt/maquita-webmail && git status --porcelain --untracked-files=no | grep -q . && { echo "Hay cambios locales en el código."; exit 1; }
# Identidad de la máquina: claves SSH (se regeneran en el primer arranque), machine-id y semilla aleatoria.
rm -f /etc/ssh/ssh_host_*
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id /var/lib/systemd/random-seed
# Accesos de quien la preparó: claves autorizadas, historial y contraseña de root (la pone el asistente
# o cloud-init de Proxmox).
rm -f /root/.ssh/authorized_keys /root/.ssh/known_hosts* /root/.bash_history /root/.lesshst /root/.wget-hsts
find /home -maxdepth 3 \( -name authorized_keys -o -name .bash_history \) -delete 2>/dev/null || true
passwd -l root >/dev/null
# cloud-init vuelve a correr en cada clon (red, usuario y claves que ponga Proxmox).
command -v cloud-init >/dev/null && cloud-init clean --logs --seed >/dev/null 2>&1 || true
# Registros y temporales.
journalctl --rotate >/dev/null 2>&1 || true; journalctl --vacuum-time=1s >/dev/null 2>&1 || true
find /var/log -type f \( -name "*.gz" -o -name "*.[0-9]" -o -name "*.old" \) -delete
find /var/log -type f -exec truncate -s 0 {} +
rm -rf /tmp/* /var/tmp/* /root/.cache 2>/dev/null || true
apt-get clean
touch /etc/maquita-plantilla/sin-configurar
systemctl enable maquita-primer-arranque.service >/dev/null
sync
echo "Plantilla sellada."
[ -n "${SIN_APAGAR:-}" ] || poweroff
