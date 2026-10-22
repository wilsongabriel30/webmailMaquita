"""Órdenes de las transferencias de zona: «maquita-dns servidor [opciones]» y las del panel.

  maquita-dns servidor                                   muestra la configuración (sin el secreto TSIG)
  maquita-dns servidor --mostrar-secreto                 lo mismo con el secreto y el bloque para el secundario
  maquita-dns servidor --transferir-a IP[,RED] --notificar-a IP[:PUERTO][,…]
                       [--tsig generar|quitar] [--tsig-nombre NOMBRE] [--maestro-oculto si|no]
                       [--quitar-transferencias]
  maquita-dns servidor --zona ZONA --transferir-a … --notificar-a …   ajuste propio de una zona
  maquita-dns servidor --zona ZONA --heredar                          la zona vuelve a lo global

«ninguna» como valor vacía la lista. Cada cambio regenera la declaración de todas las zonas, la comprueba
con named-checkconf y recarga BIND («rndc reconfig»); si algo falla, todo vuelve a como estaba.
"""

import grp
import os

import transferencias as T
import zona as Z
from comun import SERVIDOR, TSIG_BIND, ErrorDns, ejecutar, guardar_json, leer_json

CON_VALOR = {"--transferir-a", "--notificar-a", "--tsig", "--tsig-nombre", "--zona", "--maestro-oculto"}
BANDERAS = {"--quitar-transferencias", "--heredar", "--mostrar-secreto"}
SI_NO = {"si": True, "sí": True, "no": False}


def _leer_texto(ruta):
    try:
        with open(ruta) as f:
            return f.read()
    except FileNotFoundError:
        return None


def _guardar_clave(texto):
    """La clave TSIG nace con 0600 y pasa a root:bind 0640 antes de ocupar su sitio: nunca es legible por
    otros, ni siquiera un instante (escribir() crea el temporal con la umask)."""
    tmp = TSIG_BIND + ".tmp"
    if os.path.lexists(tmp):
        os.remove(tmp)
    with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
        f.write(texto)
    os.chown(tmp, -1, grp.getgrnam("bind").gr_gid)
    os.chmod(tmp, 0o640)
    os.replace(tmp, TSIG_BIND)


def _zonas():
    """[(zona, datos)] de todas las zonas del servidor."""
    return [(z["zona"], Z.leer(z["zona"])) for z in Z.listar()]


def mostrar(secreto=False):
    srv = leer_json(SERVIDOR, {})
    conf = T.de_servidor(srv)
    salida = {"servidor": {k: srv[k] for k in ("ip_correo", "ip_web", "ns") if k in srv},
              "transferencias": T.resumen(conf),
              "zonas_con_ajuste_propio": {nombre: T.resumen(dict(T.defecto(), **T.normalizar_zona(z["transferencias"])))
                                          for nombre, z in _zonas() if T.normalizar_zona(z.get("transferencias"))}}
    tsig = conf.get("tsig")
    if tsig:
        tsig = dict(tsig, archivo=TSIG_BIND, clave_presente=os.path.exists(TSIG_BIND))
        if secreto:
            valor = T.secreto_de(_leer_texto(TSIG_BIND))
            if not valor:
                raise ErrorDns(f"no se encuentra el secreto en {TSIG_BIND}: genere otro con «--tsig generar»")
            tsig["secreto"] = valor
            tsig["para_el_secundario"] = T.para_el_secundario(conf["tsig"], valor, srv.get("ip_correo") or "IP-DEL-MAESTRO")
        salida["transferencias"]["tsig"] = tsig
    return salida


def _recargar(conf_por_zona):
    """Declaración nueva (con named-checkconf dentro), recarga y aviso a los secundarios."""
    Z._escribir_lista()
    ejecutar(["rndc", "reconfig"])
    for nombre, conf in conf_por_zona:
        if conf["notificar_a"]:
            try:
                ejecutar(["rndc", "notify", nombre], tiempo=30)
            except ErrorDns:
                pass  # la zona puede no estar cargada aún; los secundarios la pedirán en el próximo «refresh»


def _restaurar(srv_antes, clave_antes):
    guardar_json(SERVIDOR, srv_antes)
    if clave_antes is None:
        if os.path.exists(TSIG_BIND):
            os.remove(TSIG_BIND)
    else:
        _guardar_clave(clave_antes)
    try:
        Z._escribir_lista()
        ejecutar(["rndc", "reconfig"])
    except ErrorDns:
        pass  # se informa del error original


def aplicar_global(nueva, accion_tsig=None, nombre_tsig=None):
    """Guarda la configuración global y la aplica a todas las zonas, o deja todo como estaba."""
    srv = leer_json(SERVIDOR, {})
    conf = T.normalizar(nueva)
    clave_antes = _leer_texto(TSIG_BIND)
    texto_clave = None
    if accion_tsig == "generar":
        conf["tsig"] = {"nombre": T.nombre_tsig(nombre_tsig or (conf.get("tsig") or {}).get("nombre")), "algoritmo": T.ALGORITMO}
        texto_clave = T.texto_clave(conf["tsig"], T.secreto_nuevo())
    elif accion_tsig == "quitar":
        conf["tsig"] = None
    elif accion_tsig is not None:
        raise ErrorDns("--tsig: use «generar» o «quitar»")
    elif conf.get("tsig") and not T.secreto_de(clave_antes):
        raise ErrorDns(f"falta la clave TSIG en {TSIG_BIND}: genere otra con «--tsig generar» o quítela con «--tsig quitar»")
    T.comprobar_maestro_oculto(conf, srv)
    try:
        if texto_clave:
            _guardar_clave(texto_clave)
        guardar_json(SERVIDOR, dict(srv, transferencias=conf))
        _recargar([(n, T.efectiva(conf, z.get("transferencias"))) for n, z in _zonas()])
    except ErrorDns:
        _restaurar(srv, clave_antes)
        raise
    if accion_tsig == "quitar" and os.path.exists(TSIG_BIND):
        os.remove(TSIG_BIND)  # ya ninguna zona la usa
    salida = mostrar()
    if texto_clave:
        salida["aviso"] = "clave TSIG nueva: «maquita-dns servidor --mostrar-secreto» la muestra para copiarla al secundario"
    return salida


def aplicar_zona(nombre, cambios, heredar=False):
    """Ajuste propio de una zona (o vuelta a lo global con «heredar»)."""
    z = Z.leer(nombre)
    antes = dict(z)
    if heredar:
        z.pop("transferencias", None)
    else:
        z["transferencias"] = T.normalizar_zona(dict(z.get("transferencias") or {}, **cambios))
    conf = T.de_servidor(leer_json(SERVIDOR, {}))
    guardar_json(Z._ruta(nombre), z)
    try:
        _recargar([(nombre, T.efectiva(conf, z.get("transferencias")))])
    except ErrorDns:
        guardar_json(Z._ruta(nombre), antes)
        try:
            Z._escribir_lista()
        except ErrorDns:
            pass
        raise
    return mostrar()


def _opciones(args):
    vistas = {}
    i = 0
    while i < len(args):
        clave, _, valor = args[i].partition("=")
        if clave in BANDERAS and not valor:
            vistas[clave], i = True, i + 1
            continue
        if clave not in CON_VALOR:
            raise ErrorDns(f"opción desconocida: {clave}")
        if not valor:
            if i + 1 >= len(args):
                raise ErrorDns(f"{clave}: falta el valor")
            valor, i = args[i + 1], i + 1
        if clave in vistas:
            raise ErrorDns(f"{clave} repetida")
        vistas[clave], i = valor, i + 1
    return vistas


def orden_cli(args):
    """«maquita-dns servidor [opciones]» desde la consola del servidor."""
    o = _opciones(args)
    if not o:
        return mostrar()
    if set(o) == {"--mostrar-secreto"}:
        return mostrar(secreto=True)
    if "--zona" in o:
        sobran = set(o) - {"--zona", "--transferir-a", "--notificar-a", "--heredar"}
        if sobran or ("--heredar" in o) == bool({"--transferir-a", "--notificar-a"} & set(o)):
            raise ErrorDns("con --zona: --transferir-a y/o --notificar-a, o solo --heredar")
        import registros

        cambios = {}
        if "--transferir-a" in o:
            cambios["transferir_a"] = o["--transferir-a"]
        if "--notificar-a" in o:
            cambios["notificar_a"] = o["--notificar-a"]
        return aplicar_zona(registros.zona_valida(o["--zona"].strip().lower()), cambios, heredar="--heredar" in o)
    if "--heredar" in o or "--mostrar-secreto" in o:
        raise ErrorDns("--heredar va con --zona; --mostrar-secreto, solo")
    if "--tsig-nombre" in o and o.get("--tsig") != "generar":
        raise ErrorDns("--tsig-nombre solo con --tsig generar")
    conf = T.de_servidor(leer_json(SERVIDOR, {}))
    if "--quitar-transferencias" in o:
        conf.update(transferir_a=[], notificar_a=[], maestro_oculto=False)
    if "--transferir-a" in o:
        conf["transferir_a"] = o["--transferir-a"]
    if "--notificar-a" in o:
        conf["notificar_a"] = o["--notificar-a"]
    if "--maestro-oculto" in o:
        if o["--maestro-oculto"].lower() not in SI_NO:
            raise ErrorDns("--maestro-oculto: «si» o «no»")
        conf["maestro_oculto"] = SI_NO[o["--maestro-oculto"].lower()]
    return aplicar_global(conf, o.get("--tsig"), o.get("--tsig-nombre"))


def orden_panel(datos):
    """«maquita-dns transferencias <json-b64>» desde el panel: {"transferir_a", "notificar_a",
    "maestro_oculto", "tsig": "mantener" | "generar" | "quitar"}."""
    accion = datos.get("tsig") or "mantener"
    if accion not in ("mantener", "generar", "quitar"):
        raise ErrorDns("tsig: mantener, generar o quitar")
    actual = T.de_servidor(leer_json(SERVIDOR, {}))
    conf = {"transferir_a": datos.get("transferir_a"), "notificar_a": datos.get("notificar_a"),
            "maestro_oculto": datos.get("maestro_oculto") is True, "tsig": actual.get("tsig")}
    return aplicar_global(conf, None if accion == "mantener" else accion)
