"""Traduce la configuración a reglas de iptables / ip6tables (cadena propia CORTAFUEGOS).

Orden en INPUT: primero las cadenas de fail2ban (las inserta él al principio), al final el salto a
CORTAFUEGOS. Así una IP bloqueada por fail2ban se rechaza aunque el puerto esté abierto.
Dentro de CORTAFUEGOS: bucle local y conexiones ya establecidas, bloqueos manuales, ICMP, servicios
abiertos según su origen y, al final, registro limitado y descarte de todo lo demás.
"""

import ipaddress

from config import PUERTOS_PROXY, SERVICIOS, apps, bases, proxy

CADENA = "CORTAFUEGOS"


def _es_v6(red):
    return ipaddress.ip_network(red).version == 6


def _abrir(lineas, proto, puertos, origenes, comentario):
    multi = "-m multiport --dports" if ("," in puertos or ":" in puertos) else "--dport"
    for origen in origenes:
        src = f"-s {origen} " if origen else ""
        lineas.append(f'-A {CADENA} {src}-p {proto} {multi} {puertos} -m comment --comment "{comentario}" -j ACCEPT')


def texto(conf, v6=False):
    """Entrada para «iptables-restore --noflush» (tabla filter, solo la cadena propia)."""
    familia_ok = (lambda r: _es_v6(r)) if v6 else (lambda r: not _es_v6(r))
    admin = [a for a in conf["admin"] if familia_ok(a)]
    lineas = ["*filter", f":{CADENA} - [0:0]", f"-F {CADENA}",
              f"-A {CADENA} -i lo -j ACCEPT",
              f"-A {CADENA} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
              f"-A {CADENA} -m conntrack --ctstate INVALID -j DROP",
              # Contenedores locales (Docker) hablando con el propio servidor.
              f"-A {CADENA} -i docker0 -j ACCEPT",
              f"-A {CADENA} -i br-+ -j ACCEPT"]
    for b in conf["bloqueados"]:
        if familia_ok(b["red"]):
            lineas.append(f'-A {CADENA} -s {b["red"]} -m comment --comment "bloqueo manual" -j DROP')
    if v6:
        # ICMPv6 es imprescindible en IPv6 (descubrimiento de vecinos, MTU).
        lineas.append(f"-A {CADENA} -p ipv6-icmp -j ACCEPT")
    else:
        lineas += [f"-A {CADENA} -p icmp --icmp-type echo-request -m limit --limit 5/second --limit-burst 10 -j ACCEPT",
                   f"-A {CADENA} -p icmp --icmp-type echo-request -j DROP",
                   f"-A {CADENA} -p icmp -j ACCEPT"]
    for clave, origen in conf["servicios"].items():
        if origen == "cerrado":
            continue
        s = SERVICIOS[clave]
        origenes = [None] if origen == "todos" else admin
        for proto in ("tcp", "udp"):
            if s.get(proto):
                _abrir(lineas, proto, s[proto], origenes, clave)
    for e in conf["extras"]:
        origenes = [None] if e["origen"] == "todos" else admin
        _abrir(lineas, e["protocolo"], e["puertos"], origenes, ("extra " + e["descripcion"]).strip()[:60])
    for a in apps():
        _abrir(lineas, a["protocolo"], a["puertos"], [None], f"app {a['dominio']}"[:60])
    for b in bases():
        # Acceso remoto a las bases de un sitio: el puerto solo para esas IP o redes (nunca para todos).
        _abrir(lineas, "tcp", b["puerto"], [o for o in b["origenes"] if familia_ok(o)], f"bases {b['dominio']}"[:60])
    # Entradas del proxy de confianza (TLS passthrough con PROXY protocol): solo desde el proxy.
    origenes_proxy = [o for o in proxy() if familia_ok(o)]
    if origenes_proxy:
        _abrir(lineas, "tcp", PUERTOS_PROXY, origenes_proxy, "proxy de confianza")
    # Difusión y multidifusión de la red local: se descartan sin llenar el registro.
    if v6:
        lineas.append(f"-A {CADENA} -d ff00::/8 -j DROP")
    else:
        lineas.append(f"-A {CADENA} -m addrtype --dst-type BROADCAST,MULTICAST -j DROP")
    lineas += [f'-A {CADENA} -m limit --limit 6/minute -j LOG --log-prefix "cortafuegos-descartado: " --log-level 6',
               f"-A {CADENA} -j DROP", "COMMIT", ""]
    return "\n".join(lineas)
