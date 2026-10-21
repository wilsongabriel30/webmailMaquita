"""Órdenes de «observación y datos» del ayudante de sitios: registros, estadísticas, disponibilidad, copias del
sitio y administrador de archivos. maquita-sitios les pasa los argumentos tal cual; aquí se revalida la forma
(maquita-sudo ya lo hizo) y se llama al módulo de cada función.

También la limpieza: lo que hace «datos-noche» (temporizador), lo que se quita al dar de baja un sitio y lo que
recoge «regenerar» (datos de sitios que ya no existen).
"""

import os
import re
import time

import validacion as v
from comun import PAPELERA, ErrorSitio, de_base64, todos_los_meta

SUBIDAS = "/var/lib/maquita-sitios/subidas"
RE_COPIA = re.compile(r"^\d{8}-\d{6}$")
RE_PAPELERA = re.compile(r"^[0-9a-f]{12}$")
DIA = 86400

ORDENES = {
    "registros", "estadisticas", "estadisticas-generar", "estadisticas-informe", "disponibilidad",
    "copias", "copia-crear", "copia-descargar", "copia-restaurar", "copia-borrar",
    "archivos-listar", "archivos-subir", "archivos-descargar", "archivos-carpeta", "archivos-mover",
    "archivos-copiar", "archivos-borrar", "archivos-comprimir", "archivos-descomprimir", "archivos-permisos",
    "archivos-papelera", "archivos-recuperar", "archivos-vaciar",
}
# Solo desde el sistema (temporizadores); maquita-sudo no las admite.
DEL_SISTEMA = {"disponibilidad-comprobar", "datos-noche"}


def _ruta(b64):
    try:
        return de_base64(b64)
    except ValueError:
        raise ErrorSitio("ruta no válida")


def _copia(ident):
    if not RE_COPIA.match(ident or ""):
        raise ErrorSitio("copia no válida")
    return ident


def despachar(args):
    orden, resto = args[0], args[1:]
    if orden == "disponibilidad-comprobar" and not resto:
        import disponibilidad

        return disponibilidad.comprobar_todos()
    if orden == "datos-noche" and not resto:
        return noche()
    if not resto:
        raise ErrorSitio("orden o argumentos no permitidos")
    dominio = v.dominio(resto[0])
    resto = resto[1:]
    if orden == "registros" and len(resto) in (2, 3) and resto[1].isdigit():
        import visor_registros

        filtro = _ruta(resto[2]) if len(resto) == 3 else None
        return visor_registros.ultimas(dominio, resto[0], int(resto[1]), filtro)
    if orden.startswith("estadisticas") and not resto:
        import estadisticas

        if orden == "estadisticas":
            return estadisticas.ver(dominio)
        if orden == "estadisticas-generar":
            return estadisticas.generar(dominio)
        return estadisticas.informe(dominio, SUBIDAS)
    if orden == "disponibilidad" and not resto:
        import disponibilidad

        return disponibilidad.ver(dominio)
    if orden.startswith("copia"):
        return _copias(orden, dominio, resto)
    if orden.startswith("archivos-"):
        return _archivos(orden, dominio, resto)
    raise ErrorSitio("orden o argumentos no permitidos")


def _copias(orden, dominio, resto):
    import copias_cliente as c

    if orden == "copias" and not resto:
        return c.listar(dominio)
    if orden == "copia-crear" and not resto:
        return c.crear(dominio)
    if len(resto) == 1:
        ident = _copia(resto[0])
        if orden == "copia-descargar":
            return c.descargar(dominio, ident, SUBIDAS)
        if orden == "copia-restaurar":
            return c.restaurar(dominio, ident)
        if orden == "copia-borrar":
            return c.borrar(dominio, ident)
    raise ErrorSitio("orden o argumentos no permitidos")


def _archivos(orden, dominio, resto):
    import archivos_ordenes as a

    n = len(resto)
    if orden == "archivos-listar" and n == 1:
        return a.listar(dominio, _ruta(resto[0]))
    if orden == "archivos-subir" and n in (2, 3) and (n == 2 or resto[2] == "reemplazar"):
        return a.subir(dominio, _ruta(resto[0]), resto[1], reemplazar=n == 3)
    if orden == "archivos-descargar" and n == 1:
        return a.descargar(dominio, _ruta(resto[0]))
    if orden == "archivos-carpeta" and n == 1:
        return a.carpeta(dominio, _ruta(resto[0]))
    if orden in ("archivos-mover", "archivos-copiar", "archivos-descomprimir") and n == 2:
        funcion = {"archivos-mover": a.mover, "archivos-copiar": a.copiar, "archivos-descomprimir": a.descomprimir}[orden]
        return funcion(dominio, _ruta(resto[0]), _ruta(resto[1]))
    if orden == "archivos-borrar" and n == 1:
        return a.borrar(dominio, _ruta(resto[0]))
    if orden == "archivos-comprimir" and n == 1:
        return a.comprimir(dominio, v.json_b64(resto[0], tope=200000))
    if orden == "archivos-permisos" and n == 2:
        return a.permisos(dominio, _ruta(resto[0]), resto[1])
    if orden == "archivos-papelera" and n == 0:
        return a.ver_papelera(dominio)
    if orden == "archivos-recuperar" and n == 1 and RE_PAPELERA.match(resto[0]):
        return a.recuperar(dominio, resto[0])
    if orden == "archivos-vaciar" and n == 0:
        return a.vaciar(dominio)
    raise ErrorSitio("orden o argumentos no permitidos")


# --- Limpieza ---


def descargas_viejas(subidas=SUBIDAS, horas=24):
    """Descargas que el panel no llegó a entregar (y borrar)."""
    quitadas = 0
    if os.path.isdir(subidas):
        limite = time.time() - horas * 3600
        for n in os.listdir(subidas):
            ruta = os.path.join(subidas, n)
            # .entregando: la que el panel había reclamado para enviarla y no llegó a borrar.
            if re.fullmatch(r"[0-9a-f]{32}\.(descarga|subida|descarga\.\d+\.entregando)", n) and os.lstat(ruta).st_mtime < limite:
                os.remove(ruta)
                quitadas += 1
    return quitadas


def noche():
    """Cada noche: estadísticas de todos los sitios, papeleras de más de 30 días y descargas olvidadas."""
    import archivos_ordenes
    import estadisticas

    resultado = estadisticas.todos()
    papeleras = {}
    for meta in todos_los_meta():
        try:
            n = archivos_ordenes.purgar(meta)
        except (ErrorSitio, OSError, KeyError):
            continue
        if n:
            papeleras[meta["dominio"]] = n
    resultado.update(papeleras_vaciadas=papeleras, descargas_borradas=descargas_viejas())
    return resultado


def limpiar_sitio(meta, papelera=None):
    """Al dar de baja el sitio: estadísticas y disponibilidad se borran; las copias van a su papelera."""
    import copias_cliente
    import disponibilidad
    import estadisticas

    estadisticas.quitar(meta["dominio"])
    disponibilidad.quitar(meta["dominio"])
    copias_cliente.quitar(meta["dominio"], papelera)


def huerfanos():
    """«regenerar»: datos de sitios que ya no existen."""
    import copias_cliente
    import disponibilidad
    import estadisticas

    def copias_a_papelera(dominio):
        # Son datos del cliente: no se borran, van a la papelera general como el resto del sitio.
        destino = os.path.join(PAPELERA, f"{dominio}-copias-{time.strftime('%Y%m%d-%H%M%S')}")
        os.makedirs(destino, mode=0o700)
        copias_cliente.quitar(dominio, destino)

    dominios = {m["dominio"] for m in todos_los_meta()}
    quitados = set(disponibilidad.huerfanos(dominios))
    for carpeta, quitar in ((estadisticas.DATOS, estadisticas.quitar), (copias_cliente.COPIAS, copias_a_papelera)):
        if os.path.isdir(carpeta):
            for n in os.listdir(carpeta):
                if n not in dominios and v.RE_DOMINIO.match(n):
                    quitar(n)
                    quitados.add(n)
    return {"datos_huerfanos_borrados": sorted(quitados), "descargas_borradas": descargas_viejas()}
