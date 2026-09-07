# -*- coding: utf-8 -*-
"""Cabeceras de las páginas del editor OnlyOffice (N-5, auditoría del 03/09).

La página del editor (`/archivos-almacen/editar` y la pública `/almacen-s/<token>/editar`) es una
carcasa: el JavaScript pide la configuración firmada al backend y carga `api.js` del Document
Server. Aun sin datos propios, una página sin CSP es un sitio donde inyectar y desde donde llamar a
la API con la cookie del usuario. Aquí se fija una política cerrada con `nonce` por petición: solo
el script y el estilo de la propia página, y solo el Document Server como origen externo (script,
marco, conexiones e imágenes). El marco del editor solo puede incrustarse desde este origen.
"""
import secrets
from urllib.parse import urlsplit


def nonce() -> str:
    return secrets.token_urlsafe(16)


def origen(url: str) -> str:
    """`https://office.dominio.tld/ruta` → `https://office.dominio.tld`; vacío si la URL es relativa."""
    p = urlsplit(url or '')
    return f'{p.scheme}://{p.netloc}' if p.scheme and p.netloc else ''


def csp_editor(url_ds: str, nonce_peticion: str) -> str:
    ds = origen(url_ds)
    externo = f' {ds}' if ds else ''
    # api.js del Document Server añade estilos en línea al contenedor: style-src los admite;
    # script-src NO: solo el script de la página (nonce) y el propio Document Server.
    return (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce_peticion}'{externo}; "
        f"style-src 'self' 'nonce-{nonce_peticion}' 'unsafe-inline'; "
        f"img-src 'self' data: blob:{externo}; "
        f"frame-src 'self'{externo}; "
        f"connect-src 'self'{externo}; "
        "font-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
    )


def cabeceras_editor(url_ds: str, nonce_peticion: str) -> dict:
    return {
        'Content-Type': 'text/html; charset=utf-8',
        'Content-Security-Policy': csp_editor(url_ds, nonce_peticion),
        'Referrer-Policy': 'no-referrer',
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
    }
