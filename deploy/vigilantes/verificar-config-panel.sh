#!/bin/bash
# maquita-vigilantes (repo)
# Comprueba que los valores prestados del correo siguen alineados en el panel.
# =============================================================================
# Desde la fase 2 (hallazgo A-15) el panel no corre como root y NO puede leer la
# configuracion del correo. Los valores que necesita se copiaron a su propia
# configuracion con el prefijo WEBMAIL_.
#
# Eso deja una dependencia incomoda: el mismo valor vive en dos archivos. Si
# cambia en el correo y nadie lo copia, AIR, los agentes, el copiloto y RAG
# fallan o se comportan raro, y el motivo no salta a la vista.
#
# El panel NO puede detectarlo por si mismo: comparar exigiria leer el archivo
# del correo, que es justo lo que se quiere evitar. Por eso la comprobacion vive
# aqui, en un guion que corre como root y compara HUELLAS, nunca valores.
#
# Uso:  verificar-config-panel.sh          (informe por pantalla)
#       verificar-config-panel.sh --avisar (ademas, correo si hay desalineados)
#
# Instalado 2026-09-04.

set -uo pipefail

CORREO=/opt/maquita-webmail/backend/.env
PANEL=/opt/maquita-webmail/admin-panel/backend/.env
. /usr/local/lib/maquita-vigilantes/lib-avisos.sh

OBLIGATORIAS="SECRET_KEY ADMIN_JWT_SECRET MASTER_PASSWORD DATABASE_URL"
OPCIONALES="IA_PROVIDER IA_BASE_URL IA_MODEL IA_API_KEY IA_TIMEOUT IA_EMBED_URL
            IA_EMBED_MODEL OLLAMA_URL IMAP_HOST IMAP_PORT ORG_NAME AI_ORG_CONTEXT
            REDIS_URL"

for f in "$CORREO" "$PANEL"; do
    [ -r "$f" ] || { echo "No puedo leer $f. Ejecuta esto como root."; exit 2; }
done

# Huella de un valor, nunca el valor.
#
# Se quitan las comillas de envoltura antes de comparar. En el archivo del panel
# los valores con espacios o parentesis van entrecomillados, para que un guion de
# shell pueda hacer source sin abortar; en el del correo no. Sin esto, la
# comparacion diria «desalineado» cuando el valor es el mismo y solo cambia la
# envoltura.
sin_comillas() {
    sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

huella() {
    local archivo="$1" clave="$2"
    grep -m1 "^${clave}=" "$archivo" 2>/dev/null | cut -d= -f2- \
        | sin_comillas | sha256sum | cut -c1-12
}

desalineadas=()
ausentes=()
alineadas=0

for clave in $OBLIGATORIAS $OPCIONALES; do
    if ! grep -q "^${clave}=" "$CORREO" 2>/dev/null; then
        continue   # no esta en el correo: no hay nada que alinear
    fi
    if ! grep -q "^WEBMAIL_${clave}=" "$PANEL" 2>/dev/null; then
        ausentes+=("$clave")
        continue
    fi
    a="$(huella "$CORREO" "$clave")"
    b="$(grep -m1 "^WEBMAIL_${clave}=" "$PANEL" | cut -d= -f2- \
         | sin_comillas | sha256sum | cut -c1-12)"
    if [ "$a" != "$b" ]; then
        desalineadas+=("$clave")
    else
        alineadas=$((alineadas + 1))
    fi
done

echo "Valores alineados:      $alineadas"
echo "Valores desalineados:   ${#desalineadas[@]} ${desalineadas[*]:-}"
echo "Ausentes en el panel:   ${#ausentes[@]} ${ausentes[*]:-}"

problemas=$(( ${#desalineadas[@]} + ${#ausentes[@]} ))
[ "$problemas" -eq 0 ] && { echo "Todo en orden."; exit 0; }

echo
echo "QUE HACER: copia el valor de $CORREO a $PANEL con el prefijo WEBMAIL_,"
echo "y despues: systemctl restart maquita-admin"

if [ "${1:-}" = "--avisar" ]; then
    cuerpo="La configuracion del panel de administracion se ha desalineado de la del correo.

Desalineados (el valor cambio en el correo y no se copio al panel):
  ${desalineadas[*]:-ninguno}

Ausentes en el panel (el correo los tiene y el panel no):
  ${ausentes[*]:-ninguno}

CONSECUENCIA
Los procesos que el panel lanza del correo (AIR, agentes, copiloto y RAG) pueden
fallar al arrancar o comportarse de forma incorrecta. Si falta alguna de las
cuatro obligatorias, fallan seguro.

QUE HACER
Copiar el valor de $CORREO al archivo
$PANEL con el prefijo WEBMAIL_,
y reiniciar: systemctl restart maquita-admin

Comprobado: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "$cuerpo" | vig_enviar "[$(vig_servidor)] Configuracion del panel desalineada de la del correo" "$(vig_destinos)"
fi
exit 1
