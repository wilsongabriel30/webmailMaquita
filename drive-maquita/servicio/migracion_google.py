# -*- coding: utf-8 -*-
"""Arreglar al vuelo los libros que llegan de Google Sheets.

Cuando alguien sube al Drive un `.xlsx` bajado de Google, el archivo llega con
tres cosas rotas (medidas el 07/09/2026 sobre un libro real):

  1. Los anchos de columna vienen un ~10 % más cortos de lo que Google dibuja, y
     como muchas celdas llevan «ajustar texto», el texto salta de línea, las
     filas crecen al doble y la tabla se descuadra.
  2. No trae la altura de las filas, así que cada programa se la inventa.
  3. Las etiquetas de los gráficos pierden su formato: enseñan 0,633333333 donde
     debería poner 63 %.

Y además, los gráficos que Google no supo convertir llegan como una IMAGEN.

Este módulo lo arregla en el momento de subir, sobre el archivo temporal y antes
de publicarlo, para que quien lo suba lo vea ya bien. Si algo falla, el archivo
se sube TAL CUAL: nunca se pierde la subida por esto.

Las cuentas están en las dos herramientas de `almacen-maquita/herramientas/`;
aquí solo se decide cuándo aplicarlas.
"""
import contextlib
import importlib.util
import io
import logging
import os
import re
import shutil
import tempfile
import zipfile

log = logging.getLogger(__name__)

HERRAMIENTAS = '/home/sistemas/almacen-maquita/herramientas'
_cache = {}


def _herramienta(nombre_fichero, clave):
    """Carga una de las herramientas (son guiones sueltos, no un paquete)."""
    if clave in _cache:
        return _cache[clave]
    ruta = os.path.join(HERRAMIENTAS, nombre_fichero)
    if not os.path.isfile(ruta):
        _cache[clave] = None
        return None
    try:
        spec = importlib.util.spec_from_file_location('maq_' + clave, ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
    except Exception as excepcion:            # noqa: BLE001
        log.warning('migración Google: no se pudo cargar %s (%s)', nombre_fichero, excepcion)
        modulo = None
    _cache[clave] = modulo
    return modulo


def viene_de_google(ruta):
    """¿Este `.xlsx` lo exportó Google Sheets?

    Se mira por tres señales, y basta la primera más cualquiera de las otras:
      · Google no escribe `docProps/app.xml` ni `core.xml`; Excel y OnlyOffice sí.
      · Deja `__xludf.DUMMYFUNCTION` donde había fórmulas que Excel no tiene.
      · Nombra `ChartN.png` las imágenes de los gráficos que no supo convertir.
    """
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
            if 'xl/workbook.xml' not in nombres:
                return False
            sin_docprops = not any(n.startswith('docProps/') for n in nombres)
            if not sin_docprops:
                return False
            if any(re.search(r'xl/media/Chart\d*\.png$', n, re.I) for n in nombres):
                return True
            for n in nombres:
                if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'):
                    trozo = z.read(n)[:400000]
                    if b'DUMMYFUNCTION' in trozo:
                        return True
            # Sin las otras señales, se mira si hay «ajustar texto» y ninguna
            # altura de fila: la mezcla que descuadra las tablas.
            estilos = z.read('xl/styles.xml').decode('utf-8', 'replace') \
                if 'xl/styles.xml' in nombres else ''
            if 'wrapText="1"' not in estilos:
                return False
            for n in nombres:
                if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'):
                    hoja = z.read(n)[:200000].decode('utf-8', 'replace')
                    filas = re.findall(r'<row\b[^>]*>', hoja)[:40]
                    if filas and sum(1 for f in filas if 'ht=' in f) <= 1:
                        return True
            return False
    except Exception:                          # noqa: BLE001
        return False


def arreglar(ruta, nombre=None):
    """Deja el archivo listo para verse como en Google. Devuelve un resumen de
       lo que se tocó, o None si no había nada que hacer.

     es el nombre de verdad del archivo: al subir, lo que hay en disco
    es un temporal («…xlsx.subiendo-123-456»), así que la extensión hay que
    mirarla en el nombre, no en la ruta."""
    if not str(nombre or ruta).lower().endswith('.xlsx'):
        return None
    if not viene_de_google(ruta):
        return None

    formato = _herramienta('arreglar-xlsx-de-google.py', 'formato')
    graficos = _herramienta('rehacer-graficos-imagen.py', 'graficos')
    if not formato and not graficos:
        return None

    carpeta = os.path.dirname(ruta)
    # El Drive deduplica con ENLACES DUROS: dos archivos con el mismo contenido
    # comparten inodo. Si se escribiera encima, se cambiaría también el archivo
    # de la otra persona. Por eso, si este archivo está compartido, primero se
    # le hace una copia propia (y así el arreglo solo le toca a él).
    try:
        if os.stat(ruta).st_nlink > 1:
            aparte = tempfile.mktemp(prefix='.google-copia-', suffix='.xlsx', dir=carpeta)
            shutil.copyfile(ruta, aparte)
            os.replace(aparte, ruta)
            log.info('migración Google: %s estaba compartido con otro archivo; '
                     'se le hizo copia propia antes de arreglarlo', ruta)
    except OSError as excepcion:
        log.warning('migración Google: no se pudo separar %s (%s)', ruta, excepcion)
        return None

    hecho = {}
    paso = None
    # Las herramientas cuentan por pantalla lo que hacen; aquí eso solo
    # ensuciaría el registro del servidor.
    callado = io.StringIO()
    try:
        if formato:
            paso = tempfile.mktemp(prefix='.google-formato-', suffix='.xlsx', dir=carpeta)
            with contextlib.redirect_stdout(callado):
                formato.main(ruta, paso)
            shutil.move(paso, ruta)
            paso = None
            hecho['formato'] = True
        if graficos:
            paso = tempfile.mktemp(prefix='.google-graficos-', suffix='.xlsx', dir=carpeta)
            with contextlib.redirect_stdout(callado):
                graficos.main(ruta, paso)
            if os.path.isfile(paso) and os.path.getsize(paso) > 0:
                shutil.move(paso, ruta)
                hecho['graficos'] = True
            paso = None
    except Exception as excepcion:              # noqa: BLE001
        log.warning('migración Google: no se pudo arreglar %s (%s)', ruta, excepcion)
        return None
    finally:
        if paso and os.path.exists(paso):
            try:
                os.remove(paso)
            except OSError:
                pass
    return hecho or None
