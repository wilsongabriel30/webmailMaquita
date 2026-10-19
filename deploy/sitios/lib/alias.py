"""Dominios alias de un sitio: otros dominios o subdominios que muestran el mismo sitio.

P. ej. «fundacion.org» y «fundacion.com.ec» con el mismo contenido. Cada alias responde también con
«www.» si el sitio lo tiene. Si el sitio ya tiene HTTPS, el certificado se amplía con los alias que ya
apuntan a este servidor; los que todavía no apuntan quedan solo por HTTP hasta volver a guardarlos.
"""

import validacion as v
from comun import ACME_WEBROOT, ErrorSitio, ejecutar, guardar_meta, leer_meta, todos_los_meta

MAXIMO = 10


def nombres(meta, con_alias=True):
    """server_name del sitio: dominio, alias y sus «www.»."""
    base = [meta["dominio"]] + (list(meta.get("alias", [])) if con_alias else [])
    www = meta.get("www", True)
    return [n for d in base for n in ([d, "www." + d] if www else [d])]


def _ocupados(propio):
    """Dominios que ya usa otro sitio (como principal o como alias)."""
    ocupados = {}
    for m in todos_los_meta():
        if m["dominio"] == propio:
            continue
        for d in [m["dominio"]] + list(m.get("alias", [])):
            ocupados[d] = m["dominio"]
    return ocupados


def cambiar(dominio, lista):
    import sitio

    meta = leer_meta(dominio)
    if not isinstance(lista, list) or len(lista) > MAXIMO:
        raise ErrorSitio(f"se admiten hasta {MAXIMO} dominios alias")
    limpia = []
    ocupados = _ocupados(dominio)
    usados = sitio._nombres_en_uso()
    for valor in lista:
        d = v.dominio(str(valor).strip().lower())
        if d == dominio or d in limpia:
            continue
        if d in ocupados:
            raise ErrorSitio(f"{d} ya es del sitio {ocupados[d]}")
        if d in usados or f"www.{d}" in usados:
            raise ErrorSitio(f"{d} ya lo usa otro servicio de este servidor (correo o panel)")
        limpia.append(d)
    anterior = list(meta.get("alias", []))
    meta["alias"] = limpia
    sin_https = []
    if meta.get("ssl"):
        sin_https = _ampliar_certificado(meta)
    meta["alias_sin_https"] = sin_https
    guardar_meta(meta)
    try:
        sitio.escribir_vhost(meta)
        sitio.recargar_nginx()
    except ErrorSitio:
        meta["alias"] = anterior
        guardar_meta(meta)
        sitio.escribir_vhost(meta)
        sitio.recargar_nginx()
        raise
    return sitio.publico(meta)


def certificables(meta):
    """Nombres que lleva el certificado: los del sitio menos los alias que no pudieron validarse."""
    fuera = set(meta.get("alias_sin_https", []))
    return [n for n in nombres(meta) if n.removeprefix("www.") not in fuera]


def _ampliar_certificado(meta):
    """Pide el certificado con todos los nombres; si falla, prueba alias por alias y deja fuera los que
    todavía no apuntan aquí. Devuelve los alias sin HTTPS."""
    correo = meta.get("ssl_correo") or f"postmaster@{meta['dominio']}"

    def emitir(lista):
        ejecutar(["certbot", "certonly", "--webroot", "-w", ACME_WEBROOT, "--non-interactive", "--agree-tos",
                  "-m", correo, "--cert-name", meta["dominio"], "--key-type", "ecdsa", "--expand",
                  "--deploy-hook", "systemctl reload nginx"] + sum((["-d", n] for n in lista), []), tiempo=300)

    principales = nombres(meta, con_alias=False)
    try:
        emitir(principales + [n for d in meta["alias"] for n in ([d, "www." + d] if meta.get("www", True) else [d])])
        return []
    except ErrorSitio:
        pass
    validos, fuera = [], []
    for d in meta["alias"]:
        prueba = [d, "www." + d] if meta.get("www", True) else [d]
        try:
            emitir(principales + [n for a in validos for n in ([a, "www." + a] if meta.get("www", True) else [a])] + prueba)
            validos.append(d)
        except ErrorSitio:
            fuera.append(d)
    if not validos:
        emitir(principales)
    return fuera
