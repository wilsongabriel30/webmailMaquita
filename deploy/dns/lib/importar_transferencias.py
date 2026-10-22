"""Pasa a la configuración las transferencias que hoy están escritas en /etc/bind/maquita-zonas.conf.

Para los servidores que parcheaban zona.py a mano: hasta ahora la siguiente zona nueva (o una
actualización) volvía a escribir «allow-transfer { none; }» y los secundarios dejaban de recibir la zona.
Lo usa el ajuste 67-dns-transferencias.sh:

  maquita-dns transferencias-importar [--simular]

Devuelve {"estado": "sin-cambios" | "pendiente" | "revisar" | "listo", ...}. Con claves TSIG, listas de
control con nombre o cualquier cosa que no sea una IP o red, no importa nada y pide revisarlo a mano.
"""

import collections
import json
import re

import transferencias as T
import zona as Z
from comun import LISTA_BIND, SERVIDOR, ErrorDns, guardar_json, leer_json

RE_ZONA = re.compile(r'zone\s+"([^"]+)"\s*\{(.*?)\n\};', re.DOTALL)
RE_CLAUSULA = r"{}\s*\{{([^{{}}]*)\}};"


def _elementos(cuerpo, clausula):
    m = re.search(RE_CLAUSULA.format(clausula), cuerpo)
    if not m:
        return []
    return [e.strip() for e in m.group(1).split(";") if e.strip() and e.strip() != "none"]


def leer_actual(texto):
    """{zona: {"transferir_a": [...], "notificar_a": [...]}} tal como lo declara hoy BIND."""
    zonas = {}
    for nombre, cuerpo in RE_ZONA.findall(texto or ""):
        if re.search(r"\bkey\b|!\s*\{", cuerpo):
            raise ErrorDns(f"la zona {nombre} usa claves TSIG o listas anidadas: revísela a mano")
        avisos = []
        for e in _elementos(cuerpo, "also-notify"):
            m = re.fullmatch(r"([0-9a-fA-F:.]+)(?:\s+port\s+([0-9]+))?", e)
            if not m:
                raise ErrorDns(f"la zona {nombre} avisa a «{e}»: revísela a mano")
            avisos.append({"ip": m.group(1), "puerto": m.group(2)})
        zonas[nombre] = T.normalizar_zona({"transferir_a": _elementos(cuerpo, "allow-transfer"),
                                           "notificar_a": avisos})
    return zonas


def _clave(c):
    return json.dumps(c, sort_keys=True)


def importar(simular=False):
    srv = leer_json(SERVIDOR, {})
    if "transferencias" in srv:
        return {"estado": "sin-cambios", "motivo": "las transferencias ya están en la configuración"}
    try:
        with open(LISTA_BIND) as f:
            texto = f.read()
    except FileNotFoundError:
        return {"estado": "sin-cambios", "motivo": "no hay zonas declaradas"}
    try:
        actual = leer_actual(texto)
    except ErrorDns as e:
        return {"estado": "revisar", "motivo": str(e)}
    if not any(c["transferir_a"] or c["notificar_a"] for c in actual.values()):
        return {"estado": "sin-cambios", "motivo": "ninguna zona transfiere ni avisa a secundarios"}
    # Lo más repetido pasa a ser lo global; las zonas distintas guardan su ajuste propio.
    comun, _ = collections.Counter(_clave(c) for c in actual.values()).most_common(1)[0]
    glob = json.loads(comun)
    propias = {z: c for z, c in actual.items() if _clave(c) != comun}
    resultado = {"global": T.resumen(dict(T.defecto(), **glob)), "zonas_con_ajuste_propio": sorted(propias)}
    if simular:
        return dict(resultado, estado="pendiente")
    conocidas = {z["zona"] for z in Z.listar()}
    for nombre, c in propias.items():
        if nombre in conocidas:
            z = Z.leer(nombre)
            z["transferencias"] = c
            guardar_json(Z._ruta(nombre), z)
    import ordenes_transferencias as O

    O.aplicar_global(dict(T.defecto(), **glob))
    return dict(resultado, estado="listo")
