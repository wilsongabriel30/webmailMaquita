"""Certificado propio por dominio de cliente (CERTIFICADO_MODO=por-dominio en organizacion.env).

En hospedaje, los clientes no deben compartir certificado: es público (Certificate Transparency) y
relacionaría a organizaciones distintas. En este modo cada dominio de correo con zona en el servidor,
salvo el principal, tiene su linaje mail.<dominio> con mail., webmail., autoconfig., autodiscover. (y
mta-sts. si se publica), solo con los nombres que desde Internet ya apuntan a la IP del correo.

Mientras mail.<dominio> no resuelve aquí (dominio sin delegar), sus nombres se sirven con el certificado
del servidor (provisional) y se vuelve a mirar en cada pasada, sin pedir nada a Let's Encrypt. Cuando
resuelve, se emite y certificado_sni.py lo instala sin intervención. Un linaje que falla espera cada vez
más antes de reintentarse (certificado_espera.py).
"""

import os
import time

import certificado_base as B
import certificado_espera as E
import zona as Z
from comun import ErrorDns

PREFIJOS = ("mail", "webmail", "autoconfig", "autodiscover", "mta-sts")
SITIOS_ACTIVOS = "/etc/nginx/sites-enabled"


def linaje(dominio):
    return f"mail.{dominio}"


def dominios_cliente(host, dominio_principal, zonas=None):
    """Zonas del servidor que llevan certificado propio: todas menos la del servidor."""
    if zonas is None:
        zonas = [z["zona"] for z in Z.listar()]
    return sorted(z for z in set(zonas) if z != dominio_principal and linaje(z) != host)


def candidatos(dominio):
    nombres = []
    for prefijo in PREFIJOS:
        if prefijo == "mta-sts" and not os.path.exists(f"{SITIOS_ACTIVOS}/mta-sts.{dominio}"):
            continue
        nombres.append(f"{prefijo}.{dominio}")
    return nombres


def _texto_espera(segundos):
    horas = max(1, round(segundos / 3600))
    return f"{horas} h" if horas < 48 else f"{round(horas / 24)} días"


def procesar(dominio, ip, correo, forzar=False, ahora=None):
    """Una pasada para un dominio: emite o amplía su linaje si hay nombres nuevos que ya apuntan aquí."""
    ahora = ahora or time.time()
    l = linaje(dominio)
    salida = {"dominio": dominio, "linaje": l}
    apuntan = [n for n in candidatos(dominio) if B.apunta(n, ip)]
    actual = B.leer_certificado(l)
    if l not in apuntan:
        motivo = f"{l} todavía no apunta a {ip} desde Internet"
        if actual:
            return dict(salida, estado="activo", nombres=actual["nombres"], vence=actual["vence"], motivo=motivo)
        return dict(salida, estado="pendiente", motivo=motivo + ": se usa el certificado del servidor")
    cubiertos = set(actual["nombres"]) if actual else set()
    nuevos = [n for n in apuntan if n not in cubiertos]
    if not nuevos:
        return dict(salida, estado="activo", nombres=actual["nombres"], vence=actual["vence"])
    falta = E.espera(l, ahora)
    if falta and not forzar:
        previo = E.de_linaje(l)
        return dict(salida, estado="en-espera", nombres=(actual or {}).get("nombres", []),
                    motivo=f"falló ({previo.get('error', '')}); se reintenta en {_texto_espera(falta)}")
    try:
        B.pedir(l, apuntan, correo)
    except ErrorDns as e:
        pausa = E.fallo(l, e, ahora)
        return dict(salida, estado="error", nombres=(actual or {}).get("nombres", []),
                    motivo=f"{e}; se reintenta en {_texto_espera(pausa)}")
    E.exito(l, ahora)
    nuevo = B.leer_certificado(l) or {"nombres": apuntan, "vence": ""}
    return dict(salida, estado="emitido", nombres=nuevo["nombres"], vence=nuevo["vence"], nuevos=nuevos,
                omitidos=[n for n in candidatos(dominio) if n not in apuntan])


def pasada(host, dominio_principal, ip, forzar=False):
    """Todos los dominios de cliente. Un dominio que falla no detiene a los demás."""
    correo = f"postmaster@{dominio_principal}"
    return [procesar(d, ip, correo, forzar=forzar) for d in dominios_cliente(host, dominio_principal)]


def activos(host, dominio_principal):
    """{dominio: [nombres]} de los dominios de cliente cuyo linaje ya existe (lo que se instala por SNI)."""
    salida = {}
    for d in dominios_cliente(host, dominio_principal):
        l = linaje(d)
        if B.existe(l):
            cert = B.leer_certificado(l)
            if cert:
                salida[d] = cert["nombres"]
    return salida


def estado(host, dominio_principal):
    """Para el panel, sin consultar el DNS: linaje, nombres, vencimiento y espera de cada dominio."""
    lista = []
    for d in dominios_cliente(host, dominio_principal):
        l = linaje(d)
        cert = B.leer_certificado(l)
        fila = {"dominio": d, "linaje": l, "emitido": bool(cert)}
        if cert:
            fila.update(nombres=cert["nombres"], vence=cert["vence"])
        previo = E.de_linaje(l)
        if previo.get("fallos"):
            fila.update(error=previo.get("error", ""), espera=E.espera(l))
        lista.append(fila)
    return lista
