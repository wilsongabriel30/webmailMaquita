#!/bin/bash
# maquita-vigilantes (repo)
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin   # cron no incluye /usr/sbin (falsa alarma CORTAFUEGOS_AUSENTE)
# ============================================================================
# Vigilante de intrusión del servidor de correo — cada minuto (cron vigilante-correo).
# Creado el 14/09/2026 con lo aprendido de dos ataques reales a un servidor de correo anterior
# (24/08 y 12/09 de 2026).
#
# Lo que hizo el atacante, y que aqui se vigila:
#   1. Ejecutar un binario desde una carpeta oculta del arbol de la aplicacion.
#   2. Borrar el binario del disco para no dejar rastro.
#   3. Disfrazarse de hilo del nucleo ([kworker/...]).
#   4. Dejar la persistencia en un archivo de inicio de sesion.
#   5. Descargar componentes de internet con el usuario del servicio.
#
# Criterio: se NEUTRALIZA solo lo inequivoco; lo dudoso se REPORTA sin tocar.
# Un vigilante que mata procesos legitimos es peor que no tener vigilante.
# ============================================================================
set -u

LOG=/var/log/vigilante-correo.log
ESTADO=/run/vigilante-correo.ultimo-aviso
. /usr/local/lib/maquita-vigilantes/lib-avisos.sh
SERVIDOR=$(vig_servidor)
MIN_ENTRE_AVISOS=1800          # como maximo un aviso cada 30 minutos
HALLAZGOS=""

ts() { date '+%Y-%m-%d %H:%M:%S'; }

# --- 1. Ejecutables en rutas donde nada legitimo deberia correr --------------
for d in /proc/[0-9]*; do
    pid=${d##*/}
    [ "$pid" = "$$" ] && continue
    exe=$(readlink "$d/exe" 2>/dev/null) || continue
    case "$exe" in
        /tmp/*|/var/tmp/*|/dev/shm/*|/var/vmail/*)
            usr=$(stat -c %U "$d" 2>/dev/null)
            cmd=$( { tr '\0' ' ' < "$d/cmdline"; } 2>/dev/null )
            HALLAZGOS="${HALLAZGOS}EJECUTABLE_EN_RUTA_TEMPORAL pid=$pid usuario=$usr exe=$exe cmd=$cmd
"
            kill -9 "$pid" 2>/dev/null
            ;;
    esac
done

# --- 2. Procesos con el ejecutable ya borrado del disco ----------------------
# Tambien ocurre de forma legitima tras actualizar un paquete, asi que solo se
# neutraliza cuando ademas hay disfraz o carpeta oculta de por medio.
for d in /proc/[0-9]*; do
    pid=${d##*/}
    [ "$pid" = "$$" ] && continue
    exe=$(readlink "$d/exe" 2>/dev/null) || continue
    case "$exe" in *" (deleted)") ;; *) continue;; esac

    usr=$(stat -c %U "$d" 2>/dev/null)
    comm=$(cat "$d/comm" 2>/dev/null)
    cmd=$( { tr '\0' ' ' < "$d/cmdline"; } 2>/dev/null )
    limpio=${exe% (deleted)}
    grave=0
    # a) se hace pasar por hilo del nucleo: los hilos reales no tienen ejecutable
    case "$comm" in
        kworker*|kthread*|ksoftirqd*|migration*|rcu_*|kswapd*|khugepaged*|jbd2*) grave=1;;
    esac
    case "$cmd" in "["*) grave=1;; esac
    # b) el ejecutable vivia en una carpeta oculta
    case "$limpio" in */.*/*) grave=1;; esac

    if [ "$grave" = "1" ]; then
        HALLAZGOS="${HALLAZGOS}PROCESO_BORRADO_DISFRAZADO pid=$pid usuario=$usr comm=$comm exe=$exe cmd=$cmd
"
        kill -9 "$pid" 2>/dev/null
    elif [ "$usr" != "root" ] && [ ! -e "$limpio" ]; then
        # Si el archivo sigue existiendo en disco, es un binario reemplazado por
        # una actualizacion del sistema y el servicio aun no se ha reiniciado:
        # es normal y no se reporta. Solo interesa cuando el archivo ya no esta.
        HALLAZGOS="${HALLAZGOS}AVISO_EXE_BORRADO (no se toco) pid=$pid usuario=$usr comm=$comm exe=$exe
"
    fi
done

# --- 3. Ejecutables en carpetas ocultas del arbol de las aplicaciones --------
for d in /proc/[0-9]*; do
    pid=${d##*/}
    [ "$pid" = "$$" ] && continue
    exe=$(readlink "$d/exe" 2>/dev/null) || continue
    case "$exe" in
        /opt/maquita-webmail/*/.*/*|/opt/maquita-webmail/.*/*|/var/lib/*/.*/*|/var/vmail/*/.*/*)
            usr=$(stat -c %U "$d" 2>/dev/null)
            cmd=$( { tr '\0' ' ' < "$d/cmdline"; } 2>/dev/null )
            HALLAZGOS="${HALLAZGOS}EJECUTABLE_EN_CARPETA_OCULTA pid=$pid usuario=$usr exe=$exe cmd=$cmd
"
            kill -9 "$pid" 2>/dev/null
            ;;
    esac
done

# --- 4. Persistencia: tareas programadas de los usuarios de servicio ---------
# Ninguno de estos usuarios deberia tener tareas propias.
for f in /var/spool/cron/crontabs/*; do
    [ -f "$f" ] || continue
    u=$(basename "$f")
    # root y las personas (uid >= 1000) pueden tener tareas propias; los servicios no.
    [ "$u" = root ] && continue
    [ "$(id -u "$u" 2>/dev/null || echo 0)" -ge 1000 ] && continue
    case "$u" in
        www-data|dovecot|dovenull|vmail|sogo|radicale|redis|postgres|postfix|clamav|_rspamd|maquita-admin)
            HALLAZGOS="${HALLAZGOS}CRON_DE_SERVICIO archivo=$f usuario=$u contenido=$(grep -vE '^[[:space:]]*#' "$f" | tr '\n' ';' | cut -c1-200)
"
            ;;
    esac
done

# --- 5. Persistencia: unidades de systemd creadas en los ultimos 2 dias ------
# Solo se reportan, y cada una UNA vez (las actualizaciones del sistema también crean unidades):
# puede ser trabajo legitimo del administrador.
VISTAS=/var/lib/vigilante-correo/unidades-vistas
mkdir -p "${VISTAS%/*}"; touch "$VISTAS"
nuevas=""
while IFS= read -r u; do
    huella="$u $(stat -c %Y "$u" 2>/dev/null)"
    grep -qxF "$huella" "$VISTAS" && continue
    echo "$huella" >> "$VISTAS"
    nuevas="$nuevas $u"
done < <(find /etc/systemd/system -maxdepth 2 \( -name '*.service' -o -name '*.timer' \) -newermt '-2 days' 2>/dev/null)
if [ -n "${nuevas// /}" ]; then
    HALLAZGOS="${HALLAZGOS}UNIDAD_SYSTEMD_NUEVA (no se toco) $nuevas
"
fi

# --- 6. Persistencia: archivos de inicio de sesion de usuarios de servicio ---
# Aqui todos tienen 'nologin', asi que cualquier archivo de este tipo es raro.
PAT_INICIO='curl |wget |base64 -d|nohup |/dev/shm|\.cache/\.'
for h in /var/www /var/vmail /var/lib/postgresql /var/lib/rspamd /usr/lib/sogo; do
    for f in "$h"/.bashrc "$h"/.bash_profile "$h"/.profile; do
        [ -f "$f" ] || continue
        linea=$(grep -nE "$PAT_INICIO" "$f" 2>/dev/null | grep -vE '^[0-9]+:[[:space:]]*#')
        if [ -n "$linea" ]; then
            HALLAZGOS="${HALLAZGOS}INICIO_SESION_SOSPECHOSO archivo=$f linea=$linea
"
            cp "$f" "/root/$(echo "$f" | tr / _)-$(date +%Y%m%d%H%M%S).bak" 2>/dev/null
        fi
    done
done

# --- 7. El cortafuegos sigue en su sitio ------------------------------------
# Dos esquemas: la cadena CORTAFUEGOS de iptables (maquita-cortafuegos, instalaciones desde la
# plantilla) o la tabla «inet filter» de nftables (servidores configurados a mano).
if iptables -S INPUT 2>/dev/null | grep -q -- '-j CORTAFUEGOS'; then
    iptables -S CORTAFUEGOS 2>/dev/null | tail -1 | grep -q -- '-j DROP' \
        || HALLAZGOS="${HALLAZGOS}CORTAFUEGOS_ABIERTO la cadena CORTAFUEGOS ya no termina en DROP
"
elif ! nft list chain inet filter input >/dev/null 2>&1; then
    HALLAZGOS="${HALLAZGOS}CORTAFUEGOS_AUSENTE la tabla de filtrado ya no existe
"
elif ! nft list chain inet filter input 2>/dev/null | grep -q 'policy drop'; then
    HALLAZGOS="${HALLAZGOS}CORTAFUEGOS_ABIERTO la cadena de entrada ya no esta en modo bloqueo
"
fi

# --- 8. Registrar y avisar ---------------------------------------------------
if [ -n "$HALLAZGOS" ]; then
    {
        echo "===== $(ts) — DETECCION ====="
        printf '%s' "$HALLAZGOS"
        echo "carga: $(cut -d' ' -f1-3 /proc/loadavg)"
    } >> "$LOG"

    ahora=$(date +%s)
    ultimo=0
    [ -f "$ESTADO" ] && ultimo=$(cat "$ESTADO" 2>/dev/null || echo 0)
    if [ $((ahora - ultimo)) -ge "$MIN_ENTRE_AVISOS" ]; then
        echo "$ahora" > "$ESTADO"
        {
            echo "El vigilante detecto actividad sospechosa en $SERVIDOR."
            echo
            echo "Fecha: $(ts)"
            echo
            echo "Hallazgos:"
            printf '%s' "$HALLAZGOS"
            echo
            echo "Los marcados como 'no se toco' son solo avisos: reviselos antes de actuar."
            echo "Registro completo en: $LOG"
        } | vig_enviar "[ALERTA] Actividad sospechosa en el servidor de correo $SERVIDOR" "$(vig_destinos)" 2>/dev/null || true
    fi
    exit 1
fi
exit 0
