"""Órdenes de «Avanzado», versión de PHP y paquete propio, recortadas a lo que es seguro desde el portal.

- Reglas propias de nginx: no se ofrecen (se quitan de la respuesta y de las versiones restaurables);
  sí se restauran versiones de PHP y de archivos.
- Ver y guardar archivos de la carpeta pública: sí. maquita-sitios los abre componente a componente sin
  seguir enlaces (deploy/sitios/lib/archivo_seguro.py), así que un enlace puesto por FTP no lleva fuera.
- PHP: solo los ajustes del sitio y elegir entre las versiones YA instaladas; nada de instalar.
"""

import json

import ayudantes
import cuotas
import subidas
from errores import ErrorPortal
from ordenes_sitios import RE_VERSION_GUARDADA, RE_VERSION_PHP, b64, sitios


def avanzado(ctx):
    datos = sitios("avanzado", ctx.sitio)
    for clave in ("nginx_propias",):
        datos.pop(clave, None)
    datos["versiones"] = [v for v in datos.get("versiones", []) if v.get("tipo") in ("php", "archivo")]
    return datos


def avanzado_php(ctx):
    ajustes = ctx.args.get("ajustes")
    if not isinstance(ajustes, dict):
        raise ErrorPortal(400, "Ajustes no válidos")
    datos = b64(json.dumps(ajustes, ensure_ascii=False, separators=(",", ":")))
    if len(datos) > 200:
        raise ErrorPortal(400, "Demasiados ajustes de una vez: guárdelos en dos pasos")
    return sitios("avanzado-php", ctx.sitio, datos)


def avanzado_restaurar(ctx):
    version = ctx.args.get("version")
    if not isinstance(version, str) or not RE_VERSION_GUARDADA.fullmatch(version):
        raise ErrorPortal(400, "Versión no válida")
    guardadas = sitios("avanzado", ctx.sitio).get("versiones", [])
    entrada = next((v for v in guardadas if v.get("id") == version), None)
    if not entrada:
        raise ErrorPortal(404, "No encontrado")
    if entrada.get("tipo") not in ("php", "archivo"):
        raise ErrorPortal(403, "Desde el portal solo se restauran los ajustes de PHP y los archivos")
    return sitios("avanzado-restaurar", ctx.sitio, version)


def _ruta(ctx):
    ruta = ctx.args.get("ruta")
    if (not isinstance(ruta, str) or not ruta or len(ruta) > 300 or ruta.startswith("/")
            or any(p == ".." for p in ruta.split("/")) or any(ord(c) < 32 for c in ruta)):
        raise ErrorPortal(400, "Ruta no válida")
    return b64(ruta)


def avanzado_ver(ctx):
    return sitios("avanzado-ver", ctx.sitio, _ruta(ctx))


def avanzado_archivo(ctx):
    ruta, subida = _ruta(ctx), ctx.args.get("subida")
    cuotas.comprobar_disco(ctx.dominio, subidas.tamano(subida, "texto"))
    tomado = subidas.tomar(subida, "texto")
    try:
        args = ["avanzado-archivo", ctx.sitio, ruta, tomado]
        ayudantes.validar("maquita-sitios", args)
    except BaseException:
        subidas.descartar(tomado)
        raise
    return sitios(*args)


def _instaladas(ctx):
    return sitios("php-estado", ctx.sitio)


def php_estado(ctx):
    datos = _instaladas(ctx)
    instaladas = datos.get("instaladas", [])
    return {"instaladas": instaladas, "sitio": datos.get("sitio"),
            "notas": {v: n for v, n in (datos.get("notas") or {}).items() if v in instaladas}}


def php_version(ctx):
    version = ctx.args.get("version")
    if not isinstance(version, str) or not RE_VERSION_PHP.fullmatch(version):
        raise ErrorPortal(400, "Versión de PHP no válida")
    if version not in _instaladas(ctx).get("instaladas", []):
        raise ErrorPortal(403, f"PHP {version} no está instalado en este servidor: pídaselo al administrador")
    return sitios("php-version", ctx.sitio, version, tiempo=600)


def paquete(ctx):
    """Paquete propio (y, si se manda, el respaldo .sql de su base) subido por el portal."""
    archivo, respaldo = ctx.args.get("subida"), ctx.args.get("respaldo")
    con_bd = bool(ctx.args.get("con_bd")) or bool(respaldo)
    cuotas.comprobar_disco(ctx.dominio, subidas.tamano(archivo, "paquete"))
    if con_bd:
        cuotas.comprobar_bases(ctx.dominio, subidas.tamano(respaldo, "respaldo") if respaldo else 0)
    tomados = []
    try:
        tomados.append(subidas.tomar(archivo, "paquete"))
        if respaldo:
            tomados.append(subidas.tomar(respaldo, "respaldo"))
        args = ["paquete", ctx.sitio, tomados[0], "con-bd" if con_bd else "sin-bd"] + tomados[1:]
        ayudantes.validar("maquita-sitios", args)
    except BaseException:
        for t in tomados:
            subidas.descartar(t)
        raise
    # Desde aquí los archivos son de maquita-sitios, que los borra al terminar (bien o mal).
    return sitios(*args, tiempo=1200)
