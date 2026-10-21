"""Observación y datos (v1.10) desde el portal: registros, estadísticas, disponibilidad, copias del sitio y
administrador de archivos (deploy/sitios/lib/ordenes_datos.py).

- Todo opera dentro del sitio y, en los archivos, con su usuario de sistema (lo hace maquita-sitios).
- Lo que hace crecer el disco (subir, copiar, comprimir, descomprimir, crear o restaurar una copia) pasa antes
  por la cuota de disco del dominio, que desde la v1.10 suma también las copias del sitio.
- Las descargas (un archivo, una copia, el informe de visitas) no se leen desde el portal: el intermediario las
  pasa a la carpeta del portal (entrega.py) y el portal las entrega con un enlace de un solo uso.
- `disponibilidad-comprobar` y `datos-noche` son del sistema: no hay orden para ellas.
"""

import json
import re

import alcance
import cuotas
import cuotas_copias
import entrega
import subidas
from ayudantes import validar
from errores import ErrorPortal
from ordenes_sitios import b64, sitios
from ordenes_web import _CONTROL

TIPOS_REGISTRO = ("error", "acceso", "php")
MODOS = ("644", "755", "600", "700", "640", "750")
RE_COPIA = re.compile(r"\d{8}-\d{6}")
RE_PAPELERA = re.compile(r"[0-9a-f]{12}")
LARGO = 1150  # el portal espera 1190 s: la respuesta (también la de «tardó demasiado») llega antes


def _ruta(valor, raiz_admitida=True):
    """Ruta relativa a la carpeta pública («.» = la raíz), en base64url para maquita-sitios."""
    if not isinstance(valor, str):
        raise ErrorPortal(400, "Ruta no válida")
    valor = valor.strip().lstrip("/") or "."
    if (len(valor) > 1000 or _CONTROL.search(valor) or "\\" in valor
            or any(p == ".." for p in valor.split("/")) or (valor == "." and not raiz_admitida)):
        raise ErrorPortal(400, "Ruta no válida")
    return b64(valor)


def _con_cuota(ctx):
    """Para lo que crece sin saber cuánto (copiar, comprimir, descomprimir): no se empieza si ya no queda sitio."""
    cuotas.comprobar_disco(ctx.dominio)


# --- Registros, estadísticas y disponibilidad ---


def registros(ctx):
    tipo, lineas, filtro = ctx.args.get("tipo"), ctx.args.get("lineas", 200), ctx.args.get("filtro") or ""
    if tipo not in TIPOS_REGISTRO:
        raise ErrorPortal(400, "Registro no válido (error, acceso o php)")
    if not isinstance(lineas, int) or isinstance(lineas, bool) or not 1 <= lineas <= 1000:
        raise ErrorPortal(400, "Entre 1 y 1000 líneas")
    if not isinstance(filtro, str) or len(filtro) > 100 or len(filtro.encode()) > 140 or _CONTROL.search(filtro):
        raise ErrorPortal(400, "Filtro no válido (hasta 100 caracteres)")
    args = ["registros", ctx.sitio, tipo, str(lineas)] + ([b64(filtro.strip())] if filtro.strip() else [])
    return sitios(*args)


def estadisticas(ctx):
    return sitios("estadisticas", ctx.sitio)


def estadisticas_generar(ctx):
    return sitios("estadisticas-generar", ctx.sitio, tiempo=LARGO)


def estadisticas_informe(ctx):
    return entrega.entregar(sitios("estadisticas-informe", ctx.sitio), f"estadisticas-{ctx.sitio}.html")


def disponibilidad(ctx):
    """Los avisos van a los correos del sitio o a los generales del servidor: estos últimos no se enseñan."""
    datos = sitios("disponibilidad", ctx.sitio)
    if isinstance(datos, dict):
        propios = [d for d in datos.get("destinatarios") or [] if isinstance(d, str) and "@" in d
                   and any(d.lower().rsplit("@", 1)[1] == x or d.lower().rsplit("@", 1)[1].endswith("." + x)
                           for x in ctx.admin["dominios"])]
        datos["destinatarios"] = propios or ["(los avisos generales del servidor)"]
    return datos


# --- Copias del sitio ---


def _copia(ctx):
    ident = ctx.args.get("id")
    if not isinstance(ident, str) or not RE_COPIA.fullmatch(ident):
        raise ErrorPortal(400, "Copia no válida")
    return ident


def copias(ctx):
    datos = sitios("copias", ctx.sitio)
    if isinstance(datos, dict):
        datos["espacio"] = {"disco_mb": cuotas.de(ctx.dominio)["disco_mb"],
                            "ocupado_mb": cuotas.disco_mb(alcance.sitios_de(ctx.dominio))}
    return datos


def copia_crear(ctx):
    cuotas_copias.comprobar_crear(ctx)
    return sitios("copia-crear", ctx.sitio, tiempo=LARGO)


def copia_descargar(ctx):
    ident = _copia(ctx)
    return entrega.entregar(sitios("copia-descargar", ctx.sitio, ident, tiempo=LARGO), f"{ctx.sitio}-{ident}.tar.gz")


def copia_restaurar(ctx):
    ident = _copia(ctx)
    cuotas_copias.comprobar_restaurar(ctx, ident)
    return sitios("copia-restaurar", ctx.sitio, ident, tiempo=LARGO)


def copia_borrar(ctx):
    return sitios("copia-borrar", ctx.sitio, _copia(ctx))


# --- Administrador de archivos ---


def archivos_listar(ctx):
    return sitios("archivos-listar", ctx.sitio, _ruta(ctx.args.get("ruta", ".")))


def archivos_subir(ctx):
    ruta, subida = _ruta(ctx.args.get("ruta"), raiz_admitida=False), ctx.args.get("subida")
    reemplazar = ctx.args.get("reemplazar", False)
    if not isinstance(reemplazar, bool):
        raise ErrorPortal(400, "«reemplazar» debe ser sí o no")
    cuotas.comprobar_disco(ctx.dominio, subidas.tamano(subida, "archivo"))
    tomado = subidas.tomar(subida, "archivo")
    try:
        args = ["archivos-subir", ctx.sitio, ruta, tomado] + (["reemplazar"] if reemplazar else [])
        validar("maquita-sitios", args)
    except BaseException:
        subidas.descartar(tomado)
        raise
    # Desde aquí la copia es de maquita-sitios, que la borra al terminar (bien o mal).
    return sitios(*args, tiempo=LARGO)


def archivos_descargar(ctx):
    datos = sitios("archivos-descargar", ctx.sitio, _ruta(ctx.args.get("ruta"), raiz_admitida=False), tiempo=LARGO)
    nombre = datos.get("nombre") if isinstance(datos, dict) else None
    return entrega.entregar(datos, str(nombre or "descarga"))


def archivos_ruta(orden, raiz_admitida=False):
    def funcion(ctx):
        return sitios(orden, ctx.sitio, _ruta(ctx.args.get("ruta"), raiz_admitida), tiempo=LARGO)

    funcion.__name__ = orden.replace("-", "_")
    return funcion


def archivos_par(orden, crece):
    def funcion(ctx):
        origen = _ruta(ctx.args.get("origen"), raiz_admitida=False)
        destino = _ruta(ctx.args.get("destino"), raiz_admitida=orden == "archivos-descomprimir")
        if crece:
            _con_cuota(ctx)
        return sitios(orden, ctx.sitio, origen, destino, tiempo=LARGO)

    funcion.__name__ = orden.replace("-", "_")
    return funcion


def archivos_comprimir(ctx):
    rutas_, destino = ctx.args.get("rutas"), ctx.args.get("destino")
    if not isinstance(rutas_, list) or not 1 <= len(rutas_) <= 500:
        raise ErrorPortal(400, "Elija entre 1 y 500 elementos")
    for r in rutas_ + [destino]:
        _ruta(r)
    datos = {"rutas": [r.strip().lstrip("/") or "." for r in rutas_], "destino": destino.strip().lstrip("/")}
    texto = b64(json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    if len(texto) > 40000:
        raise ErrorPortal(400, "Demasiados elementos: comprímalos por partes")
    _con_cuota(ctx)
    return sitios("archivos-comprimir", ctx.sitio, texto, tiempo=LARGO)


def archivos_permisos(ctx):
    modo = ctx.args.get("modo")
    if modo not in MODOS:
        raise ErrorPortal(400, "Permisos no admitidos (644, 755, 600, 700, 640 o 750)")
    return sitios("archivos-permisos", ctx.sitio, _ruta(ctx.args.get("ruta"), raiz_admitida=False), modo)


def archivos_recuperar(ctx):
    ident = ctx.args.get("id")
    if not isinstance(ident, str) or not RE_PAPELERA.fullmatch(ident):
        raise ErrorPortal(400, "Elemento no válido")
    return sitios("archivos-recuperar", ctx.sitio, ident)


def solo_sitio(orden, tiempo=300):
    def funcion(ctx):
        return sitios(orden, ctx.sitio, tiempo=tiempo)

    funcion.__name__ = orden.replace("-", "_")
    return funcion


ORDENES = {
    "registros": ("sitio", registros),
    "estadisticas": ("sitio", estadisticas),
    "estadisticas-generar": ("sitio", estadisticas_generar),
    "estadisticas-informe": ("sitio", estadisticas_informe),
    "disponibilidad": ("sitio", disponibilidad),
    "copias": ("sitio", copias),
    "copia-crear": ("sitio", copia_crear),
    "copia-descargar": ("sitio", copia_descargar),
    "copia-restaurar": ("sitio", copia_restaurar),
    "copia-borrar": ("sitio", copia_borrar),
    "archivos-listar": ("sitio", archivos_listar),
    "archivos-subir": ("sitio", archivos_subir),
    "archivos-descargar": ("sitio", archivos_descargar),
    "archivos-carpeta": ("sitio", archivos_ruta("archivos-carpeta")),
    "archivos-mover": ("sitio", archivos_par("archivos-mover", crece=False)),
    "archivos-copiar": ("sitio", archivos_par("archivos-copiar", crece=True)),
    "archivos-descomprimir": ("sitio", archivos_par("archivos-descomprimir", crece=True)),
    "archivos-borrar": ("sitio", archivos_ruta("archivos-borrar")),
    "archivos-comprimir": ("sitio", archivos_comprimir),
    "archivos-permisos": ("sitio", archivos_permisos),
    "archivos-papelera": ("sitio", solo_sitio("archivos-papelera")),
    "archivos-recuperar": ("sitio", archivos_recuperar),
    "archivos-vaciar": ("sitio", solo_sitio("archivos-vaciar", tiempo=LARGO)),
}
