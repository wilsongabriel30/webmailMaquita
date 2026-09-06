# -*- coding: utf-8 -*-
"""
API de EDICIÓN TIPO WORD del Editor PDF (herramienta "Digitalizar y OCR").
==========================================================================
Desde el 27-jul-2026, "Digitalizar y OCR" ya no extrae texto suelto: convierte
el PDF en un documento de Word EDITABLE y lo abre dentro del propio editor con
el OnlyOffice Document Server de Maquita (VM 131). Ahí el usuario tiene tablas
de verdad — insertar y eliminar filas y columnas — y el formato, el tipo de
letra y las imágenes se conservan.

Flujo completo:

  1. POST /api/pdf/word/abrir      El navegador sube el PDF que tiene abierto.
                                   Si el PDF es un escaneo (sin capa de texto)
                                   se le pasa OCR con tesseract para que el Word
                                   salga con texto de verdad y no con fotos.
                                   Luego pdf2docx genera el .docx (layout,
                                   tablas, imágenes y fuentes) y se devuelve la
                                   configuración FIRMADA del editor.
  2. GET  /api/pdf/word/download   El Document Server descarga el .docx.
  3. POST /api/pdf/word/callback   El Document Server devuelve lo editado.
  4. POST /api/pdf/word/finalizar  Fuerza el guardado, convierte el .docx de
                                   vuelta a PDF (Gotenberg/LibreOffice) y lo
                                   entrega para recargarlo en el editor.

Seguridad (mismo patrón ya probado en el Almacén, `api_onlyoffice.py`):
  - La configuración del editor va firmada con JWT HS256 (secreto compartido
    con el Document Server). Sin secreto, el módulo responde 503 y el editor
    avisa al usuario en lugar de romperse.
  - /download y /callback los llama el Document Server, NO el navegador: no
    hay sesión, así que exigen un token propio firmado en el query (`t=`) que
    fija usuario + documento + uso. Si el DS manda además su firma
    (Authorization: Bearer) también se verifica.
  - Cada documento vive en una carpeta privada por usuario, fuera de rutas web.
  - El JWT se implementa con la librería estándar: cero dependencias nuevas.

Lección heredada de la Nube y del Almacén: la `key` del documento debe ser
ESTABLE durante toda la sesión de edición. Aquí cada conversión abre un
documento nuevo con clave propia, así que la clave nace estable y no se toca.

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import base64
import hashlib
import hmac
import io
import json
import logging
import os
import shutil
import time
import uuid

import requests
from flask import Blueprint, jsonify, request, send_file

from .pdf_editor_api import obtener_usuario_id, requiere_autenticacion
from ...infraestructura.externos import cliente_conversiones as conv

logger = logging.getLogger(__name__)

bp_pdf_word = Blueprint('pdf_word', __name__)

# Carpeta privada de los documentos en edición (fuera de rutas web)
_DIR_WORD = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', '..', 'data', 'pdf_word'))

# Validez del token de descarga/callback. Una edición puede quedar abierta un
# buen rato; si el token venciera a mitad se perdería lo escrito.
DIAS_TOKEN = 3

# A los documentos abandonados se les da una semana antes de barrerlos.
DIAS_RETENCION = 7

# Umbral para decidir "esto es un escaneo": menos de estos caracteres de texto
# real en todo el documento y toca pasarle OCR antes de convertir.
_MIN_CARACTERES_TEXTO = 40


# ── configuración del Document Server ────────────────────────────────────
# Se lee del entorno y, si no está, de la tabla config_kv del Almacén, que es
# donde ya vive la del Document Server dedicado (VM 131). Así no se duplica el
# secreto en dos sitios ni hay que reiniciar FARO para cambiarlo.
def _cfg(clave, variable_entorno):
    valor = os.getenv(variable_entorno, '').strip()
    if valor:
        return valor
    try:
        from ...infraestructura.externos.config_onlyoffice import valor_config_kv
        return (valor_config_kv(clave) or '').strip()
    except Exception as excepcion:
        logger.warning('config OnlyOffice (%s): %s', clave, excepcion)
        return ''


def _secreto_ds():
    return _cfg('onlyoffice_secret', 'PDF_ONLYOFFICE_SECRET')


def _url_publica_ds():
    return _cfg('onlyoffice_url_publica', 'PDF_ONLYOFFICE_URL_PUBLICA').rstrip('/')


def _url_interna_ds():
    return _cfg('onlyoffice_url_interna', 'PDF_ONLYOFFICE_URL_INTERNA').rstrip('/')


def _url_publica_faro():
    """La URL con la que el Document Server ve a FARO (tiene que ser pública:
    el DS vive en otra VM y no resuelve rutas internas del editor)."""
    return os.getenv('FARO_URL_PUBLICA', 'https://datos.maquita.com.ec').rstrip('/')


# ── JWT HS256 con la librería estándar (sin dependencias nuevas) ─────────
def _b64url(datos):
    return base64.urlsafe_b64encode(datos).rstrip(b'=').decode('ascii')


def _des_b64url(texto):
    return base64.urlsafe_b64decode(texto + '=' * (-len(texto) % 4))


def firmar_jwt(payload):
    """JWT HS256 igual al que espera el Document Server."""
    cabecera = _b64url(json.dumps({'alg': 'HS256', 'typ': 'JWT'},
                                  separators=(',', ':')).encode())
    cuerpo = _b64url(json.dumps(payload, separators=(',', ':')).encode())
    firma = hmac.new(_secreto_ds().encode(), f'{cabecera}.{cuerpo}'.encode(),
                     hashlib.sha256).digest()
    return f'{cabecera}.{cuerpo}.{_b64url(firma)}'


def verificar_jwt(token):
    """Payload si la firma (y `exp`, si viene) son válidas; si no, None."""
    try:
        cabecera, cuerpo, firma = token.split('.')
        esperada = hmac.new(_secreto_ds().encode(),
                            f'{cabecera}.{cuerpo}'.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_des_b64url(firma), esperada):
            return None
        datos = json.loads(_des_b64url(cuerpo))
        if datos.get('exp') and int(datos['exp']) < int(time.time()):
            return None
        return datos
    except Exception:
        return None


# ── documentos en edición ────────────────────────────────────────────────
def _dir_usuario(uid):
    ruta = os.path.join(_DIR_WORD, str(int(uid)))
    os.makedirs(ruta, mode=0o700, exist_ok=True)
    return ruta


def _ruta_docx(uid, clave):
    """Ruta del .docx. `clave` se sanea siempre: nunca sale de la carpeta."""
    clave = os.path.basename(str(clave))
    if not clave or not all(c in '0123456789abcdef' for c in clave):
        raise ValueError('Clave de documento inválida')
    return os.path.join(_dir_usuario(uid), clave + '.docx')


def _ruta_meta(uid, clave):
    return _ruta_docx(uid, clave)[:-5] + '.json'


def _guardar_meta(uid, clave, datos):
    with open(_ruta_meta(uid, clave), 'w', encoding='utf-8') as fh:
        json.dump(datos, fh, ensure_ascii=False)


def _leer_meta(uid, clave):
    try:
        with open(_ruta_meta(uid, clave), encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _limpiar_antiguos(uid):
    """Barre los documentos que quedaron abandonados. Best-effort."""
    limite = time.time() - DIAS_RETENCION * 86400
    try:
        carpeta = _dir_usuario(uid)
        for nombre in os.listdir(carpeta):
            ruta = os.path.join(carpeta, nombre)
            if os.path.isfile(ruta) and os.path.getmtime(ruta) < limite:
                os.remove(ruta)
    except Exception as excepcion:
        logger.warning('limpieza pdf_word: %s', excepcion)


# ── OCR previo (solo si el PDF es un escaneo) ────────────────────────────
def _tiene_texto(contenido_pdf):
    """¿El PDF trae texto de verdad o son fotos de páginas?"""
    try:
        import fitz
        documento = fitz.open(stream=contenido_pdf, filetype='pdf')
        total = 0
        for pagina in documento:
            total += len((pagina.get_text() or '').strip())
            if total >= _MIN_CARACTERES_TEXTO:
                documento.close()
                return True
        documento.close()
        return False
    except Exception as excepcion:
        logger.warning('no se pudo inspeccionar el texto del PDF: %s', excepcion)
        return True     # ante la duda, no se toca el documento


def _ocr_a_pdf(contenido_pdf, idioma='spa'):
    """Rehace el escaneo como un PDF de texto REAL, listo para convertir a Word.

    El trabajo está en `ocr_pagina_texto.py` —incluido el porqué de rehacer la
    página en vez de usar el OCR clásico— y corre SIEMPRE en un proceso aparte:
    tesseract es CPU pura y dentro del worker eventlet congelaría el event loop
    y tumbaría al worker, dejando colgados a los demás usuarios de FARO.

    Si algo falla se devuelve el PDF original: más vale un Word pobre que nada.
    """
    try:
        resultado = conv.en_subproceso('ocr-a-texto', [contenido_pdf],
                                       timeout=900, params={'idioma': idioma})
        return resultado or contenido_pdf
    except Exception as excepcion:
        logger.warning('OCR previo falló (%s): se convierte el PDF tal cual', excepcion)
        return contenido_pdf


# ── validación de las peticiones del Document Server ─────────────────────
def _error(mensaje, codigo=400):
    return jsonify({'exito': False, 'mensaje': mensaje}), codigo


def _validar_peticion_ds(uso):
    """Valida lo que llega del Document Server (sin sesión web)."""
    if not _secreto_ds():
        return _error('La edición tipo Word no está configurada', 503)
    datos = verificar_jwt(request.args.get('t', '') or '')
    if not datos or datos.get('uso') != uso:
        return _error('Token inválido', 401)
    autorizacion = request.headers.get('Authorization', '')
    if autorizacion.startswith('Bearer '):
        if verificar_jwt(autorizacion[7:]) is None:
            return _error('Firma del Document Server inválida', 403)
    return datos


def _nombre_usuario(uid):
    try:
        from flask_login import current_user
        for atributo in ('nombre_completo', 'nombre', 'username', 'email'):
            valor = getattr(current_user, atributo, None)
            if valor:
                return str(valor)
    except Exception:
        pass
    return f'Usuario {uid}'


def _buscar_por_huella(uid, huella, idioma):
    """(clave, meta) de una conversión anterior del MISMO PDF sin editar."""
    try:
        carpeta = _dir_usuario(uid)
    except Exception:
        return None
    for nombre in os.listdir(carpeta):
        if not nombre.endswith('.json'):
            continue
        clave = nombre[:-5]
        meta = _leer_meta(uid, clave)
        if (meta.get('huella') == huella
                and meta.get('idioma', 'spa') == idioma
                and not meta.get('guardado')
                and os.path.isfile(_ruta_docx(uid, clave))):
            return clave, meta
    return None


def _sala_del_documento(uid, clave, meta, nueva=False):
    """La `key` con la que el Document Server identifica esta edición.

    **Cada apertura estrena sala** (17-08-2026). Antes la sala se derivaba del
    propio documento, así que abrir el mismo PDF dos veces caía siempre en la
    misma: si esa sala se quedaba colgada en el Document Server —un usuario que
    figura dentro aunque haya cerrado el navegador— la siguiente apertura se
    quedaba esperando a un participante que ya no existe, con el reloj girando
    para siempre. Pasó de verdad: el 17-08-2026 el usuario avisó de que «editar
    como Word se queda cargando» con TODOS los documentos, y la sala colgada ni
    siquiera se dejaba echar abajo con el comando `drop`.

    Estrenando sala en cada apertura, una sala colgada deja de importar: la
    nueva nace limpia. No se pierde nada por el camino, porque aquí cada usuario
    edita su propia copia (`data/pdf_word/<uid>/`) y nunca hubo edición
    compartida entre dos personas sobre el mismo documento.

    La sala se guarda en la ficha del documento porque hay que volver a nombrarla
    después, al pedirle al servidor que vuelque lo escrito (`_forzar_guardado`).
    """
    if nueva:
        sala = '%s-%s' % (clave[:20], format(int(time.time() * 1000), 'x'))
        meta['key'] = sala
        _guardar_meta(uid, clave, meta)
        return sala
    # Documentos abiertos antes de este cambio: su sala era la de siempre.
    return meta.get('key') or clave[:20]


def _echar_de_la_sala(sala):
    """Cierra una sala anterior en el Document Server, si se puede.

    Se hace al estrenar sala, para no ir dejando salas abiertas detrás. Es un
    intento: si el servidor no puede con ella —el caso que motivó todo esto— da
    igual, porque la edición ya va por una sala nueva.
    """
    interna = _url_interna_ds() or _url_publica_ds()
    if not interna or not sala:
        return
    peticion = {'c': 'drop', 'key': sala}
    try:
        requests.post(interna + '/coauthoring/CommandService.ashx', json=peticion,
                      headers={'Authorization': 'Bearer ' + firmar_jwt(peticion)},
                      timeout=8)
    except Exception as excepcion:
        logger.info('no se pudo cerrar la sala anterior %s: %s', sala, excepcion)


def _respuesta_editor(uid, clave, meta):
    """Configuración firmada del editor para un documento ya convertido."""
    exp = int(time.time()) + DIAS_TOKEN * 86400
    token_descarga = firmar_jwt({'u': uid, 'k': clave, 'uso': 'descarga', 'exp': exp})
    token_callback = firmar_jwt({'u': uid, 'k': clave, 'uso': 'callback', 'exp': exp})
    base = _url_publica_faro()
    titulo = meta.get('titulo') or 'documento'
    _echar_de_la_sala(meta.get('key'))
    sala = _sala_del_documento(uid, clave, meta, nueva=True)

    config = {
        'document': {
            'fileType': 'docx',
            # La sala de esta edición: se estrena en cada apertura y no cambia
            # mientras dure (si cambiara a mitad, se partiría y se perdería lo
            # escrito). Ver `_sala_del_documento`.
            'key': sala,
            'title': titulo + '.docx',
            'url': f'{base}/api/pdf/word/download?t={token_descarga}',
            'permissions': {
                'chat': False,
                'comment': True,
                'download': True,
                'edit': True,
                'print': True,
                'review': True,
            },
        },
        'documentType': 'word',
        'editorConfig': {
            'callbackUrl': f'{base}/api/pdf/word/callback?t={token_callback}',
            'coEditing': {'mode': 'fast', 'change': False},
            'lang': 'es',
            'mode': 'edit',
            'user': {'id': str(uid), 'name': _nombre_usuario(uid)},
            'customization': {
                'autosave': True,
                'comments': True,
                'compactHeader': False,
                'feedback': False,
                'forcesave': True,
                'help': False,
                'zoom': 100,
            },
        },
        'height': '100%',
        'width': '100%',
        'type': 'desktop',
    }
    config['token'] = firmar_jwt(config)

    return jsonify({
        'exito': True,
        'clave': clave,
        'titulo': titulo,
        'ocr': bool(meta.get('ocr')),
        'config': config,
        'api_js_url': f'{_url_publica_ds()}/web-apps/apps/api/documents/api.js',
    })


# ============================================================
# 1. ABRIR: PDF → Word editable dentro del editor
# ============================================================
@bp_pdf_word.route('/word/abrir', methods=['POST'])
@requiere_autenticacion
def word_abrir():
    """Convierte el PDF recibido a .docx y devuelve la configuración firmada
    del editor OnlyOffice para incrustarlo en la página."""
    uid = obtener_usuario_id()
    if not (_secreto_ds() and _url_publica_ds()):
        return _error('La edición tipo Word no está configurada en el servidor. '
                      'Avisa a Tecnología.', 503)

    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return _error('Falta el archivo PDF.')
    contenido = archivo.read()
    if not contenido:
        return _error('El archivo PDF llegó vacío.')

    nombre_original = os.path.basename(archivo.filename or 'documento.pdf')
    titulo = os.path.splitext(nombre_original)[0][:80] or 'documento'
    idioma = (request.form.get('idioma') or 'spa').strip()

    # ¿Ya se convirtió este mismo PDF? Abrir el Word, cerrarlo y volver a
    # entrar era volver a pagar la conversión entera (y el OCR). Se reconoce
    # por la huella del contenido. Solo se reutiliza lo que NADIE editó: si ya
    # se tocó, se hace uno limpio para no mezclar dos sesiones de trabajo.
    huella = hashlib.sha256(contenido).hexdigest()
    reutilizada = _buscar_por_huella(uid, huella, idioma)
    if reutilizada:
        clave, meta = reutilizada
        logger.info('word/abrir: se reutiliza la conversión %s', clave)
        return _respuesta_editor(uid, clave, meta)

    # Escaneo → OCR primero, para que el Word traiga texto y no fotos
    hubo_ocr = False
    if not _tiene_texto(contenido):
        contenido = _ocr_a_pdf(contenido, idioma)
        hubo_ocr = True

    # PDF → Word. Va en subproceso: pdf2docx es CPU pura y dentro del worker
    # eventlet bloquearía a todos los demás usuarios de FARO.
    try:
        docx = conv.en_subproceso('pdf-a-word', [contenido])
    except Exception as excepcion:
        logger.exception('word/abrir: conversión a Word')
        return _error('No se pudo convertir el documento a Word: %s' % excepcion, 500)
    if not docx:
        return _error('La conversión a Word no devolvió ningún documento.', 500)

    # pdf2docx guarda TODAS las imágenes como PNG sin comprimir: la proforma
    # real del usuario daba un Word de 16 MB, de los cuales 15,4 MB eran fotos.
    # Ese peso se paga tres veces —al generarlo, al descargarlo el Document
    # Server y al abrirlo el navegador— y era la causa principal de la espera.
    # Medido el 27-jul-2026: 15,5 MB → 1,8 MB en 0,8 s, sin tocar el texto,
    # las tablas ni los estilos (el PDF resultante sale idéntico).
    try:
        from ...infraestructura.externos.aligerar_docx import aligerar
        docx = aligerar(docx)
    except Exception as excepcion:
        logger.warning('no se pudo aligerar el documento: %s', excepcion)


    _limpiar_antiguos(uid)
    clave = uuid.uuid4().hex
    with open(_ruta_docx(uid, clave), 'wb') as fh:
        fh.write(docx)
    os.chmod(_ruta_docx(uid, clave), 0o600)
    meta = {
        'titulo': titulo,
        'nombre_original': nombre_original,
        'creado': int(time.time()),
        'ocr': hubo_ocr,
        'guardado': 0,
        'huella': huella,
        'idioma': idioma,
    }
    _guardar_meta(uid, clave, meta)
    return _respuesta_editor(uid, clave, meta)


# ============================================================
# 2. El Document Server descarga el documento
# ============================================================
@bp_pdf_word.route('/word/download', methods=['GET'])
def word_download():
    datos = _validar_peticion_ds('descarga')
    if not isinstance(datos, dict):
        return datos
    try:
        ruta = _ruta_docx(int(datos['u']), datos['k'])
    except (KeyError, ValueError):
        return _error('Documento inválido', 400)
    if not os.path.isfile(ruta):
        return _error('Documento no encontrado', 404)
    return send_file(ruta, as_attachment=True, download_name='documento.docx')


# ============================================================
# 3. El Document Server devuelve lo editado
# ============================================================
@bp_pdf_word.route('/word/callback', methods=['POST'])
def word_callback():
    """Contrato del Document Server: hay que responder {'error': 0}.

    status: 1 editando · 2 cerrado (guardar) · 4 cerrado sin cambios ·
            6 guardado forzado (autosave/forcesave) · 3 y 7 error del DS.
    """
    datos = _validar_peticion_ds('callback')
    if not isinstance(datos, dict):
        return datos

    cuerpo = request.get_json(silent=True) or {}
    # El DS firma también el cuerpo: si viene, se verifica
    if cuerpo.get('token') and verificar_jwt(cuerpo['token']) is None:
        logger.error('word/callback: firma del cuerpo inválida')
        return jsonify({'error': 1})

    try:
        uid = int(datos['u'])
        clave = datos['k']
        ruta = _ruta_docx(uid, clave)
    except (KeyError, ValueError):
        return jsonify({'error': 1})

    status = cuerpo.get('status')
    if status not in (2, 6):
        return jsonify({'error': 0})

    url = cuerpo.get('url')
    if not url:
        logger.error('word/callback sin URL del documento editado')
        return jsonify({'error': 1})

    # [C-8] Lista blanca: solo se descarga si la URL la publico NUESTRO Document
    # Server. Sin esto, quien tuviera un vale de callback podia hacer que el motor
    # descargara de donde quisiera y lo guardara como contenido del documento.
    publica, interna = _url_publica_ds(), _url_interna_ds()
    _permitida = None
    if publica and (url == publica or url.startswith(publica + '/')):
        _permitida = (interna + url[len(publica):]) if interna else url
    elif interna and (url == interna or url.startswith(interna + '/')):
        _permitida = url
    if not _permitida:
        logger.error('word/callback rechazado: la URL del documento no es del Document Server')
        return jsonify({'error': 1})
    url = _permitida

    inicio = time.monotonic()
    try:
        # CRÍTICO: responder antes del timeout del proxy. Si el DS recibe 504
        # reintenta y luego DESCARTA el documento (incidente Nube 2026-07-01).
        respuesta = requests.get(url, timeout=120)
        if respuesta.status_code != 200:
            logger.error('word/callback: la descarga devolvió %s', respuesta.status_code)
            return jsonify({'error': 1})
        temporal = ruta + '.tmp'
        with open(temporal, 'wb') as fh:
            fh.write(respuesta.content)
        os.replace(temporal, ruta)      # escritura atómica
        os.chmod(ruta, 0o600)
    except Exception as excepcion:
        logger.error('word/callback: fallo guardando %s: %s', clave, excepcion)
        return jsonify({'error': 1})

    meta = _leer_meta(uid, clave)
    meta['guardado'] = int(time.time())
    _guardar_meta(uid, clave, meta)

    total = time.monotonic() - inicio
    mensaje = ('word/callback guardado clave=%s bytes=%d status=%s en %.1fs'
               % (clave, len(respuesta.content), status, total))
    (logger.warning if total > 10 else logger.info)(mensaje)
    return jsonify({'error': 0})


# ============================================================
# 4. Terminar: forzar el guardado y volver a PDF
# ============================================================
# Cuánto se espera, como mucho, a que el Document Server devuelva lo editado.
# Solo se espera cuando ACEPTÓ el encargo (ver abajo): si no, no se espera nada.
ESPERA_GUARDADO = 20        # segundos


def _forzar_guardado(uid, clave):
    """Pide al Document Server que vuelque YA lo que el usuario lleva escrito
    (CommandService `forcesave`) y espera a que llegue por el callback.

    Solo se espera si el servidor dice que ACEPTÓ el encargo (`error: 0`).
    Cualquier otra respuesta significa que no va a llegar ningún callback —
    documento ya cerrado, sin cambios pendientes, clave desconocida— y quedarse
    esperando solo hace perder el tiempo al usuario: se medió que "Volver al
    PDF" tardaba 31 s por esto (27-jul-2026). En esos casos se sigue con el
    documento que ya está guardado, que es justo lo que el usuario editó.
    """
    interna = _url_interna_ds() or _url_publica_ds()
    if not interna:
        return False
    ruta = _ruta_docx(uid, clave)
    marca = os.path.getmtime(ruta) if os.path.isfile(ruta) else 0
    # La sala de ESTA edición, no la del documento: desde el 17-08-2026 se
    # estrena una en cada apertura y hay que nombrar la que está abierta.
    peticion = {'c': 'forcesave',
                'key': _sala_del_documento(uid, clave, _leer_meta(uid, clave))}
    try:
        respuesta = requests.post(
            interna + '/coauthoring/CommandService.ashx',
            json=peticion,
            headers={'Authorization': 'Bearer ' + firmar_jwt(peticion)},
            timeout=15)
        resultado = respuesta.json()
    except Exception as excepcion:
        logger.warning('forcesave no se pudo pedir: %s', excepcion)
        return False

    codigo = resultado.get('error')
    if codigo != 0:
        # 4 = "no hay nada que guardar" (final feliz); el resto, aviso al log
        if codigo != 4:
            logger.warning('forcesave devolvió %s: no se espera callback', resultado)
        return False

    # Aceptado: el documento llega por el callback, que es otro camino
    limite = time.monotonic() + ESPERA_GUARDADO
    while time.monotonic() < limite:
        time.sleep(0.3)
        if os.path.isfile(ruta) and os.path.getmtime(ruta) > marca:
            return True
    logger.warning('forcesave aceptado pero el documento no llegó en %d s', ESPERA_GUARDADO)
    return False


@bp_pdf_word.route('/word/finalizar', methods=['POST'])
@requiere_autenticacion
def word_finalizar():
    """Guarda lo último que se escribió y devuelve el documento como PDF."""
    uid = obtener_usuario_id()
    clave = (request.form.get('clave') or
             (request.get_json(silent=True) or {}).get('clave') or '')
    try:
        ruta = _ruta_docx(uid, clave)
    except ValueError:
        return _error('Documento inválido.')
    if not os.path.isfile(ruta):
        return _error('El documento ya no está disponible. Vuelve a abrirlo.', 404)

    _forzar_guardado(uid, clave)

    with open(ruta, 'rb') as fh:
        docx = fh.read()
    meta = _leer_meta(uid, clave)
    titulo = meta.get('titulo') or 'documento'
    try:
        pdf = conv.oficina_a_pdf(titulo + '.docx', docx, timeout=300)
    except Exception as excepcion:
        logger.exception('word/finalizar: Word a PDF')
        return _error('No se pudo volver a PDF: %s' % excepcion, 500)

    return send_file(io.BytesIO(pdf), mimetype='application/pdf',
                     as_attachment=False, download_name=titulo + '.pdf')


@bp_pdf_word.route('/word/descargar-docx', methods=['GET'])
@requiere_autenticacion
def word_descargar_docx():
    """Baja el Word tal cual, por si el usuario prefiere seguir en Word."""
    uid = obtener_usuario_id()
    try:
        ruta = _ruta_docx(uid, request.args.get('clave', ''))
    except ValueError:
        return _error('Documento inválido.')
    if not os.path.isfile(ruta):
        return _error('El documento ya no está disponible.', 404)
    _forzar_guardado(uid, request.args.get('clave', ''))
    titulo = _leer_meta(uid, request.args.get('clave', '')).get('titulo') or 'documento'
    return send_file(ruta, as_attachment=True, download_name=titulo + '.docx')


@bp_pdf_word.route('/word/estado', methods=['GET'])
@requiere_autenticacion
def word_estado():
    """Diagnóstico: ¿está configurado? ¿responde el Document Server?"""
    configurado = bool(_secreto_ds() and _url_publica_ds())
    conectado = False
    # El editor consulta esto nada más abrirse, solo para saber a qué servidor
    # pedir el api.js y precargarlo. Ahi no hace falta ir a preguntarle al
    # Document Server si esta vivo: con `rapido` se responde al instante.
    rapido = request.args.get("rapido") in ("1", "true", "si")
    destino = "" if rapido else (_url_interna_ds() or _url_publica_ds())
    if destino:
        try:
            conectado = requests.get(destino + '/healthcheck', timeout=5).ok
        except Exception:
            conectado = False
    return jsonify({'exito': True, 'configurado': configurado,
                    'conectado': conectado, 'servidor': _url_publica_ds()})
