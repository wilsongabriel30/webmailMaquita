# -*- coding: utf-8 -*-
"""Columna LINK de los consolidados: de enlaces de Google a enlaces del Drive.

    enlaces_drive.py [--sandbox] [--solo <texto>]

Solo cambia el HIPERVÍNCULO de las celdas con texto; el texto (nombre del archivo
o URL de Google en «Respaldo») se conserva porque es lo que lee la consolidación.
Salta los consolidados abiertos en el editor (el cierre pisaría el cambio).
"""
import io, os, sys
from urllib.parse import quote
sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio/consolidados')
import openpyxl
from openpyxl.styles import Font
import consolidar_asc as c
import nucleo_archivos as nucleo
from api_onlyoffice import invalidar_cache, _base_documento
from guardado_forzado import _sala_abierta

if '--sandbox' in sys.argv:
    import sandbox
    sandbox.aplicar(c.__dict__)
solo = sys.argv[sys.argv.index('--solo') + 1] if '--solo' in sys.argv else ''
indice = c.indice_de_archivos()
equiv = c.mapa_ids_google()
EDITOR = 'https://datos.maquita.com.ec/archivos-almacen/editar?ruta='


def ruta_virtual(fisica):
    return c.BASE_VIRTUAL + '/' + os.path.relpath(fisica, c.BASE_FISICA).replace(os.sep, '/')


for d in c.CONSOLIDADOS:
    if solo and solo.lower() not in d['archivo'].lower():
        continue
    fisica = os.path.join(c.BASE_FISICA, d['archivo'])
    if not os.path.isfile(fisica):
        continue
    virt = c.BASE_VIRTUAL + '/' + d['archivo']
    if _sala_abierta(_base_documento(c.USUARIO, virt)):
        print('ABIERTO, se salta:', d['archivo'])
        continue
    libro = openpyxl.load_workbook(fisica)
    hoja = libro[d['hoja']]
    cambiados, sin_resolver = 0, []
    for fila in range(d['fila_inicio'], d['fila_fin'] + 1):
        celda = hoja.cell(row=fila, column=3)
        texto = str(celda.value).strip() if celda.value is not None else ''
        if not texto:
            celda.hyperlink = None          # sin texto no hay enlace (openpyxl escribiría la URL)
            continue
        destino = celda.hyperlink.target if celda.hyperlink else ''
        if 'datos.maquita.com.ec' in (destino or ''):
            continue
        referencia = texto
        m = c._RE_ID_GOOGLE.search(texto) or c._RE_ID_GOOGLE.search(destino or '')
        if m:
            referencia = equiv.get(m.group(1), referencia)
        ruta = indice.get(referencia)
        if not ruta:
            sin_resolver.append(texto[:50]); continue
        celda.hyperlink = EDITOR + quote(ruta_virtual(ruta))
        f = celda.font
        celda.font = Font(name=f.name, size=f.size, bold=f.bold, underline='single', color='1155CC')
        cambiados += 1
    if cambiados:
        memoria = io.BytesIO(); libro.save(memoria); memoria.seek(0)
        carpeta, _, nombre = virt.rpartition('/')
        nucleo.subir(c.USUARIO, carpeta, nombre, memoria)
        invalidar_cache(c.USUARIO, virt)
    libro.close()
    print('%s: %d enlaces al Drive%s' % (d['archivo'], cambiados,
          (' | sin resolver: %s' % sin_resolver) if sin_resolver else ''))
