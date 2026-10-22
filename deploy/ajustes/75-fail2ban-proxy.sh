#!/usr/bin/env bash
# fail2ban no banea al proxy de confianza y nginx registra la IP real tras él (reportado por Andes, 22/10/2026).
#
# Detrás de un proxy TLS «passthrough» (nginx stream con SNI → servidor:443) el servidor solo ve la IP del
# proxy: las cárceles de los sitios (sitios-escaneo, sitios-abuso, sitios-wp-login) leen sitios-acceso.log y
# banearon esa IP 24 h; el webmail, el portal 8444 y los sitios quedaron 11 h fuera de Internet. jail.local fija
# «ignoreip = 127.0.0.1/8 ::1» y los instaladores lo reescriben. Este ajuste lleva a fail2ban y a nginx lo que
# digan FAIL2BAN_IGNORAR, PROXY_CONFIABLE y PROXY_MODO en /etc/maquita-mail/organizacion.env, y desbanea las
# direcciones de esas listas que estén baneadas. Con proxy, además, lo que banea fail2ban se corta también en
# nginx (acción maquita-nginx-baneo) y el cortafuegos del panel abre 4443 y 4444 solo para el proxy (o, sin
# ese cortafuegos, se avisa). Sin esas variables no cambia nada. Detalle y ejemplo del
# proxy: docs/PROXY-CONFIABLE.md. El trabajo lo hace deploy/hardening/proxy/instalar.sh (copias, «nginx -t»,
# «fail2ban-client -t» y vuelta atrás).
set -euo pipefail
export APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
bash "$APP_DIR/deploy/hardening/proxy/instalar.sh" "$@"
