# -*- coding: utf-8 -*-
"""
API de conversiones "premium" del Editor PDF.

Blueprint separado de pdf_editor_api.py para mantener el módulo pequeño:
aquí viven solo las conversiones de formato y las herramientas de páginas
que agregan valor frente a los editores de pago:

- POST /operacion/pdf-a-word        PDF → .docx editable (pdf2docx)
- POST /operacion/pdf-a-excel       Tablas del PDF → .xlsx (pdfplumber)
- POST /operacion/pdf-a-ppt         PDF → .pptx (una diapositiva por página)
- POST /operacion/convertir-oficina Word/Excel/PPT/ODF/RTF/HTML/TXT → PDF (Gotenberg en Docker)
- POST /operacion/numerar-paginas   Estampa números de página
- POST /operacion/dividir           Divide por rangos ("1-3,5,8-10") → zip o PDF
- POST /ia/consulta                 Consulta al asistente de IA institucional (Ollama)
- POST /operacion/desbloquear       Quita la contraseña (conociéndola)
- POST /operacion/comparar          Compara dos PDFs → PDF-reporte de diferencias

Todos reciben multipart con el campo `archivo` y devuelven el archivo
resultante como descarga. La autenticación se reutiliza de pdf_editor_api.
"""

import io
from urllib.parse import quote
import logging
import os
import zipfile

from flask import Blueprint, request, jsonify, send_file

from .pdf_editor_api import requiere_autenticacion
from ...infraestructura.externos import cliente_conversiones as conv

logger = logging.getLogger(__name__)

bp_pdf_conversiones = Blueprint('pdf_conversiones', __name__)


def _leer_archivo(campo='archivo'):
    """Lee el archivo del multipart. Devuelve (nombre, bytes) o aborta con 400."""
    archivo = request.files.get(campo)
    if not archivo or not archivo.filename:
        return None, None
    return archivo.filename, archivo.read()


def _nombre_base(nombre):
    """Nombre sin extensión, apto para armar el nombre de descarga."""
    return os.path.splitext(os.path.basename(nombre or 'documento'))[0]


def _error(mensaje, codigo=400):
    return jsonify({'exito': False, 'mensaje': mensaje}), codigo


def _descarga(contenido, nombre, mimetype):
    return send_file(io.BytesIO(contenido), mimetype=mimetype,
                     as_attachment=True, download_name=nombre)


# ============================================================
# PDF → OFFICE
# ============================================================

@bp_pdf_conversiones.route('/operacion/pdf-a-word', methods=['POST'])
@requiere_autenticacion
def pdf_a_word():
    """Convierte el PDF subido a Word (.docx) editable."""
    nombre, contenido = _leer_archivo()
    if not contenido:
        return _error('Falta el archivo PDF.')
    aviso = None
    try:
        # En subproceso: CPU-intensivo, no debe congelar el worker eventlet (504)
        docx = conv.en_subproceso('pdf-a-word', [contenido])
    except conv.ErrorConversion as e:
        # pdf2docx no pudo con este documento. Antes el usuario se quedaba sin nada
        # (medido el 30-jul-2026: respuesta 400 y ni un archivo). Ahora se intenta el
        # respaldo: se saca el texto y las tablas y se monta un Word sencillo. Pierde
        # la maquetación, pero es editable y el usuario se lleva su documento.
        logger.warning('pdf-a-word con maquetación falló (%s): se prueba el respaldo', e)
        try:
            docx = conv.en_subproceso('pdf-a-word-sencillo', [contenido])
        except conv.ErrorConversion as e2:
            # El respaldo también avisa cuando no hay NADA que convertir (un escaneo
            # sin OCR): ese mensaje es el útil para el usuario, no el de pdf2docx.
            return _error(str(e2))
        except Exception as e2:
            logger.exception('pdf-a-word-sencillo')
            return _error('No se pudo convertir a Word: %s' % e, 500)
        aviso = ('Este documento no admitió la conversión con maquetación, así que se '
                 'convirtió de forma sencilla: el texto y las tablas están completos y '
                 'editables, pero la colocación en la hoja no se conserva.')
    except Exception as e:
        logger.exception('pdf-a-word')
        return _error('Error inesperado al convertir a Word: %s' % e, 500)
    respuesta = _descarga(docx, _nombre_base(nombre) + '.docx',
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    if aviso:
        # El editor lee esta cabecera y lo dice en pantalla. Va codificada porque una
        # cabecera HTTP no admite tildes.
        respuesta.headers['X-Aviso-Conversion'] = quote(aviso)
    return respuesta


@bp_pdf_conversiones.route('/operacion/pdf-a-excel', methods=['POST'])
@requiere_autenticacion
def pdf_a_excel():
    """Extrae las tablas (o el texto) del PDF a Excel (.xlsx)."""
    nombre, contenido = _leer_archivo()
    if not contenido:
        return _error('Falta el archivo PDF.')
    try:
        xlsx = conv.en_subproceso('pdf-a-excel', [contenido])
    except conv.ErrorConversion as e:
        return _error(str(e))
    except Exception as e:
        logger.exception('pdf-a-excel')
        return _error('Error inesperado al convertir a Excel: %s' % e, 500)
    return _descarga(xlsx, _nombre_base(nombre) + '.xlsx',
                     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@bp_pdf_conversiones.route('/operacion/pdf-a-ppt', methods=['POST'])
@requiere_autenticacion
def pdf_a_ppt():
    """Convierte el PDF a PowerPoint (.pptx), una diapositiva por página."""
    nombre, contenido = _leer_archivo()
    if not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pptx = conv.en_subproceso('pdf-a-ppt', [contenido])
    except conv.ErrorConversion as e:
        return _error(str(e))
    except Exception as e:
        logger.exception('pdf-a-ppt')
        return _error('Error inesperado al convertir a PowerPoint: %s' % e, 500)
    return _descarga(pptx, _nombre_base(nombre) + '.pptx',
                     'application/vnd.openxmlformats-officedocument.presentationml.presentation')


# ============================================================
# OFFICE → PDF (Gotenberg)
# ============================================================

@bp_pdf_conversiones.route('/operacion/convertir-oficina', methods=['POST'])
@requiere_autenticacion
def convertir_oficina():
    """Convierte Word/Excel/PowerPoint/ODF/RTF/HTML/TXT a PDF via Gotenberg."""
    nombre, contenido = _leer_archivo()
    if not contenido:
        return _error('Falta el archivo a convertir.')
    try:
        pdf = conv.oficina_a_pdf(nombre, contenido)
    except conv.ErrorConversion as e:
        return _error(str(e))
    except Exception as e:
        logger.exception('convertir-oficina')
        return _error('Error inesperado al convertir a PDF: %s' % e, 500)
    return _descarga(pdf, _nombre_base(nombre) + '.pdf', 'application/pdf')


# ============================================================
# HERRAMIENTAS DE PÁGINAS
# ============================================================

@bp_pdf_conversiones.route('/operacion/numerar-paginas', methods=['POST'])
@requiere_autenticacion
def numerar_paginas():
    """Estampa números de página. Params: posicion, formato ({n}, {total}), tamano, desde."""
    nombre, contenido = _leer_archivo()
    if not contenido:
        return _error('Falta el archivo PDF.')
    try:
        resultado = conv.numerar_paginas(
            contenido,
            posicion=request.form.get('posicion', 'abajo-centro'),
            formato=request.form.get('formato', '{n} de {total}'),
            tamano=int(request.form.get('tamano', '10')),
            desde=int(request.form.get('desde', '1')),
        )
    except conv.ErrorConversion as e:
        return _error(str(e))
    except ValueError:
        return _error('Parámetros numéricos inválidos.')
    except Exception as e:
        logger.exception('numerar-paginas')
        return _error('Error inesperado al numerar: %s' % e, 500)
    return _descarga(resultado, _nombre_base(nombre) + '_numerado.pdf', 'application/pdf')


@bp_pdf_conversiones.route('/operacion/dividir', methods=['POST'])
@requiere_autenticacion
def dividir():
    """Divide el PDF por rangos. Param `rangos` ("1-3,5,8-10").

    Un solo rango → devuelve ese PDF. Varios → zip con todas las partes.
    """
    nombre, contenido = _leer_archivo()
    if not contenido:
        return _error('Falta el archivo PDF.')
    try:
        partes = conv.dividir(contenido, request.form.get('rangos', ''))
    except conv.ErrorConversion as e:
        return _error(str(e))
    except Exception as e:
        logger.exception('dividir')
        return _error('Error inesperado al dividir: %s' % e, 500)

    base = _nombre_base(nombre)
    if len(partes) == 1:
        nombre_parte, pdf = partes[0]
        return _descarga(pdf, '%s_%s' % (base, nombre_parte), 'application/pdf')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for nombre_parte, pdf in partes:
            z.writestr('%s_%s' % (base, nombre_parte), pdf)
    return _descarga(buf.getvalue(), base + '_dividido.zip', 'application/zip')


@bp_pdf_conversiones.route('/operacion/comparar', methods=['POST'])
@requiere_autenticacion
def comparar():
    """Compara dos PDFs y devuelve un PDF-reporte con las diferencias.

    Multipart: `archivo_original` y `archivo_modificado`.
    El reporte trae resumen (páginas cambiadas/agregadas/eliminadas + diff de
    texto) y cada página modificada con las zonas distintas recuadradas en rojo.
    """
    original = request.files.get('archivo_original')
    modificado = request.files.get('archivo_modificado')
    if not original or not modificado:
        return _error('Se necesitan los dos PDFs: original y modificado.')
    try:
        # En subproceso: el diff visual con OpenCV es CPU-intensivo
        reporte = conv.en_subproceso('comparar', [original.read(), modificado.read()])
    except conv.ErrorConversion as e:
        return _error(str(e))
    except Exception as e:
        logger.exception('comparar')
        return _error('Error inesperado al comparar: %s' % e, 500)
    return _descarga(reporte, 'comparacion.pdf', 'application/pdf')


@bp_pdf_conversiones.route('/operacion/desbloquear', methods=['POST'])
@requiere_autenticacion
def desbloquear():
    """Quita la contraseña de un PDF. Param `password` (hay que conocerla)."""
    nombre, contenido = _leer_archivo()
    if not contenido:
        return _error('Falta el archivo PDF.')
    try:
        resultado = conv.desbloquear(contenido, request.form.get('password', ''))
    except conv.ErrorConversion as e:
        return _error(str(e))
    except Exception as e:
        logger.exception('desbloquear')
        return _error('Error inesperado al desbloquear: %s' % e, 500)
    return _descarga(resultado, _nombre_base(nombre) + '_desbloqueado.pdf', 'application/pdf')

@bp_pdf_conversiones.route('/operacion/texto-a-word', methods=['POST'])
@requiere_autenticacion
def texto_a_word():
    """Convierte texto plano (extraído del PDF o del OCR) en un documento Word.

    JSON: `texto` (obligatorio), `nombre` (opcional, sin extensión). El usuario
    prefiere Word en lugar de .txt para poder seguir editando el contenido.
    """
    datos = request.get_json(silent=True) or {}
    texto = (datos.get('texto') or '').strip()
    if not texto:
        return _error('No hay texto para exportar.')
    if len(texto) > 5 * 1024 * 1024:
        return _error('El texto es demasiado grande para exportarlo a Word.')
    try:
        from docx import Document
        doc = Document()
        for parrafo in texto.split('\n'):
            doc.add_paragraph(parrafo)
        buf = io.BytesIO()
        doc.save(buf)
        contenido = buf.getvalue()
    except Exception as e:
        logger.exception('texto-a-word')
        return _error('No se pudo generar el Word: %s' % e, 500)
    nombre = (datos.get('nombre') or 'documento').strip() or 'documento'
    return _descarga(contenido, nombre + '.docx',
                     'application/vnd.openxmlformats-officedocument.wordprocessingml.document')


# La URL del servidor Ollama la administra FARO (admin -> Configuración IA,
# tabla system_config). Se cachea 5 minutos para no consultar la BD por pregunta.
_CFG_IA = {'url': '', 'habilitado': False, 'ts': 0.0}


def _config_ia():
    import time as _t
    if _t.time() - _CFG_IA['ts'] < 300 and _CFG_IA['url']:
        return _CFG_IA
    try:
        from flask import current_app
        from sqlalchemy import create_engine, text as _sql
        uri = (current_app.config.get('AUTH_DATABASE_URI')
               or current_app.config.get('SQLALCHEMY_DATABASE_URI'))
        if not uri:
            # la app no publica la URI en app.config: usar la clase Config
            # (ya importada por la app con el .env cargado)
            from config import Config as _Cfg
            uri = _Cfg.AUTH_DATABASE_URI
        eng = create_engine(uri, pool_pre_ping=True)
        with eng.connect() as c:
            fila = c.execute(_sql(
                "SELECT ollama_api_url, ollama_enabled FROM system_config LIMIT 1")).fetchone()
        eng.dispose()
        if fila:
            _CFG_IA.update(url=(fila[0] or '').rstrip('/'),
                           habilitado=bool(fila[1]), ts=_t.time())
    except Exception:
        logger.exception('No se pudo leer la configuración de IA')
    return _CFG_IA


@bp_pdf_conversiones.route('/ia/consulta', methods=['POST'])
@requiere_autenticacion
def ia_consulta():
    """Consulta al asistente de IA institucional (Ollama) y devuelve su respuesta.

    JSON: `mensaje` (obligatorio). Bajo eventlet la espera HTTP es cooperativa,
    así que el worker sigue atendiendo al resto de usuarios mientras el modelo genera.
    """
    import requests

    datos = request.get_json(silent=True) or {}
    mensaje = (datos.get('mensaje') or '').strip()
    if not mensaje:
        return _error('Falta la pregunta para el asistente.')
    if len(mensaje) > 40000:
        mensaje = mensaje[:40000]

    cfg = _config_ia()
    if not cfg['habilitado'] or not cfg['url']:
        return _error('El asistente de IA no está habilitado en la configuración del sistema.', 503)

    sistema = ('Eres el Asistente de IA de FARO Maquita. Responde siempre en español, '
               'de forma clara y concisa. Si recibes el texto de un documento, basa tu '
               'respuesta únicamente en ese contenido.')
    try:
        r = requests.post(cfg['url'] + '/api/chat', json={
            'model': 'qwen2.5:14b',
            'messages': [{'role': 'system', 'content': sistema},
                         {'role': 'user', 'content': mensaje}],
            'stream': False,
            'options': {'temperature': 0.3, 'num_predict': 800},
        }, timeout=180)
        if r.status_code == 404:
            # el modelo configurado no existe en el servidor: usar el primero disponible
            tags = requests.get(cfg['url'] + '/api/tags', timeout=15).json().get('models') or []
            if not tags:
                return _error('El servidor de IA no tiene modelos instalados.', 502)
            r = requests.post(cfg['url'] + '/api/chat', json={
                'model': tags[0]['name'],
                'messages': [{'role': 'system', 'content': sistema},
                             {'role': 'user', 'content': mensaje}],
                'stream': False,
                'options': {'temperature': 0.3, 'num_predict': 800},
            }, timeout=180)
        r.raise_for_status()
        contenido = ((r.json().get('message') or {}).get('content') or '').strip()
    except requests.Timeout:
        return _error('El asistente tardó demasiado en responder. Intenta con una pregunta más corta.', 504)
    except Exception as e:
        logger.warning('IA no disponible: %s', e)
        return _error('El asistente de IA no respondió. Avisa a Tecnología si persiste.', 502)

    if not contenido:
        return _error('El asistente no devolvió respuesta.', 502)
    return jsonify({'exito': True, 'respuesta': contenido})

