"""Nombre visible del Drive para las Aplicaciones del Drive (Editor de PDF, Tableros).

Sale de la MISMA perilla que usa el Almacén: `config_kv['drive_name']`, que el Almacén
resuelve en `config_almacen.drive_name()` y publica en `GET /api/almacen/marca`. Así
cada réplica pone su marca una sola vez y las aplicaciones la heredan, sin nombres
escritos en las plantillas ni en el JS.

Orden: lo que diga el Almacén → variable de entorno `DRIVE_NAME` (si el Almacén no
responde) → «Nube» (el mismo valor neutro por defecto del Almacén). Se guarda en memoria
unos minutos para no preguntar en cada página.

ESTE ARCHIVO ES IDÉNTICO en `almacen/aplicaciones/pdf_editor` y `almacen/aplicaciones/bi`
(cada aplicación se instala por separado). Si cambias uno, copia el otro: la prueba
`almacen/tests/test_auth_drive_aplicaciones.py` falla si divergen.
"""
import json
import logging
import os
import time
import urllib.request

_log = logging.getLogger(__name__)

POR_DEFECTO = "Nube"
_SEGUNDOS_CACHE = 300
_SEGUNDOS_CACHE_FALLO = 60
_cache = {"valor": None, "hasta": 0.0}


def _url_marca():
    base = os.getenv("ALMACEN_INTERNAL_URL", "http://127.0.0.1:8788").rstrip("/")
    return base + "/api/almacen/marca"


def _preguntar_al_almacen():
    """drive_name que publica el Almacén, o '' si no responde."""
    try:
        with urllib.request.urlopen(_url_marca(), timeout=2) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8") or "{}")
        return str(datos.get("drive_name") or "").strip()
    except Exception as excepcion:
        _log.warning("No se pudo leer la marca del Almacén: %s", excepcion)
        return ""


def nombre_drive():
    """Nombre visible del Drive configurado en esta instalación."""
    ahora = time.time()
    if _cache["valor"] and ahora < _cache["hasta"]:
        return _cache["valor"]
    valor = _preguntar_al_almacen()
    vigencia = _SEGUNDOS_CACHE if valor else _SEGUNDOS_CACHE_FALLO
    valor = valor or (os.getenv("DRIVE_NAME") or "").strip() or POR_DEFECTO
    _cache.update(valor=valor, hasta=ahora + vigencia)
    return valor


def registrar_en_plantillas(app):
    """Deja `drive_name` disponible en todas las plantillas Jinja de la aplicación."""
    @app.context_processor
    def _marca_drive():
        return {"drive_name": nombre_drive()}
