# -*- coding: utf-8 -*-
"""
Seguridad de rutas del Almacén Maquita.
=======================================
TODO acceso a disco pasa por aquí. Este módulo garantiza que un usuario
jamás pueda salir de su propia carpeta (ataques de tipo "../", rutas
absolutas, enlaces simbólicos, bytes de control).

Es deliberadamente pequeño y paranoico: es la pieza de seguridad más
importante del servicio.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import os
import re
import posixpath

from config_almacen import raiz_datos

# Una ruta de unidad compartida se ve así: /unidades/<id>/<subruta>
_RE_UNIDAD = re.compile(r'^/unidades/(\d+)(/.*)?$')


def unidad_de_ruta(ruta_virtual: str):
    """Si la ruta pertenece a una unidad compartida devuelve (unidad_id, subruta);
    si es del espacio personal, devuelve (None, ruta)."""
    limpia = normalizar_ruta_virtual(ruta_virtual)
    m = _RE_UNIDAD.match(limpia)
    if m:
        return int(m.group(1)), (m.group(2) or '/')
    return None, limpia


class RutaInvalida(Exception):
    """La ruta pedida es peligrosa o está fuera del espacio del usuario."""


def normalizar_ruta_virtual(ruta: str) -> str:
    """
    Limpia una ruta "virtual" (la que ve el usuario, ej. '/Proyectos/2026').

    - Siempre devuelve una ruta que empieza con '/' y sin '/' final (salvo la raíz).
    - Rechaza: bytes nulos, saltos de línea, y cualquier intento de '..'.

    Lanza RutaInvalida si la ruta es peligrosa.
    """
    if ruta is None:
        raise RutaInvalida('Ruta vacía')
    ruta = str(ruta)
    if '\x00' in ruta or '\n' in ruta or '\r' in ruta:
        raise RutaInvalida('Caracteres de control en la ruta')

    # Unificar separadores y colapsar // y ./
    ruta = ruta.replace('\\', '/')
    limpia = posixpath.normpath('/' + ruta.strip('/'))

    # normpath ya resolvió los '..'; si aun así quedara alguno, es un ataque
    if '..' in limpia.split('/'):
        raise RutaInvalida('Ruta con ".." no permitida')

    return '/' if limpia in ('', '.', '/') else limpia


def raiz_usuario(usuario_id: int, zona: str = 'archivos') -> str:
    """
    Carpeta física raíz de un usuario. Zonas: 'archivos' (su unidad) y
    'papelera'. Se crea si no existe.
    """
    if zona not in ('archivos', 'papelera', 'retencion', 'versiones'):
        raise RutaInvalida(f'Zona desconocida: {zona}')
    base = os.path.join(raiz_datos(), str(int(usuario_id)), zona)
    os.makedirs(base, exist_ok=True)
    return base


def ruta_fisica(usuario_id: int, ruta_virtual: str, zona: str = 'archivos') -> str:
    """
    Convierte la ruta virtual del usuario en la ruta física en disco,
    GARANTIZANDO que queda contenida dentro de su carpeta.

    Contención doble:
      1. normalizar_ruta_virtual ya eliminó '..' y rarezas.
      2. realpath + verificación de prefijo: aunque existiera un enlace
         simbólico malicioso dentro del árbol, no se puede escapar.
    """
    if zona not in ('archivos', 'papelera', 'retencion', 'versiones'):
        raise RutaInvalida(f'Zona desconocida: {zona}')

    unidad_id, sub = unidad_de_ruta(ruta_virtual)
    if unidad_id is not None:
        # Espacio de una unidad compartida (propiedad de la organización, no del usuario)
        base = os.path.join(raiz_datos(), '_unidades', str(unidad_id), zona)
        os.makedirs(base, exist_ok=True)
        limpia = sub
    else:
        base = raiz_usuario(usuario_id, zona)
        limpia = sub   # ya normalizada por unidad_de_ruta

    destino = os.path.join(base, limpia.lstrip('/'))
    base_real = os.path.realpath(base)
    destino_real = os.path.realpath(destino)
    if destino_real != base_real and not destino_real.startswith(base_real + os.sep):
        raise RutaInvalida('La ruta escapa del espacio permitido')

    return destino
