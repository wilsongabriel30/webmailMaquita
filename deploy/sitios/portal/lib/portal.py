"""Atender una petición del portal: sesión, orden de la lista, alcance, nombres reservados y ejecución.

El orden de las comprobaciones importa: primero quién es (sesión en la base), después si la orden existe,
después si el sitio es suyo (404 si no: lo ajeno ni se confirma) y solo entonces si el nombre está
reservado (403). Cada orden de ORDENES dice qué alcance pide:
- "ninguno": no lleva dominio (listar, catálogo);
- "nuevo":   un sitio de su alcance que todavía no existe (crear);
- "sitio":   un sitio de su alcance que existe;
- "zona":    exactamente uno de sus dominios asignados (DNS).
"""

import alcance
import ayudantes
import ordenes_avanzado as av
import ordenes_dns as od
import ordenes_sitios as os_
import sesion
import subidas
from errores import ErrorPortal, no_encontrado

ORDENES = {
    "listar": ("ninguno", os_.listar),
    "catalogo": ("ninguno", os_.catalogo),
    "crear": ("nuevo", os_.crear),
    "app": ("sitio", os_.app),
    "entrar": ("sitio", os_.simple("entrar")),
    "clave-admin": ("sitio", os_.simple("clave-admin")),
    "revisar": ("sitio", os_.simple("revisar")),
    "actualizar": ("sitio", os_.simple("actualizar", tiempo=960)),
    "terminar": ("sitio", os_.simple("terminar")),
    "ssl": ("sitio", os_.ssl),
    "ftp": ("sitio", os_.ftp),
    "tareas": ("sitio", os_.simple("tareas")),
    "tareas-guardar": ("sitio", os_.tareas_guardar),
    "tarea-ejecutar": ("sitio", os_.tarea("tarea-ejecutar")),
    "tarea-registro": ("sitio", os_.tarea("tarea-registro")),
    "bases": ("sitio", os_.simple("bases")),
    "base-crear": ("sitio", os_.base_crear),
    "base-entrar": ("sitio", os_.base_entrar),
    "base-borrar": ("sitio", os_.base_borrar),
    "avanzado": ("sitio", av.avanzado),
    "avanzado-php": ("sitio", av.avanzado_php),
    "avanzado-ver": ("sitio", av.avanzado_ver),
    "avanzado-archivo": ("sitio", av.avanzado_archivo),
    "avanzado-restaurar": ("sitio", av.avanzado_restaurar),
    "php-estado": ("sitio", av.php_estado),
    "php-version": ("sitio", av.php_version),
    "paquete": ("sitio", av.paquete),
    "dns-ver": ("zona", od.ver),
    "dns-agregar": ("zona", od.agregar),
    "dns-modificar": ("zona", od.modificar),
    "dns-borrar": ("zona", od.borrar),
}


class Contexto:
    def __init__(self, admin, args):
        self.admin, self.args = admin, args
        self.sitio = self.dominio = None


def _subidas_de(args):
    return [args.get(k) for k in ("subida", "respaldo") if isinstance(args.get(k), str)]


def atender(peticion):
    """Devuelve {"ok": true, "datos": ...} o lanza ErrorPortal."""
    args = peticion.get("args") or {}
    try:
        return _atender(peticion, args)
    except BaseException:
        # Una subida que no llegó a usarse no se queda en la carpeta del portal.
        if isinstance(args, dict):
            for nombre in _subidas_de(args):
                subidas.quitar(nombre)
        raise


def _atender(peticion, args):
    admin = sesion.verificar(peticion.get("ficha"))
    orden = peticion.get("orden")
    if not isinstance(orden, str) or orden not in ORDENES:
        raise ErrorPortal(400, "Orden no permitida")
    if not isinstance(args, dict):
        raise ErrorPortal(400, "Petición no válida")
    tipo, funcion = ORDENES[orden]
    ctx = Contexto(admin, args)
    if tipo != "ninguno":
        ctx.sitio = alcance.nombre_valido(peticion.get("dominio"))
        ctx.dominio = alcance.dominio_asignado(ctx.sitio, admin["dominios"])
        if tipo == "zona":
            if ctx.sitio != ctx.dominio:
                raise no_encontrado()
        else:
            alcance.comprobar_reservado(ctx.sitio, sesion.nombres_de_portales())
            if tipo == "sitio" and not alcance.sitio_existe(ctx.sitio):
                raise no_encontrado()
    datos = funcion(ctx)
    ayudantes.registro().info("MAQUITA_SITIOS_PORTAL ok admin=%s orden=%s dominio=%s",
                              admin["usuario"], orden, ctx.sitio or "-")
    return {"ok": True, "datos": datos}
