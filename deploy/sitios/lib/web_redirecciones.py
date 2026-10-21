"""Redirecciones del sitio: de una ruta a otra dirección, o de todo el dominio, con 301 (permanente) o 302
(temporal).

Cada entrada: {"origen": "/ruta" o "*" (todo el dominio), "destino": "https://…", "codigo": 301|302,
"subrutas": sí/no (también /ruta/lo-que-siga → destino/lo-que-siga), "conservar_ruta": sí/no (solo con «*»:
añade la ruta pedida al destino)}.

Se escriben como directivas del server{} (rewrite y return), que se evalúan antes que las location del sitio:
no chocan con las reglas de WordPress ni con las propias de «Avanzado». El desafío de Let's Encrypt nunca se
redirige: el certificado tiene que poder renovarse.
"""

from urllib.parse import urlsplit

import web_comun as w
from comun import ErrorSitio

MAXIMO = 200
TODO = "*"


def _nombres(meta):
    import alias

    return set(alias.nombres(meta))


def validar(meta, datos, bucles=True):
    """Lista limpia. Con `bucles=False` (al generar) no se mira si el destino es el propio sitio: un alias añadido
    después no debe impedir escribir el vhost."""
    limpias, vistos = [], set()
    for entrada in w.lista(datos, MAXIMO, "redirecciones"):
        if not isinstance(entrada, dict):
            raise ErrorSitio("redirección no válida")
        codigo = entrada.get("codigo", 301)
        if codigo not in (301, 302, "301", "302"):
            raise ErrorSitio("el código de una redirección es 301 o 302")
        destino = w.url(entrada.get("destino"))
        origen = str(entrada.get("origen") or "").strip()
        propio = bucles and (urlsplit(destino).hostname or "").lower() in _nombres(meta)
        if origen == TODO:
            if propio:
                raise ErrorSitio("redirigir todo el dominio a sí mismo daría un bucle")
            conservar = w.booleano(entrada.get("conservar_ruta", True))
            # Con la ruta conservada, «https://example.org/» + «/pagina» daría «//pagina».
            limpia = {"origen": TODO, "destino": destino.rstrip("/") if conservar else destino,
                      "codigo": int(codigo), "conservar_ruta": conservar}
        else:
            origen = w.ruta(origen, "ruta de origen")
            if origen == "/" and w.booleano(entrada.get("subrutas", False)):
                raise ErrorSitio("para redirigir todo el sitio, use «todo el dominio»")
            if origen.startswith("/.well-known"):
                raise ErrorSitio("/.well-known no se puede redirigir (lo usan los certificados)")
            if propio and urlsplit(destino).path.rstrip("/") == origen.rstrip("/"):
                raise ErrorSitio(f"{origen} redirige a sí misma: daría un bucle")
            limpia = {"origen": origen, "destino": destino, "codigo": int(codigo),
                      "subrutas": w.booleano(entrada.get("subrutas", False))}
        if limpia["origen"] in vistos:
            raise ErrorSitio(f"hay dos redirecciones para {limpia['origen']}")
        vistos.add(limpia["origen"])
        limpias.append(limpia)
    if sum(1 for r in limpias if r["origen"] == TODO) > 1:
        raise ErrorSitio("solo puede haber una redirección de todo el dominio")
    return limpias


def fragmentos(meta, ajustes):
    if not ajustes:
        return {}
    lineas = ["# Redirecciones"]
    # Se vuelve a validar al generar: un meta editado a mano tampoco puede colar texto en nginx.
    for r in sorted(validar(meta, ajustes, bucles=False), key=lambda r: r["origen"] != TODO):  # la de todo el dominio, primero
        if r["origen"] == TODO:
            destino = r["destino"] + ("$request_uri" if r.get("conservar_ruta") else "")
            lineas.append(f'if ($uri !~ "^/\\.well-known/acme-challenge/") {{ return {r["codigo"]} "{destino}"; }}')
            continue
        bandera = "permanent" if r["codigo"] == 301 else "redirect"
        if r.get("subrutas"):
            lineas.append(f'rewrite "^{w.regex(r["origen"])}(/.*)?$" "{r["destino"].rstrip("/")}$1" {bandera};')
        else:
            lineas.append(f'rewrite "^{w.regex(r["origen"])}$" "{r["destino"]}" {bandera};')
    return {"servidor": "\n".join(lineas)}


def estado(meta, ajustes):
    return {"lista": ajustes or [], "maximo": MAXIMO}
