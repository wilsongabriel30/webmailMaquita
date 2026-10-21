"""Protección contra hotlinking: que otras páginas no muestren las imágenes (o vídeos, PDF…) del sitio
gastando su tráfico.

Con la protección activa, un archivo con una de las extensiones elegidas solo se sirve si la petición viene del
propio sitio (sus nombres y alias), de un dominio permitido o sin página de origen (quien abre el enlace directo o
un navegador que no la envía). Lo demás recibe 403. Opcionalmente se permite a los buscadores (vistas previas de
imágenes).
"""

import re

import web_comun as w
from comun import ErrorSitio

EXTENSIONES = ["jpg", "jpeg", "png", "gif", "webp", "avif", "svg", "mp4", "webm", "mp3", "pdf"]
RE_EXTENSION = re.compile(r"^[a-z0-9]{1,8}$")
BUSCADORES = (r"~\.google\.", r"~\.bing\.", r"~\.duckduckgo\.", r"~\.yahoo\.", r"~\.ecosia\.")
MAX_DOMINIOS = 50
MAX_EXTENSIONES = 30


def validar(meta, datos):
    if not isinstance(datos, dict):
        raise ErrorSitio("datos de hotlinking no válidos")
    extensiones = []
    for e in w.lista(datos.get("extensiones", EXTENSIONES), MAX_EXTENSIONES, "extensiones"):
        e = str(e).strip().lower().lstrip(".")
        if not RE_EXTENSION.fullmatch(e):
            raise ErrorSitio(f"extensión no válida: {e[:20]}")
        if e not in extensiones:
            extensiones.append(e)
    activo = w.booleano(datos.get("activo", False))
    if activo and not extensiones:
        raise ErrorSitio("elija al menos una extensión")
    permitidos = []
    for d in w.lista(datos.get("permitidos"), MAX_DOMINIOS, "dominios permitidos"):
        d = w.nombre(d)
        if d not in permitidos:
            permitidos.append(d)
    return {"activo": activo, "extensiones": extensiones, "permitidos": permitidos,
            "buscadores": w.booleano(datos.get("buscadores", True))}


def fragmentos(meta, ajustes):
    if not ajustes or not ajustes.get("activo"):
        return {}
    a = validar(meta, ajustes)  # otra vez al generar: un meta editado a mano no cuela texto en nginx
    referentes = ["none", "blocked", "server_names"] + [n for d in a["permitidos"] for n in (d, f"www.{d}")
                                                         if not (d.startswith("*.") and n.startswith("www."))]
    if a["buscadores"]:
        referentes += BUSCADORES
    tipos = "|".join(a["extensiones"])
    return {"servidor": "\n".join([
        "# Protección contra hotlinking",
        f"valid_referers {' '.join(referentes)};",
        'set $sitio_hotlink "";',
        f'if ($uri ~* "\\.(?:{tipos})$") {{ set $sitio_hotlink "a"; }}',
        'if ($invalid_referer) { set $sitio_hotlink "${sitio_hotlink}b"; }',
        'if ($sitio_hotlink = "ab") { return 403; }',
    ])}


def estado(meta, ajustes):
    return ajustes or {"activo": False, "extensiones": EXTENSIONES, "permitidos": [], "buscadores": True}
