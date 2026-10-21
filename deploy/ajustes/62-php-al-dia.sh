#!/usr/bin/env bash
# PHP del servidor al día (2026-10-21, «PHP2Shell»: CVE-2026-109618 y CVE-2026-109619, ejecución remota
# de código sin autenticación en todo PHP que atiende peticiones web). Corregido en 8.5.12, 8.4.27, 8.3.36
# y 8.2.35. Los sitios web usan los paquetes php* del sistema (Debian o packages.sury.org), que el
# repositorio de sury no siempre entra en las actualizaciones automáticas: aquí se instalan las versiones
# nuevas de los paquetes php* ya instalados (no se instala ninguno nuevo) y se comprueba PHP-FPM.
# Z-Push corre en su propio contenedor: lo pone al día el ajuste 61 al reconstruir la imagen.
set -euo pipefail
command -v apt-get >/dev/null || { echo "Sin cambios: el sistema no usa apt."; exit 0; }
dpkg -l 2>/dev/null | grep -qE '^ii\s+php[0-9.]*-(cli|fpm|common) ' || { echo "Sin cambios: PHP no está instalado."; exit 0; }

apt-get update -qq >/dev/null 2>&1 || echo "Aviso: apt-get update no terminó bien; se usa la lista que había."
mapfile -t pendientes < <(apt list --upgradable 2>/dev/null | grep -E '^php' | cut -d/ -f1)
if [ "${#pendientes[@]}" -eq 0 ]; then
  echo "Sin cambios: PHP ya está en la última versión de sus repositorios ($(php -r 'echo PHP_VERSION;' 2>/dev/null || echo '?'))."; exit 0
fi
echo "Pendiente: actualizar ${#pendientes[@]} paquetes de PHP (${pendientes[*]:0:4}…)."
[ "${1:-}" = "--simular" ] && exit 0

DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --only-upgrade -o Dpkg::Options::=--force-confold "${pendientes[@]}" >/dev/null
for unidad in $(systemctl list-units --type=service --no-legend --plain 'php*-fpm.service' | awk '{print $1}'); do
  systemctl is-active -q "$unidad" || { echo "Error: $unidad no quedó activo tras actualizar." >&2; exit 1; }
done
echo "Listo: PHP actualizado ($(for b in /usr/sbin/php-fpm[0-9]*; do [ -x "$b" ] && "$b" -v | head -1 | cut -d' ' -f2; done | tr '\n' ' '))."
