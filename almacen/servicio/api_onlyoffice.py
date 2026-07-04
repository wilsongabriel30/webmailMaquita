# -*- coding: utf-8 -*-
"""
API OnlyOffice del Almacén Maquita (edición online de Word/Excel/PowerPoint).
==============================================================================
Conecta el explorador del Almacén con un OnlyOffice Document Server DEDICADO
(VM propia). NO toca el OnlyOffice de la Nube/Nextcloud (VM300), que sigue
en producción con su propia integración.

Flujo (mismo patrón probado de la Nube):
  1. GET  /onlyoffice/config    → el navegador pide la configuración firmada.
  2. El editor (api.js del Document Server) descarga el archivo con /download.
  3. Al guardar/cerrar, el Document Server llama a /callback y el motor
     guarda el documento con nucleo.subir() → versionado y dedup automáticos.

Seguridad:
  - La configuración del editor va FIRMADA (JWT HS256, secreto compartido con
    el Document Server). Sin secreto configurado el módulo responde 503.
  - /download y /callback NO tienen sesión de usuario (los llama el Document
    Server, no el navegador): exigen un token propio firmado en el query
    (`t=`) que fija usuario + ruta + uso; y si el Document Server envía su
    propia firma (Authorization: Bearer / campo token) también se verifica.
  - El JWT se implementa con la librería estándar (hmac/hashlib/base64/json):
    CERO dependencias nuevas (política de superficie mínima del motor).

Lección aprendida en la Nube (incidente 2026-06): la `key` del documento debe
ser ESTABLE durante toda la sesión de co-edición y cambiar SOLO cuando la
sesión se cierra (callback status 2). Si cambia en cada guardado se parte la
sala de co-edición y se pierden datos. Aquí se replica ese diseño con la
tabla `onlyoffice_sesion`.

Configuración (variable de entorno, o tabla config_kv si no hay variable):
  ALMACEN_ONLYOFFICE_SECRET      / config_kv 'onlyoffice_secret'
  ALMACEN_ONLYOFFICE_URL_PUBLICA / config_kv 'onlyoffice_url_publica'
      (la que ve el navegador, ej. https://datos.maquita.com.ec/office-almacen)
  ALMACEN_ONLYOFFICE_URL_INTERNA / config_kv 'onlyoffice_url_interna'
      (la que usa el motor para hablar con el DS, ej. http://193.16.0.X:8080)

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import time

import requests
from flask import Blueprint, jsonify, request, send_file

import nucleo_archivos as nucleo
from almacen_bd import consultar, ejecutar
from api_archivos import _permiso_unidad, error, usuario_actual
from config_almacen import URL_PUBLICA
from registro import registrar_actividad
from seguridad_rutas import (RutaInvalida, normalizar_ruta_virtual,
                             ruta_fisica, unidad_de_ruta)

log = logging.getLogger('almacen.onlyoffice')

bp_onlyoffice = Blueprint('almacen_onlyoffice', __name__)
bp_onlyoffice_web = Blueprint('almacen_onlyoffice_web', __name__)

# Validez del token de descarga/callback. Una sesión de edición puede quedar
# abierta varios días; si el token venciera a mitad, el guardado fallaría
# (pérdida de datos). Por eso es holgado.
DIAS_TOKEN = 7

# Tipos que entiende el Document Server (word/cell/slide) — igual que la Nube
TIPOS_DOCUMENTO = {
    # Documentos de texto
    'doc': 'word', 'docx': 'word', 'docm': 'word', 'dot': 'word',
    'dotx': 'word', 'odt': 'word', 'ott': 'word', 'rtf': 'word',
    'txt': 'word', 'html': 'word', 'htm': 'word', 'pdf': 'word',
    'epub': 'word', 'xps': 'word',
    # Hojas de cálculo
    'xls': 'cell', 'xlsx': 'cell', 'xlsm': 'cell', 'xlt': 'cell',
    'xltx': 'cell', 'ods': 'cell', 'ots': 'cell', 'csv': 'cell',
    # Presentaciones
    'ppt': 'slide', 'pptx': 'slide', 'pptm': 'slide', 'pps': 'slide',
    'ppsx': 'slide', 'odp': 'slide', 'otp': 'slide',
}

# Extensiones que permiten EDICIÓN (el resto solo se visualiza)
EXTENSIONES_EDITABLES = {'docx', 'xlsx', 'pptx', 'odt', 'ods', 'odp', 'txt', 'csv'}


# ── configuración (entorno > config_kv) ──────────────────────────────────
def _cfg(clave: str, variable_entorno: str) -> str:
    """Valor de configuración: primero variable de entorno, luego config_kv."""
    valor = os.getenv(variable_entorno, '').strip()
    if valor:
        return valor
    try:
        filas = consultar("SELECT valor FROM config_kv WHERE clave = %s", (clave,))
        if filas and filas[0]['valor']:
            return filas[0]['valor'].strip()
    except Exception:
        pass
    return ''


def secreto_ds() -> str:
    return _cfg('onlyoffice_secret', 'ALMACEN_ONLYOFFICE_SECRET')


def url_publica_ds() -> str:
    return _cfg('onlyoffice_url_publica', 'ALMACEN_ONLYOFFICE_URL_PUBLICA').rstrip('/')


def url_interna_ds() -> str:
    return _cfg('onlyoffice_url_interna', 'ALMACEN_ONLYOFFICE_URL_INTERNA').rstrip('/')


# ── JWT HS256 con la librería estándar (sin dependencias nuevas) ─────────
def _b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b'=').decode('ascii')


def _des_b64url(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + '=' * (-len(texto) % 4))


def firmar_jwt(payload: dict) -> str:
    """Genera un JWT HS256 (compatible con el que espera el Document Server)."""
    cabecera = _b64url(json.dumps({'alg': 'HS256', 'typ': 'JWT'},
                                  separators=(',', ':')).encode())
    cuerpo = _b64url(json.dumps(payload, separators=(',', ':')).encode())
    firma = hmac.new(secreto_ds().encode(), f'{cabecera}.{cuerpo}'.encode(),
                     hashlib.sha256).digest()
    return f'{cabecera}.{cuerpo}.{_b64url(firma)}'


def verificar_jwt(token: str):
    """Payload del token si la firma (y exp, si trae) son válidas; si no, None."""
    try:
        cabecera, cuerpo, firma = token.split('.')
        esperada = hmac.new(secreto_ds().encode(), f'{cabecera}.{cuerpo}'.encode(),
                            hashlib.sha256).digest()
        if not hmac.compare_digest(esperada, _des_b64url(firma)):
            return None
        payload = json.loads(_des_b64url(cuerpo))
        if 'exp' in payload and time.time() > float(payload['exp']):
            return None
        return payload
    except Exception:
        return None


# ── sala de co-edición: key estable por documento + versión de sesión ────
_tabla_sesion_lista = False


def _asegurar_tabla_sesion():
    global _tabla_sesion_lista
    if _tabla_sesion_lista:
        return
    ejecutar("""
        CREATE TABLE IF NOT EXISTS onlyoffice_sesion (
            doc_base    TEXT PRIMARY KEY,
            version     INTEGER NOT NULL DEFAULT 1,
            actualizado TIMESTAMP DEFAULT NOW()
        )
    """)
    _tabla_sesion_lista = True


def _base_documento(usuario: int, ruta: str) -> str:
    """Identificador de la SALA de co-edición. En unidades compartidas no
    depende del usuario (todos los miembros deben entrar a la misma sala);
    en el espacio personal sí."""
    unidad_id, _ = unidad_de_ruta(ruta)
    if unidad_id is not None:
        return 'unidad:' + ruta
    return f'usuario:{usuario}:{ruta}'


def _version_sesion(doc_base: str) -> int:
    try:
        _asegurar_tabla_sesion()
        filas = consultar("SELECT version FROM onlyoffice_sesion WHERE doc_base = %s",
                          (doc_base,))
        return int(filas[0]['version']) if filas else 1
    except Exception as excepcion:
        log.warning('OnlyOffice: no se pudo leer versión de sesión: %s', excepcion)
        return 1


def _cerrar_sesion(doc_base: str) -> None:
    """Sube la versión al cerrarse la sesión (status 2): la próxima apertura
    usa una key nueva y el Document Server refresca su caché del documento."""
    try:
        _asegurar_tabla_sesion()
        ejecutar("""
            INSERT INTO onlyoffice_sesion (doc_base, version) VALUES (%s, 2)
            ON CONFLICT (doc_base) DO UPDATE
            SET version = onlyoffice_sesion.version + 1, actualizado = NOW()
        """, (doc_base,))
        log.info('OnlyOffice: sesión cerrada, versión subida (%s)', doc_base)
    except Exception as excepcion:
        log.warning('OnlyOffice: no se pudo subir versión de sesión: %s', excepcion)


# ── ayudantes ────────────────────────────────────────────────────────────
def _nombre_usuario(usuario_id: int) -> str:
    """Nombre visible del usuario (para la lista de coeditores del editor)."""
    try:
        filas = consultar("""
            SELECT COALESCE(full_name, username) AS nombre
            FROM usuarios WHERE id = %s
        """, (usuario_id,), nomina=True)
        if filas and filas[0]['nombre']:
            return filas[0]['nombre']
    except Exception:
        pass
    return f'Usuario {usuario_id}'


def _reescribir_url_interna(url: str) -> str:
    """El Document Server publica URLs con su dominio público; desde el motor
    conviene descargar por la URL interna (el dominio público puede no
    resolver, o dar la vuelta por el gateway)."""
    publica, interna = url_publica_ds(), url_interna_ds()
    if publica and interna and url.startswith(publica + '/'):
        return interna + url[len(publica):]
    return url


def _validar_peticion_ds(uso: str):
    """Valida una petición que viene del Document Server (SIN sesión web):
      1) token propio en el query `t=` con el uso correcto (descarga/callback);
      2) si el Document Server además envía su firma (Authorization: Bearer),
         también debe ser válida.
    Devuelve el payload (dict) si todo bien; si no, una respuesta de error."""
    if not secreto_ds():
        return error('OnlyOffice no está configurado', 503)
    token = request.args.get('t', '')
    datos = verificar_jwt(token) if token else None
    if not datos or datos.get('uso') != uso:
        return error('Token inválido', 401)
    autorizacion = request.headers.get('Authorization', '')
    if autorizacion.startswith('Bearer '):
        if verificar_jwt(autorizacion[7:]) is None:
            return error('Firma del Document Server inválida', 403)
    return datos


# ── endpoints ────────────────────────────────────────────────────────────
@bp_onlyoffice.route('/onlyoffice/config', methods=['GET'])
def onlyoffice_config():
    """GET /onlyoffice/config?ruta=/documento.xlsx — configuración firmada
    para embeber el editor. Requiere sesión (la pide el navegador)."""
    usuario = usuario_actual()
    if not (secreto_ds() and url_publica_ds()):
        return error('La edición online aún no está configurada '
                     '(falta el servidor OnlyOffice dedicado)', 503)
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)

    nombre = ruta.rsplit('/', 1)[-1]
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    tipo_documento = TIPOS_DOCUMENTO.get(extension)
    if not tipo_documento:
        return error(f'Tipo de archivo no soportado: {extension}', 400)

    try:
        fisica = ruta_fisica(usuario, ruta)
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    if not os.path.isfile(fisica):
        return error('Archivo no encontrado', 404)

    # Nivel efectivo: editar solo si la extensión lo permite y (en unidades
    # compartidas) el usuario tiene rol de escritura. Espacio personal: dueño.
    escritura = _permiso_unidad(usuario, ruta, escritura=True)
    modo = 'edit' if (escritura and extension in EXTENSIONES_EDITABLES) else 'view'

    # Key ESTABLE de la sala de co-edición (ver nota en el encabezado)
    doc_base = _base_documento(usuario, ruta)
    version = _version_sesion(doc_base)
    doc_key = hashlib.sha1(f'{doc_base}:v{version}'.encode()).hexdigest()[:20]

    # Tokens de un solo uso lógico (usuario + ruta + propósito) para que el
    # Document Server descargue y devuelva el archivo sin sesión web
    exp = int(time.time()) + DIAS_TOKEN * 86400
    token_descarga = firmar_jwt({'u': usuario, 'r': ruta, 'uso': 'descarga', 'exp': exp})
    token_callback = firmar_jwt({'u': usuario, 'r': ruta, 'uso': 'callback',
                                 'b': doc_base, 'exp': exp})
    url_descarga = f'{URL_PUBLICA}/api/almacen/onlyoffice/download?t={token_descarga}'
    url_callback = f'{URL_PUBLICA}/api/almacen/onlyoffice/callback?t={token_callback}'

    puede_editar = (modo == 'edit')
    config = {
        'document': {
            'fileType': extension,
            'key': doc_key,
            'title': nombre,
            'url': url_descarga,
            'permissions': {
                'comment': puede_editar,
                'download': True,
                'edit': puede_editar,
                'print': True,
                'review': puede_editar,
            },
        },
        'documentType': tipo_documento,
        'editorConfig': {
            'callbackUrl': url_callback,
            'coEditing': {'mode': 'fast', 'change': False},
            'lang': 'es',
            'mode': 'edit' if puede_editar else 'view',
            'user': {'id': str(usuario), 'name': _nombre_usuario(usuario)},
            'customization': {
                'autosave': True,
                'chat': True,
                'comments': puede_editar,
                'compactHeader': False,
                'feedback': False,
                'forcesave': True,
                'help': False,
                'logo': {
                    'image': f'{URL_PUBLICA}/static/img/maquita.jpg',
                    'imageEmbedded': f'{URL_PUBLICA}/static/img/maquita.jpg',
                    'url': URL_PUBLICA,
                },
                'zoom': 100,
            },
        },
        'height': '100%',
        'width': '100%',
        'type': 'desktop',
    }
    config['token'] = firmar_jwt(config)

    return jsonify({
        'success': True,
        'config': config,
        'api_js_url': f'{url_publica_ds()}/web-apps/apps/api/documents/api.js',
        'puede_editar': puede_editar,
    })


@bp_onlyoffice.route('/onlyoffice/download', methods=['GET'])
def onlyoffice_download():
    """GET /onlyoffice/download?t=<token> — el Document Server descarga el
    archivo. Sin sesión web: autenticado por el token firmado."""
    datos = _validar_peticion_ds('descarga')
    if not isinstance(datos, dict):
        return datos
    try:
        fisica = ruta_fisica(int(datos['u']), datos['r'])
    except (RutaInvalida, KeyError, ValueError):
        return error('Ruta inválida', 400)
    if not os.path.isfile(fisica):
        return error('Archivo no encontrado', 404)
    return send_file(fisica, as_attachment=True,
                     download_name=os.path.basename(fisica))


@bp_onlyoffice.route('/onlyoffice/callback', methods=['POST'])
def onlyoffice_callback():
    """POST /onlyoffice/callback?t=<token> — el Document Server avisa el estado
    de la edición. Contrato de respuesta del DS: {'error': 0} = OK.

    status: 1 editando · 2 cerrado, guardar (y cerrar la sala) ·
            4 cerrado sin cambios · 6 guardado forzado (autosave/forcesave) ·
            3 y 7 error en el DS.
    """
    datos = _validar_peticion_ds('callback')
    if not isinstance(datos, dict):
        return datos

    cuerpo = request.get_json(silent=True) or {}
    # El Document Server también firma el CUERPO (campo 'token'): verificarla
    if cuerpo.get('token') and verificar_jwt(cuerpo['token']) is None:
        log.error('OnlyOffice callback: firma del cuerpo inválida')
        return jsonify({'error': 1})

    try:
        usuario = int(datos['u'])
        ruta = datos['r']
    except (KeyError, ValueError):
        return jsonify({'error': 1})

    status = cuerpo.get('status')
    log.info('OnlyOffice callback ruta=%s status=%s usuario=%s', ruta, status, usuario)

    if status in (2, 6):
        # CRÍTICO: responder antes del timeout del proxy; si el DS recibe 504
        # reintenta y luego DESCARTA el documento (incidente Nube 2026-07-01).
        # Se cronometra todo para diagnosticar lentitud.
        inicio = time.monotonic()
        url = cuerpo.get('url')
        if not url:
            log.error('OnlyOffice callback sin URL del documento editado')
            return jsonify({'error': 1})

        try:
            respuesta = requests.get(_reescribir_url_interna(url), timeout=120)
        except Exception as excepcion:
            log.error('OnlyOffice: no se pudo descargar el documento editado: %s', excepcion)
            return jsonify({'error': 1})
        if respuesta.status_code != 200:
            log.error('OnlyOffice: descarga del editado devolvió %s', respuesta.status_code)
            return jsonify({'error': 1})
        contenido = respuesta.content

        carpeta = ruta.rsplit('/', 1)[0] or '/'
        nombre = ruta.rsplit('/', 1)[-1]
        try:
            # nucleo.subir = versionado del contenido anterior + dedup + escritura atómica
            nucleo.subir(usuario, carpeta, nombre, io.BytesIO(contenido))
        except Exception as excepcion:
            log.error('OnlyOffice: fallo guardando %s: %s', ruta, excepcion)
            return jsonify({'error': 1})

        registrar_actividad(usuario, 'edito', ruta, nucleo.tamano_humano(len(contenido)))
        total = time.monotonic() - inicio
        mensaje = ('OnlyOffice guardado ruta=%s bytes=%d status=%s en %.1fs'
                   % (ruta, len(contenido), status, total))
        (log.warning if total > 10 else log.info)(mensaje)

        if status == 2:
            _cerrar_sesion(datos.get('b') or _base_documento(usuario, ruta))

    return jsonify({'error': 0})


@bp_onlyoffice.route('/onlyoffice/estado', methods=['GET'])
def onlyoffice_estado():
    """GET /onlyoffice/estado — diagnóstico: ¿configurado? ¿el DS responde?"""
    usuario_actual()   # exige sesión
    configurado = bool(secreto_ds() and url_publica_ds())
    conectado = False
    destino = url_interna_ds() or url_publica_ds()
    if destino:
        try:
            conectado = requests.get(destino + '/healthcheck', timeout=5).status_code == 200
        except Exception:
            pass
    return jsonify({'success': True, 'configurado': configurado,
                    'conectado': conectado, 'url_publica': url_publica_ds()})


# ── página del editor (web) ──────────────────────────────────────────────
@bp_onlyoffice_web.route('/archivos-almacen/editar')
def editor_almacen():
    """Página del editor embebido del Almacén. La ruta del archivo viaja en
    ?ruta= y el JavaScript de la página pide la configuración a
    /api/almacen/onlyoffice/config. El candado maestro de /archivos-almacen*
    (integracion_faro) protege el acceso durante la fase de pruebas."""
    plantilla = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'plantillas', 'editor_onlyoffice.html')
    return send_file(plantilla, mimetype='text/html')
