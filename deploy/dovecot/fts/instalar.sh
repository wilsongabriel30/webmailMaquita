#!/usr/bin/env bash
# Texto de los adjuntos en el índice de texto completo del correo, carpetas que no se indexan al llegar,
# ayudante del panel (maquita-fts) e indexación inicial de los buzones existentes.
# Completa deploy/dovecot/busqueda (motor fts-flatcurve, ajuste 52), que se instala antes si falta.
# Lo usan el instalador del servidor (deploy/webmail/instalar.sh) y el ajuste deploy/ajustes/63-*.
#
# Uso: sudo bash deploy/dovecot/fts/instalar.sh [--simular] [--con-ocr]
#   --simular  solo dice qué falta.
#   --con-ocr  además instala Tesseract (español e inglés) y activa el OCR de PDF escaneados y fotos.
# Contrato de los ajustes: imprime «Sin cambios: …», «Pendiente: …» o «Listo: …»; sale con 0 si todo fue bien.
# Idempotente. Respalda lo que toca (.bak.FECHA) y, si Dovecot rechaza la configuración, la deja como estaba.
# Solo Dovecot 2.4 (la sintaxis de fts_decoder y de las carpetas excluidas cambió respecto de la 2.3).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
SIMULAR=0
OCR=0
for a in "$@"; do
  case "$a" in
    --simular) SIMULAR=1 ;;
    --con-ocr) OCR=1 ;;
    *) echo "Opción desconocida: $a" >&2; exit 2 ;;
  esac
done

DOVECOT_CONF=/etc/dovecot/dovecot.conf
MODULOS=/etc/dovecot/maquita.d
BASE="$MODULOS/60-busqueda.conf"
CONF="$MODULOS/61-busqueda-adjuntos.conf"
LIB=/usr/local/lib/maquita-fts
AYUDANTE=/usr/local/sbin/maquita-fts
ETC=/etc/maquita-fts
ESTADO=/var/lib/maquita-fts
USUARIO=maquita-fts
UNIDAD=maquita-fts-indexar-inicial

[ -f "$DOVECOT_CONF" ] || { echo "Sin cambios: este servidor no tiene Dovecot ($DOVECOT_CONF)."; exit 0; }
version=$(dovecot --version 2>/dev/null || true)
case "$version" in
  2.4*|2.5*|3.*) ;;
  *) echo "Sin cambios: Dovecot ${version:-desconocido}; el texto de adjuntos de este proyecto es para Dovecot 2.4."; exit 0 ;;
esac

# El motor (ajuste 52) va primero. En simulación solo se informa.
if [ ! -f "$BASE" ]; then
  if [ "$SIMULAR" = 1 ]; then
    echo "Pendiente: antes, la búsqueda de texto completo (deploy/dovecot/busqueda, ajuste 52); después, el texto de los adjuntos."
    exit 0
  fi
  bash "$DIR/../busqueda/instalar.sh"
  [ -f "$BASE" ] || { echo "Sin cambios: este servidor usa otro motor de búsqueda; no se le añade el de adjuntos."; exit 0; }
fi

herramienta() { command -v "$1" >/dev/null 2>&1; }
paquetes=()
herramienta pdftotext || paquetes+=(poppler-utils)
herramienta catdoc || paquetes+=(catdoc)
herramienta exiftool || paquetes+=(libimage-exiftool-perl)
herramienta 7z || paquetes+=(7zip)
if [ "$OCR" = 1 ]; then
  herramienta tesseract || paquetes+=(tesseract-ocr)
  for l in spa eng; do dpkg -s "tesseract-ocr-$l" >/dev/null 2>&1 || paquetes+=("tesseract-ocr-$l"); done
fi

pendiente=()
[ ${#paquetes[@]} -eq 0 ] || pendiente+=("paquetes: ${paquetes[*]}")
id -u "$USUARIO" >/dev/null 2>&1 || pendiente+=("usuario sin privilegios $USUARIO")
[ -d "$ESTADO/tmp" ] || pendiente+=("carpeta temporal del decodificador")
cmp -s "$DIR/decode2text.sh" "$LIB/decode2text.sh" || pendiente+=("decodificador ($LIB)")
for f in "$DIR"/decodificador/*.py; do
  cmp -s "$f" "$LIB/$(basename "$f")" || { pendiente+=("módulo $(basename "$f")"); }
done
cmp -s "$DIR/maquita-fts" "$AYUDANTE" || pendiente+=("ayudante del panel ($AYUDANTE)")
# maquita-sudo con la orden maquita-fts (el panel llega al ayudante solo por ahí).
cmp -s "$DIR/../../sudoers/maquita-sudo" /usr/local/sbin/maquita-sudo || pendiente+=("maquita-sudo con la orden maquita-fts")
[ -f "$ETC/decodificador.conf" ] || pendiente+=("límites del decodificador ($ETC/decodificador.conf)")
if [ "$OCR" = 1 ] && ! grep -qx 'OCR=1' "$ETC/decodificador.conf" 2>/dev/null; then pendiente+=("activar el OCR"); fi
cmp -s "$DIR/61-busqueda-adjuntos.conf" "$CONF" || pendiente+=("configuración de Dovecot ($CONF)")
[ -e "$ESTADO/inicial-lanzada" ] || pendiente+=("indexación inicial de los buzones existentes")

if [ ${#pendiente[@]} -eq 0 ]; then
  echo "Sin cambios: el texto de los adjuntos ya entra en el índice de búsqueda."
  exit 0
fi
printf 'Pendiente: %s\n' "${pendiente[@]}"
[ "$SIMULAR" = 1 ] && exit 0

if [ ${#paquetes[@]} -gt 0 ]; then
  # 7zip es el paquete de Debian 13; en versiones anteriores, p7zip-full.
  if [[ " ${paquetes[*]} " == *" 7zip "* ]] && ! apt-cache show 7zip >/dev/null 2>&1; then
    paquetes=("${paquetes[@]/7zip/p7zip-full}")
  fi
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends "${paquetes[@]}" >/dev/null
fi

id -u "$USUARIO" >/dev/null 2>&1 ||
  useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$USUARIO"
install -d -m 755 -o root -g root "$ESTADO"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$ESTADO/tmp"
install -d -m 755 "$LIB" "$ETC"
install -m 755 "$DIR/decode2text.sh" "$LIB/decode2text.sh"
install -m 644 "$DIR"/decodificador/*.py "$LIB/"
install -m 750 "$DIR/maquita-fts" "$AYUDANTE"
bash "$DIR/../../sudoers/instalar.sh"  # maquita-sudo y sus validadores (/usr/local/lib/maquita-sudo)
[ -f "$ETC/decodificador.conf" ] || install -m 644 "$DIR/decodificador.conf" "$ETC/decodificador.conf"
if [ "$OCR" = 1 ]; then
  cp -p "$ETC/decodificador.conf" "$ETC/decodificador.conf.bak.$(date +%Y%m%d%H%M%S)"
  sed -i 's/^OCR=0$/OCR=1/' "$ETC/decodificador.conf"
  grep -qx 'OCR=1' "$ETC/decodificador.conf" || echo 'OCR=1' >>"$ETC/decodificador.conf"
fi
touch /var/log/maquita-fts.log && chmod 640 /var/log/maquita-fts.log

# Configuración de Dovecot: respaldo, instalación, validación y vuelta atrás si no valida.
sello=$(date +%Y%m%d%H%M%S)
cp -p "$DOVECOT_CONF" "$DOVECOT_CONF.bak.$sello"
habia=0
[ -f "$CONF" ] && { habia=1; cp -p "$CONF" "$CONF.bak.$sello"; }
install -m 644 "$DIR/61-busqueda-adjuntos.conf" "$CONF"
if ! salida=$(doveconf -n 2>&1 >/dev/null); then
  if [ "$habia" = 1 ]; then cp -p "$CONF.bak.$sello" "$CONF"; else rm -f "$CONF"; fi
  echo "Dovecot rechazó la configuración; se dejó como estaba: ${salida:0:300}" >&2
  exit 1
fi
if systemctl is-active --quiet dovecot; then doveadm reload; fi

# Indexación inicial en segundo plano, con la prioridad de CPU y disco más baja y sin cortar el servicio.
# Las cuentas ya indexadas (por la pasada nocturna) se saltan; lo que quede, lo retoma la noche.
lanzada=""
if [ ! -e "$ESTADO/inicial-lanzada" ]; then
  if systemctl is-active --quiet "$UNIDAD" 2>/dev/null; then
    lanzada="ya estaba en curso"
  elif command -v systemd-run >/dev/null 2>&1 && systemd-run --unit="$UNIDAD" --collect --quiet \
    --description="Índice de texto completo: indexación inicial de los buzones" \
    --nice=19 -p IOSchedulingClass=idle -p CPUSchedulingPolicy=batch \
    "$AYUDANTE" indexar-inicial; then
    lanzada="lanzada en segundo plano ($UNIDAD)"
  else
    nohup nice -n 19 ionice -c3 "$AYUDANTE" indexar-inicial >/dev/null 2>&1 &
    lanzada="lanzada en segundo plano"
  fi
  touch "$ESTADO/inicial-lanzada"
fi
echo "Listo: el índice incluye el texto de los adjuntos; papelera y no deseado no se indexan al llegar${lanzada:+; indexación inicial $lanzada}. Estado: maquita-fts estado."
