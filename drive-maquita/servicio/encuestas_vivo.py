# -*- coding: utf-8 -*-
"""
Respuestas en la hoja del formulario CON EL LIBRO ABIERTO (21/09/2026)
=====================================================================
El archivo de respuestas de un formulario suele ser un Excel que la persona
trabaja: pestañas propias, columnas con fórmulas, encabezados renombrados. Por
eso el servidor no lo rehace, solo AÑADE filas (`encuestas_hoja_libro`). Pero
mientras alguien lo tiene abierto en el editor, el servidor no puede escribir:
el siguiente guardado de esa sesión pisa lo escrito (pasó el 21/09/2026).

Quien sí puede escribir dentro de la sesión es un complemento del editor. Este
módulo es lo que ese complemento —a través de la página del Drive, que tiene la
sesión— necesita saber:

  1. `hojas_de(...)`  → qué formularios escriben en este libro, en qué hoja, y
     cuántas respuestas tienen pendientes.
  2. `filas_para(...)` → esas respuestas ya colocadas en las columnas que el
     editor tiene AHORA (las manda él, que es quien ve el libro vivo), más las
     columnas que haya que crear y los encabezados que haya que renombrar.
  3. `estado_tras(...)` → el estado que se anota cuando el complemento confirma
     que escribió. Antes de la confirmación no se anota nada: si la escritura no
     cuaja, la respuesta sigue pendiente y entra por el camino del servidor.

La diferencia con `api_vinculos_vivo` (11/09) es que aquel PEGA la tabla entera
del origen en su hoja; aquí se AÑADEN filas al final de la tabla de la persona,
respetando sus fórmulas y sus columnas.

Autoría: Equipo de Tecnología Maquita — 2026-09-21
"""
import logging

import encuestas_bd as ebd
import encuestas_hoja as hoja_mod
import encuestas_hoja_libro as libro_mod
import encuestas_hoja_xml as xml_mod
import nucleo_archivos as nucleo

log = logging.getLogger('almacen.encuestas.vivo')


def _formularios_de(usuario, ruta_hoja):
    """Formularios cuya hoja de respuestas es este archivo."""
    return ebd.bd.consultar(
        "SELECT * FROM encuestas WHERE hoja_ruta = %s "
        "  AND (propietario = %s OR hoja_ruta LIKE '/unidades/%%') "
        "ORDER BY creada_en", (ruta_hoja, int(usuario)))


def _definicion(fila):
    from api_encuestas import leer_definicion
    return leer_definicion(int(fila['propietario']), fila['ruta'])


def _pendientes(fila, definicion):
    """(datos de la hoja, respuestas aún no escritas)."""
    datos = hoja_mod.datos_de_hoja(fila, definicion)
    estado = libro_mod.leer_estado(definicion['id'])
    hasta = estado['hasta'] if estado else None
    nuevas = [(c, e) for c, e in zip(datos['cuerpo'], datos['enviadas'])
              if e and (hasta is None or e > hasta)]
    return datos, nuevas


def hojas_de(usuario, ruta_hoja):
    """Qué hay que escribir en este libro abierto, sin leer respuestas de más.

    Devuelve una lista de {encuesta_id, titulo, hoja, pendientes}. `hoja` es la
    pestaña donde vive la tabla «Respuestas» del archivo en disco; si el libro
    no se puede leer, se devuelve vacío y no se toca nada.
    """
    salida, vistos = [], set()
    # Libros que reciben respuestas por una conexión (28/09/2026).
    try:
        import formulario_destinos
        salida.extend(formulario_destinos.vivo_hojas(usuario, ruta_hoja))
    except Exception as excepcion:
        log.warning('vivo %s: destinos (%s)', ruta_hoja, excepcion)
    for fila in _formularios_de(usuario, ruta_hoja):
        try:
            definicion = _definicion(fila)
            # Un mismo `.forma` puede tener varias filas en `encuestas` (copias
            # antiguas del registro): el formulario es uno solo.
            if definicion is None or definicion['id'] in vistos:
                continue
            vistos.add(definicion['id'])
            datos, nuevas = _pendientes(fila, definicion)
            if not nuevas:
                continue
            salida.append({'encuesta_id': definicion['id'],
                           'titulo': fila.get('titulo') or '',
                           'hoja': _hoja_de_la_tabla(usuario, ruta_hoja),
                           'pendientes': len(nuevas)})
        except Exception as excepcion:
            log.warning('vivo %s: no se pudo mirar (%s)', ruta_hoja, excepcion)
    return salida


def _hoja_de_la_tabla(usuario, ruta_hoja):
    """Nombre de la pestaña donde está la tabla «Respuestas»."""
    import io
    import re
    import zipfile
    fisica = nucleo.ruta_fisica(int(usuario), ruta_hoja)
    with open(fisica, 'rb') as archivo:
        contenido = archivo.read()
    z = zipfile.ZipFile(io.BytesIO(contenido))
    parte_hoja, _ = xml_mod._buscar_tabla(z)
    relaciones = xml_mod._rels(z, 'xl/workbook.xml')
    libro = z.read('xl/workbook.xml').decode('utf-8')
    for etiqueta in re.findall(r'<sheet [^>]*/>', libro):
        nombre = re.search(r'name="([^"]+)"', etiqueta)
        rid = re.search(r'r:id="([^"]+)"', etiqueta)
        if nombre and rid and relaciones.get(rid.group(1)) == parte_hoja:
            return xml_mod.unescape(nombre.group(1))
    return ''


def filas_para(usuario, ruta_hoja, encuesta_id, encabezados):
    """Las respuestas pendientes colocadas en las columnas del editor.

    `encabezados` son los que el complemento lee de la hoja ABIERTA (el disco
    puede estar desfasado). Devuelve {filas, columnas, renombres, hasta} donde
    cada fila es una lista del ancho final con `None` en las columnas que no se
    deben tocar (las de fórmulas de la persona, por ejemplo).
    """
    import formulario_destinos
    if str(encuesta_id).startswith(formulario_destinos.PREFIJO_VIVO):
        return formulario_destinos.vivo_filas(usuario, ruta_hoja, encuesta_id, encabezados)
    for fila in _formularios_de(usuario, ruta_hoja):
        definicion = _definicion(fila)
        if definicion is None or definicion['id'] != encuesta_id:
            continue
        datos, nuevas = _pendientes(fila, definicion)
        if not nuevas:
            return {'filas': [], 'columnas': [], 'renombres': [], 'hasta': ''}

        cabeceras, listado = datos['cabeceras'], datos['listado']
        desplazamiento = len(cabeceras) - len(listado)
        titulos = {p['id']: cabeceras[desplazamiento + i]
                   for i, p in enumerate(listado)}
        estado = libro_mod.leer_estado(encuesta_id)
        preguntas = estado['preguntas'] if estado else None
        if not isinstance(preguntas, dict):
            preguntas = libro_mod._preguntas_deducidas(preguntas, titulos, encabezados)

        plan = libro_mod._planear(encabezados, cabeceras[:desplazamiento],
                                  listado, titulos, preguntas)
        ancho = len(encabezados) + len(plan['columnas'])
        filas = [[_celda(celdas[plan['mapa'][i]]) if i in plan['mapa'] else None
                  for i in range(ancho)] for celdas, _ in nuevas]
        return {'filas': filas, 'columnas': plan['columnas'],
                'renombres': [list(r) for r in plan['renombres']],
                'hasta': max(e for _, e in nuevas).isoformat()}
    return None


def _celda(valor):
    """Valor tal como lo entiende el editor (las fechas, como texto local)."""
    import datetime
    if isinstance(valor, datetime.datetime):
        return valor.strftime('%d/%m/%Y %H:%M:%S')
    if isinstance(valor, datetime.date):
        return valor.strftime('%d/%m/%Y')
    return '' if valor is None else valor


def confirmar(usuario, ruta_hoja, encuesta_id, hasta, encabezados):
    """El complemento escribió: se da por escrito hasta esa respuesta.

    Las preguntas se vuelven a deducir contra los encabezados que quedaron en
    la hoja, que es lo que el próximo refresco va a encontrar.
    """
    import datetime
    import formulario_destinos
    if str(encuesta_id).startswith(formulario_destinos.PREFIJO_VIVO):
        return formulario_destinos.vivo_confirmar(usuario, ruta_hoja, encuesta_id, hasta)
    for fila in _formularios_de(usuario, ruta_hoja):
        definicion = _definicion(fila)
        if definicion is None or definicion['id'] != encuesta_id:
            continue
        datos = hoja_mod.datos_de_hoja(fila, definicion)
        cabeceras, listado = datos['cabeceras'], datos['listado']
        desplazamiento = len(cabeceras) - len(listado)
        titulos = {p['id']: cabeceras[desplazamiento + i]
                   for i, p in enumerate(listado)}
        momento = datetime.datetime.fromisoformat(hasta)
        # PROVISIONAL: esto está en la sesión del editor, no todavía en el
        # archivo. Al cerrarse el libro se comprueba y, si no llegó, la
        # respuesta vuelve a contar como pendiente (22/09/2026).
        # Se parte del estado anterior: deducir de cero olvidaba las columnas
        # que la persona borró en el editor y el motor las volvía a crear.
        previo = libro_mod.leer_estado(encuesta_id)
        libro_mod.guardar_estado(
            encuesta_id, momento,
            libro_mod.estado_tras_editor(previo and previo['preguntas'],
                                         titulos, encabezados),
            provisional=True)
        log.info('vivo %s: escrito en el editor hasta %s', ruta_hoja, momento)
        return True
    return False
