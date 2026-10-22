# maquita-vigilantes (repo) — el servidor visto desde Internet y el proxy de confianza.
# Se carga con «. /usr/local/lib/maquita-vigilantes/lib-proxy.sh» después de lib-avisos.sh (que lee
# /etc/maquita-mail/organizacion.env). Nació del incidente de Andes (22/10/2026): las cárceles de los sitios
# banearon la IP del proxy TLS, el servidor quedó 11 h sin webmail para Internet y el guardián, que solo
# probaba localhost, lo vio todo sano. Detalle: docs/PROXY-CONFIABLE.md.
# shellcheck shell=bash

# Nombre público del correo: MAIL_HOST de backend/.env y, si no, el del servidor.
vig_nombre_publico() {
    local env="${MAQUITA_BACKEND_ENV:-/opt/maquita-webmail/backend/.env}" nombre=""
    [ -r "$env" ] && nombre="$(grep -E '^MAIL_HOST=' "$env" | head -1 | cut -d= -f2- | tr -d "\"' " || true)"
    [[ "$nombre" =~ ^[A-Za-z0-9.-]+$ ]] || nombre=""
    echo "${nombre:-$(vig_servidor)}"
}

# Direcciones y redes que nunca deberían estar baneadas (FAIL2BAN_IGNORAR y PROXY_CONFIABLE).
vig_redes_protegidas() {
    echo "${FAIL2BAN_IGNORAR:-} ${PROXY_CONFIABLE:-}" | tr ',' ' ' | xargs
}

# «ip cárcel» por cada dirección baneada ahora por fail2ban que cae en esas redes. Nada si no hay redes,
# fail2ban no está o no responde. Los valores van a Python como argumentos (nunca como código).
vig_baneadas_protegidas() {
    local redes j ips
    redes="$(vig_redes_protegidas)"
    [ -n "$redes" ] && command -v fail2ban-client >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1 || return 0
    for j in $(fail2ban-client status 2>/dev/null | sed -n 's/.*Jail list:[[:space:]]*//p' | tr ',' ' '); do
        ips="$(fail2ban-client status "$j" 2>/dev/null | sed -n 's/.*Banned IP list:[[:space:]]*//p' || true)"
        [ -n "${ips// /}" ] || continue
        # shellcheck disable=SC2086
        python3 - "$j" "$redes" $ips <<'PY'
import ipaddress, sys
carcel, redes, ips = sys.argv[1], sys.argv[2].split(), sys.argv[3:]
nets = []
for r in redes:
    try:
        nets.append(ipaddress.ip_network(r, strict=False))
    except ValueError:
        pass
for t in ips:
    try:
        ip = ipaddress.ip_address(t)
    except ValueError:
        continue
    if any(ip.version == n.version and ip in n for n in nets):
        print(ip, carcel)
PY
    done
}
