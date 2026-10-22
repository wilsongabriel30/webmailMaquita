#!/usr/bin/env bash
# Agente Wazuh en este servidor de correo (opcional). El MANAGER (con el indexador OpenSearch y el
# tablero de Wazuh) va en OTRA máquina: docs/WAZUH.md explica cómo montarlo.
#
#   sudo WAZUH_MANAGER=siem.example.org WAZUH_REGISTRATION_PASSWORD='…' \
#        bash deploy/webmail/instalar-app.sh wazuh [--simular]
#
# Variables:
#   WAZUH_MANAGER                dirección (nombre o IP) del manager. Si el agente ya está instalado y
#                                no se indica, se conserva la que tiene.
#   WAZUH_REGISTRATION_PASSWORD  clave de registro del manager (authd), si el manager la exige.
#   WAZUH_AGENT_NAME             nombre del agente (por omisión, el nombre corto de la máquina).
#   WAZUH_AGENT_GROUP            grupo del agente en el manager (por omisión «maquita»).
#   WAZUH_VERSION                versión fija del agente (por omisión la de abajo). Nunca más nueva
#                                que la del manager: el manager rechaza agentes más nuevos que él.
#   WAZUH_GPG_HUELLA             huella de la clave de firma de los paquetes de Wazuh.
#
# Qué hace: repositorio oficial de Wazuh con la clave verificada, agente con versión fija (y retenido
# para que una actualización automática no lo deje más nuevo que el manager), registro contra el
# manager, bloque propio en ossec.conf (registros de Maquita e integridad de archivos), copia del
# diario de systemd si no hay /var/log/mail.log, y el ayudante «maquita-wazuh estado» para el panel.
# Idempotente: se puede repetir (el actualizador lo repite en cada versión).
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
SELF="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SELF}/../.." && pwd)"
OSSEC=/var/ossec
CONF="$OSSEC/etc/ossec.conf"
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
[ "$(id -u)" -eq 0 ] || { echo -e "${RED}Ejecutar como root.${NC}"; exit 1; }

VERSION="${WAZUH_VERSION:-4.12.0}"
HUELLA="${WAZUH_GPG_HUELLA:-0DCFCA5547B19D2A6099506096B3EE5F29111145}"
NOMBRE="${WAZUH_AGENT_NAME:-$(hostname -s)}"
GRUPO="${WAZUH_AGENT_GROUP:-maquita}"
MANAGER="${WAZUH_MANAGER:-}"
[[ "$VERSION" =~ ^[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,3}$ ]] || { echo -e "${RED}WAZUH_VERSION no válida: $VERSION${NC}"; exit 2; }
[[ "$HUELLA" =~ ^[0-9A-F]{40}$ ]] || { echo -e "${RED}WAZUH_GPG_HUELLA debe tener 40 cifras hexadecimales en mayúsculas.${NC}"; exit 2; }
[[ "$NOMBRE" =~ ^[A-Za-z0-9._-]{1,64}$ ]] || { echo -e "${RED}WAZUH_AGENT_NAME no válido: $NOMBRE${NC}"; exit 2; }
[[ "$GRUPO" =~ ^[A-Za-z0-9._-]{1,64}$ ]] || { echo -e "${RED}WAZUH_AGENT_GROUP no válido: $GRUPO${NC}"; exit 2; }

instalada="$(dpkg-query -W -f='${Version}' wazuh-agent 2>/dev/null || true)"
if [ -z "$MANAGER" ] && [ -f "$CONF" ]; then
    MANAGER="$(sed -n '/<client>/,/<\/client>/{s/.*<address>[[:space:]]*\([^<[:space:]]*\)[[:space:]]*<\/address>.*/\1/p}' "$CONF" | head -1)"
fi
[ -n "$MANAGER" ] || { echo -e "${RED}Falta WAZUH_MANAGER (dirección del manager de Wazuh). Ver docs/WAZUH.md.${NC}"; exit 2; }
[[ "$MANAGER" =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$|^[0-9A-Fa-f:.]{2,45}$ ]] \
    || { echo -e "${RED}WAZUH_MANAGER no es un nombre ni una IP válidos: $MANAGER${NC}"; exit 2; }

if [ "$SIMULAR" = 1 ]; then
    if [ "${instalada%%-*}" = "$VERSION" ]; then echo "Agente Wazuh $VERSION ya instalado (manager $MANAGER): se refrescaría el bloque de Maquita."
    else echo "Pendiente: instalar el agente Wazuh $VERSION (ahora: ${instalada:-ninguno}) contra $MANAGER."; fi
    exit 0
fi

echo -e "${GREEN}[1/5] Agente Wazuh $VERSION (manager $MANAGER)...${NC}"
if [ "${instalada%%-*}" != "$VERSION" ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y -qq curl gnupg apt-transport-https >/dev/null
    TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
    curl -fsSL --max-time 60 https://packages.wazuh.com/key/GPG-KEY-WAZUH -o "$TMP/clave.asc"
    huellas="$(gpg --batch --show-keys --with-colons "$TMP/clave.asc" 2>/dev/null | awk -F: '$1=="fpr"{print $10}')"
    grep -qx "$HUELLA" <<<"$huellas" || {
        echo -e "${RED}La clave descargada de packages.wazuh.com no tiene la huella esperada ($HUELLA).${NC}"
        echo "Compruébela en la documentación oficial de Wazuh y, si cambió, indíquela en WAZUH_GPG_HUELLA."
        exit 1; }
    gpg --batch --yes --dearmor -o /usr/share/keyrings/wazuh.gpg "$TMP/clave.asc"
    chmod 644 /usr/share/keyrings/wazuh.gpg
    echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" > /etc/apt/sources.list.d/wazuh.list
    apt-get update -qq >/dev/null
    apt-mark unhold wazuh-agent >/dev/null 2>&1 || true
    WAZUH_MANAGER="$MANAGER" WAZUH_REGISTRATION_PASSWORD="${WAZUH_REGISTRATION_PASSWORD:-}" \
    WAZUH_AGENT_NAME="$NOMBRE" WAZUH_AGENT_GROUP="$GRUPO" \
        apt-get install -y -qq --allow-downgrades "wazuh-agent=${VERSION}-1" >/dev/null
    # Retenido: unattended-upgrades no debe dejarlo más nuevo que el manager.
    apt-mark hold wazuh-agent >/dev/null
else
    echo "  ya instalado"
fi
# Cambio de manager en un agente ya instalado
actual="$(sed -n '/<client>/,/<\/client>/{s/.*<address>[[:space:]]*\([^<[:space:]]*\)[[:space:]]*<\/address>.*/\1/p}' "$CONF" | head -1)"
if [ "$actual" != "$MANAGER" ]; then
    cp -p "$CONF" "$CONF.anterior-$(date +%Y%m%d%H%M%S)"
    sed -i "0,/<address>[^<]*<\/address>/s//<address>${MANAGER}<\/address>/" "$CONF"
    echo "  manager cambiado: ${actual:-ninguno} → $MANAGER"
fi
if [ -n "${WAZUH_REGISTRATION_PASSWORD:-}" ]; then
    install -m 640 -o root -g wazuh /dev/null "$OSSEC/etc/authd.pass"
    printf '%s' "$WAZUH_REGISTRATION_PASSWORD" > "$OSSEC/etc/authd.pass"
fi

echo -e "${GREEN}[2/5] Copia del diario de systemd (si no hay /var/log/mail.log)...${NC}"
install -d -m 750 -o root -g adm /var/log/maquita
install -m 644 "$APP_DIR/deploy/seguridad/logrotate-maquita" /etc/logrotate.d/maquita
if [ ! -s /var/log/mail.log ]; then
    install -m 644 "$SELF/maquita-diario-wazuh.service" /etc/systemd/system/maquita-diario-wazuh.service
    systemctl daemon-reload
    systemctl enable --now maquita-diario-wazuh.service >/dev/null 2>&1
    echo "  maquita-diario-wazuh activo → /var/log/maquita/diario.log"
else
    echo "  hay /var/log/mail.log: no hace falta"
fi

echo -e "${GREEN}[3/5] Registros de Maquita e integridad de archivos en ossec.conf...${NC}"
nuevo="$(mktemp)"
bash "$SELF/bloque-ossec.sh" "$CONF" "$APP_DIR" > "$nuevo"
if ! cmp -s "$nuevo" "$CONF"; then
    copia="$CONF.anterior-$(date +%Y%m%d%H%M%S)"
    cp -p "$CONF" "$copia"
    cat "$nuevo" > "$CONF"
    if [ -x "$OSSEC/bin/wazuh-logcollector" ] && ! "$OSSEC/bin/wazuh-logcollector" -t >/dev/null 2>&1; then
        cat "$copia" > "$CONF"
        echo -e "${RED}Wazuh no acepta el bloque de Maquita; ossec.conf vuelve a como estaba ($copia).${NC}"
        rm -f "$nuevo"; exit 1
    fi
    echo "  bloque actualizado (copia anterior: $copia)"
else
    echo "  sin cambios"
fi
rm -f "$nuevo"

echo -e "${GREEN}[4/5] Ayudante del panel (maquita-wazuh) y maquita-sudo...${NC}"
install -m 755 "$SELF/maquita-wazuh" /usr/local/sbin/maquita-wazuh
install -m 755 "$APP_DIR/deploy/sudoers/maquita-sudo" /usr/local/sbin/maquita-sudo

echo -e "${GREEN}[5/5] Arranque del agente...${NC}"
systemctl daemon-reload
systemctl enable wazuh-agent >/dev/null 2>&1
systemctl restart wazuh-agent
for _ in $(seq 1 15); do
    grep -qs "status='connected'" "$OSSEC/var/run/wazuh-agentd.state" && break
    sleep 2
done
if grep -qs "status='connected'" "$OSSEC/var/run/wazuh-agentd.state"; then
    echo -e "${GREEN}Listo.${NC} Agente «$NOMBRE» conectado a $MANAGER. En el panel: Seguridad → Tableros → Wazuh."
else
    echo -e "${YELLOW}El agente está instalado pero aún no conecta con $MANAGER (puertos 1514 y 1515/TCP, clave de registro).${NC}"
    echo "  Estado: /usr/local/sbin/maquita-wazuh estado · Registro: $OSSEC/logs/ossec.log"
fi
