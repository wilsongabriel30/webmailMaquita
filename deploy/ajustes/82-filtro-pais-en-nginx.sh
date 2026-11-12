#!/usr/bin/env bash
# El filtro por país del puerto 443 pasa del cortafuegos a nginx (12/11/2026).
#
# Motivo: el cortafuegos filtra en bloque. Con el 443 cerrado por país, un servidor de otro país no
# puede pedirnos recuperar un correo ni avisar una reacción (/api/federacion/), y quien recibe fuera
# un enlace seguro (/api/safelink) no puede abrirlo. nginx sí ve la ruta: el webmail sigue cerrado
# por país y esas rutas quedan abiertas a todo el mundo. IMAP, envío y los demás puertos no cambian.
#
# Qué hace (solo si esta instalación filtra el 443 por país en nftables; si no, únicamente deja
# instalada la configuración, que sin filtro deja pasar a todos):
#   1. instala el generador de la lista y la configuración de nginx, y genera la lista;
#   2. añade el filtro a cada «server» del 443 (menos mta-sts), valida y recarga nginx;
#   3. comprueba que nginx ya filtra y SOLO entonces retira del cortafuegos la regla del 443.
# Respalda todo; si nginx no valida, restaura y no toca el cortafuegos.
set -euo pipefail
SIMULAR=0; [ "${1:-}" = "--simular" ] && SIMULAR=1
AQUI="$(cd "$(dirname "$0")" && pwd)"; RAIZ="$(cd "$AQUI/../.." && pwd)"
REGLA='tcp dport 443 ip saddr != @paises_permitidos drop'

command -v nginx >/dev/null 2>&1 || { echo "Sin cambios: este servidor no tiene nginx."; exit 0; }
hay_regla() { command -v nft >/dev/null 2>&1 && nft list chain inet filter input 2>/dev/null | grep -qF "$REGLA"; }
nginx_filtra() { nginx -T 2>/dev/null | grep -q 'if (\$fuera_de_pais)'; }

if nginx_filtra && ! hay_regla; then
    echo "Sin cambios: el filtro por país del 443 ya está en nginx."; exit 0
fi
if [ "$SIMULAR" = 1 ]; then
    if hay_regla; then echo "Pendiente: pasar el filtro por país del 443 del cortafuegos a nginx."
    else echo "Pendiente: instalar en nginx el filtro por país del 443 (sin efecto mientras no se filtre por país)."; fi
    exit 0
fi

RESPALDO="/etc/nginx/respaldos/antes-ajuste82.$(date +%Y%m%d%H%M%S)"
mkdir -p "$RESPALDO"; cp -a /etc/nginx/sites-enabled "$RESPALDO/"; cp -a /etc/nginx/conf.d "$RESPALDO/" 2>/dev/null || true

# 1. Generador, configuración y lista
install -m 755 "$RAIZ/deploy/tools/geo-nginx-rebuild.sh" /usr/local/sbin/geo-nginx-rebuild.sh
install -m 755 "$RAIZ/deploy/tools/geo-nginx-lista.py" /usr/local/sbin/geo-nginx-lista.py
/usr/local/sbin/geo-nginx-rebuild.sh
grep -rqs 'geo \$origen_permitido' /etc/nginx/conf.d/ \
    || install -m 644 "$RAIZ/deploy/webmail/nginx/filtro-pais.conf" /etc/nginx/conf.d/maquita-filtro-pais.conf
install -m 644 "$RAIZ/deploy/webmail/nginx/filtro-pais-servidor.conf" /etc/nginx/snippets/filtro-pais.conf
printf '%s\n' '# Mantiene la lista de nginx (filtro por país del 443) igual a los conjuntos del cortafuegos.' \
    '*/10 * * * * root /usr/local/sbin/geo-nginx-rebuild.sh >/dev/null 2>&1' > /etc/cron.d/geo-nginx-rebuild
chmod 644 /etc/cron.d/geo-nginx-rebuild

# 2. El filtro en cada «server» del 443 (menos mta-sts)
python3 - <<'PY'
import glob, re
for f in sorted(glob.glob("/etc/nginx/sites-enabled/*")):
    try:
        lineas = open(f, encoding="utf-8").read().split("\n")
    except (OSError, UnicodeDecodeError):
        continue
    prof, ini, puntos = 0, None, []
    for i, l in enumerate(lineas):
        t = l.split("#")[0]
        if re.match(r"\s*server\s*\{", t) and prof == 0:
            ini = i
        prof += t.count("{") - t.count("}")
        if ini is not None and prof == 0:
            cuerpo = "\n".join(x.split("#")[0] for x in lineas[ini:i + 1])
            sn = re.search(r"server_name\s+([^;]+);", cuerpo)
            if (re.search(r"listen\s+(\[::\]:)?443\b", cuerpo) and sn and "mta-sts" not in sn.group(1)
                    and "filtro-pais.conf" not in cuerpo and "$fuera_de_pais" not in cuerpo):
                j = next(k for k in range(ini, i + 1) if re.search(r"^\s*server_name\s", lineas[k]))
                while ";" not in lineas[j].split("#")[0]:
                    j += 1
                puntos.append(j)
            ini = None
    for j in sorted(puntos, reverse=True):
        sangria = re.match(r"\s*", lineas[j]).group(0)
        lineas.insert(j + 1, sangria + "include snippets/filtro-pais.conf;   # filtro por país (ajuste 82)")
    if puntos:
        open(f, "w", encoding="utf-8").write("\n".join(lineas))
        print(f"  filtro añadido en {len(puntos)} bloque(s) de {f.rsplit('/', 1)[-1]}")
PY
if ! nginx -t >/dev/null 2>&1; then
    cp -a "$RESPALDO/sites-enabled/." /etc/nginx/sites-enabled/
    rm -f /etc/nginx/conf.d/maquita-filtro-pais.conf
    nginx -t >/dev/null 2>&1 || true
    echo "nginx no validó con el filtro: se restauró la configuración (respaldo en $RESPALDO). El cortafuegos no se tocó." >&2
    exit 1
fi
nginx -s reload 2>/dev/null || systemctl reload nginx

# 3. El cortafuegos deja de filtrar el 443 solo cuando nginx ya lo hace
if hay_regla; then
    nginx_filtra || { echo "nginx no muestra el filtro activo: el cortafuegos se deja como está." >&2; exit 1; }
    nft list ruleset > "$RESPALDO/nftables-antes.nft"
    manejador="$(nft -a list chain inet filter input | grep -F "$REGLA" | grep -oE 'handle [0-9]+' | awk '{print $2}' | head -1)"
    nft delete rule inet filter input handle "$manejador"
    if nft list ruleset > /etc/nftables.conf.nuevo 2>/dev/null && nft -c -f /etc/nftables.conf.nuevo 2>/dev/null; then
        mv /etc/nftables.conf.nuevo /etc/nftables.conf
    else
        rm -f /etc/nftables.conf.nuevo
    fi
    echo "Listo: el filtro por país del 443 lo hace nginx; el cortafuegos sigue filtrando IMAP y envío (respaldo en $RESPALDO)."
else
    echo "Listo: filtro por país del 443 instalado en nginx (esta instalación no filtraba el 443 en el cortafuegos; respaldo en $RESPALDO)."
fi
