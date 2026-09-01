"""Cliente del Drive Maquita para el BI: descarga archivos y lista datos del Drive,
autenticando con el token del usuario (cookie `access_token`) que reenvía la petición.
"""
import os

import httpx
from flask import request

_API = os.getenv("ALMACEN_INTERNAL_URL", "http://127.0.0.1:8788") + "/api/almacen"


def _cookies():
    return {"access_token": request.cookies.get("access_token", "")}


def leer_bytes(ruta):
    """Descarga el contenido de un archivo del Drive por su ruta -> bytes."""
    with httpx.Client(timeout=60) as c:
        r = c.get(_API + "/archivos/descargar", params={"ruta": ruta}, cookies=_cookies())
        r.raise_for_status()
        return r.content


def listar_datos(carpeta="/"):
    """Lista los archivos de datos (.xlsx/.xls/.csv) de una carpeta del Drive."""
    with httpx.Client(timeout=30) as c:
        r = c.get(_API + "/archivos", params={"carpeta": carpeta}, cookies=_cookies())
        r.raise_for_status()
        cuerpo = r.json() or {}
    items = cuerpo.get("archivos") or cuerpo.get("items") or cuerpo.get("elementos") or []
    salida = []
    for it in items:
        nombre = it.get("nombre") or it.get("name") or ""
        ruta = it.get("ruta") or it.get("path") or ((carpeta.rstrip("/") + "/" + nombre) if nombre else "")
        if nombre.lower().endswith((".xlsx", ".xls", ".csv")):
            salida.append({"nombre": nombre, "ruta": ruta})
    return salida
