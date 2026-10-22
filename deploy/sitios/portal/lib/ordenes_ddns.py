"""DNS dinámico desde el portal (v1.11): fichas por nombre dentro de la zona de un dominio asignado.

Una ficha permite que un equipo con IP cambiante (la oficina, una cámara, un servidor en casa) mantenga al día
su registro A o AAAA llamando a https://<servidor>/nic/update con el protocolo dyndns2 (publico.py). Cada ficha
tiene su usuario y su contraseña, que valen SOLO para ese nombre.

No se puede pedir para nombres del correo ni de los servidores de nombres (dns_protegido.py y ns1…ns9), ni para
un sitio web de este servidor (su registro lo pone la web), ni donde haya un CNAME o un registro A/AAAA que puso
el asistente del dominio.
"""

import re

import alcance
import ddns
import dns_protegido
import sesion
from errores import ErrorPortal
from ordenes_dns import dns

ETIQUETA = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
RE_NOMBRE = re.compile(rf"{ETIQUETA}(?:\.{ETIQUETA}){{0,4}}")
RE_ID = re.compile(r"[0-9a-f]{8}")
RUTA = "/nic/update"


def _nombre(ctx):
    nombre = ctx.args.get("nombre")
    nombre = nombre.strip().lower().rstrip(".") if isinstance(nombre, str) else ""
    if nombre.endswith("." + ctx.dominio):
        nombre = nombre[: -len(ctx.dominio) - 1]
    if not RE_NOMBRE.fullmatch(nombre) or len(f"{nombre}.{ctx.dominio}") > 200:
        raise ErrorPortal(400, "Nombre no válido: una o varias etiquetas dentro del dominio, p. ej. «casa» u «oficina.quito»")
    servidor_de_nombres = re.fullmatch(r"ns[0-9]", nombre.split(".")[-1])
    if servidor_de_nombres or dns_protegido.es_protegido({"tipo": "A", "nombre": nombre}, ctx.dominio):
        raise ErrorPortal(403, f"{nombre}.{ctx.dominio} es del correo o de los servidores de nombres: "
                               "no puede tener DNS dinámico")
    completo = f"{nombre}.{ctx.dominio}"
    alcance.comprobar_reservado(completo, sesion.nombres_de_portales())
    if alcance.sitio_existe(completo) or alcance.es_alias(completo):
        raise ErrorPortal(409, f"{completo} es un sitio web de este servidor: su registro lo pone la web")
    return nombre


def _comprobar_zona(ctx, nombre):
    for r in dns("ver", ctx.dominio).get("registros", []):
        if dns_protegido.nombre_relativo(r.get("nombre"), ctx.dominio) != nombre:
            continue
        if r.get("tipo") == "CNAME":
            raise ErrorPortal(409, f"{nombre}.{ctx.dominio} tiene un registro CNAME: bórrelo antes")
        if r.get("tipo") in ("A", "AAAA") and r.get("sistema"):
            raise ErrorPortal(409, f"{nombre}.{ctx.dominio} lo puso el asistente del dominio (web o correo): use otro nombre")


def _respuesta(ctx, fichas):
    return {"zona": ctx.dominio, "ruta": RUTA, "fichas": [ddns.visible(f) for f in ddns.de_zona(fichas, ctx.dominio)]}


def ver(ctx):
    return _respuesta(ctx, ddns.cargar())


def crear(ctx):
    nombre = _nombre(ctx)
    _comprobar_zona(ctx, nombre)
    with ddns.cerrojo():
        fichas = ddns.cargar()
        ficha, clave = ddns.nueva(fichas, ctx.dominio, nombre)
        ddns.guardar(fichas)
    return dict(_respuesta(ctx, fichas), creada=ddns.visible(ficha), clave=clave)


def _id(ctx):
    ident = ctx.args.get("id")
    if not isinstance(ident, str) or not RE_ID.fullmatch(ident):
        raise ErrorPortal(400, "Ficha no válida")
    return ident


def clave(ctx):
    ident = _id(ctx)
    with ddns.cerrojo():
        fichas = ddns.cargar()
        ficha = ddns.buscar(fichas, ctx.dominio, ident)
        nueva = ddns.renovar(ficha)
        ddns.guardar(fichas)
    return dict(_respuesta(ctx, fichas), creada=ddns.visible(ficha), clave=nueva)


def borrar(ctx):
    """Quita la ficha. El registro A/AAAA que mantenía se queda en la zona (se ve y se borra en el editor)."""
    ident = _id(ctx)
    with ddns.cerrojo():
        fichas = ddns.cargar()
        ficha = ddns.buscar(fichas, ctx.dominio, ident)
        fichas.remove(ficha)
        ddns.guardar(fichas)
    return _respuesta(ctx, fichas)


ORDENES = {
    "ddns-ver": ("zona", ver),
    "ddns-crear": ("zona", crear),
    "ddns-clave": ("zona", clave),
    "ddns-borrar": ("zona", borrar),
}
