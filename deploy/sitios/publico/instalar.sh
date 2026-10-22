#!/usr/bin/env bash
# Despliegue desde git de los sitios PHP y DNS dinámico (v1.11): lo que el servidor necesita fuera del código.
#   - herramientas del despliegue: git, rsync y ssh-keygen (openssh-client), de los repositorios del sistema;
#   - carpetas de root de los secretos de los ganchos y de las fichas del DNS dinámico (0700);
#   - si está el portal de dominio (que atiende estas rutas): las rutas públicas /git-despliegue/ y /nic/update en
#     el server{} HTTPS del correo (snippets/maquita-apps/) y su límite de peticiones por IP (conf.d), con
#     respaldo y vuelta atrás si nginx las rechaza.
# Idempotente.
#
# Uso:  sudo bash deploy/sitios/publico/instalar.sh              instala o actualiza
#       sudo bash deploy/sitios/publico/instalar.sh --pendiente  solo dice qué falta (no toca nada)
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)"
SNIPPET=/etc/nginx/snippets/maquita-apps/sitios-publico.conf
ZONA=/etc/nginx/conf.d/maquita-sitios-publico.conf
RESPALDOS=/var/backups/maquita-sitios-publico
SECRETOS=(/etc/maquita-sitios/ganchos /etc/maquita-sitios/ddns)
PENDIENTE=0; [ "${1:-}" = "--pendiente" ] && PENDIENTE=1

[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)." >&2; exit 2; }
[ -x /usr/local/sbin/maquita-sitios ] || { echo "Sin cambios: este servidor no tiene los sitios web (maquita-sitios)."; exit 0; }

con_portal() { getent passwd maquita-dominio >/dev/null && [ -f /etc/systemd/system/maquita-panel-dominio.service ]; }
# Sitios de nginx que incluyen las rutas de las aplicaciones (el server{} HTTPS del correo).
vhosts_correo() { grep -lsE '^\s*include\s+\S*snippets/maquita-apps/\*\.conf;' /etc/nginx/sites-enabled/* 2>/dev/null || true; }

# --- Qué falta ---
falta=()
paquetes=()
command -v git >/dev/null || paquetes+=(git)
command -v rsync >/dev/null || paquetes+=(rsync)
command -v ssh-keygen >/dev/null || paquetes+=(openssh-client)
[ "${#paquetes[@]}" -eq 0 ] || falta+=("paquetes ${paquetes[*]}")
for d in "${SECRETOS[@]}"; do
  [ "$(stat -c '%U %a' "$d" 2>/dev/null)" = "root 700" ] || falta+=("carpeta $d")
done
if con_portal; then
  cmp -s "${SELF}/sitios-publico.conf" "$SNIPPET" || falta+=("rutas públicas en nginx ($SNIPPET)")
  cmp -s "${SELF}/sitios-publico-zona.conf" "$ZONA" || falta+=("límite de peticiones ($ZONA)")
fi

if [ "${#falta[@]}" -eq 0 ]; then
  echo "Sin cambios: el despliegue desde git y el DNS dinámico ya tienen lo que necesitan."
  con_portal || echo "Nota: sin el portal de dominio no hay gancho de git ni /nic/update (el despliegue desde el panel sí funciona)."
  exit 0
fi
echo "Pendiente: $(IFS=,; echo "${falta[*]}" | sed 's/,/, /g')"
[ "$PENDIENTE" = 1 ] && exit 0

# --- Herramientas y carpetas ---
if [ "${#paquetes[@]}" -gt 0 ]; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${paquetes[@]}" >/dev/null
fi
install -d -m 700 /etc/maquita-sitios
for d in "${SECRETOS[@]}"; do install -d -o root -g root -m 700 "$d"; done

# --- Rutas públicas (solo con el portal, que es quien las atiende) ---
if con_portal && { ! cmp -s "${SELF}/sitios-publico.conf" "$SNIPPET" || ! cmp -s "${SELF}/sitios-publico-zona.conf" "$ZONA"; }; then
  install -d -m 700 "$RESPALDOS"
  sello="$(date +%Y%m%d%H%M%S)"
  for f in "$SNIPPET" "$ZONA"; do [ -f "$f" ] && cp -p "$f" "${RESPALDOS}/$(basename "$f").${sello}"; done
  install -d -m 755 "$(dirname "$SNIPPET")"
  install -m 644 "${SELF}/sitios-publico.conf" "$SNIPPET"
  install -m 644 "${SELF}/sitios-publico-zona.conf" "$ZONA"
  if ! nginx -t >/dev/null 2>&1; then
    for f in "$SNIPPET" "$ZONA"; do
      if [ -f "${RESPALDOS}/$(basename "$f").${sello}" ]; then cp -p "${RESPALDOS}/$(basename "$f").${sello}" "$f"; else rm -f "$f"; fi
    done
    echo "Error: nginx rechazó las rutas públicas de los sitios; quedó como estaba (nginx -t para ver el motivo)." >&2
    exit 1
  fi
  systemctl reload nginx
  if [ -z "$(vhosts_correo)" ]; then
    echo "Aviso: ningún sitio de nginx incluye «include /etc/nginx/snippets/maquita-apps/*.conf;»: añádalo en el server{} HTTPS del correo (como en deploy/webmail/nginx/webmail.conf) para publicar /git-despliegue/ y /nic/update." >&2
  fi
fi
echo "Listo: herramientas del despliegue desde git y carpetas de secretos$(con_portal && echo ', y rutas públicas /git-despliegue/ y /nic/update en nginx')."
