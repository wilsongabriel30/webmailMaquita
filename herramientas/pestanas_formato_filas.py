# -*- coding: utf-8 -*-
"""Iguala el formato de TODAS las filas preparadas de cada pestaña de provincia.

Las pestañas tienen 100 filas listas para recibir respuestas, pero el formato
(el de la fecha, sobre todo) solo llegaba hasta la última fila que tenía datos
cuando se armaron. A partir de ahí las celdas quedaban en «General», así que una
respuesta nueva mostraba la fecha como número (46275,47…) en vez de 10/09/2026.

Toma el estilo de la PRIMERA fila de datos de cada columna y lo aplica al resto
de las filas preparadas. Trabaja sobre el paquete del `.xlsx`; no toca fórmulas
ni valores, solo el atributo de estilo de cada celda.

Uso:
    python pestanas_formato_filas.py <usuario> "<ruta>" [--aplicar]

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import io
import re
import sys
import zipfile

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
sys.path.insert(0, '/home/sistemas/almacen-maquita/herramientas')

import nucleo_archivos as nucleo
from encuestas_hoja_xml import RE_CELDA, RE_FILA, _col_num
from formulas_provincias import HOJA_BASE, FILA_CABECERAS_PESTANA
from pestanas_encabezados import _hojas_del_paquete

PRIMERA = FILA_CABECERAS_PESTANA + 1
ULTIMA = FILA_CABECERAS_PESTANA + 100


def igualar(xml):
    """(xml con los estilos igualados, celdas cambiadas)."""
    modelo, cambios = {}, [0]

    def en_fila(m):
        fila = int(m.group(1))
        if not (PRIMERA <= fila <= ULTIMA):
            return m.group(0)

        def en_celda(c):
            columna = _col_num(c.group(1))
            atributos = c.group(3) or ''
            estilo = re.search(r'\bs="(\d+)"', atributos)
            if fila == PRIMERA:
                if estilo:
                    modelo[columna] = estilo.group(1)
                return c.group(0)
            if columna not in modelo or (estilo and estilo.group(1) == modelo[columna]):
                return c.group(0)
            cambios[0] += 1
            nuevos = re.sub(r'\s*\bs="\d+"', '', atributos)
            nuevos = ' s="%s"%s' % (modelo[columna], nuevos)
            cuerpo = c.group(4)
            if cuerpo is None:
                return '<c r="%s%s"%s/>' % (c.group(1), c.group(2), nuevos)
            return '<c r="%s%s"%s>%s</c>' % (c.group(1), c.group(2), nuevos, cuerpo)
        return '<row r="%s"%s>%s</row>' % (m.group(1), m.group(2),
                                           RE_CELDA.sub(en_celda, m.group(3) or ''))
    return RE_FILA.sub(en_fila, xml), cambios[0]


def principal(usuario, ruta, aplicar):
    fisica = nucleo.ruta_fisica(usuario, ruta)
    entrada = zipfile.ZipFile(io.BytesIO(open(fisica, 'rb').read()))
    hojas = _hojas_del_paquete(entrada)
    partes = {}
    for nombre, (parte, _) in hojas.items():
        if nombre == HOJA_BASE:
            continue
        xml, cambios = igualar(entrada.read(parte).decode('utf-8'))
        print('  %-12s %d celdas igualadas' % (nombre, cambios))
        if cambios:
            partes[parte] = xml
    if not partes:
        print('  nada que igualar')
        return 0
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as z:
        for elemento in entrada.infolist():
            datos = partes[elemento.filename].encode('utf-8') \
                if elemento.filename in partes else entrada.read(elemento.filename)
            z.writestr(elemento, datos)
    salida.seek(0)
    open('/tmp/pestanas-formato.xlsx', 'wb').write(salida.getvalue())
    print('  resultado en /tmp/pestanas-formato.xlsx')
    if aplicar:
        import sala_editor
        from api_onlyoffice import _base_documento, invalidar_cache
        dentro = sala_editor.usuarios_conectados(_base_documento(usuario, ruta))
        if dentro is None or dentro:
            print('  NO se aplica: el Excel está abierto en el editor (%s)' % dentro)
            return 2
        carpeta, _, nombre = ruta.rpartition('/')
        salida.seek(0)
        nucleo.subir(usuario, carpeta or '/', nombre, salida)
        invalidar_cache(usuario, ruta)
        print('  aplicado al Drive')
    return 0


if __name__ == '__main__':
    sys.exit(principal(int(sys.argv[1]), sys.argv[2], '--aplicar' in sys.argv))
