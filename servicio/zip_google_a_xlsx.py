# -*- coding: utf-8 -*-
"""
Al descomprimir un ZIP de Google, dejar también el Excel
========================================================
Wilson, 08/09/2026: «al descomprimir debe descomprimirse un Excel».

Cuando alguien exporta un libro desde Google Drive, lo que baja **no es una hoja
de cálculo**: es un `.zip` con la exportación **HTML** —una página por hoja más
`resources/`—. Descomprimirlo dejaba en el Drive un montón de páginas web que no
se pueden editar como libro.

Aquí, después de extraer, se mira si lo que salió es esa exportación de Google y,
si lo es, se arma el `.xlsx` y se deja **dentro de la misma carpeta**, para abrirlo
con el editor del Drive sin salir de aquí.

Las cuentas están en `almacen-maquita/herramientas/html-a-xlsx.py`; aquí solo está
la decisión de cuándo hacerlo y cómo dejarlo en el Drive.

Lo que conserva: texto, números y porcentajes como números, colores de fondo y de
letra, negrita y cursiva, tipo y tamaño, alineación, celdas combinadas, anchos y
altos. Lo que NO viaja en la exportación HTML de Google (y por tanto no puede
salir de aquí): fórmulas —vienen ya calculadas—, listas desplegables, formato
condicional, imágenes y gráficos. Para eso hay que bajar de Google con
«Archivo → Descargar → Microsoft Excel (.xlsx)».

Autoría: Equipo de Tecnología Maquita — 2026-09-08
"""
import importlib.util
import logging
import os
import tempfile

import nucleo_archivos as nucleo

log = logging.getLogger(__name__)

HERRAMIENTAS = '/home/sistemas/almacen-maquita/herramientas'


def _herramienta():
    """Carga `html-a-xlsx.py` (el guion tiene guiones: no se puede importar sin más)."""
    ruta = os.path.join(HERRAMIENTAS, 'html-a-xlsx.py')
    if not os.path.isfile(ruta):
        return None
    especificacion = importlib.util.spec_from_file_location('maq_html_a_xlsx', ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def hacer_libro(usuario_id, carpeta_virtual, carpeta_fisica, nombre_libro):
    """Si `carpeta_fisica` es la exportación HTML de un libro de Google, escribe el
    `.xlsx` y lo sube a `carpeta_virtual`. Devuelve el nombre del archivo creado, o
    `None` si no había nada que convertir.

    Nunca revienta hacia fuera: si algo falla, la descompresión ya está hecha y lo
    único que se pierde es el añadido (queda en el registro del servicio).
    """
    try:
        herramienta = _herramienta()
        if herramienta is None:
            log.warning('html-a-xlsx.py no está en %s', HERRAMIENTAS)
            return None
        if not herramienta.es_exportacion_de_google(carpeta_fisica):
            return None

        nombre = '%s.xlsx' % nombre_libro
        temporal = os.path.join(tempfile.gettempdir(),
                                'zip-google-%d-%s' % (os.getpid(), nombre))
        try:
            hojas = herramienta.convertir(carpeta_fisica, temporal)
            if not hojas:
                return None
            with open(temporal, 'rb') as flujo:
                nucleo.subir(usuario_id, carpeta_virtual, nombre, flujo)
        finally:
            if os.path.exists(temporal):
                os.remove(temporal)

        log.info('ZIP de Google: libro «%s» con %d hoja(s) en %s',
                 nombre, hojas, carpeta_virtual)
        return nombre
    except Exception:                                # noqa: BLE001
        log.exception('No se pudo armar el libro del ZIP de Google en %s', carpeta_virtual)
        return None
