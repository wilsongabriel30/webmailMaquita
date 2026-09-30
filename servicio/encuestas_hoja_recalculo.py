# -*- coding: utf-8 -*-
"""
Formularios del Almacén — que OnlyOffice deje calculadas las fórmulas de la hoja
===============================================================================
Las filas que añade `encuestas_hoja_xml` llevan la fórmula pero no su resultado
(Python no sabe calcular `SUM(Respuestas[[#This Row],…])`). Sin resultado
guardado, la fórmula se veía como texto «=SUM(…» en vez del número (caso
«prueba IFO», 17/09/2026).

Solución: se le pide al propio Document Server (servicio `docbuilder`) que abra
el libro y lo vuelva a guardar. OnlyOffice calcula todo al abrir y guarda los
resultados, igual que cuando la persona guarda desde el editor.

- El docbuilder de esta versión no admite `argument`, así que el script se
  genera por petición con la URL de descarga firmada (caduca en 5 minutos), se
  publica con nombre aleatorio en los estáticos y se borra al terminar.
- **Nunca falla hacia fuera:** si no se puede recalcular se devuelve None y se
  queda el libro con las filas añadidas (los datos ya están bien).

Autoría: Equipo de Tecnología Maquita — 2026-09-17
"""
import io
import logging
import os
import secrets
import time
import zipfile

log = logging.getLogger('almacen.encuestas.hoja_recalculo')

CARPETA_SCRIPTS = ('/home/sistemas/Maquita/interfaces/web/estaticos/'
                   'almacen/recalculo')
URL_SCRIPTS = '/static/almacen/recalculo'
SEGUNDOS_TOKEN = 300

# OnlyOffice NO recalcula al abrir las fórmulas AGGREGATE con matrices (las de
# reparto por provincia, columna CC de «prueba IFO»): conserva el resultado
# guardado, ni con fullCalcOnLoad ni con RecalculateAllFormulas. Las respuestas
# nuevas no llegaban a su pestaña (28/09/2026). Reescribir la fórmula sí la
# calcula. Se busca en qué columnas están (primeras filas y la última) y se
# reescriben por tramos de fórmula idéntica: celda a celda tardaba 60 s, así 12 s.
REAPLICAR_AGREGAR = '''
(function () {
  var hojas = Api.GetSheets();
  for (var i = 0; i < hojas.length; i++) {
    var hoja = hojas[i], usado = hoja.GetUsedRange();
    var f0 = usado.GetRow() - 1, c0 = usado.GetCol() - 1;
    var filas = usado.GetRowsCount(), cols = usado.GetCount() / filas;
    var muestra = [], columnas = {};
    for (var f = 0; f < Math.min(filas, 12); f++) muestra.push(f);
    if (filas > 12) muestra.push(filas - 1);
    for (var m = 0; m < muestra.length; m++)
      for (var c = 0; c < cols; c++) {
        var x = hoja.GetRangeByNumber(f0 + muestra[m], c0 + c).GetFormula();
        if (typeof x === "string" && x.indexOf("AGGREGATE(") > 0) columnas[c] = true;
      }
    for (var col in columnas) {
      var cc = c0 + Number(col), tramo = null;
      var cerrar = function () {
        if (!tramo) return;
        hoja.GetRange(hoja.GetRangeByNumber(tramo.desde, cc).GetAddress(false, false) + ":" +
                      hoja.GetRangeByNumber(tramo.hasta, cc).GetAddress(false, false))
            .SetValue(tramo.formula);
        tramo = null;
      };
      for (var f = 0; f < filas; f++) {
        var y = hoja.GetRangeByNumber(f0 + f, cc).GetFormula();
        var es = typeof y === "string" && y.indexOf("AGGREGATE(") > 0;
        if (es && tramo && tramo.formula === y && tramo.hasta === f0 + f - 1) tramo.hasta = f0 + f;
        else { cerrar(); if (es) tramo = {desde: f0 + f, hasta: f0 + f, formula: y}; }
      }
      cerrar();
    }
  }
})();
'''


def _tiene_formulas(fisica):
    """¿Alguna pestaña del libro lleva fórmulas? Ante la duda, sí."""
    try:
        with zipfile.ZipFile(fisica) as z:
            for nombre in z.namelist():
                if nombre.startswith('xl/worksheets/') and nombre.endswith('.xml') \
                        and b'<f' in z.read(nombre):
                    return True
        return False
    except Exception:
        return True


def recalcular(usuario, ruta):
    """Bytes del libro de disco (usuario, ruta) recalculado por OnlyOffice, o None."""
    script = None
    try:
        # Sin fórmulas no hay nada que calcular: se ahorra la ida al Document
        # Server, que tarda segundos y hacía esperar al abrir la hoja (29/09/2026).
        import nucleo_archivos
        if not _tiene_formulas(nucleo_archivos.ruta_fisica(int(usuario), ruta)):
            return None
        import requests
        from config_almacen import URL_PUBLICA
        from api_onlyoffice import firmar_jwt, url_interna_ds, _reescribir_url_interna

        token = firmar_jwt({'u': int(usuario), 'r': ruta, 'uso': 'descarga',
                            'exp': int(time.time()) + SEGUNDOS_TOKEN})
        url_libro = '%s/api/almacen/onlyoffice/download?t=%s' % (URL_PUBLICA, token)
        os.makedirs(CARPETA_SCRIPTS, exist_ok=True)
        nombre = secrets.token_hex(16) + '.docbuilder'
        script = os.path.join(CARPETA_SCRIPTS, nombre)
        with open(script, 'w', encoding='utf-8') as salida:
            # Sin RecalculateAllFormulas solo se calcula la pestaña activa.
            salida.write('builder.OpenFile("%s");\n' % url_libro.replace('"', '')
                         + REAPLICAR_AGREGAR
                         + 'Api.RecalculateAllFormulas();\n'
                           'builder.SaveFile("xlsx", "recalculado.xlsx");\n'
                           'builder.CloseFile();\n')
        os.chmod(script, 0o644)

        cuerpo = {'async': False, 'key': 'hoja' + secrets.token_hex(8),
                  'url': '%s%s/%s' % (URL_PUBLICA, URL_SCRIPTS, nombre)}
        cuerpo['token'] = firmar_jwt(dict(cuerpo))
        respuesta = requests.post(
            url_interna_ds().rstrip('/') + '/docbuilder', json=cuerpo, timeout=(3, 120),
            headers={'Authorization': 'Bearer ' + firmar_jwt({'payload': cuerpo})})
        datos = respuesta.json() or {}
        urls = list((datos.get('urls') or {}).values())
        if not urls:
            log.warning('recalcular %s: docbuilder respondió %s', ruta, datos)
            return None
        libro = requests.get(_reescribir_url_interna(urls[0]), timeout=(3, 60))
        libro.raise_for_status()
        contenido = libro.content
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:      # que sea un xlsx sano
            if 'xl/workbook.xml' not in z.namelist():
                return None
        return contenido
    except Exception as excepcion:
        log.warning('recalcular %s: %s', ruta, excepcion)
        return None
    finally:
        if script:
            try:
                os.remove(script)
            except OSError:
                pass
