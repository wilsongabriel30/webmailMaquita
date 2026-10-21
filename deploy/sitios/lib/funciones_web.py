"""Órdenes de las funciones web por sitio (v1.10) y de las cuentas FTP adicionales.

maquita-sitios pasa aquí todo lo que empieza por «web» o «ftp-». La forma de cada orden (la misma que comprueba
maquita-sudo, validar_sitios_web):

  web <dominio>                                     estado de todas las funciones web del sitio
  web-redirecciones <dominio> <lista JSON b64url>   [{origen, destino, codigo, subrutas, conservar_ruta}]
  web-privado-agregar <dominio> <carpeta b64url> <usuario> [contraseña b64url]   (sin contraseña: se genera)
  web-privado-quitar <dominio> <carpeta b64url> [usuario]   (sin usuario: quita la protección de la carpeta)
  web-errores <dominio> <JSON b64url>               {"404": "/errores/404.html", …}
  web-hotlink <dominio> <JSON b64url>               {activo, extensiones, permitidos, buscadores}
  web-bloqueo <dominio> <lista JSON b64url>         ["192.0.2.1", "2001:db8::/32", …]
  web-optimizacion <dominio> <JSON b64url>          {compresion, estaticos, cache_pagina, cache_minutos}
  web-purgar <dominio>                              vacía la caché de página
  ftp-cuentas <dominio>                             cuentas FTP adicionales
  ftp-cuenta-crear <dominio> <nombre> <subcarpeta b64url>
  ftp-cuenta-clave <dominio> <nombre>               contraseña nueva (se muestra una vez)
  ftp-cuenta-quitar <dominio> <nombre>
Solo desde el sistema (no la admite maquita-sudo):
  ftp-montar                                        vuelve a montar las carpetas de las cuentas (al arrancar)
"""

import validacion as v
from comun import ErrorSitio, de_base64

# Orden → función del meta que guarda (todas las que reciben un JSON y pasan por nginx_web.aplicar).
CON_JSON = {
    "web-redirecciones": "redirecciones",
    "web-errores": "errores",
    "web-hotlink": "hotlink",
    "web-bloqueo": "bloqueo",
    "web-optimizacion": "optimizacion",
}


def _texto(b64, que):
    try:
        texto = de_base64(b64)
    except ValueError:
        raise ErrorSitio(f"{que} no válida")
    if not texto or len(texto) > 200:
        raise ErrorSitio(f"{que} no válida")
    return texto


def guardar(dominio, funcion, datos):
    """Valida con el módulo de la función y aplica con el mecanismo común (copia, nginx -t, marcha atrás)."""
    import nginx_web
    from comun import leer_meta

    meta = leer_meta(dominio)
    ajustes = nginx_web.modulo(funcion).validar(meta, datos)
    nginx_web.aplicar(dominio, funcion, None if ajustes in ([], {}) else ajustes)
    return nginx_web.ver(dominio)


def despachar(args):
    import ftp_cuentas
    import nginx_web
    import web_optimizacion
    import web_privacidad

    n, orden = len(args), args[0] if args else ""
    if n == 2 and orden == "web":
        return nginx_web.ver(v.dominio(args[1]))
    if n == 3 and orden in CON_JSON:
        tope = 20000 if orden in ("web-redirecciones", "web-bloqueo") else 8000
        return guardar(v.dominio(args[1]), CON_JSON[orden], v.json_b64(args[2], tope=tope))
    if n in (4, 5) and orden == "web-privado-agregar":
        secreto = _texto(args[4], "contraseña") if n == 5 else None
        return web_privacidad.agregar(v.dominio(args[1]), _texto(args[2], "carpeta"), args[3], secreto)
    if n in (3, 4) and orden == "web-privado-quitar":
        return web_privacidad.quitar(v.dominio(args[1]), _texto(args[2], "carpeta"), args[3] if n == 4 else None)
    if n == 2 and orden == "web-purgar":
        return web_optimizacion.purgar(v.dominio(args[1]))
    if n == 2 and orden == "ftp-cuentas":
        return ftp_cuentas.listar(v.dominio(args[1]))
    if n == 4 and orden == "ftp-cuenta-crear":
        return ftp_cuentas.crear(v.dominio(args[1]), args[2], _texto(args[3], "subcarpeta"))
    if n == 3 and orden == "ftp-cuenta-clave":
        return ftp_cuentas.nueva_clave(v.dominio(args[1]), args[2])
    if n == 3 and orden == "ftp-cuenta-quitar":
        return ftp_cuentas.quitar(v.dominio(args[1]), args[2])
    if args == ["ftp-montar"]:
        return ftp_cuentas.montar_todas()
    raise ErrorSitio("orden o argumentos no permitidos")
