#!/usr/bin/env bash
# Buzón virtual «Virtual.Todo» para buscar en todas las carpetas (15/11/2026, informe de Andes).
#
# El webmail busca en «Todas las carpetas» con una sola búsqueda IMAP sobre un buzón virtual de
# Dovecot que reúne todas las carpetas de la persona. Las instalaciones hechas antes de este ajuste
# no lo tienen: el webmail lo detecta y solo ofrece «Esta carpeta». Este ajuste lo crea:
#   - /etc/dovecot/virtual/Todo/dovecot-virtual   qué carpetas reúne (todas menos el propio virtual)
#   - /etc/dovecot/virtual/dovecot-acl-list       vacío (ver el ajuste 40)
#   - /etc/dovecot/maquita.d/62-buzon-virtual.conf   el espacio de nombres (dovecot-config/96-virtual.conf)
# No toca ningún correo: el buzón virtual es una vista; por cuenta solo guarda un índice propio.
# Respalda dovecot.conf si tiene que añadirle la línea de módulos, valida con «doveconf», recarga sin
# cortar sesiones y prueba el buzón con una cuenta real; si algo falla, deja el servidor como estaba.
# El webmail tarda hasta 5 minutos en enterarse (recuerda la respuesta anterior ese tiempo).
set -euo pipefail
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
DIR="$(cd "$(dirname "$0")" && pwd)"
ORIGEN="$DIR/../../dovecot-config/96-virtual.conf"
DOVECOT_CONF="${DOVECOT_CONF:-/etc/dovecot/dovecot.conf}"
MODULOS=/etc/dovecot/maquita.d
INCLUDE='!include_try /etc/dovecot/maquita.d/*.conf'
CONF="$MODULOS/62-buzon-virtual.conf"
VIRTUAL="${DOVECOT_VIRTUAL:-/etc/dovecot/virtual}"

command -v doveconf >/dev/null 2>&1 && [ -f "$DOVECOT_CONF" ] || { echo "Sin cambios: este servidor no tiene Dovecot."; exit 0; }
VERSION="$(doveconf --version 2>/dev/null || dovecot --version 2>/dev/null || true)"
case "$VERSION" in
  2.4*) ;;
  *) echo "Sin cambios: este ajuste es para Dovecot 2.4 (aquí: ${VERSION:-desconocida}). Instrucciones a mano: UPGRADING.md («buscar en todas las carpetas»)."; exit 0 ;;
esac

hay_espacio() { doveconf -n 2>/dev/null | grep -Eq '^[[:space:]]*prefix = Virtual\.$'; }

pendiente=()
ESPACIO=1; hay_espacio || { ESPACIO=0; pendiente+=("espacio de nombres «Virtual.» en $CONF"); }
[ -f "$VIRTUAL/Todo/dovecot-virtual" ] || pendiente+=("definición del buzón en $VIRTUAL/Todo/dovecot-virtual")
[ -e "$VIRTUAL/dovecot-acl-list" ] || pendiente+=("lista de permisos vacía en $VIRTUAL/dovecot-acl-list")
if [ "$ESPACIO" = 0 ] && ! grep -qxF "$INCLUDE" "$DOVECOT_CONF"; then pendiente+=("incluir $MODULOS en dovecot.conf"); fi

if [ ${#pendiente[@]} -eq 0 ]; then echo "Sin cambios: el buzón virtual ya existe."; exit 0; fi
printf 'Pendiente: %s\n' "${pendiente[@]}"
[ "$SIMULAR" = 1 ] && exit 0

[ -f "$ORIGEN" ] || { echo "Falta $ORIGEN en la copia del programa." >&2; exit 1; }
DIR_MODULOS_DOVECOT="$(doveconf -h mail_plugin_dir 2>/dev/null || echo /usr/lib/dovecot/modules)"
ls "$DIR_MODULOS_DOVECOT"/lib*virtual_plugin.so >/dev/null 2>&1 || {
  echo "A este Dovecot le falta el módulo «virtual» ($DIR_MODULOS_DOVECOT); en Debian viene en dovecot-core." >&2; exit 1; }
GRUPO=root; getent group vmail >/dev/null 2>&1 && GRUPO=vmail

sello="$(date +%Y%m%d%H%M%S)"
creados=()   # lo que este ajuste crea, para deshacerlo si algo falla
RESPALDO=""        # copia de dovecot.conf, si hubo que tocarlo
RESPALDO_CONF=""   # copia del módulo, si ya existía
volver_atras() {
  local i
  for ((i = ${#creados[@]} - 1; i >= 0; i--)); do
    if [ -d "${creados[$i]}" ]; then rmdir "${creados[$i]}" 2>/dev/null || true; else rm -f "${creados[$i]}"; fi
  done
  [ -z "$RESPALDO" ] || cp -p "$RESPALDO" "$DOVECOT_CONF"
  [ -z "$RESPALDO_CONF" ] || cp -p "$RESPALDO_CONF" "$CONF"
  if systemctl is-active --quiet dovecot 2>/dev/null; then doveadm reload || true; fi
}

[ -d "$VIRTUAL" ] || { install -d -o root -g "$GRUPO" -m 755 "$VIRTUAL"; creados+=("$VIRTUAL"); }
[ -d "$VIRTUAL/Todo" ] || { install -d -o root -g "$GRUPO" -m 755 "$VIRTUAL/Todo"; creados+=("$VIRTUAL/Todo"); }
if [ ! -f "$VIRTUAL/Todo/dovecot-virtual" ]; then
  # Todas las carpetas de la persona menos las del propio espacio virtual; «all» = todos los mensajes.
  printf '*\n-Virtual.*\n  all\n' >"$VIRTUAL/Todo/dovecot-virtual"
  chown root:"$GRUPO" "$VIRTUAL/Todo/dovecot-virtual"; chmod 644 "$VIRTUAL/Todo/dovecot-virtual"
  creados+=("$VIRTUAL/Todo/dovecot-virtual")
fi
if [ ! -e "$VIRTUAL/dovecot-acl-list" ]; then
  install -o root -g "$GRUPO" -m 644 /dev/null "$VIRTUAL/dovecot-acl-list"; creados+=("$VIRTUAL/dovecot-acl-list")
fi

if [ "$ESPACIO" = 0 ]; then
  [ -d "$MODULOS" ] || { install -d -m 755 "$MODULOS"; creados+=("$MODULOS"); }
  if [ -f "$CONF" ]; then RESPALDO_CONF="$CONF.antes-ajuste84.$sello"; cp -p "$CONF" "$RESPALDO_CONF"; else creados+=("$CONF"); fi
  # Mismo archivo que el servidor de referencia; solo cambia la ruta si se pidió otra (pruebas).
  sed "s#^\([[:space:]]*mail_path = \)/etc/dovecot/virtual\$#\1$VIRTUAL#" "$ORIGEN" >"$CONF"
  chmod 644 "$CONF"
  if ! grep -qxF "$INCLUDE" "$DOVECOT_CONF"; then
    RESPALDO="$DOVECOT_CONF.antes-ajuste84.$sello"
    cp -p "$DOVECOT_CONF" "$RESPALDO"
    printf '\n# ---- Módulos opcionales (búsqueda, cuotas…): uno por archivo, ver deploy/dovecot/ ----\n%s\n' "$INCLUDE" >>"$DOVECOT_CONF"
  fi
  if ! salida="$(doveconf -n 2>&1 >/dev/null)" || ! hay_espacio; then
    volver_atras
    echo "Dovecot no aceptó la configuración del buzón virtual; se dejó como estaba: ${salida:0:300}" >&2
    exit 1
  fi
fi

if systemctl is-active --quiet dovecot 2>/dev/null; then doveadm reload; fi

# Prueba con una cuenta real: abrir el buzón virtual y contar. Solo lee (y crea el índice virtual de esa cuenta).
CUENTA="$(doveadm user '*' 2>/dev/null | head -1 || true)"
if [ -n "$CUENTA" ]; then
  rc=0
  salida="$(timeout 120 doveadm mailbox status -u "$CUENTA" messages Virtual.Todo 2>&1)" || rc=$?
  if [ "$rc" = 124 ]; then
    echo "Aviso: contar «Virtual.Todo» de $CUENTA pasó de 2 minutos (buzón grande); el ajuste queda aplicado."
  elif [ "$rc" != 0 ]; then
    volver_atras
    echo "El buzón virtual no se pudo abrir con $CUENTA; se dejó el servidor como estaba: ${salida:0:300}" >&2
    exit 1
  fi
fi
echo "Listo: buzón virtual «Virtual.Todo» creado. El webmail ofrecerá «Todas las carpetas» en unos minutos."
