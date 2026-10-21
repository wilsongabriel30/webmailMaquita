"""Órdenes de la zona DNS de un dominio asignado (solo el dominio exacto, nunca un subdominio).

Se ven todos los registros, cada uno marcado «protegido» o no; los protegidos (los del correo) no se
pueden crear, cambiar ni borrar. Para cambiar o borrar se busca antes el registro en la zona: así se
sabe qué es lo que se toca, no solo lo que se pide.
"""

import base64
import json
import re

import ayudantes
import dns_protegido
from errores import ErrorPortal

RE_ID = re.compile(r"^[0-9a-f]{8}$")
CAMPOS = ("nombre", "tipo", "valor", "ttl", "prioridad")


def dns(*args):
    return ayudantes.ejecutar("maquita-dns", list(args), tiempo=120)


def _b64(datos):
    texto = base64.urlsafe_b64encode(json.dumps(datos, ensure_ascii=False).encode()).decode().rstrip("=")
    if len(texto) > 8000:
        raise ErrorPortal(400, "Registro demasiado largo")
    return texto


def _registro(ctx):
    """El registro pedido, solo con sus campos (la marca «sistema» la pone maquita-dns, no el portal)."""
    reg = ctx.args.get("registro")
    if not isinstance(reg, dict):
        raise ErrorPortal(400, "Registro no válido")
    limpio = {k: reg[k] for k in CAMPOS if reg.get(k) is not None}
    if dns_protegido.es_protegido(limpio, ctx.dominio):
        raise ErrorPortal(403, "Ese registro es del correo del dominio: no se puede crear ni cambiar desde el portal")
    return limpio


def _actual(ctx):
    reg_id = ctx.args.get("id")
    if not isinstance(reg_id, str) or not RE_ID.match(reg_id):
        raise ErrorPortal(400, "Registro no válido")
    for r in dns("ver", ctx.dominio).get("registros", []):
        if r.get("id") == reg_id:
            if dns_protegido.es_protegido(r, ctx.dominio):
                raise ErrorPortal(403, "Ese registro es del correo del dominio: no se puede cambiar ni borrar desde el portal")
            return reg_id
    raise ErrorPortal(404, "No encontrado")


def ver(ctx):
    return dns_protegido.marcar(dns("ver", ctx.dominio), ctx.dominio)


def agregar(ctx):
    return dns("agregar", ctx.dominio, _b64(_registro(ctx)))


def modificar(ctx):
    nuevo = _registro(ctx)
    return dns("modificar", ctx.dominio, _actual(ctx), _b64(nuevo))


def borrar(ctx):
    return dns("borrar-registro", ctx.dominio, _actual(ctx))
