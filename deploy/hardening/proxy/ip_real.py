#!/usr/bin/env python3
"""IP real tras un proxy de confianza y lista blanca de fail2ban (reportado por Andes, 22/10/2026).

Un proxy TLS «passthrough» (nginx stream con SNI) entrega al servidor las conexiones con SU dirección: nginx
registra la IP del proxy en /var/log/nginx/sitios-acceso.log, las cárceles de los sitios la banean y todo el
servidor queda fuera de Internet. Este módulo genera, desde /etc/maquita-mail/organizacion.env:

  FAIL2BAN_IGNORAR   direcciones o redes que fail2ban nunca banea (separadas por espacios).
  PROXY_CONFIABLE    direcciones o redes del proxy de confianza (también se suman a FAIL2BAN_IGNORAR).
  PROXY_MODO         «proxy_protocol» (por defecto: el proxy reenvía TCP con «proxy_protocol on;» al puerto
                     4443, y al 4444 el portal) o «cabecera» (el proxy termina el TLS y manda X-Forwarded-For).

los archivos (rutas relativas a la raíz del sistema):

  etc/fail2ban/jail.d/zz-maquita-ignorar.local   [DEFAULT] ignoreip para TODAS las cárceles. fail2ban lee
                                                 jail.conf, jail.d/*.conf, jail.local y por último jail.d/*.local,
                                                 así que gana al «ignoreip» de jail.local (que los instaladores
                                                 reescriben). «%(known/ignoreip)s» no sirve en [DEFAULT] (bucle de
                                                 interpolación): se copian aquí las listas anteriores.
  etc/nginx/conf.d/maquita-ip-real.conf          set_real_ip_from y real_ip_header en http{}.
  etc/nginx/snippets/maquita-ip-real.conf        «listen 4443 ssl proxy_protocol;» para cada vhost HTTPS.
  etc/nginx/snippets/maquita-ip-real-defecto.conf  lo mismo con default_server (el vhost del webmail).
  etc/nginx/snippets/maquita-ip-real-portal.conf   «listen 4444 ssl proxy_protocol;» (portal de dominio, 8444).

Con proxy (en los dos modos), además, el bloqueo en nginx de lo que banea fail2ban y, en modo proxy_protocol,
los puertos 4443 y 4444 en el cortafuegos del panel solo para el proxy: baneo_proxy.py.

El puerto 443 sigue directo, sin PROXY protocol: la red local, el propio servidor, el guardián y
deploy-webmail.sh (--resolve a 127.0.0.1) siguen entrando como siempre. Los vhosts incluyen los fragmentos
con «include snippets/maquita-ip-real.con[f];»: el corchete lo vuelve un patrón y nginx no se queja si el
archivo no existe (servidor sin proxy).

Todo valor se valida con ipaddress antes de escribirse: nada que no sea una dirección o red llega a los
archivos. Uso (lo llama deploy/hardening/proxy/instalar.sh):

  ip_real.py generar  --raiz R --destino D     escribe en D los archivos que deberían existir; imprime una
                                               línea «ruta relativa» por cada archivo gestionado
  ip_real.py vhosts   --raiz R --destino D [--mail-host H]   vhosts de sites-enabled a los que les falta el
                                               fragmento: escribe la versión nueva en D e imprime su ruta
  ip_real.py ips      --raiz R                 direcciones y redes que nunca deben quedar baneadas
  ip_real.py dentro   --raiz R IP...           de las IP dadas, las que caen en esas redes
  ip_real.py modo     --raiz R                 proxy_protocol, cabecera o nada (sin proxy)
"""

import argparse
import configparser
import glob
import ipaddress
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baneo_proxy  # noqa: E402

ORGANIZACION = "etc/maquita-mail/organizacion.env"
F2B_NUESTRO = "etc/fail2ban/jail.d/zz-maquita-ignorar.local"
NGINX_HTTP = "etc/nginx/conf.d/maquita-ip-real.conf"
SNIPPET = "etc/nginx/snippets/maquita-ip-real.conf"
SNIPPET_DEFECTO = "etc/nginx/snippets/maquita-ip-real-defecto.conf"
SNIPPET_PORTAL = "etc/nginx/snippets/maquita-ip-real-portal.conf"

PUERTO_PROXY = 4443          # HTTPS de webmail y sitios a través del proxy (PROXY protocol)
PUERTO_PROXY_PORTAL = 4444   # portal de dominio (8444) a través del proxy
BASE_IGNORAR = ("127.0.0.1/8", "::1")
MODOS = ("proxy_protocol", "cabecera")
MAX_ENTRADAS = 64
CABECERA = ("# Generado por deploy/hardening/proxy/ip_real.py desde /etc/maquita-mail/organizacion.env.\n"
            "# No editar a mano: cambie FAIL2BAN_IGNORAR, PROXY_CONFIABLE o PROXY_MODO y aplique el ajuste 75\n"
            "# (sudo bash deploy/ajustes/75-fail2ban-proxy.sh).\n")


class ErrorConfig(ValueError):
    """Un valor de organizacion.env que no se puede aplicar."""


def leer_entorno(ruta):
    """CLAVE=valor de un archivo .env (sin shell), como deploy/panel/lib/panel_bd.leer_entorno."""
    valores = {}
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, valor = linea.split("=", 1)
                clave = clave.strip().removeprefix("export ").strip()
                valor = valor.strip()
                if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "'\"":
                    valor = valor[1:-1]
                valores[clave] = valor
    except OSError:
        pass
    return valores


def red(texto, variable="valor", estricta=True):
    """Una dirección o red en forma canónica. Rechaza lo que no lo sea y las redes demasiado amplias. «estricta»
    rechaza además una red con bits de equipo («192.0.2.1/24»: ¿la dirección o la red?); sin ella se toma la red
    (127.0.0.1/8 → 127.0.0.0/8), como hace fail2ban."""
    t = texto.strip()
    if not t or len(t) > 64 or not re.fullmatch(r"[0-9A-Fa-f.:/]+", t):
        raise ErrorConfig(f"{variable}: «{t[:40]}» no es una dirección IP ni una red")
    try:
        r = ipaddress.ip_network(t, strict=estricta)
    except ValueError as e:
        raise ErrorConfig(f"{variable}: «{t}» no es una dirección IP ni una red válida ({e})") from None
    if r.prefixlen < (8 if r.version == 4 else 16):
        raise ErrorConfig(f"{variable}: la red {r} es demasiado amplia (mínimo /8 en IPv4 y /16 en IPv6)")
    if r.num_addresses == 1:
        return str(r.network_address)
    return str(r)


def lista(texto, variable):
    """Lista de direcciones o redes separadas por espacios o comas, sin repetir y en el orden dado."""
    salida = []
    for trozo in re.split(r"[\s,]+", texto or ""):
        if trozo:
            valor = red(trozo, variable)
            if valor not in salida:
                salida.append(valor)
    if len(salida) > MAX_ENTRADAS:
        raise ErrorConfig(f"{variable}: demasiadas entradas ({len(salida)}; máximo {MAX_ENTRADAS})")
    return salida


def configuracion(valores):
    """Lo que piden FAIL2BAN_IGNORAR, PROXY_CONFIABLE y PROXY_MODO, validado."""
    ignorar = lista(valores.get("FAIL2BAN_IGNORAR", ""), "FAIL2BAN_IGNORAR")
    proxy = lista(valores.get("PROXY_CONFIABLE", ""), "PROXY_CONFIABLE")
    modo = (valores.get("PROXY_MODO", "") or "").strip().lower()
    if modo and modo not in MODOS:
        raise ErrorConfig(f"PROXY_MODO: «{modo[:40]}» no vale; use «proxy_protocol» o «cabecera»")
    if not proxy:
        modo = ""
    elif not modo:
        modo = "proxy_protocol"
    return {"ignorar": ignorar, "proxy": proxy, "modo": modo}


def leer_configuracion(raiz):
    return configuracion(leer_entorno(os.path.join(raiz, ORGANIZACION)))


def ignoreip_previos(raiz):
    """Las «ignoreip» de [DEFAULT] que ya tenía el servidor (jail.local y los demás jail.d/*.local), para no
    perderlas al ganarles. Solo las que son direcciones o redes válidas."""
    archivos = [os.path.join(raiz, "etc/fail2ban/jail.local")]
    archivos += sorted(glob.glob(os.path.join(raiz, "etc/fail2ban/jail.d/*.local")))
    nuestro = os.path.join(raiz, F2B_NUESTRO)
    vistos = []
    for ruta in archivos:
        if os.path.abspath(ruta) == os.path.abspath(nuestro) or not os.path.isfile(ruta):
            continue
        cp = configparser.RawConfigParser(strict=False, default_section="__ninguna__")
        try:
            cp.read(ruta, encoding="utf-8")
        except (configparser.Error, UnicodeDecodeError, OSError):
            continue
        if not cp.has_option("DEFAULT", "ignoreip"):
            continue
        for trozo in re.split(r"[\s,]+", cp.get("DEFAULT", "ignoreip")):
            try:
                valor = red(trozo, estricta=False) if trozo else None
            except ErrorConfig:
                continue  # nombres o basura: no se copian
            if valor and valor not in vistos:
                vistos.append(valor)
    return vistos


def ignorar_todas(cfg, previos=()):
    """127.0.0.1/8 ::1, lo que ya había, FAIL2BAN_IGNORAR y el proxy de confianza, sin repetir (127.0.0.0/8 de
    un jail.local es la misma red que 127.0.0.1/8)."""
    salida, redes = [], []
    for valor in (*BASE_IGNORAR, *previos, *cfg["ignorar"], *cfg["proxy"]):
        n = ipaddress.ip_network(valor, strict=False)
        if n not in redes:
            redes.append(n)
            salida.append(valor)
    return salida


def contenido_fail2ban(cfg, previos=()):
    if not cfg["ignorar"] and not cfg["proxy"]:
        return None
    return (CABECERA + "# fail2ban lee jail.conf, jail.d/*.conf, jail.local y por último jail.d/*.local: esta lista\n"
            "# vale para TODAS las cárceles y gana a la de jail.local. Incluye la que ya tenía el servidor.\n"
            "[DEFAULT]\nignoreip = " + " ".join(ignorar_todas(cfg, previos)) + "\n")


def contenido_nginx_http(cfg):
    if not cfg["modo"]:
        return None
    lineas = [CABECERA.rstrip("\n")]
    if cfg["modo"] == "proxy_protocol":
        lineas.append("# El proxy reenvía TCP con PROXY protocol a los puertos %d (HTTPS) y %d (portal); la IP real"
                      % (PUERTO_PROXY, PUERTO_PROXY_PORTAL))
        lineas.append("# llega en la cabecera PROXY. En el 443 directo no hay cabecera PROXY y no cambia nada.")
    else:
        lineas.append("# El proxy termina el TLS y manda X-Forwarded-For: solo se cree si viene de estas redes.")
    lineas += [f"set_real_ip_from {r};" for r in cfg["proxy"]]
    if cfg["modo"] == "proxy_protocol":
        lineas.append("real_ip_header proxy_protocol;")
    else:
        lineas += ["real_ip_header X-Forwarded-For;", "real_ip_recursive on;"]
    return "\n".join(lineas) + "\n" + baneo_proxy.GEO


def contenido_snippet(cfg, puerto, defecto=False):
    """Lo que va en cada server{} HTTPS: en modo proxy_protocol, la entrada dedicada al proxy; en los dos modos,
    el corte de las direcciones baneadas por fail2ban."""
    if not cfg["modo"]:
        return None
    lineas = [CABECERA.rstrip("\n")]
    if cfg["modo"] == "proxy_protocol":
        extra = " default_server" if defecto else ""
        lineas += ["# Entrada dedicada al proxy de confianza (PROXY protocol). Solo la debe usar el proxy: una conexión",
                   "# directa a este puerto no trae la cabecera PROXY y nginx la corta.",
                   f"listen {puerto} ssl proxy_protocol{extra};"]
        if any(":" in r for r in cfg["proxy"]):
            lineas.append(f"listen [::]:{puerto} ssl proxy_protocol{extra};")
    return "\n".join(lineas) + "\n" + baneo_proxy.SI_BANEADO


def archivos(cfg, previos=()):
    """{ruta relativa: contenido o None (no debe existir)} de todos los archivos gestionados."""
    return {
        F2B_NUESTRO: contenido_fail2ban(cfg, previos),
        NGINX_HTTP: contenido_nginx_http(cfg),
        SNIPPET: contenido_snippet(cfg, PUERTO_PROXY),
        SNIPPET_DEFECTO: contenido_snippet(cfg, PUERTO_PROXY, defecto=True),
        SNIPPET_PORTAL: contenido_snippet(cfg, PUERTO_PROXY_PORTAL),
        **baneo_proxy.archivos(cfg, CABECERA),
    }


# --- vhosts --------------------------------------------------------------------------------------------------
def _listen_ipv4(puerto):
    # «listen 443 ssl…;», «listen 0.0.0.0:443 ssl;», «listen 192.0.2.1:443 ssl http2;» (no las de [::]).
    return re.compile(r"^([ \t]*)listen[ \t]+(?:(?:\d{1,3}\.){3}\d{1,3}:|\*:)?%d\b[^;\n]*\bssl\b[^;\n]*;[^\n]*$"
                      % puerto, re.M)


def incluir_en_vhost(texto, defecto=False):
    """El vhost con «include snippets/maquita-ip-real….con[f];» tras cada «listen 443 ssl» de IPv4 (y tras
    «listen 8444 ssl» el del portal). Con «defecto», solo el primero lleva el default_server. None si no cambia:
    ya lo incluye, ya escucha en los puertos del proxy o no tiene HTTPS."""
    if "maquita-ip-real" in texto or re.search(r"\blisten[ \t]+[^;\n]*\b(?:%d|%d)\b" % (PUERTO_PROXY, PUERTO_PROXY_PORTAL), texto):
        return None
    cambios = {"n": 0}

    def poner(nombre):
        def sustituir(m):
            cambios["n"] += 1
            fragmento = nombre
            if nombre == "maquita-ip-real" and defecto and cambios["n"] == 1:
                fragmento = "maquita-ip-real-defecto"
            return f"{m.group(0)}\n{m.group(1)}include snippets/{fragmento}.con[f];  # proxy de confianza (ajuste 75)"
        return sustituir

    nuevo = _listen_ipv4(443).sub(poner("maquita-ip-real"), texto)
    nuevo = _listen_ipv4(8444).sub(poner("maquita-ip-real-portal"), nuevo)
    return nuevo if cambios["n"] else None


def _es_webmail(texto):
    return bool(re.search(r"^[ \t]*location[ \t]+(?:\^~[ \t]+)?/webmail", texto, re.M))


def vhosts_pendientes(raiz, mail_host=""):
    """[(ruta real del vhost, texto nuevo)] de sites-enabled a los que les falta el fragmento del proxy."""
    reales = []
    for enlace in sorted(glob.glob(os.path.join(raiz, "etc/nginx/sites-enabled/*"))):
        real = os.path.realpath(enlace)
        if os.path.isfile(real) and real not in reales:
            reales.append(real)
    textos = {}
    for real in reales:
        try:
            with open(real, encoding="utf-8") as f:
                textos[real] = f.read()
        except (OSError, UnicodeDecodeError):
            continue
    # El vhost del webmail lleva el default_server del 4443: el de MAIL_HOST o, si no, el que sirve /webmail.
    webmail = None
    if mail_host and re.fullmatch(r"[a-z0-9.-]+", mail_host):
        candidato = os.path.realpath(os.path.join(raiz, "etc/nginx/sites-available", mail_host))
        webmail = candidato if candidato in textos else None
    if webmail is None:
        webmail = next((r for r, t in textos.items() if _es_webmail(t) and _listen_ipv4(443).search(t)), None)
    ya_hay_defecto = any("maquita-ip-real-defecto" in t for t in textos.values())
    salida = []
    for real, texto in textos.items():
        nuevo = incluir_en_vhost(texto, defecto=(real == webmail and not ya_hay_defecto))
        if nuevo is not None:
            salida.append((real, nuevo))
    return salida


# --- direcciones protegidas ----------------------------------------------------------------------------------
def protegidas(cfg):
    """Redes que nunca deben quedar baneadas: FAIL2BAN_IGNORAR y PROXY_CONFIABLE."""
    salida = []
    for valor in (*cfg["ignorar"], *cfg["proxy"]):
        if valor not in salida:
            salida.append(valor)
    return salida


def dentro(ips, redes):
    """De las IP dadas (lo que fail2ban tiene baneado), las que caen en alguna de las redes."""
    nets = [ipaddress.ip_network(r, strict=False) for r in redes]
    salida = []
    for texto in ips:
        try:
            ip = ipaddress.ip_address(texto.strip())
        except ValueError:
            continue
        if any(ip.version == n.version and ip in n for n in nets) and str(ip) not in salida:
            salida.append(str(ip))
    return salida


# --- línea de órdenes ----------------------------------------------------------------------------------------
def _escribir(destino, relativa, texto):
    ruta = os.path.join(destino, relativa.lstrip("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)


def main(argv=None):
    p = argparse.ArgumentParser(description="IP real tras un proxy de confianza y lista blanca de fail2ban.")
    p.add_argument("orden", choices=("generar", "vhosts", "ips", "dentro", "modo"))
    p.add_argument("--raiz", default="/")
    p.add_argument("--destino")
    p.add_argument("--mail-host", default="")
    p.add_argument("ip", nargs="*")
    a = p.parse_args(argv)
    try:
        cfg = leer_configuracion(a.raiz)
    except ErrorConfig as e:
        print(f"Error en {os.path.join(a.raiz, ORGANIZACION)}: {e}", file=sys.stderr)
        return 1
    if a.orden in ("generar", "vhosts") and not a.destino:
        print("Falta --destino.", file=sys.stderr)
        return 2
    if a.orden == "generar":
        for relativa, texto in archivos(cfg, ignoreip_previos(a.raiz)).items():
            if texto is not None:
                _escribir(a.destino, relativa, texto)
            print(relativa)
    elif a.orden == "vhosts":
        if cfg["modo"]:  # los dos modos: el corte de los baneados va en los mismos snippets
            raiz = os.path.realpath(a.raiz)
            for real, texto in vhosts_pendientes(a.raiz, a.mail_host.strip().lower()):
                relativa = os.path.relpath(real, raiz)
                _escribir(a.destino, relativa, texto)
                print(relativa)
    elif a.orden == "modo":
        print(cfg["modo"])
    elif a.orden == "ips":
        print(" ".join(protegidas(cfg)))
    else:
        print(" ".join(dentro(a.ip, protegidas(cfg))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
