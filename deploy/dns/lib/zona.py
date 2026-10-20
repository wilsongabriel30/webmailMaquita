"""Zonas DNS del servidor: datos en /etc/maquita-dns/<zona>.json, archivo de BIND generado.

El servidor es autoritativo solo de sus zonas (sin recursión). Cada cambio regenera el archivo de
zona con número de serie nuevo, lo valida con named-checkzone y recarga solo esa zona. Si la
validación falla, el archivo anterior queda intacto.
"""

import glob
import grp
import os
import re
import time

import dkim
import registros as R
from comun import DATOS, LISTA_BIND, ZONAS_BIND, ErrorDns, ejecutar, escribir, guardar_json, leer_json, servidor


def _ruta(zona):
    return os.path.join(DATOS, f"{zona}.json")


def leer(zona):
    R.zona_valida(zona)
    try:
        return leer_json(_ruta(zona))
    except FileNotFoundError:
        raise ErrorDns(f"la zona {zona} no existe")


def listar():
    salida = []
    for ruta in sorted(glob.glob(os.path.join(DATOS, "*.json"))):
        if os.path.basename(ruta) == "servidor.json":
            continue
        z = leer_json(ruta)
        salida.append({"zona": z["zona"], "registros": len(z["registros"]), "serial": z.get("serial"),
                       "creada": z.get("creada")})
    return salida


def _siguiente_serial(actual):
    hoy = int(time.strftime("%Y%m%d")) * 100
    return max(hoy, int(actual or 0) + 1)


def _registros_base(zona, srv, con_web=True):
    """Todo lo que necesitan el correo, la web y la autoconfiguración de los clientes."""
    ip_correo = srv["ip_correo"]
    ip_web = srv.get("ip_web") or ip_correo
    base = []

    def r(nombre, tipo, valor, prioridad=None):
        base.append(R.normalizar({"nombre": nombre, "tipo": tipo, "valor": valor, "prioridad": prioridad,
                                  "sistema": True}, zona))

    for ns in srv["ns"]:
        r("@", "NS", ns["nombre"])  # ns1 → ns1.<zona>.
        r(ns["nombre"], "A", ns["ip"])
    if con_web:
        r("@", "A", ip_web)
        r("www", "A", ip_web)
    r("mail", "A", ip_correo)
    r("autodiscover", "CNAME", "mail")
    r("autoconfig", "CNAME", "mail")
    r("@", "MX", "mail", 10)
    r("@", "TXT", f"v=spf1 mx ip4:{ip_correo} -all")
    r("_dmarc", "TXT", f"v=DMARC1; p=quarantine; adkim=s; aspf=s; rua=mailto:postmaster@{zona}")
    r("mail._domainkey", "TXT", dkim.registro(zona))
    r("_smtp._tls", "TXT", f"v=TLSRPTv1; rua=mailto:postmaster@{zona}")
    if os.path.exists(f"/etc/nginx/sites-enabled/mta-sts.{zona}"):
        # MTA-STS solo si el servidor publica la política de ese dominio (si no, el registro mentiría).
        r("mta-sts", "A", ip_correo)
        r("_mta-sts", "TXT", f"v=STSv1; id={time.strftime('%Y%m%d%H%M%S')}")
    r("_autodiscover._tcp", "SRV", "1 443 mail", 0)
    r("_imaps._tcp", "SRV", "1 993 mail", 0)
    r("_submission._tcp", "SRV", "1 587 mail", 0)
    r("_submissions._tcp", "SRV", "1 465 mail", 0)
    r("@", "CAA", "issue letsencrypt.org")
    return base


def crear(zona, con_web=True):
    R.zona_valida(zona)
    if os.path.exists(_ruta(zona)):
        raise ErrorDns(f"la zona {zona} ya existe")
    srv = servidor()
    datos = {
        "zona": zona,
        "serial": None,
        "creada": time.strftime("%Y-%m-%d %H:%M"),
        "hostmaster": f"hostmaster.{zona}.",
        "primario": f"{srv['ns'][0]['nombre']}.{zona}.",
        "registros": _registros_base(zona, srv, con_web),
    }
    aplicar(datos)
    return ver(zona)


def ver(zona):
    z = leer(zona)
    return {"zona": z["zona"], "serial": z["serial"], "registros": z["registros"],
            "servidores": [f"{ns['nombre']}.{zona}" for ns in servidor().get("ns", [])]}


def agregar(zona, reg):
    z = leer(zona)
    nuevo = R.normalizar(reg, zona)
    z["registros"].append(nuevo)
    aplicar(z)
    return nuevo


def modificar(zona, reg_id, reg):
    z = leer(zona)
    for i, actual in enumerate(z["registros"]):
        if actual["id"] == reg_id:
            reg = dict(reg, id=reg_id, sistema=actual.get("sistema", False))
            z["registros"][i] = R.normalizar(reg, zona)
            aplicar(z)
            return z["registros"][i]
    raise ErrorDns("registro no encontrado")


def borrar_registro(zona, reg_id):
    z = leer(zona)
    restantes = [r for r in z["registros"] if r["id"] != reg_id]
    if len(restantes) == len(z["registros"]):
        raise ErrorDns("registro no encontrado")
    if not any(r["tipo"] == "NS" and r["nombre"] == "@" for r in restantes):
        raise ErrorDns("la zona debe conservar al menos un servidor de nombres (NS)")
    z["registros"] = restantes
    aplicar(z)
    return {"borrado": reg_id}


def borrar(zona):
    z = leer(zona)
    os.remove(_ruta(zona))
    ruta_bind = os.path.join(ZONAS_BIND, f"db.{zona}")
    if os.path.exists(ruta_bind):
        os.replace(ruta_bind, ruta_bind + time.strftime(".borrada-%Y%m%d%H%M%S"))
    _escribir_lista()
    ejecutar(["rndc", "reconfig"])
    return {"zona": z["zona"], "borrada": True}


def cambiar_ips(anterior, srv):
    """Al cambiar las IP del servidor (p. ej. al llegar el enlace propio): en todas las zonas se rehacen los
    servidores de nombres y se pasan a la IP nueva los registros A y el SPF que apuntaban a la anterior.
    Los registros que apuntan a otros servidores no se tocan. Devuelve las zonas cambiadas."""
    viejas = {}
    for clave in ("ip_correo", "ip_web"):
        if anterior.get(clave) and anterior[clave] != srv[clave]:
            viejas.setdefault(anterior[clave], srv[clave])
    for ns in anterior.get("ns", []):
        viejas.setdefault(ns["ip"], srv["ip_web"])
    nombres_ns = {ns["nombre"] for ns in anterior.get("ns", [])} | {ns["nombre"] for ns in srv["ns"]}
    cambiadas = []
    for ruta in sorted(glob.glob(os.path.join(DATOS, "*.json"))):
        if os.path.basename(ruta) == "servidor.json":
            continue
        z = leer_json(ruta)
        zona = z["zona"]
        propios = [r for r in z["registros"]
                   if not (r.get("sistema") and ((r["tipo"] == "NS" and r["nombre"] == "@")
                                                 or (r["tipo"] == "A" and r["nombre"] in nombres_ns)))]
        for r in propios:
            if r["tipo"] == "A" and r["valor"] in viejas:
                r["valor"] = viejas[r["valor"]]
            elif r["tipo"] == "TXT" and r["valor"].startswith("v=spf1"):
                r["valor"] = re.sub(r"ip4:([0-9.]+)", lambda m: "ip4:" + viejas.get(m.group(1), m.group(1)), r["valor"])
        servidores = []
        for ns in srv["ns"]:
            servidores.append(R.normalizar({"nombre": "@", "tipo": "NS", "valor": ns["nombre"], "sistema": True}, zona))
            servidores.append(R.normalizar({"nombre": ns["nombre"], "tipo": "A", "valor": ns["ip"], "sistema": True}, zona))
        nuevos = servidores + propios
        if [(r["nombre"], r["tipo"], r["valor"]) for r in nuevos] != [(r["nombre"], r["tipo"], r["valor"]) for r in z["registros"]]:
            z["registros"] = nuevos
            z["primario"] = f"{srv['ns'][0]['nombre']}.{zona}."
            aplicar(z)
            cambiadas.append(zona)
    return cambiadas


def _texto_zona(z):
    lineas = [
        "; Generado por el panel (Zonas DNS). No editar a mano: el panel lo regenera.",
        "$TTL 3600",
        f"@ IN SOA {z['primario']} {z['hostmaster']} ( {z['serial']} 3600 900 1209600 3600 )",
    ]
    orden = {t: i for i, t in enumerate(("NS", "A", "AAAA", "CNAME", "MX", "TXT", "SRV", "CAA"))}
    for r in sorted(z["registros"], key=lambda r: (r["nombre"] != "@", r["nombre"], orden.get(r["tipo"], 9))):
        lineas.append(R.linea(r))
    return "\n".join(lineas) + "\n"


def _escribir_lista():
    """Declaración de todas las zonas para BIND (named.conf.local incluye este archivo)."""
    bloques = ["// Generado por el panel (Zonas DNS). No editar a mano."]
    for ruta in sorted(glob.glob(os.path.join(DATOS, "*.json"))):
        if os.path.basename(ruta) == "servidor.json":
            continue
        zona = leer_json(ruta)["zona"]
        bloques.append(
            f'zone "{zona}" {{\n    type primary;\n    file "{ZONAS_BIND}/db.{zona}";\n'
            "    allow-transfer { none; };\n    notify no;\n};"
        )
    escribir(LISTA_BIND, "\n".join(bloques) + "\n", 0o644, grp.getgrnam("bind").gr_gid)


def aplicar(z):
    """Valida el conjunto, genera el archivo, lo comprueba con named-checkzone y recarga."""
    R.comprobar_conjunto(z["registros"])
    if not any(r["tipo"] == "NS" and r["nombre"] == "@" for r in z["registros"]):
        raise ErrorDns("la zona necesita al menos un servidor de nombres (NS)")
    z["serial"] = _siguiente_serial(z.get("serial"))
    os.makedirs(ZONAS_BIND, exist_ok=True)
    final = os.path.join(ZONAS_BIND, f"db.{z['zona']}")
    nueva = final + ".nueva"
    escribir(nueva, _texto_zona(z), 0o644, grp.getgrnam("bind").gr_gid)
    try:
        ejecutar(["named-checkzone", z["zona"], nueva])
    except ErrorDns as e:
        os.remove(nueva)
        raise ErrorDns(f"la zona no pasa la validación de BIND: {e}")
    nueva_zona = not os.path.exists(_ruta(z["zona"]))
    os.replace(nueva, final)
    guardar_json(_ruta(z["zona"]), z)
    if nueva_zona or not _declarada(z["zona"]):
        _escribir_lista()
        ejecutar(["rndc", "reconfig"])
    else:
        ejecutar(["rndc", "reload", z["zona"]])


def _declarada(zona):
    try:
        with open(LISTA_BIND) as f:
            return f'zone "{zona}"' in f.read()
    except FileNotFoundError:
        return False
