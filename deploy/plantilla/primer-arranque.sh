#!/usr/bin/env bash
# Asistente de primer arranque de una VM salida de la plantilla «sin personalizar».
#
# Lo lanza maquita-primer-arranque.service en la consola (tty1) mientras exista
# /etc/maquita-plantilla/sin-configurar; también se puede correr por SSH:  sudo bash primer-arranque.sh
#
# Pregunta la red, el dominio, el nombre de la institución, la clave inicial, la clave de root y las IP de
# administración, y deja el servidor instalado con SUS propias claves (DKIM, SSH, bases, sesiones): por eso
# la plantilla nunca se configura antes de clonarla.
#
# Sin preguntas (varias sedes, pruebas): un archivo /etc/maquita-plantilla/respuestas con
#   DOMINIO=  NOMBRE=  CORTO=  CORREO=  CLAVE_INICIAL=  CLAVE_ROOT=  ADMIN_IPS=
#   RED=mantener|fija  IP=192.0.2.10/24  PUERTA=  DNS="9.9.9.9 1.1.1.1"
# (se borra en cuanto se lee).
set -uo pipefail
APP_DIR=/opt/maquita-webmail
MARCA=/etc/maquita-plantilla/sin-configurar
RESPUESTAS=/etc/maquita-plantilla/respuestas
REGISTRO=/root/instalacion-primer-arranque.log
LEEME=/root/LEEME-primer-arranque.txt
TITULO="Primer arranque: servidor de correo y sitios"
export NEWT_COLORS='root=,blue'

[ "$EUID" -eq 0 ] || { echo "Ejecutar como root."; exit 1; }
[ -f "$MARCA" ] || { echo "Este servidor ya está configurado (no existe $MARCA)."; exit 0; }

RE_DOMINIO='^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'
RE_CORREO='^[a-z0-9][a-z0-9._+-]{0,63}@([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'
RE_IPCIDR='^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$'
RE_IP='^([0-9]{1,3}\.){3}[0-9]{1,3}$'

BOTONES=(--yes-button "Sí" --no-button "No" --ok-button "Aceptar" --cancel-button "Cancelar")
caja() { whiptail --title "$TITULO" "${BOTONES[@]}" "$@" 3>&1 1>&2 2>&3; }
aviso() { whiptail --title "$TITULO" "${BOTONES[@]}" --msgbox "$1" 16 74; }
pedir() {  # pedir <variable> <texto> <defecto> <regex> <mensaje si no vale>
    local valor="$3"
    while true; do
        valor=$(caja --inputbox "$2" 12 74 "$valor") || exit 1
        valor="$(echo "$valor" | xargs)"
        [[ "$valor" =~ $4 ]] && break
        aviso "$5"
    done
    printf -v "$1" '%s' "$valor"
}
pedir_clave() {  # pedir_clave <variable> <para qué>
    local a b
    while true; do
        a=$(caja --passwordbox "$2\n\nMínimo 12 caracteres, con letras y números." 12 74) || exit 1
        b=$(caja --passwordbox "Repita la clave." 10 74) || exit 1
        if [ "$a" != "$b" ]; then aviso "Las dos claves no coinciden."; continue; fi
        if [ ${#a} -lt 12 ] || ! [[ "$a" =~ [A-Za-z] && "$a" =~ [0-9] ]]; then aviso "La clave es demasiado corta o no tiene letras y números."; continue; fi
        break
    done
    printf -v "$1" '%s' "$a"
}

IF="$(ip -o route show default | awk '{print $5; exit}')"
IP_ACTUAL="$(ip -o -4 addr show "${IF:-eth0}" 2>/dev/null | awk '{print $4; exit}')"
PUERTA_ACTUAL="$(ip -o route show default | awk '{print $3; exit}')"

# --- Preguntas (o archivo de respuestas) ---
if [ -f "$RESPUESTAS" ]; then
    # shellcheck disable=SC1090
    source "$RESPUESTAS"; rm -f "$RESPUESTAS"; SIN_PREGUNTAS=1
    RED="${RED:-mantener}"; CORTO="${CORTO:-$NOMBRE}"; ADMIN_IPS="${ADMIN_IPS:-10.0.0.0/8 172.16.0.0/12 192.168.0.0/16}"
    for v in DOMINIO NOMBRE CORREO CLAVE_INICIAL CLAVE_ROOT; do [ -n "${!v:-}" ] || { echo "Falta $v en $RESPUESTAS"; exit 1; }; done
    [[ "$DOMINIO" =~ $RE_DOMINIO && "$CORREO" =~ $RE_CORREO ]] || { echo "Dominio o correo no válidos"; exit 1; }
else
    aviso "Bienvenido.\n\nEste asistente deja listo el servidor de su institución: correo, webmail, chat institucional, panel de administración, sitios web y DNS propios.\n\nCada instalación genera sus propias claves de cifrado y firma. Tardará entre 10 y 40 minutos según la conexión.\n\nPuede volver a empezar en cualquier momento con Esc."
    if caja --yesno "Red actual:\n\n  Interfaz: ${IF:-?}\n  IP: ${IP_ACTUAL:-sin IP}\n  Puerta de enlace: ${PUERTA_ACTUAL:-?}\n\n¿Mantener esta configuración de red?\n(«No» para poner una IP fija.)" 16 74; then
        RED=mantener
    else
        RED=fija
        pedir IP "IP fija del servidor con su máscara (ej. 192.168.1.20/24):" "${IP_ACTUAL:-}" "$RE_IPCIDR" "Escriba la IP con su máscara, por ejemplo 192.168.1.20/24."
        pedir PUERTA "Puerta de enlace (router):" "${PUERTA_ACTUAL:-}" "$RE_IP" "Escriba una IP, por ejemplo 192.168.1.1."
        pedir DNS "Servidores DNS para salir a Internet (separados por espacio):" "9.9.9.9 1.1.1.1" '^([0-9]{1,3}\.){3}[0-9]{1,3}( ([0-9]{1,3}\.){3}[0-9]{1,3})*$' "Una o más IP separadas por espacio."
    fi
    pedir DOMINIO "Dominio principal de la institución (sin www), ej. miinstitucion.org.ec:" "" "$RE_DOMINIO" "Dominio no válido: solo minúsculas, números, guiones y puntos."
    pedir NOMBRE "Nombre completo de la institución (aparece en el correo, el panel y la página web):" "" '^[^<>"]{3,100}$' "Entre 3 y 100 caracteres, sin < > ni comillas."
    pedir CORTO "Nombre corto o sigla (ej. para la app del celular):" "$(echo "$NOMBRE" | cut -c1-30)" '^[^<>"]{2,30}$' "Entre 2 y 30 caracteres."
    pedir CORREO "Correo de contacto del responsable técnico (avisos de certificados):" "" "$RE_CORREO" "Correo no válido."
    pedir_clave CLAVE_INICIAL "Clave inicial del panel de administración y del primer buzón (se pedirá cambiarla al entrar):"
    pedir_clave CLAVE_ROOT "Nueva clave de root de este servidor (consola y mantenimiento):"
    pedir ADMIN_IPS "Redes o IP desde donde se administrará (SSH y panel), separadas por espacio:" "10.0.0.0/8 172.16.0.0/12 192.168.0.0/16" '^[0-9a-fA-F:./ ]{7,400}$' "Escriba IP o redes, p. ej. 192.168.1.0/24 203.0.113.7"
    caja --yesno "Resumen\n\n  Dominio: ${DOMINIO}  (servidor mail.${DOMINIO})\n  Institución: ${NOMBRE}  (${CORTO})\n  Responsable: ${CORREO}\n  Red: ${RED}${IP:+  ${IP} vía ${PUERTA}}\n  Administración desde: ${ADMIN_IPS}\n\n¿Instalar ahora?" 18 74 || exit 1
fi

# En un subproceso: con «set -e», un paso que falle termina la instalación, no el asistente.
(
echo "== Primer arranque $(date '+%F %T') — ${DOMINIO}"
set -e
# --- Red fija (systemd-networkd); cloud-init deja de tocar la red ---
if [ "$RED" = "fija" ]; then
    echo "Red fija ${IP} vía ${PUERTA}"
    mkdir -p /etc/cloud/cloud.cfg.d
    echo 'network: {config: disabled}' > /etc/cloud/cloud.cfg.d/99-red-fija.cfg
    rm -f /etc/systemd/network/10-cloud-init-*.network
    { echo "[Match]"; echo "Name=${IF}"; echo; echo "[Network]"; echo "Address=${IP}"; echo "Gateway=${PUERTA}"
      for d in ${DNS:-9.9.9.9}; do echo "DNS=$d"; done; } > /etc/systemd/network/10-servidor.network
    networkctl reload && networkctl reconfigure "$IF"
    sleep 5
fi
hostnamectl set-hostname "mail.${DOMINIO}"
grep -q "mail.${DOMINIO}" /etc/hosts || sed -i "1i 127.0.1.1 mail.${DOMINIO} mail" /etc/hosts

# --- Correo, webmail, panel y aplicaciones del Drive ---
DOMAIN="$DOMINIO" ASSUME_YES=1 CLAVE_INICIAL="$CLAVE_INICIAL" bash "${APP_DIR}/deploy/webmail/instalar.sh"
# --- Secciones del panel propio ---
bash "${APP_DIR}/deploy/webmail/instalar-app.sh" sitios
bash "${APP_DIR}/deploy/webmail/instalar-app.sh" dns
ADMIN_IPS="$ADMIN_IPS" bash "${APP_DIR}/deploy/webmail/instalar-app.sh" cortafuegos
bash "${APP_DIR}/deploy/webmail/instalar-app.sh" chat
bash "${APP_DIR}/deploy/webmail/instalar-app.sh" activesync
bash "${APP_DIR}/deploy/webmail/instalar-app.sh" respaldos
bash "${APP_DIR}/deploy/webmail/instalar-app.sh" actualizar

# --- Identidad de la institución (Personalización) y «Aplicar en todo» ---
URL_BD="$(grep '^DATABASE_URL=' "${APP_DIR}/backend/.env" | cut -d= -f2-)"
python3 - "$URL_BD" "$NOMBRE" "$CORTO" "$CORREO" <<'PY'
import subprocess, sys
url, nombre, corto, correo = sys.argv[1:5]
def lit(t): return "'" + t.replace("'", "''") + "'"
sql = ["CREATE TABLE IF NOT EXISTS branding_settings (key VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"]
# «primeros_pasos» pendiente: al entrar al panel se ofrece subir el logo y completar la información (se puede omitir).
for clave, valor in (("org_name", nombre), ("org_short", corto), ("app_name", f"Correo {corto}"), ("org_email", correo),
                     ("primeros_pasos", '{"estado": "pendiente", "pasos": {}}')):
    sql.append(f"INSERT INTO branding_settings (key, value) VALUES ({lit(clave)}, {lit(valor)}) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();")
subprocess.run(["psql", "-q", "-v", "ON_ERROR_STOP=1", url], input="\n".join(sql), text=True, check=True)
PY
IDENTIDAD="$(python3 -c 'import base64,json,sys; print(base64.urlsafe_b64encode(json.dumps({"nombre":sys.argv[1],"corto":sys.argv[2],"app":"Correo "+sys.argv[2],"correo":sys.argv[3]}).encode()).decode().rstrip("="))' "$NOMBRE" "$CORTO" "$CORREO")"
/usr/local/sbin/maquita-identidad aplicar "$IDENTIDAD" || echo "AVISO: no se pudo aplicar la identidad; hágalo desde el panel (Personalización)."

# --- Acceso al servidor ---
echo "root:${CLAVE_ROOT}" | chpasswd
) > >(tee -a "$REGISTRO") 2>&1
ESTADO=$?
chmod 600 "$REGISTRO"
sleep 1

if [ "$ESTADO" -ne 0 ] || ! systemctl is-active -q maquita-webmail maquita-admin; then
    MENSAJE="La instalación no terminó bien. El detalle está en ${REGISTRO}.\n\nCorrija la causa (casi siempre la conexión a Internet) y vuelva a lanzar el asistente: los pasos ya hechos se repiten sin problema."
    [ -n "${SIN_PREGUNTAS:-}" ] || [ ! -t 0 ] || aviso "$MENSAJE"
    echo -e "$MENSAJE"
    exit 1
fi

cat > "$LEEME" <<EOF
Servidor de ${NOMBRE} — instalado el $(date '+%F %H:%M')

Webmail:  https://mail.${DOMINIO}/webmail/
Panel:    https://mail.${DOMINIO}:8443   (usuario «admin», clave inicial elegida en el asistente)
          El navegador pide antes una clave de acceso: usuario «admin», la misma clave inicial.

Primeros pasos: al entrar al panel aparece la pantalla «Primeros pasos» (logo, información de la
institución y lo que queda). Cada paso se puede omitir y hacer después. En resumen:
  1. Cambiar la clave inicial (panel y navegador).
  2. Subir el logo y la información de la institución (o luego en Personalización → «Aplicar en todo»).
  3. Nuevo dominio: ${DOMINIO} (zona DNS, correo con DKIM, sitio «en construcción», primer buzón).
  4. En el registrador del dominio: servidores de nombres apuntando a este servidor (o los registros
     que muestra «Zonas DNS») y, en el router, los puertos 25, 80, 443, 465, 587, 993 y 53 hacia esta IP.
  5. Zonas DNS → «Certificado del correo» cuando el dominio ya apunte aquí.

Actualizaciones: automáticas cada noche (versiones firmadas). Panel → Protección → Actualizaciones.
Registro de la instalación (con claves internas; no lo comparta): ${REGISTRO}
EOF
chmod 600 "$LEEME"
rm -f "$MARCA"
systemctl disable maquita-primer-arranque.service >/dev/null 2>&1 || true
if [ -z "${SIN_PREGUNTAS:-}" ] && [ -t 0 ]; then
    whiptail --title "$TITULO" "${BOTONES[@]}" --msgbox "Listo.\n\nWebmail: https://mail.${DOMINIO}/webmail/\nPanel:   https://mail.${DOMINIO}:8443  (usuario admin)\n\nLa clave es la que eligió. Los primeros pasos están en ${LEEME}." 16 74 || true
fi
echo "Listo: https://mail.${DOMINIO}:8443 — primeros pasos en ${LEEME}"
exit 0
