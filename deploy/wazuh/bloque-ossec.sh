#!/usr/bin/env bash
# Escribe en la salida estándar el ossec.conf del agente con el bloque de Maquita al día (entre las
# marcas «maquita: inicio» y «maquita: fin»; lo de fuera no se toca). Lo usa deploy/wazuh/instalar.sh.
#
# Uso: bloque-ossec.sh <ossec.conf> <carpeta de la aplicación>
# WAZUH_LOG_RAIZ: solo para las pruebas (busca los registros bajo otra raíz).
set -euo pipefail
CONF="$1"; APP_DIR="$2"
RAIZ="${WAZUH_LOG_RAIZ:-}"
INICIO="<!-- maquita: inicio (deploy/wazuh/instalar.sh; se regenera al volver a instalar) -->"
FIN="<!-- maquita: fin -->"

# ossec.conf sin el bloque anterior
sin_bloque="$(awk '/<!-- maquita: inicio/{fuera=1} !fuera{print} /<!-- maquita: fin -->/{fuera=0}' "$CONF")"

archivo() {  # formato ruta: solo si existe y Wazuh no lo lee ya por su cuenta
    local formato="$1" ruta="$2"
    [ -e "$RAIZ$ruta" ] || return 0
    grep -qF "<location>$ruta</location>" <<<"$sin_bloque" && return 0
    printf '  <localfile>\n    <log_format>%s</log_format>\n    <location>%s</location>\n  </localfile>\n' "$formato" "$ruta"
}

printf '%s\n' "$sin_bloque"
echo "$INICIO"
echo "<ossec_config>"
echo "  <!-- Alertas de anomalía, auditoría del panel y cumplimiento (lo escribe el recolector de los tableros) -->"
printf '  <localfile>\n    <log_format>json</log_format>\n    <location>/var/log/maquita/seguridad.json</location>\n  </localfile>\n'
archivo syslog /var/log/maquita/diario.log
archivo syslog /var/log/mail.log
archivo syslog /var/log/auth.log
archivo apache /var/log/nginx/access.log
archivo syslog /var/log/nginx/error.log
archivo apache /var/log/nginx/activesync-access.log
for vigilante in guardian-web-correo vigila-entrega-local vigilante-correo mail-health maquita-anomalia; do
    archivo syslog "/var/log/$vigilante.log"
done
cat <<EOF
  <!-- Integridad de archivos: configuración del correo y de la web, ayudantes con privilegios y el
       código. Sin report_changes: varios de estos archivos llevan claves y Wazuh enviaría su contenido. -->
  <syscheck>
    <directories realtime="yes">/etc/postfix,/etc/dovecot,/etc/nginx,/etc/maquita-mail,/etc/rspamd,/etc/sudoers.d</directories>
    <directories>/usr/local/sbin,/usr/local/lib/maquita-vigilantes,/etc/systemd/system</directories>
    <directories>$APP_DIR</directories>
    <ignore type="sregex">/venv/|/node_modules/|/__pycache__/|.pyc$|/.git/|/dist/|/logs/</ignore>
  </syscheck>
</ossec_config>
EOF
echo "$FIN"
