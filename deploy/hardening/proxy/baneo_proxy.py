"""Bloqueo efectivo para lo que entra por el proxy de confianza (lo usa ip_real.py).

Tras un proxy, los paquetes de un atacante llegan con la IP del proxy: el bloqueo de fail2ban en el cortafuegos
(por la IP real) no los alcanza. Con PROXY_CONFIABLE (en los dos modos) se añade:

  etc/fail2ban/action.d/maquita-nginx-baneo.conf   acción que apunta la IP en /etc/nginx/maquita-baneados.conf
  usr/local/sbin/maquita-nginx-baneo               su ayudante (cerrojo, temporal + mv, recargas agrupadas)
  etc/fail2ban/jail.d/zz-maquita-proxy-baneo.local la acción en las cárceles de nginx y del webmail, además de la
                                                   que ya tengan («%(known/action)s»: se conservan, por ejemplo,
                                                   las acciones del MikroTik)
  en conf.d   «geo $maquita_baneado { default 0; include /etc/nginx/maquita-baneados.conf; }» (geo usa la
              dirección del cliente, que tras realip es la real)
  en los snippets de los vhosts   «if ($maquita_baneado) { return 444; }»

Y, en modo proxy_protocol, si el servidor usa el cortafuegos del panel (deploy/cortafuegos):
  etc/maquita-cortafuegos/proxy.json   los puertos 4443 y 4444 SOLO para PROXY_CONFIABLE (lo lee
                                       config.proxy() de maquita-cortafuegos, persistente al arrancar)
"""

import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
GEO_ARCHIVO = "/etc/nginx/maquita-baneados.conf"
ACCION = "etc/fail2ban/action.d/maquita-nginx-baneo.conf"
AYUDANTE = "usr/local/sbin/maquita-nginx-baneo"
JAIL_BANEO = "etc/fail2ban/jail.d/zz-maquita-proxy-baneo.local"
CORTAFUEGOS = "etc/maquita-cortafuegos/proxy.json"
# Cárceles que leen registros de nginx (sitios y webmail) o del webmail (la IP que le pasa nginx). Una que no
# exista en el servidor queda definida solo con «action» y, sin «enabled = true», no se activa.
CARCELES = ("sitios-wp-login", "sitios-escaneo", "sitios-abuso", "nginx-http-auth", "nginx-limit-req",
            "maquita-webmail")

GEO = ("# Direcciones baneadas por fail2ban (acción maquita-nginx-baneo): con el proxy, el cortafuegos no las\n"
       "# alcanza y los vhosts las cortan con 444. geo usa la IP del cliente, la real tras realip.\n"
       "geo $maquita_baneado {\n    default 0;\n    include maquita-baneados.conf;   # " + GEO_ARCHIVO + "\n}\n")
SI_BANEADO = ("# Baneada por fail2ban (tras el proxy el cortafuegos no la alcanza): se corta sin respuesta.\n"
              "if ($maquita_baneado) { return 444; }\n")


def _repo(nombre):
    with open(os.path.join(DIR, nombre), encoding="utf-8") as f:
        return f.read()


def contenido_jail(cfg, cabecera):
    if not cfg["modo"]:
        return None
    partes = [cabecera + "# La acción maquita-nginx-baneo se suma a la que ya tenga cada cárcel: tras el proxy, el\n"
              "# bloqueo del cortafuegos no alcanza a quien entra por él; el de nginx (por la IP real), sí.\n"]
    for c in CARCELES:
        partes.append(f"[{c}]\naction = %(known/action)s\n         maquita-nginx-baneo\n")
    return "\n".join(partes)


def contenido_cortafuegos(cfg):
    if cfg["modo"] != "proxy_protocol":
        return None
    datos = {"_generado": "deploy/hardening/proxy/instalar.sh (ajuste 75) desde PROXY_CONFIABLE; no editar a mano",
             "origenes": cfg["proxy"]}
    return json.dumps(datos, indent=2, ensure_ascii=False) + "\n"


def archivos(cfg, cabecera):
    """{ruta relativa: contenido o None}. La acción y su ayudante solo se instalan (nunca se quitan: una cárcel
    que se para todavía los llama), así que sin proxy no figuran."""
    salida = {JAIL_BANEO: contenido_jail(cfg, cabecera), CORTAFUEGOS: contenido_cortafuegos(cfg)}
    if cfg["modo"]:
        salida[ACCION] = _repo("fail2ban-maquita-nginx-baneo.conf")
        salida[AYUDANTE] = _repo("maquita-nginx-baneo")
    return salida
