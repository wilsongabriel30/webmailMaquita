# -*- coding: utf-8 -*-
"""
Operaciones sueltas sobre un PDF que se sube.
=============================================

Comprimir, proteger con contraseña, marca de agua, encabezado y pie,
censurar, extraer páginas, reconocer texto y anotar. Se separaron de la API
del editor por el mismo motivo: eran otro bloque con vida propia.

Autoría: Equipo de Tecnología Maquita — 29-jul-2026
"""

import os
import logging
from flask import Blueprint, request, jsonify, send_file, g, current_app
from functools import wraps

logger = logging.getLogger(__name__)

bp_pdf_api = Blueprint('pdf_api', __name__)

from . import cabeceras
from .pdf_editor_api import (bp_pdf_api, obtener_servicio_pdf,
                             obtener_usuario_id,
                             requiere_autenticacion)

logger = logging.getLogger(__name__)


def _leer_pdf_upload():
    """Lee el archivo PDF del request como bytes. Retorna (bytes, nombre) o (None, None)."""
    archivo = request.files.get('archivo')
    if not archivo:
        return None, None
    nombre = archivo.filename or 'documento.pdf'
    if not nombre.lower().endswith('.pdf'):
        return None, None
    return archivo.read(), nombre



@bp_pdf_api.route('/operacion/comprimir', methods=['POST'])
@requiere_autenticacion
def operacion_comprimir():
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    calidad = request.form.get('calidad', 'media')
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        # En subproceso: comprimir con garbage collection es CPU-intensivo y
        # congelaria el worker eventlet (ver conversor_cli.py) -> 504
        from ...infraestructura.externos import cliente_conversiones as _conv
        resultado = _conv.en_subproceso('comprimir', [datos], params={'calidad': calidad})
        from io import BytesIO
        nombre_salida = nombre.rsplit('.', 1)[0] + '_comprimido.pdf'
        return send_file(BytesIO(resultado), mimetype='application/pdf',
                         as_attachment=True, download_name=nombre_salida)
    except Exception as e:
        logger.error(f"Error comprimiendo: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



@bp_pdf_api.route('/operacion/proteger', methods=['POST'])
@requiere_autenticacion
def operacion_proteger():
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    password = request.form.get('password', '').strip()
    if not password:
        return jsonify({'exito': False, 'mensaje': 'Se requiere una contraseña'}), 400
    permisos_impresion = request.form.get('impresion', 'true').lower() == 'true'
    permisos_copia = request.form.get('copia', 'false').lower() == 'true'
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        resultado = servicio.cliente_pdf.proteger_con_password(
            datos, password, permisos_impresion, permisos_copia)
        from io import BytesIO
        nombre_salida = nombre.rsplit('.', 1)[0] + '_protegido.pdf'
        return send_file(BytesIO(resultado), mimetype='application/pdf',
                         as_attachment=True, download_name=nombre_salida)
    except Exception as e:
        logger.error(f"Error protegiendo: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



@bp_pdf_api.route('/operacion/marca-agua', methods=['POST'])
@requiere_autenticacion
def operacion_marca_agua():
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    texto = request.form.get('texto', 'CONFIDENCIAL').strip() or 'CONFIDENCIAL'
    try:
        opacidad = float(request.form.get('opacidad', '0.25'))
        tamano   = float(request.form.get('tamano',   '60'))
        rotacion = float(request.form.get('rotacion', '45'))
    except ValueError:
        opacidad, tamano, rotacion = 0.25, 60, 45
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        resultado = servicio.cliente_pdf.agregar_marca_agua(datos, texto, opacidad, tamano, rotacion)
        from io import BytesIO
        nombre_salida = nombre.rsplit('.', 1)[0] + '_marcado.pdf'
        return send_file(BytesIO(resultado), mimetype='application/pdf',
                         as_attachment=True, download_name=nombre_salida)
    except Exception as e:
        logger.error(f"Error marca de agua: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



@bp_pdf_api.route('/operacion/encabezado-pie', methods=['POST'])
@requiere_autenticacion
def operacion_encabezado_pie():
    """Encabezado y pie con hasta tres textos por banda (izquierda/centro/derecha).

    Se siguen aceptando los campos sueltos `encabezado` y `pie` de la versión
    anterior, que se entienden como el texto de la izquierda: así nada de lo que
    ya llamaba a esto se queda sin funcionar.
    """
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400

    def _banda(prefijo, suelto=''):
        banda = {sitio: request.form.get('%s_%s' % (prefijo, sitio), '').strip()
                 for sitio in ('izquierda', 'centro', 'derecha')}
        if not any(banda.values()) and suelto:
            banda['izquierda'] = suelto
        return banda

    encabezado = _banda('encabezado', request.form.get('encabezado', '').strip())
    pie = _banda('pie', request.form.get('pie', '').strip())
    if not any(encabezado.values()) and not any(pie.values()):
        return jsonify({'exito': False,
                        'mensaje': 'Escribe al menos un texto en el encabezado o en el pie'}), 400
    try:
        tamano = int(request.form.get('tamano', '10'))
    except ValueError:
        tamano = 10
    margen = request.form.get('margen', 'normal')
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        resultado, aviso = servicio.cliente_pdf.agregar_encabezado_pie(
            datos, encabezado, pie, tamano, margen, nombre)
        from io import BytesIO
        nombre_salida = nombre.rsplit('.', 1)[0] + '_encabezado.pdf'
        respuesta = send_file(BytesIO(resultado), mimetype='application/pdf',
                              as_attachment=True, download_name=nombre_salida)
        # Va en una cabecera para no estropear el propio PDF de la respuesta
        cabeceras.poner(respuesta, 'X-Faro-Aviso', aviso)
        return respuesta
    except ValueError as e:
        return jsonify({'exito': False, 'mensaje': str(e)}), 400
    except Exception as e:
        logger.error(f"Error encabezado/pie: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



@bp_pdf_api.route('/operacion/censurar', methods=['POST'])
@requiere_autenticacion
def operacion_censurar():
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    terminos_raw = request.form.get('terminos', '')
    terminos = [t.strip() for t in terminos_raw.splitlines() if t.strip()]
    if not terminos:
        return jsonify({'exito': False, 'mensaje': 'Se requiere al menos un término a censurar'}), 400
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        resultado = servicio.cliente_pdf.censurar_texto(datos, terminos)
        from io import BytesIO
        nombre_salida = nombre.rsplit('.', 1)[0] + '_censurado.pdf'
        return send_file(BytesIO(resultado), mimetype='application/pdf',
                         as_attachment=True, download_name=nombre_salida)
    except Exception as e:
        logger.error(f"Error censurando: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



@bp_pdf_api.route('/operacion/extraer', methods=['POST'])
@requiere_autenticacion
def operacion_extraer():
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    paginas_raw = request.form.get('paginas', '').strip()
    paginas = []
    try:
        for parte in paginas_raw.split(','):
            parte = parte.strip()
            if '-' in parte:
                a, b = parte.split('-', 1)
                paginas.extend(range(int(a.strip()), int(b.strip()) + 1))
            elif parte:
                paginas.append(int(parte))
    except ValueError:
        return jsonify({'exito': False, 'mensaje': 'Formato inválido. Usa: 1,3,5-7'}), 400
    paginas = sorted(set(paginas))
    if not paginas:
        return jsonify({'exito': False, 'mensaje': 'Especifica las páginas a extraer'}), 400
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        resultado = servicio.cliente_pdf.extraer_paginas_desde_bytes(datos, paginas)
        from io import BytesIO
        nombre_salida = nombre.rsplit('.', 1)[0] + '_extracto.pdf'
        return send_file(BytesIO(resultado), mimetype='application/pdf',
                         as_attachment=True, download_name=nombre_salida)
    except Exception as e:
        logger.error(f"Error extrayendo páginas: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



def _leer_area(crudo):
    """El recuadro «x0,y0,x1,y1» que manda el editor, o None si no viene o no vale.

    Se comprueba aquí y no más adentro porque esto llega de fuera: cuatro números,
    ordenados, y con algo de tamaño (un clic suelto no es un área).
    """
    if not crudo:
        return None
    try:
        numeros = [float(v) for v in str(crudo).split(',')]
    except ValueError:
        return None
    if len(numeros) != 4:
        return None
    x0, y0, x1, y1 = numeros
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    if (x1 - x0) < 3 or (y1 - y0) < 3:
        return None
    return [x0, y0, x1, y1]


@bp_pdf_api.route('/operacion/ocr', methods=['POST'])
@requiere_autenticacion
def operacion_ocr():
    datos, _ = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    try:
        pagina_raw = request.form.get('pagina', '').strip()
        pagina = int(pagina_raw) if pagina_raw else None
    except ValueError:
        pagina = None
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        idioma = request.form.get('idioma', 'spa').strip() or 'spa'
        # Un recuadro dibujado a mano sobre la hoja, en puntos del PDF: «x0,y0,x1,y1».
        # Si viene, se lee SOLO esa zona y respetando cómo está escrita (pedido del
        # usuario, 31-jul-2026). Si no viene, la hoja entera como siempre.
        area = _leer_area(request.form.get('area'))
        parametros = {'pagina': pagina, 'idioma': idioma}
        if area:
            parametros['area'] = area
            parametros['pagina'] = pagina or 1
        # En subproceso: el OCR (tesseract) puede tardar minutos con escaneados grandes
        import json as _json
        from ...infraestructura.externos import cliente_conversiones as _conv
        resultado = _json.loads(_conv.en_subproceso('ocr', [datos],
                                params=parametros).decode('utf-8'))
        return jsonify({'exito': True, 'datos': resultado})
    except Exception as e:
        logger.error(f"Error OCR: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



@bp_pdf_api.route('/operacion/digitalizar', methods=['POST'])
@requiere_autenticacion
def operacion_digitalizar():
    """Convierte un escaneo en un PDF con TEXTO de verdad, y lo devuelve.

    Es lo que el usuario llama «digitalizar»: la hoja escaneada es una foto y no se
    puede seleccionar, buscar ni editar nada. Aquí se reconoce el texto con tesseract
    y se rehace el documento con ese texto de verdad, no como una capa invisible
    debajo de la imagen: así el editor puede tratarlo como cualquier otro PDF.

    Ya existía por dentro (lo usa la edición tipo Word), pero no había forma de
    pedirlo desde el editor. (30-jul-2026.)
    """
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    idioma = request.form.get('idioma', 'spa').strip() or 'spa'
    try:
        from ...infraestructura.externos import cliente_conversiones as _conv
        # En subproceso: tesseract es CPU pura y dentro del worker congelaría a los
        # demás usuarios. El tiempo se reparte entre varias páginas a la vez.
        resultado = _conv.en_subproceso('ocr-a-texto', [datos], params={'idioma': idioma})
    except Exception as e:
        # El mensaje de dentro habla de archivos temporales del servidor y no le dice
        # nada a quien lo lee: se guarda en el registro y se responde en cristiano.
        logger.error('Error digitalizando: %s', e)
        return jsonify({'exito': False, 'mensaje':
                        'No se pudo digitalizar el documento. Comprueba que el archivo '
                        'sea un PDF válido y vuelve a intentarlo.'}), 400

    if not resultado or resultado == datos:
        return jsonify({'exito': False, 'mensaje':
                        'No se reconoció texto en este documento. Si la copia está muy '
                        'clara, torcida o borrosa, conviene volver a escanearla.'}), 400

    from io import BytesIO
    base = (nombre or 'documento').rsplit('.', 1)[0]
    return send_file(BytesIO(resultado), mimetype='application/pdf',
                     as_attachment=True, download_name=base + '_digitalizado.pdf')


@bp_pdf_api.route('/operacion/buscar', methods=['POST'])
@requiere_autenticacion
def operacion_buscar():
    datos, _ = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    termino = request.form.get('termino', '').strip()
    if not termino:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un término de búsqueda'}), 400
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        resultados = servicio.cliente_pdf.buscar_en_bytes(datos, termino)
        return jsonify({'exito': True, 'termino': termino, 'total': len(resultados), 'resultados': resultados})
    except Exception as e:
        logger.error(f"Error buscando: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



@bp_pdf_api.route('/operacion/anotar', methods=['POST'])
@requiere_autenticacion
def operacion_anotar():
    """Aplica anotaciones (highlight, subrayado, tachado, texto, nota, dibujo) al PDF."""
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    anotaciones_raw = request.form.get('anotaciones', '[]')
    try:
        import json as _json
        anotaciones = _json.loads(anotaciones_raw)
        if not isinstance(anotaciones, list):
            raise ValueError('Se esperaba una lista')
    except Exception:
        return jsonify({'exito': False, 'mensaje': 'Formato de anotaciones inválido (se esperaba JSON array)'}), 400
    if not anotaciones:
        return jsonify({'exito': False, 'mensaje': 'No hay anotaciones que aplicar'}), 400
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        resultado = servicio.cliente_pdf.aplicar_anotaciones_desde_bytes(datos, anotaciones)
        from io import BytesIO
        nombre_salida = nombre.rsplit('.', 1)[0] + '_anotado.pdf'
        return send_file(BytesIO(resultado), mimetype='application/pdf',
                         as_attachment=True, download_name=nombre_salida)
    except Exception as e:
        logger.error(f"Error aplicando anotaciones: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400



@bp_pdf_api.route('/operacion/reemplazar-texto', methods=['POST'])
@requiere_autenticacion
def operacion_reemplazar_texto():
    """Sustituye fragmentos de texto del PDF conservando su tipografía original.

    Lo usa la edición con doble clic del editor: el navegador solo dispone de las 14
    fuentes estándar, así que el reemplazo fiel (con la fuente incrustada del propio
    documento) tiene que hacerse aquí. Además el texto viejo se borra de verdad.
    """
    datos, nombre = _leer_pdf_upload()
    if datos is None:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF válido'}), 400
    try:
        import json as _json
        ediciones = _json.loads(request.form.get('ediciones', '[]'))
        if not isinstance(ediciones, list):
            raise ValueError('Se esperaba una lista')
    except Exception:
        return jsonify({'exito': False, 'mensaje': 'Formato de ediciones inválido (se esperaba JSON array)'}), 400
    if not ediciones:
        return jsonify({'exito': False, 'mensaje': 'No hay ediciones que aplicar'}), 400
    try:
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({'exito': False, 'mensaje': 'Servicio PDF no disponible'}), 503
        resultado = servicio.cliente_pdf.reemplazar_texto_desde_bytes(datos, ediciones)
        from io import BytesIO
        nombre_salida = nombre.rsplit('.', 1)[0] + '_editado.pdf'
        resp = send_file(BytesIO(resultado), mimetype='application/pdf',
                         as_attachment=True, download_name=nombre_salida)
        # El editor usa esta cabecera para decirle al usuario con qué letra quedó
        # escrito cada fragmento (la del documento, una equivalente o una estándar)
        detalle = getattr(servicio.cliente_pdf, 'ultimo_detalle_fuentes', []) or []
        cabeceras.poner(resp, 'X-Fuentes-Usadas', ','.join(detalle))
        return resp
    except Exception as e:
        logger.error(f"Error reemplazando texto: {e}")
        return jsonify({'exito': False, 'mensaje': str(e)}), 400
