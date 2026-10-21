#!/usr/bin/env bash
# Instala los vigilantes del servidor de correo (deploy/vigilantes/README.md).
# Lo llaman el instalador (deploy/webmail/instalar.sh) y el ajuste 53 (servidores ya instalados).
# Contrato de los ajustes: con --simular solo informa; sin argumentos aplica. Idempotente.
# No pisa versiones propias: si el destino ya existe, es distinto y no lleva la marca
# «maquita-vigilantes (repo)», se deja como está y se informa (servidores con vigilantes a medida).
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
O="$APP_DIR/deploy/vigilantes"
MARCA="maquita-vigilantes (repo)"
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
# VIGILANTES_RAIZ: solo para las pruebas (instala bajo otra raíz y no toca systemd).
RAIZ="${VIGILANTES_RAIZ:-}"
MANIFIESTO="$RAIZ/var/lib/maquita-vigilantes/manifiesto"
sysd() { [ -n "$RAIZ" ] || systemctl "$@"; }
FECHA=$(date +%Y%m%d%H%M%S)

# origen|destino|permisos
ARCHIVOS="
$O/lib-avisos.sh|/usr/local/lib/maquita-vigilantes/lib-avisos.sh|644
$O/aviso-limitado|/usr/local/sbin/aviso-limitado|755
$O/guardian-web-correo|/usr/local/sbin/guardian-web-correo|755
$O/vigilante-correo.sh|/usr/local/sbin/vigilante-correo.sh|755
$O/verificar-config-panel.sh|/usr/local/sbin/verificar-config-panel.sh|755
$APP_DIR/deploy/hardening/vigilar-milter.sh|/usr/local/sbin/vigilar-milter.sh|755
$O/vigila-entrega-local.sh|/usr/local/bin/vigila-entrega-local.sh|755
$O/mail-health-check.sh|/usr/local/bin/mail-health-check.sh|755
$O/informe-diario-correo.sh|/usr/local/bin/informe-diario-correo.sh|755
$O/systemd/guardian-web-correo.service|/etc/systemd/system/guardian-web-correo.service|644
$O/systemd/guardian-web-correo.timer|/etc/systemd/system/guardian-web-correo.timer|644
$O/systemd/vigilar-milter.service|/etc/systemd/system/vigilar-milter.service|644
$O/systemd/vigilar-milter.timer|/etc/systemd/system/vigilar-milter.timer|644
$O/systemd/verificar-config-panel.service|/etc/systemd/system/verificar-config-panel.service|644
$O/systemd/verificar-config-panel.timer|/etc/systemd/system/verificar-config-panel.timer|644
$O/cron/vigila-entrega-local|/etc/cron.d/vigila-entrega-local|644
$O/cron/vigilante-correo|/etc/cron.d/vigilante-correo|644
$O/cron/mail-health-check|/etc/cron.d/mail-health-check|644
$O/cron/informe-diario-correo|/etc/cron.d/informe-diario-correo|644
"
TEMPORIZADORES="guardian-web-correo.timer vigilar-milter.timer verificar-config-panel.timer"

es_nuestro() {  # el destino lo instaló este repositorio (o es una unidad/cron idéntica a la nuestra)
    grep -qsF "$MARCA" "$1" || cmp -s "$1" "$2"
}

pendientes=(); propios=()
while IFS='|' read -r src dst modo; do
    [ -n "$src" ] || continue
    dst="$RAIZ$dst"
    [ -f "$src" ] || { echo "Falta en el repositorio: $src" >&2; exit 1; }
    if [ ! -e "$dst" ]; then pendientes+=("$src|$dst|$modo"); continue; fi
    cmp -s "$src" "$dst" && continue
    case "${dst#"$RAIZ"}" in
        # Unidades y cron no llevan marca: solo se reemplazan si las instaló una versión anterior
        # de este mismo instalador (queda registrado en el manifiesto).
        /etc/*) if grep -qsxF "$dst" "$MANIFIESTO"; then pendientes+=("$src|$dst|$modo"); else propios+=("$dst"); fi ;;
        *)      if es_nuestro "$dst" "$src"; then pendientes+=("$src|$dst|$modo"); else propios+=("$dst"); fi ;;
    esac
done <<< "$ARCHIVOS"

faltan_timers=()
for t in $TEMPORIZADORES; do
    [ -e "$RAIZ/etc/systemd/system/$t" ] || continue
    [ -n "$RAIZ" ] && continue
    systemctl is-enabled --quiet "$t" 2>/dev/null || faltan_timers+=("$t")
done

[ ${#propios[@]} -gt 0 ] && echo "Se respetan versiones propias del servidor: ${propios[*]}"
if [ ${#pendientes[@]} -eq 0 ] && [ ${#faltan_timers[@]} -eq 0 ]; then
    echo "Sin cambios: los vigilantes ya están instalados."; exit 0
fi
echo "Pendiente: vigilantes del correo (${#pendientes[@]} archivos, ${#faltan_timers[@]} temporizadores por activar)"
[ "$SIMULAR" = 1 ] && exit 0

for p in "${pendientes[@]}"; do
    src=${p%%|*}; resto=${p#*|}
    case "$src" in *.sh|*/aviso-limitado|*/guardian-web-correo) bash -n "$src" || { echo "Error de sintaxis en $src: no se instala nada." >&2; exit 1; } ;; esac
done

respaldos=(); nuevos=()
deshacer() {
    for r in "${respaldos[@]}"; do cp -p "${r#*|}" "${r%%|*}"; done
    for n in "${nuevos[@]}"; do
        case "$n" in *.timer) sysd disable --now "$(basename "$n")" >/dev/null 2>&1 || true ;; esac
        rm -f "$n"
        sed -i "\#^$n\$#d" "$MANIFIESTO" 2>/dev/null || true
    done
    sysd daemon-reload || true
    echo "Se deshizo la instalación de los vigilantes." >&2
}
trap 'deshacer' ERR

install -d -m 755 "$RAIZ/usr/local/lib/maquita-vigilantes" "$RAIZ/var/lib/maquita-vigilantes"
for p in "${pendientes[@]}"; do
    src=${p%%|*}; resto=${p#*|}; dst=${resto%%|*}; modo=${resto#*|}
    if [ -e "$dst" ]; then cp -p "$dst" "$dst.bak.$FECHA"; respaldos+=("$dst|$dst.bak.$FECHA"); else nuevos+=("$dst"); fi
    install -D -m "$modo" "$src" "$dst"
    grep -qsxF "$dst" "$MANIFIESTO" || echo "$dst" >> "$MANIFIESTO"
done

sysd daemon-reload
for u in /etc/systemd/system/guardian-web-correo.service /etc/systemd/system/vigilar-milter.service \
         /etc/systemd/system/verificar-config-panel.service; do
    [ -e "$u" ] && [ -z "$RAIZ" ] || continue
    systemd-analyze verify "$u" >/dev/null 2>&1 || { echo "La unidad $u no pasa systemd-analyze verify." >&2; false; }
done
for t in $TEMPORIZADORES; do
    [ -e "$RAIZ/etc/systemd/system/$t" ] && sysd enable --now "$t" >/dev/null 2>&1
done
trap - ERR
if [ -n "$RAIZ" ]; then echo "Listo: vigilantes del correo instalados en $RAIZ"
else echo "Listo: vigilantes del correo instalados; avisos a: $(. "$O/lib-avisos.sh"; vig_destinos)"; fi
