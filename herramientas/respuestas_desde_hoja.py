# -*- coding: utf-8 -*-
"""Devuelve a la base las respuestas que solo quedan en la hoja de Excel.

Para qué: «Borrar todas las respuestas» (en la vista de respuestas del
formulario) vacía la base, pero el `.xlsx` del Drive conserva una fila por
respuesta. Pasó el 21/09/2026 a las 16:52 con «prueba IFO»: la base quedó con 3
respuestas y el Excel con 25. Esto las reconstruye desde el archivo.

Cómo empareja: por el ENCABEZADO de cada columna con el título de cada pregunta
del formulario (igual que el motor). La columna «Fecha» da el momento de envío
y «Quién» el correo. Lo que no corresponda a ninguna pregunta (las columnas
propias de la persona) se ignora.

No duplica: una respuesta cuya fecha ya está en la base se salta.

Uso:
    python respuestas_desde_hoja.py <usuario> "<ruta del .forma>" [--aplicar]

Sin `--aplicar` solo dice qué haría.

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import json
import sys
import unicodedata
import re
from datetime import datetime, timedelta

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import almacen_bd as bd
import encuestas_bd as ebd
import encuestas_hoja as hoja_mod
import encuestas_hoja_xml as xml_mod
import encuestas_modelo as modelo
import nucleo_archivos as nucleo
from api_encuestas import leer_definicion


def plano(texto):
    sin = unicodedata.normalize('NFKD', str(texto or ''))
    sin = ''.join(c for c in sin if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', sin).strip().upper()


def momento_de(texto):
    try:
        return datetime(1899, 12, 30) + timedelta(days=float(texto))
    except (TypeError, ValueError):
        return None


def principal(usuario, ruta_forma, aplicar):
    definicion = leer_definicion(usuario, ruta_forma)
    if definicion is None:
        raise SystemExit('no se pudo leer el formulario %s' % ruta_forma)
    filas_bd = bd.consultar('SELECT id, hoja_ruta FROM encuestas WHERE ruta = %s '
                            'ORDER BY actualizada_en DESC', (ruta_forma,))
    if not filas_bd:
        raise SystemExit('ese formulario no está registrado')
    encuesta_id = definicion['id']
    ruta_hoja = next((f['hoja_ruta'] for f in filas_bd if f['hoja_ruta']), None)
    if not ruta_hoja:
        raise SystemExit('ese formulario no tiene hoja de respuestas')
    print('  formulario : %s' % ruta_forma)
    print('  hoja       : %s' % ruta_hoja)

    contenido = open(nucleo.ruta_fisica(usuario, ruta_hoja), 'rb').read()
    encabezados, filas = xml_mod.leer_tabla(contenido)
    preguntas = modelo.preguntas(definicion)
    por_titulo = {plano(modelo.plano(p['titulo'])): p for p in preguntas}
    columna_de = {}
    for i, titulo in enumerate(encabezados):
        pregunta = por_titulo.get(plano(titulo))
        if pregunta:
            columna_de[i] = pregunta['id']
    i_fecha = next((i for i, t in enumerate(encabezados) if plano(t) == 'FECHA'), None)
    i_quien = next((i for i, t in enumerate(encabezados) if plano(t) == 'QUIEN'), None)
    print('  columnas emparejadas con preguntas: %d de %d encabezados'
          % (len(columna_de), len(encabezados)))

    existentes = set()
    for fila in ebd.listar_respuestas(encuesta_id):
        if fila['enviada_en']:
            existentes.add(fila['enviada_en'].replace(tzinfo=None, microsecond=0))
    nuevas = []
    for valores in filas:
        momento = momento_de(valores[i_fecha]) if i_fecha is not None else None
        if momento:
            momento = (momento + timedelta(milliseconds=500)).replace(microsecond=0)
            if momento in existentes:
                continue
        datos = {}
        for i, id_pregunta in columna_de.items():
            valor = valores[i] if i < len(valores) else ''
            if valor not in (None, ''):
                datos[id_pregunta] = valor
        if not datos:
            continue
        correo = valores[i_quien] if i_quien is not None and i_quien < len(valores) else ''
        nuevas.append((momento, datos, correo if '@' in str(correo) else ''))

    print('  respuestas en la hoja: %d | ya en la base: %d | se recuperarían: %d'
          % (len(filas), len(existentes), len(nuevas)))
    for momento, datos, correo in nuevas[:5]:
        print('     %s  %-28s  %d respuestas' % (momento, correo[:28], len(datos)))
    if len(nuevas) > 5:
        print('     … y %d más' % (len(nuevas) - 5))

    if not aplicar or not nuevas:
        return 0
    for momento, datos, correo in nuevas:
        nueva_id = ebd.guardar_respuesta(encuesta_id, json.dumps(datos, ensure_ascii=False),
                                         None, correo or None)
        if momento:
            bd.ejecutar('UPDATE encuesta_respuestas SET enviada_en = %s WHERE id = %s',
                        (momento, nueva_id))
    print('  recuperadas %d respuestas' % len(nuevas))
    # El estado de la hoja se deja como está: las filas ya están escritas.
    fila = ebd.obtener(encuesta_id)
    if fila:
        import encuestas_hoja_libro as libro
        estado = libro.leer_estado(encuesta_id)
        ultima = max(m for m, _, _ in nuevas if m) if any(m for m, _, _ in nuevas) else None
        if estado and ultima and (estado['hasta'] is None or
                                  ultima.replace(tzinfo=estado['hasta'].tzinfo if estado['hasta'] else None)
                                  > (estado['hasta'] or ultima)):
            pass
    return 0


if __name__ == '__main__':
    sys.exit(principal(int(sys.argv[1]), sys.argv[2], '--aplicar' in sys.argv))
