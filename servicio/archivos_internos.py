# -*- coding: utf-8 -*-
"""Nombres internos del Almacén: lo que el sistema guarda en el espacio de la
persona pero que NO es suyo y no debe ver ni borrar.

Vive en un módulo aparte porque lo consultan varias capas que no pueden
importarse entre sí (el núcleo, los índices de búsqueda, los formularios y el
servidor WebDAV): aquí no hay dependencias, solo nombres y tres preguntas.

- `ARCHIVOS_INTERNOS`: nombres EXACTOS de archivo. Hoy, el centinela de la
  app de Windows (`.comprobacion-drive-maquita`, ver `nucleo_archivos`).
- `CARPETAS_INTERNAS`: carpetas del sistema dentro de las carpetas de la
  persona. Hoy, `.formularios`: ahí vive el archivo de respuestas de cada
  formulario creado desde un Excel (10/09/2026). Antes ese archivo quedaba a la
  vista junto al libro y la persona veía tres archivos donde Google enseña dos.

Solo se ocultan estos nombres EXACTOS, no todo lo que empieza por punto: hay
gente con archivos propios así (.gitkeep, .env) y esos deben seguir viéndose.
"""

ARCHIVOS_INTERNOS = frozenset({'.comprobacion-drive-maquita'})
CARPETAS_INTERNAS = frozenset({'.formularios'})

CARPETA_RESPUESTAS = '.formularios'

MOTIVO_CENTINELA = ('Este archivo protege la sincronización de tu Drive y no se '
                    'puede eliminar.')
MOTIVO_CARPETA = ('Esta carpeta guarda las respuestas de tus formularios y la '
                  'administra el Drive; no se puede eliminar ni mover.')


def es_archivo_interno(nombre):
    """¿Es un archivo del sistema que la persona no debe ver ni borrar?"""
    return (nombre or '') in ARCHIVOS_INTERNOS


def es_carpeta_interna(nombre):
    """¿Es una carpeta del sistema (p. ej. `.formularios`)?"""
    return (nombre or '') in CARPETAS_INTERNAS


def es_nombre_interno(nombre):
    """Archivo o carpeta del sistema: no se lista ni se toca desde fuera."""
    return es_archivo_interno(nombre) or es_carpeta_interna(nombre)


def en_carpeta_interna(ruta_virtual):
    """¿La ruta está DENTRO de una carpeta interna (o es una)?

    Se usa para no indexar ni enseñar en búsquedas lo que cuelga de
    `.formularios`, aunque el archivo se haya subido por la API.
    """
    partes = [p for p in (ruta_virtual or '').split('/') if p]
    return any(p in CARPETAS_INTERNAS for p in partes)
