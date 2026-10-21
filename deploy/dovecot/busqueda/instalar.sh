#!/usr/bin/env bash
# Instala la búsqueda de texto completo del correo (fts-flatcurve) y su mantenimiento nocturno.
# Lo usan el instalador del servidor (deploy/webmail/instalar.sh) y el ajuste
# deploy/ajustes/52-busqueda-texto-completo.sh para los servidores ya instalados.
#
# Uso: sudo bash deploy/dovecot/busqueda/instalar.sh [--simular]
# Contrato de los ajustes: imprime «Sin cambios: …», «Pendiente: …» o «Listo: …»; sale con 0 si todo fue bien.
# Idempotente. Respalda lo que toca y, si Dovecot rechaza la configuración, la deja como estaba.
# La indexación del correo antiguo no se hace aquí: la lanza cron de noche (busqueda-indexar-noche).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
SIMULAR=0
[ "${1:-}" = "--simular" ] && SIMULAR=1

DOVECOT_CONF=/etc/dovecot/dovecot.conf
MODULOS=/etc/dovecot/maquita.d
INCLUDE='!include_try /etc/dovecot/maquita.d/*.conf'
CONF="$MODULOS/60-busqueda.conf"
PAQUETE=dovecot-flatcurve

[ -f "$DOVECOT_CONF" ] || {
  echo "Sin cambios: este servidor no tiene Dovecot ($DOVECOT_CONF)."
  exit 0
}

# Un servidor con otro motor de búsqueda configurado a mano (p. ej. fts_xapian por cuenta) no se toca.
if [ ! -f "$CONF" ] && doveconf -h mail_plugins 2>/dev/null | grep -qw fts; then
  echo "Sin cambios: Dovecot ya tiene un motor de búsqueda configurado fuera de $MODULOS."
  exit 0
fi

pendiente=()
dpkg -s "$PAQUETE" >/dev/null 2>&1 || pendiente+=("instalar el paquete $PAQUETE")
grep -qxF "$INCLUDE" "$DOVECOT_CONF" || pendiente+=("incluir $MODULOS en dovecot.conf")
# «mail_plugins = sieve» en protocol lmtp reemplaza los módulos globales: la entrega no indexaría al llegar.
grep -qx '  mail_plugins = sieve' "$DOVECOT_CONF" && pendiente+=("LMTP: sumar los módulos globales a sieve")
cmp -s "$DIR/60-busqueda.conf" "$CONF" || pendiente+=("configuración de búsqueda en $CONF")
cmp -s "$DIR/busqueda-indexar-noche" /usr/local/sbin/busqueda-indexar-noche || pendiente+=("indexación nocturna")
cmp -s "$DIR/busqueda-adjuntos-precalentar" /usr/local/sbin/busqueda-adjuntos-precalentar ||
  pendiente+=("caché nocturna de adjuntos")
cmp -s "$DIR/maquita-busqueda.cron" /etc/cron.d/maquita-busqueda || pendiente+=("tareas nocturnas (cron)")

if [ ${#pendiente[@]} -eq 0 ]; then
  echo "Sin cambios: la búsqueda de texto completo ya está instalada."
  exit 0
fi
printf 'Pendiente: %s\n' "${pendiente[@]}"
[ "$SIMULAR" = 1 ] && exit 0

if ! dpkg -s "$PAQUETE" >/dev/null 2>&1; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q "$PAQUETE" >/dev/null
fi

# Respaldo de lo que se toca y vuelta atrás si Dovecot no acepta la configuración.
sello=$(date +%Y%m%d%H%M%S)
cp -p "$DOVECOT_CONF" "$DOVECOT_CONF.bak.$sello"
habia_conf=0
[ -f "$CONF" ] && {
  habia_conf=1
  cp -p "$CONF" "$CONF.bak.$sello"
}
volver_atras() {
  cp -p "$DOVECOT_CONF.bak.$sello" "$DOVECOT_CONF"
  if [ "$habia_conf" = 1 ]; then cp -p "$CONF.bak.$sello" "$CONF"; else rm -f "$CONF"; fi
}

install -d -m 755 "$MODULOS"
install -m 644 "$DIR/60-busqueda.conf" "$CONF"
sed -i 's/^  mail_plugins = sieve$/  mail_plugins {\n    sieve = yes\n  }/' "$DOVECOT_CONF"
if ! grep -qxF "$INCLUDE" "$DOVECOT_CONF"; then
  printf '\n# ---- Módulos opcionales (búsqueda, cuotas…): uno por archivo, ver deploy/dovecot/ ----\n%s\n' \
    "$INCLUDE" >>"$DOVECOT_CONF"
fi
if ! salida=$(doveconf -n 2>&1 >/dev/null); then
  volver_atras
  echo "Dovecot rechazó la configuración; se dejó como estaba: ${salida:0:300}" >&2
  exit 1
fi

install -m 755 "$DIR/busqueda-indexar-noche" /usr/local/sbin/busqueda-indexar-noche
install -m 755 "$DIR/busqueda-adjuntos-precalentar" /usr/local/sbin/busqueda-adjuntos-precalentar
install -m 644 "$DIR/maquita-busqueda.cron" /etc/cron.d/maquita-busqueda

if systemctl is-active --quiet dovecot; then doveadm reload; fi
echo "Listo: búsqueda de texto completo instalada; el correo antiguo se indexa de noche (busqueda-indexar-noche estado)."
