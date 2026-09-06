#!/bin/bash
# Vigilancia del milter DLP — avisa si el correo empieza a pasar sin inspección.
# =============================================================================
# Postfix tiene `milter_default_action = accept` (decisión D-1 en DECISIONES.md):
# si el milter no responde, el correo SE ENTREGA IGUAL, sin inspeccionar. Es
# bueno para la disponibilidad y malo para enterarse: hoy la protección contra
# fugas de datos se puede caer y nadie lo nota.
#
# Este script cierra ese punto ciego. Comprueba tres cosas y avisa por correo al
# equipo de tecnología cuando alguna falla:
#   1. El servicio maquita-milter está activo.
#   2. El puerto 11335 acepta conexiones (activo no es lo mismo que respondiendo).
#   3. Postfix sigue apuntando al milter y su acción por defecto no cambió sin
#      que nadie lo decidiera.
#   4. La cola de evidencia diferida (B2) no acumula marcadores sin procesar.
#      Cuando la base no está disponible, el milter deja ahí un marcador JSON y
#      un cron los reinserta cada 7 minutos. Ese cron solo avisa si la base sigue
#      caída; si el marcador se queda por otro motivo, hoy no lo mira nadie.
#
# Avisa UNA vez por incidencia, no en cada pasada, y avisa también cuando se
# recupera. Sin eso, una caída de una hora son treinta correos y el aviso deja
# de leerse.
#
# El aviso se envía con sendmail local. Funciona aunque el milter esté caído,
# precisamente porque la acción por defecto es `accept`; si algún día se pasa a
# `tempfail`, hay que revisar que el propio aviso no se quede en cola.
#
# Instalado por: equipo de tecnología, 2026-09-04 (hallazgo A-15 / decisión D-1).

set -uo pipefail

DESTINOS="gestiontecnologia@maquita.org gestiontecnologia@maquita.com.ec"
REMITENTE="postmaster@maquita.org"
UNIDAD="maquita-milter"
PUERTO=11335
ESTADO="/var/lib/maquita-admin/estado-vigilancia-milter"
SERVIDOR="$(hostname -f 2>/dev/null || hostname)"

fallos=()

# 1. ¿El servicio está activo?
if ! systemctl is-active --quiet "$UNIDAD"; then
    fallos+=("El servicio $UNIDAD NO está activo (estado: $(systemctl is-active "$UNIDAD" 2>&1)).")
fi

# 2. ¿El puerto responde? Activo no basta: puede estar colgado.
if ! timeout 5 bash -c "echo > /dev/tcp/127.0.0.1/$PUERTO" 2>/dev/null; then
    fallos+=("El puerto $PUERTO no acepta conexiones. Postfix está entregando SIN inspección de fugas de datos.")
fi

# 3. ¿Postfix sigue configurado como esperamos?
milters="$(postconf -h smtpd_milters 2>/dev/null)"
accion="$(postconf -h milter_default_action 2>/dev/null)"
if [[ "$milters" != *"$PUERTO"* ]]; then
    fallos+=("Postfix ya NO apunta al milter en el puerto $PUERTO (smtpd_milters = $milters). La inspección está desconectada.")
fi
if [[ "$accion" != "accept" ]]; then
    fallos+=("milter_default_action cambió a '$accion' (se esperaba 'accept'). Si es intencionado, actualiza DECISIONES.md; si no, el correo puede quedarse en cola cuando el milter falle.")
fi

# 4. ¿Se acumulan marcadores de evidencia sin reinsertar? (B2)
COLA_EVIDENCIA="/var/lib/maquita-admin/cola-cuarentena"
UMBRAL_MARCADORES=5
if [ -d "$COLA_EVIDENCIA" ]; then
    pendientes=$(find "$COLA_EVIDENCIA" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
    if [ "$pendientes" -ge "$UMBRAL_MARCADORES" ]; then
        antiguo=$(find "$COLA_EVIDENCIA" -maxdepth 1 -name '*.json' -printf '%TY-%Tm-%Td %TH:%TM\n' 2>/dev/null | sort | head -1)
        fallos+=("La cola de evidencia de cuarentena acumula $pendientes marcadores sin reinsertar (el más antiguo, del $antiguo). El reconciliador corre cada 7 minutos: si no bajan, algo impide escribir en la base y se está perdiendo el rastro de lo que se puso en cuarentena.")
    fi
fi

avisar() {
    local asunto="$1" cuerpo="$2"
    for destino in $DESTINOS; do
        printf 'Subject: %s\nFrom: %s\nTo: %s\nAuto-Submitted: auto-generated\n\n%s\n' \
            "$asunto" "$REMITENTE" "$destino" "$cuerpo" \
            | /usr/sbin/sendmail -f "$REMITENTE" "$destino"
    done
}

if [ ${#fallos[@]} -gt 0 ]; then
    if [ ! -f "$ESTADO" ]; then          # primera vez: avisar
        detalle=$(printf '  - %s\n' "${fallos[@]}")
        avisar "[$SERVIDOR] ALERTA: el correo está pasando sin inspección de fugas" \
"La vigilancia del milter DLP ha detectado un problema en $SERVIDOR.

$detalle

QUÉ SIGNIFICA
Postfix está configurado para ENTREGAR el correo aunque el milter no responda
(milter_default_action = accept). Es decir: el correo sigue circulando con
normalidad, pero la inspección de fugas de datos NO se está aplicando.

QUÉ HACER
  systemctl status maquita-milter
  journalctl -u maquita-milter -n 50
  systemctl restart maquita-milter

Se avisará de nuevo cuando el servicio se recupere. Hasta entonces no se
repetirá este correo.

Detectado: $(date '+%Y-%m-%d %H:%M:%S')"
        date '+%Y-%m-%d %H:%M:%S' > "$ESTADO"
        logger -t vigilar-milter "ALERTA enviada: ${fallos[*]}"
    fi
    exit 1
fi

# Todo bien: si veníamos de una incidencia, avisar de la recuperación.
if [ -f "$ESTADO" ]; then
    desde="$(cat "$ESTADO" 2>/dev/null)"
    avisar "[$SERVIDOR] Recuperado: la inspección de fugas vuelve a estar activa" \
"El milter DLP de $SERVIDOR ha vuelto a responder.

La inspección estuvo interrumpida desde $desde hasta $(date '+%Y-%m-%d %H:%M:%S').
Durante ese intervalo el correo se entregó SIN inspeccionar. Conviene revisar el
tráfico de esa franja si se maneja información sensible."
    rm -f "$ESTADO"
    logger -t vigilar-milter "Recuperado tras incidencia iniciada a las $desde"
fi
exit 0
