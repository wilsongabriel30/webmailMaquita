"""Funciones web por sitio (v1.10) y cuentas FTP adicionales, desde el portal.

Son las mismas órdenes que usa el panel general (deploy/sitios/lib/funciones_web.py): redirecciones, carpetas con
contraseña, páginas de error, hotlinking, IP bloqueadas, optimización y su caché, y cuentas FTP encerradas en una
subcarpeta. Todas cambian solo el sitio del que se trata y maquita-sitios las aplica con copia previa y `nginx -t`.

Aquí se comprueba la FORMA de cada dato (claves conocidas, tipos y topes) y se arma el JSON que viaja en
base64url; los valores (rutas, destinos, extensiones, IP) los vuelve a validar maquita-sitios uno a uno. Las
reglas propias de nginx siguen siendo solo del superadministrador: no hay orden para ellas.
"""

import ipaddress
import json
import re

from errores import ErrorPortal
from ordenes_sitios import b64, sitios

RE_USUARIO = re.compile(r"[A-Za-z0-9._-]{1,32}")
RE_CUENTA = re.compile(r"[a-z][a-z0-9]{1,10}")
CODIGOS_ERROR = ("403", "404", "500", "502", "503")
CADUCIDADES = ("off", "1h", "1d", "7d", "30d", "180d", "365d")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
TIEMPO = 120


def _json(datos, tope):
    texto = b64(json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    if len(texto) > tope:
        raise ErrorPortal(400, "Demasiados datos de una vez")
    return texto


def _cadena(valor, que, maximo=200):
    if not isinstance(valor, str) or not valor.strip() or len(valor) > maximo or _CONTROL.search(valor):
        raise ErrorPortal(400, f"{que} no válido")
    return valor.strip()


def _logico(valor, que):
    if not isinstance(valor, bool):
        raise ErrorPortal(400, f"{que}: se esperaba sí o no")
    return valor


def _lista(valor, maximo, que):
    if not isinstance(valor, list) or len(valor) > maximo:
        raise ErrorPortal(400, f"{que}: se admiten hasta {maximo}")
    return valor


def _corto(valor, que):
    """Carpeta, subcarpeta o contraseña: un valor que en base64url cabe en 200 caracteres."""
    if not isinstance(valor, str) or not valor or _CONTROL.search(valor):
        raise ErrorPortal(400, f"{que} no válida")
    texto = b64(valor)
    if len(texto) > 200:
        raise ErrorPortal(400, f"{que} demasiado larga")
    return texto


def _solo(datos, claves, que):
    if not isinstance(datos, dict) or set(datos) - set(claves):
        raise ErrorPortal(400, f"{que} no válidos")
    return datos


# --- Estado y funciones que guardan un JSON ---


def web(ctx):
    return sitios("web", ctx.sitio, tiempo=TIEMPO)


def redirecciones(ctx):
    limpias = []
    for r in _lista(ctx.args.get("redirecciones"), 200, "Redirecciones"):
        r = _solo(r, ("origen", "destino", "codigo", "subrutas", "conservar_ruta"), "Datos de la redirección")
        codigo = r.get("codigo", 301)
        if codigo not in (301, 302) or isinstance(codigo, bool):
            raise ErrorPortal(400, "El código de la redirección debe ser 301 o 302")
        limpias.append({"origen": _cadena(r.get("origen"), "Origen", 500), "destino": _cadena(r.get("destino"), "Destino", 2000),
                        "codigo": codigo, "subrutas": _logico(r.get("subrutas", False), "Subrutas"),
                        "conservar_ruta": _logico(r.get("conservar_ruta", True), "Conservar la ruta")})
    return sitios("web-redirecciones", ctx.sitio, _json(limpias, 20000), tiempo=TIEMPO)


def errores(ctx):
    paginas = ctx.args.get("paginas")
    if not isinstance(paginas, dict) or set(paginas) - set(CODIGOS_ERROR):
        raise ErrorPortal(400, "Solo se admiten los códigos 403, 404, 500, 502 y 503")
    limpias = {c: _cadena(p, "Página de error", 300) for c, p in paginas.items()}
    return sitios("web-errores", ctx.sitio, _json(limpias, 8000), tiempo=TIEMPO)


def hotlink(ctx):
    datos = _solo(ctx.args.get("hotlink"), ("activo", "extensiones", "permitidos", "buscadores"), "Datos del hotlinking")
    limpio = {"activo": _logico(datos.get("activo", False), "Activo"),
              "extensiones": [_cadena(e, "Extensión", 10) for e in _lista(datos.get("extensiones", []), 30, "Extensiones")],
              "permitidos": [_cadena(d, "Dominio permitido", 253) for d in _lista(datos.get("permitidos", []), 50, "Dominios permitidos")],
              "buscadores": _logico(datos.get("buscadores", True), "Buscadores")}
    if not limpio["extensiones"]:
        limpio.pop("extensiones")  # sin lista: las de serie
    return sitios("web-hotlink", ctx.sitio, _json(limpio, 8000), tiempo=TIEMPO)


def bloqueo(ctx):
    redes = []
    for valor in _lista(ctx.args.get("redes"), 500, "IP bloqueadas"):
        valor = _cadena(valor, "IP o red", 50)
        try:
            red = ipaddress.ip_network(valor, strict=False)
        except ValueError:
            raise ErrorPortal(400, f"IP o red no válida: {valor}")
        if red.prefixlen == 0:
            raise ErrorPortal(400, "No se puede bloquear Internet entero (/0)")
        redes.append(valor)
    return sitios("web-bloqueo", ctx.sitio, _json(redes, 20000), tiempo=TIEMPO)


def optimizacion(ctx):
    datos = _solo(ctx.args.get("optimizacion"), ("compresion", "estaticos", "cache_pagina", "cache_minutos"),
                  "Datos de la optimización")
    minutos = datos.get("cache_minutos", 10)
    if not isinstance(minutos, int) or isinstance(minutos, bool) or not 1 <= minutos <= 1440:
        raise ErrorPortal(400, "Los minutos de caché van de 1 a 1440")
    if datos.get("estaticos", "30d") not in CADUCIDADES:
        raise ErrorPortal(400, "Caducidad no válida")
    limpio = {"compresion": _logico(datos.get("compresion", True), "Compresión"), "estaticos": datos.get("estaticos", "30d"),
              "cache_pagina": _logico(datos.get("cache_pagina", False), "Caché de página"), "cache_minutos": minutos}
    return sitios("web-optimizacion", ctx.sitio, _json(limpio, 8000), tiempo=TIEMPO)


def purgar(ctx):
    return sitios("web-purgar", ctx.sitio, tiempo=TIEMPO)


# --- Carpetas con contraseña ---


def _usuario(valor):
    if not isinstance(valor, str) or not RE_USUARIO.fullmatch(valor):
        raise ErrorPortal(400, "Usuario no válido (letras sin tilde, números y . _ -, hasta 32)")
    return valor


def privado_agregar(ctx):
    args = ["web-privado-agregar", ctx.sitio, _corto(ctx.args.get("carpeta"), "Carpeta"), _usuario(ctx.args.get("usuario"))]
    clave = ctx.args.get("clave")
    if clave not in (None, ""):
        if not isinstance(clave, str) or not 8 <= len(clave) <= 128:
            raise ErrorPortal(400, "La contraseña debe tener entre 8 y 128 caracteres")
        args.append(_corto(clave, "Contraseña"))
    return sitios(*args, tiempo=TIEMPO)


def privado_quitar(ctx):
    args = ["web-privado-quitar", ctx.sitio, _corto(ctx.args.get("carpeta"), "Carpeta")]
    if ctx.args.get("usuario") not in (None, ""):
        args.append(_usuario(ctx.args.get("usuario")))
    return sitios(*args, tiempo=TIEMPO)


# --- Cuentas FTP adicionales ---


def _cuenta(ctx):
    nombre = ctx.args.get("nombre")
    if not isinstance(nombre, str) or not RE_CUENTA.fullmatch(nombre):
        raise ErrorPortal(400, "Nombre no válido: de 2 a 11 minúsculas o números, empezando por una letra")
    return nombre


def ftp_cuentas(ctx):
    return sitios("ftp-cuentas", ctx.sitio)


def ftp_cuenta_crear(ctx):
    carpeta = ctx.args.get("carpeta")
    carpeta = carpeta.strip().strip("/") if isinstance(carpeta, str) else carpeta
    return sitios("ftp-cuenta-crear", ctx.sitio, _cuenta(ctx), _corto(carpeta, "Subcarpeta"), tiempo=TIEMPO)


def ftp_cuenta(orden):
    def funcion(ctx):
        return sitios(orden, ctx.sitio, _cuenta(ctx), tiempo=TIEMPO)

    funcion.__name__ = orden.replace("-", "_")
    return funcion


ORDENES = {
    "web": ("sitio", web),
    "web-redirecciones": ("sitio", redirecciones),
    "web-errores": ("sitio", errores),
    "web-hotlink": ("sitio", hotlink),
    "web-bloqueo": ("sitio", bloqueo),
    "web-optimizacion": ("sitio", optimizacion),
    "web-purgar": ("sitio", purgar),
    "web-privado-agregar": ("sitio", privado_agregar),
    "web-privado-quitar": ("sitio", privado_quitar),
    "ftp-cuentas": ("sitio", ftp_cuentas),
    "ftp-cuenta-crear": ("sitio", ftp_cuenta_crear),
    "ftp-cuenta-clave": ("sitio", ftp_cuenta("ftp-cuenta-clave")),
    "ftp-cuenta-quitar": ("sitio", ftp_cuenta("ftp-cuenta-quitar")),
}
