"""Transferencias de zona (AXFR/IXFR) y avisos NOTIFY a servidores secundarios.

La configuración vive en /etc/maquita-dns/servidor.json, clave «transferencias» (fuera del repositorio:
las actualizaciones no la pisan):

  {"transferir_a": ["198.51.100.53", "2001:db8:53::/64"],     IP o redes que pueden pedir la zona
   "notificar_a": [{"ip": "198.51.100.53", "puerto": null}],  a quién se avisa de cada cambio
   "tsig": {"nombre": "transferencias-maquita", "algoritmo": "hmac-sha256"} o null,
   "maestro_oculto": false}

Cada zona puede sobrescribir «transferir_a» y «notificar_a» con su propia clave «transferencias» en
/etc/maquita-dns/<zona>.json. Sin nada configurado se genera lo de siempre: «allow-transfer { none; };»
y «notify no;». El secreto TSIG no está aquí: va en /etc/bind/maquita-tsig.key (root:bind 0640).

Este módulo solo valida y genera texto; escribir, comprobar y recargar lo hace zona.py.
"""

import base64
import ipaddress
import re
import secrets

from comun import ErrorDns

ALGORITMO = "hmac-sha256"
NOMBRE_TSIG = "transferencias-maquita"
MAX_ELEMENTOS = 20
RE_NOMBRE_TSIG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?){0,4}")
RE_SECRETO = re.compile(r"[A-Za-z0-9+/]{43}=")
RE_PUERTO = re.compile(r"[1-9][0-9]{0,4}")
NINGUNA = ("", "ninguna", "ninguno", "none")


def defecto():
    """Lo de siempre: nadie puede pedir la zona y no se avisa a nadie."""
    return {"transferir_a": [], "notificar_a": [], "tsig": None, "maestro_oculto": False}


# --- Validación -----------------------------------------------------------------------------------------


def _lista(valor, campo):
    """Acepta una lista o un texto «a,b,c»; «ninguna» o vacío es la lista vacía."""
    if valor is None:
        return []
    if isinstance(valor, str):
        valor = [] if valor.strip().lower() in NINGUNA else [v for v in valor.split(",")]
    if not isinstance(valor, list) or len(valor) > MAX_ELEMENTOS:
        raise ErrorDns(f"{campo}: hasta {MAX_ELEMENTOS} elementos")
    return valor


def red(valor):
    """IP o red (CIDR) a la que se permite pedir la zona. Nunca «todo Internet»."""
    texto = str(valor).strip()
    try:
        r = ipaddress.ip_network(texto, strict=True)
    except ValueError:
        raise ErrorDns(f"transferir a: «{texto}» no es una IP ni una red válida (p. ej. 198.51.100.53 o 2001:db8::/64)")
    if r.prefixlen == 0 or r.network_address.is_unspecified or r.network_address.is_multicast:
        raise ErrorDns(f"transferir a: «{texto}» abriría la zona a cualquiera")
    if r.num_addresses == 1:
        return str(r.network_address)
    return str(r)


def validar_transferir(valor):
    limpio = []
    for v in _lista(valor, "transferir a"):
        r = red(v)
        if r not in limpio:
            limpio.append(r)
    return limpio


def _ip_destino(texto):
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        raise ErrorDns(f"notificar a: «{texto}» no es una IP válida")
    if ip.is_unspecified or ip.is_multicast:
        raise ErrorDns(f"notificar a: «{texto}» no es una dirección de destino")
    return str(ip)


def destino(valor):
    """«198.51.100.53», «198.51.100.53:5353», «2001:db8::53», «[2001:db8::53]:5353» o {"ip", "puerto"}."""
    if isinstance(valor, dict):
        ip, puerto = str(valor.get("ip", "")).strip(), valor.get("puerto")
        puerto = None if puerto in (None, "") else str(puerto)
    else:
        texto = str(valor).strip()
        m = re.fullmatch(r"\[([0-9a-fA-F:.]+)\](?::([0-9]+))?", texto)
        if m:
            ip, puerto = m.group(1), m.group(2)
        elif texto.count(":") == 1:
            ip, puerto = texto.split(":")
        else:
            ip, puerto = texto, None
    if puerto is not None and not (RE_PUERTO.fullmatch(puerto) and int(puerto) <= 65535):
        raise ErrorDns(f"notificar a: puerto no válido en «{valor}»")
    return {"ip": _ip_destino(ip), "puerto": int(puerto) if puerto is not None and int(puerto) != 53 else None}


def validar_notificar(valor):
    limpio = []
    for v in _lista(valor, "notificar a"):
        d = destino(v)
        if d not in limpio:
            limpio.append(d)
    return limpio


def nombre_tsig(valor):
    nombre = str(valor or NOMBRE_TSIG).strip().lower().rstrip(".")
    if not RE_NOMBRE_TSIG.fullmatch(nombre):
        raise ErrorDns("nombre de la clave TSIG no válido (letras, números, guiones y puntos)")
    return nombre


def normalizar(conf):
    """Configuración global limpia (lo que se guarda en servidor.json)."""
    conf = conf if isinstance(conf, dict) else {}
    tsig = conf.get("tsig")
    if tsig:
        if not isinstance(tsig, dict) or tsig.get("algoritmo", ALGORITMO) != ALGORITMO:
            raise ErrorDns(f"clave TSIG: solo se admite {ALGORITMO}")
        tsig = {"nombre": nombre_tsig(tsig.get("nombre")), "algoritmo": ALGORITMO}
    return {"transferir_a": validar_transferir(conf.get("transferir_a")),
            "notificar_a": validar_notificar(conf.get("notificar_a")),
            "tsig": tsig or None,
            "maestro_oculto": bool(conf.get("maestro_oculto", False))}


def normalizar_zona(propia):
    """Ajuste propio de una zona: solo las claves presentes sobrescriben a las globales."""
    if not propia:
        return None
    if not isinstance(propia, dict):
        raise ErrorDns("ajuste de transferencias de la zona no válido")
    limpio = {}
    if "transferir_a" in propia:
        limpio["transferir_a"] = validar_transferir(propia["transferir_a"])
    if "notificar_a" in propia:
        limpio["notificar_a"] = validar_notificar(propia["notificar_a"])
    return limpio or None


def de_servidor(srv):
    """La configuración global a partir de servidor.json (o la de siempre si no hay)."""
    return normalizar((srv or {}).get("transferencias") or defecto())


def efectiva(conf, propia=None):
    """Lo que se aplica a una zona: lo global con lo propio de la zona encima."""
    final = dict(conf)
    final.update(normalizar_zona(propia) or {})
    return final


def comprobar_maestro_oculto(conf, srv):
    """Maestro oculto: este servidor no figura en los NS (ni, por tanto, en el MNAME del SOA, que es ns1).

    Se comprueba que ninguno de los servidores de nombres apunte a la IP del correo o de la web de este
    servidor y que haya a quién transferir y avisar; si no, el «maestro oculto» no estaría oculto o los
    secundarios nunca tendrían la zona."""
    if not conf.get("maestro_oculto"):
        return
    if not (conf["transferir_a"] or conf.get("tsig")) or not conf["notificar_a"]:
        raise ErrorDns("maestro oculto: indique a qué secundarios se transfiere (--transferir-a) y a cuáles se avisa (--notificar-a)")
    propias = {srv.get("ip_correo"), srv.get("ip_web") or srv.get("ip_correo")} - {None}
    visibles = sorted({n["ip"] for n in srv.get("ns", []) if n.get("ip") in propias})
    if visibles:
        raise ErrorDns("maestro oculto: los servidores de nombres no pueden apuntar a este servidor ("
                       + ", ".join(visibles) + "); póngalos en las IP de los secundarios públicos")


# --- Clave TSIG -----------------------------------------------------------------------------------------


def secreto_nuevo():
    """32 bytes aleatorios en base64 (lo mismo que hace «tsig-keygen -a hmac-sha256»)."""
    return base64.b64encode(secrets.token_bytes(32)).decode()


def texto_clave(tsig, secreto):
    if not RE_SECRETO.fullmatch(secreto):
        raise ErrorDns("secreto TSIG no válido")
    return (f'// Generado por maquita-dns. Clave de las transferencias de zona: no la comparta por correo.\n'
            f'key "{tsig["nombre"]}" {{\n    algorithm {tsig["algoritmo"]};\n    secret "{secreto}";\n}};\n')


def secreto_de(texto):
    m = re.search(r'secret\s+"([A-Za-z0-9+/=]+)"', texto or "")
    return m.group(1) if m else None


def para_el_secundario(tsig, secreto, maestro):
    """Lo que se pega en el named.conf del secundario (BIND) para pedir la zona con la clave."""
    return (texto_clave(tsig, secreto)
            + f'server {maestro} {{ keys {{ "{tsig["nombre"]}"; }}; }};\n')


# --- Texto para BIND ------------------------------------------------------------------------------------


def _permitir(transferir_a, tsig):
    """Cláusula allow-transfer. Con clave TSIG y lista de IP hacen falta las dos cosas (IP Y clave): es la
    forma documentada en el manual de BIND, «!{ !ip; any; }; key k;»."""
    if not transferir_a and not tsig:
        return "allow-transfer { none; };"
    if not tsig:
        return "allow-transfer { " + " ".join(f"{r};" for r in transferir_a) + " };"
    clave = f'key "{tsig["nombre"]}";'
    if not transferir_a:
        return "allow-transfer { " + clave + " };"
    return "allow-transfer { !{ " + " ".join(f"!{r};" for r in transferir_a) + " any; }; " + clave + " };"


def _avisar(notificar_a, tsig):
    if not notificar_a:
        return ["notify no;"]
    partes = []
    for d in notificar_a:
        p = d["ip"] + (f" port {d['puerto']}" if d.get("puerto") else "")
        partes.append(p + (f' key "{tsig["nombre"]}"' if tsig else "") + ";")
    # «explicit»: solo a la lista; no a los NS de la zona (con maestro oculto, ni siquiera se conocen).
    return ["notify explicit;", "also-notify { " + " ".join(partes) + " };"]


def bloque_zona(zona, archivo, conf):
    lineas = ["type primary;", f'file "{archivo}";', _permitir(conf["transferir_a"], conf.get("tsig"))]
    lineas += _avisar(conf["notificar_a"], conf.get("tsig"))
    return f'zone "{zona}" {{\n' + "".join(f"    {x}\n" for x in lineas) + "};"


def texto_lista(zonas, conf, ruta_archivo, ruta_clave):
    """Declaración de todas las zonas. «zonas» es [(nombre, ajuste propio o None)]."""
    bloques = ["// Generado por el panel (Zonas DNS). No editar a mano."]
    if conf.get("tsig"):
        bloques.append(f'include "{ruta_clave}";')
    for zona, propia in zonas:
        bloques.append(bloque_zona(zona, ruta_archivo(zona), efectiva(conf, propia)))
    return "\n".join(bloques) + "\n"


def resumen(conf):
    """Para mostrar: la configuración sin secretos, con las IP de aviso en texto."""
    return dict(conf, notificar_a=[texto_destino(d) for d in conf["notificar_a"]])


def texto_destino(d):
    """{"ip", "puerto"} en la forma que se escribe: 198.51.100.53, 198.51.100.53:5353, [2001:db8::53]:5353."""
    if not d.get("puerto"):
        return d["ip"]
    return (f"[{d['ip']}]" if ":" in d["ip"] else d["ip"]) + f":{d['puerto']}"
