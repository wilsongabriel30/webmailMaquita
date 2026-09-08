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
from flask import Blueprint, Response, jsonify, request, send_file

import nucleo_archivos as nucleo
from almacen_bd import consultar, ejecutar
from api_archivos import _permiso_unidad, error, usuario_actual
from config_almacen import URL_PUBLICA
from registro import registrar_actividad
import onlyoffice_urls as oo_urls
import conversion_edicion
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


def bases_publicas_ds() -> list:
    """Dominios por los que el Document Server puede anunciar sus descargas.
    El Drive vive en datos... y en drive...: el DS usa aquel por el que le llego
    la peticion, asi que los dos son legitimos (ver onlyoffice_urls.py)."""
    return oo_urls.bases_publicas(
        url_publica_ds(),
        _cfg('onlyoffice_urls_publicas_extra', 'ALMACEN_ONLYOFFICE_URLS_PUBLICAS_EXTRA'))


def base_ds_publica(es_lectura: bool) -> str:
    """URL publica del Document Server segun el uso: el 2o DS de SOLO LECTURA
    (/office-lectura, VM 193.16.0.6) cuando la apertura es en modo vista, o el
    principal de EDICION (/office-almacen, VM131) cuando se edita. Asi los
    lectores NO consumen el limite de ~20 conexiones de edicion. Si no esta el
    path esperado, cae al DS principal (comportamiento seguro)."""
    base = url_publica_ds()
    if es_lectura and '/office-almacen' in base:
        return base.replace('/office-almacen', '/office-lectura')
    return base


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
    # Espacio «Compartido conmigo»: la sala es la del DUEÑO del archivo. Si no,
    # el dueño y la persona invitada abrirían dos documentos distintos del mismo
    # archivo y el último en guardar borraría el trabajo del otro.
    try:
        from seguridad_rutas import compartido_de_ruta
        propietario, subruta = compartido_de_ruta(ruta)
        if propietario is not None:
            return f'usuario:{propietario}:{subruta}'
    except Exception:
        pass
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


def invalidar_cache(usuario: int, ruta: str) -> None:
    """Avisa de que el archivo cambió POR FUERA del editor (27/08/2026).

    El Document Server guarda su propia copia de cada documento y la reconoce
    por la `key`. Esa key solo cambiaba al cerrarse una sesión de edición, así
    que cuando el archivo se reemplaza desde otro sitio —exportar las respuestas
    de un formulario encima del `.xlsx` de siempre— el editor seguía enseñando
    **la copia anterior**: el archivo del disco estaba bien y en pantalla salía
    el de antes, sin ninguna pista de por qué.

    Subir la versión de la sala hace que la próxima apertura use una key nueva y
    el Document Server descargue el archivo otra vez.

    No falla nunca hacia fuera: si esto no funciona, lo peor que pasa es que
    haya que cerrar y reabrir el documento, que es lo que ocurría siempre antes.
    """
    try:
        _cerrar_sesion(_base_documento(usuario, ruta))
    except Exception as excepcion:
        log.warning('OnlyOffice: no se pudo invalidar la caché de %s (%s)',
                    ruta, excepcion)


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
    return oo_urls.a_url_interna(url, bases_publicas_ds(), url_interna_ds()) or url


# Scripts que se anaden a la pagina del editor al servirla. Van aqui y no
# dentro del HTML porque la plantilla editor_onlyoffice.html se restaura sola a
# una version antigua (ocurrio tres veces el 31/08/2026) y el cambio se perdia.
# Aqui vive con el resto del codigo, que si persiste.
# Los añadidos del editor (arreglos de la hoja y tarjeta de enlaces) viven en
# `arreglos_editor`, que también los pone en las páginas del editor que NO pasan
# por aquí (la Nube antigua y sus visores compartidos). Una sola fuente.


def _pagina_editor(nombre_plantilla: str):
    """Devuelve la pagina del editor con los anadidos de Maquita.

    Si algo falla al leerla o al insertarlos, se entrega tal cual: el editor
    tiene que abrir SIEMPRE, aunque sea sin los extras.
    """
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'plantillas', nombre_plantilla)
    try:
        with io.open(ruta, encoding='utf-8') as archivo:
            html = archivo.read()
        from arreglos_editor import poner_en
        html = poner_en(html)
        respuesta = Response(html, mimetype='text/html')
    except Exception as excepcion:
        log.warning('No se pudieron anadir los extras del editor (%s)', excepcion)
        respuesta = send_file(ruta, mimetype='text/html')
    respuesta.headers['Permissions-Policy'] = 'unload=*'
    respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return respuesta


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
DIRECTORIO_LOGOS = ('/home/sistemas/Maquita/interfaces/web/estaticos/'
                    'uploads/logos')


def _version_estatico(nombre):
    """Marca de version para colgar de la URL de un estatico (?v=...).

    Devuelve la fecha de modificacion del archivo en segundos. Si el archivo
    no se puede leer se devuelve una constante: es preferible una URL estable
    a reventar la cache en cada peticion."""
    try:
        return str(int(os.path.getmtime(os.path.join(DIRECTORIO_LOGOS, nombre))))
    except OSError:
        return '1'


def _logo_editor(publico=False):
    """Logo de Maquita para OnlyOffice.

    CORRECCIÓN DEL 2026-07-29: este logo SÍ SE APLICA.

    Primero se concluyó que no, porque la licencia devuelve `branding: False`
    y la cabecera seguía diciendo «ONLYOFFICE». El motivo real era otro: se
    enviaba el logo general de 2446x739 px, que el editor no llegaba a pintar
    y por eso caía a su marca por defecto. Con una imagen del tamaño admitido
    (172x40 como máximo) el editor la aplica sin problema.

    Se usa la versión en BLANCO: la barra del editor cambia de color según el
    tipo de documento —verde en hojas, azul en textos, naranja en
    presentaciones— y además hay tema oscuro. A color el logo se pierde.

    En los enlaces públicos el logo NO es clicable: quien abre un archivo
    compartido no tiene sesión, y llevarlo al Drive lo dejaría en el login."""
    # OnlyOffice admite como maximo 172x40 px en el encabezado. El logo general
    # de Maquita mide 2446x739: al enviarlo tal cual, el editor lo escalaba por
    # la fuerza, se descolocaba y comia alto util. Se usa una version a medida
    # (132x40) generada del mismo original, mas la del doble para pantallas de
    # alta densidad.
    # El logo lo carga el NAVEGADOR, no el Document Server, así que debe salir
    # del MISMO dominio en el que está la persona. nginx envía al editor
    # `X-Forwarded-Host: $host/office-almacen`, de modo que en
    # drive.maquita.com.ec el editor corre bajo ese dominio: apuntar el logo a
    # datos.maquita.com.ec lo convertía en una carga entre dominios distintos, y
    # ahí es donde dejaba de verse. Los estáticos están en los dos dominios.
    try:
        base = f'{request.host_url.rstrip("/")}/static/uploads/logos'
    except Exception:
        base = f'{URL_PUBLICA}/static/uploads/logos'   # fuera de una petición

    # Sufijo de version (?v=). NO es cosmetico: en el front, drive.maquita.com.ec
    # NO tiene el bloque /static/ propio que si tiene datos.maquita.com.ec, asi
    # que hereda de la VM 101: expires 1y y Cache-Control public, immutable.
    # Con immutable el navegador NO revalida NUNCA -- ni con Ctrl+F5 -- y se
    # queda con la imagen que bajo la primera vez. Ese fue el motivo real de que
    # el logo siguiera saliendo a color solo en drive. Al colgar la fecha de
    # modificacion del archivo, cada cambio del logo produce una URL distinta y
    # la cache deja de ser un problema, sin depender de la configuracion de
    # nginx de cada dominio.
    version = _version_estatico('maquita-logo-editor-blanco.png')
    imagen = f'{base}/maquita-logo-editor-blanco.png?v={version}'
    logo = {'image': imagen, 'imageEmbedded': imagen, 'imageDark': imagen,
            'image2x': f'{base}/maquita-logo-editor-blanco@2x.png?v={version}'}
    # El destino del clic SIEMPRE se manda explícito. Si se omite, el editor
    # cae en su valor por defecto y abre https://www.onlyoffice.com en una
    # pestaña nueva: saca a la persona de su trabajo hacia la web de otra
    # empresa y a Maquita no le aporta nada (reportado por los usuarios el
    # 29/07/2026). Ese valor por defecto también se corrigió dentro del
    # contenedor, en Header.js; ver marca-onlyoffice.sh.
    from config_almacen import URL_LINKS
    if publico:
        # Invitado por enlace: NO tiene sesión. Mandarlo al Drive lo dejaría en
        # una pantalla de acceso sin explicación. Con cadena vacía el editor
        # evalúa `if (_url)` como falso y el logo simplemente no hace nada,
        # igual que el de Google Drive dentro de sus editores.
        logo['url'] = ''
    else:
        # Trabajador con sesión: al inicio de Drive Maquita. Se usa URL_LINKS
        # —el dominio de cara a las personas, siempre drive.maquita.com.ec— y
        # no URL_PUBLICA, que es el interno que resuelve el Document Server.
        logo['url'] = URL_LINKS
    return logo


def _tema_editor():
    """Tema de la interfaz del editor, siguiendo el aspecto elegido en el Drive.

    El Drive guarda la preferencia en localStorage y la reenvía como ?tema=.
    OnlyOffice solo acepta el tema dentro de la configuración firmada, por eso
    no se puede cambiar desde el navegador una vez cargado el editor."""
    tema = (request.args.get('tema') or '').strip().lower()
    return 'theme-dark' if tema in ('oscuro', 'dark') else 'theme-light'


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

    # Formatos antiguos (.doc/.xls/.ppt…): con permiso de escritura se
    # convierten al formato moderno en la misma carpeta y se abre ESE archivo
    # para poder editarlo; el original se conserva (ver conversion_edicion.py).
    ruta_original = ruta
    convertido_ahora = False
    if escritura and conversion_edicion.es_convertible(extension):
        ruta, convertido_ahora = conversion_edicion.preparar_para_editar(usuario, ruta, fisica)
        if ruta != ruta_original:
            nombre = ruta.rsplit('/', 1)[-1]
            extension = nombre.rsplit('.', 1)[-1].lower()
            tipo_documento = TIPOS_DOCUMENTO.get(extension, tipo_documento)
            fisica = ruta_fisica(usuario, ruta)

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
                                 'b': doc_base, 'w': (modo == 'edit'), 'exp': exp})
    url_descarga = f'{URL_PUBLICA}/api/almacen/onlyoffice/download?t={token_descarga}'
    url_callback = f'{URL_PUBLICA}/api/almacen/onlyoffice/callback?t={token_callback}'

    puede_editar = (modo == 'edit')
    config = {
        'document': {
            'fileType': extension,
            'key': doc_key,
            'title': nombre,
            'url': url_descarga,
            # Identidad del libro para referencias entre archivos (IMPORTRANGE)
            'referenceData': {'fileKey': f'{usuario}|{ruta}', 'instanceId': URL_PUBLICA},
            'permissions': {
                'chat': True,
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
            # Formato de fechas, moneda y separador decimal de Ecuador.
            # Importa sobre todo en hojas de cálculo.
            'region': 'es-EC',
            'customization': {
                'autosave': True,
                'comments': puede_editar,
                # Encabezado NO compacto, a propósito: el logo de Maquita va en su
                # propia franja, en el sitio donde OnlyOffice pone su marca. Así
                # estaba cuando se aprobó y así se mantiene.
                # El problema de espacio que se reportó el 2026-07-29 NO venía de
                # aquí, sino de un logo de 2446x739 px que el editor escalaba por
                # la fuerza (ver _logo_editor).
                'compactHeader': False,
                'feedback': False,
                'forcesave': True,
                'help': False,
                'spellcheck': True,
                # Sigue el aspecto elegido en el Drive (Claro / Oscuro).
                'uiTheme': _tema_editor(),
                # Botón de volver, como el de Documentos de Google: regresa a la
                # carpeta que contiene el archivo, no a la raíz.
                'goback': {
                    'blank': False,
                    'text': 'Volver a Drive Maquita',
                    # Se usa el dominio DESDE EL QUE entró el usuario, no
                    # URL_PUBLICA: la aplicación se sirve en varios dominios
                    # (drive.maquita.com.ec y datos.maquita.com.ec) y la sesión
                    # es por dominio. Mandarlo al otro lo rebotaría al login.
                    'url': f'{request.host_url.rstrip("/")}'
                           f'/archivos-almacen{ruta.rsplit("/", 1)[0] or ""}',
                },
                'logo': _logo_editor(),
                'zoom': 100,
            },
        },
        'height': '100%',
        'width': '100%',
        'type': 'desktop',
    }
    config['token'] = firmar_jwt(config)

    respuesta = jsonify({
        'success': True,
        'config': config,
        'api_js_url': f'{base_ds_publica(not puede_editar)}/web-apps/apps/api/documents/api.js',
        'puede_editar': puede_editar,
        # Si se abrió la copia moderna de un formato antiguo, la página lo
        # refleja (título, URL) y avisa si se acaba de crear.
        'ruta_abierta': ruta,
        'convertido_desde': ruta_original if ruta != ruta_original else None,
        'convertido_ahora': convertido_ahora,
    })
    # Sin Cache-Control el navegador guarda esta respuesta por heuristica y
    # sigue abriendo el editor con una configuracion vieja (logo, goback,
    # permisos). Ademas la cache es POR DOMINIO, asi que drive y datos pueden
    # quedar desincronizados entre si. El JSON lleva un JWT con caducidad:
    # nunca debe reutilizarse.
    respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    respuesta.headers['Pragma'] = 'no-cache'
    return respuesta


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
        # El token de callback debe haber sido emitido para EDICION ('w') y el
        # usuario debe conservar permiso de escritura sobre la ruta. Sin esto,
        # un enlace/modo de SOLO LECTURA podia sobrescribir el archivo del dueno.
        if not datos.get('w') or not _permiso_unidad(usuario, ruta, escritura=True):
            log.error('OnlyOffice callback SIN permiso de escritura: ruta=%s usuario=%s',
                      ruta, usuario)
            return jsonify({'error': 1})
        # CRÍTICO: responder antes del timeout del proxy; si el DS recibe 504
        # reintenta y luego DESCARTA el documento (incidente Nube 2026-07-01).
        # Se cronometra todo para diagnosticar lentitud.
        inicio = time.monotonic()
        url = cuerpo.get('url')
        if not url:
            log.error('OnlyOffice callback sin URL del documento editado')
            return jsonify({'error': 1})

        # Allowlist SSRF: solo se descarga desde el propio Document Server.
        # Allowlist SSRF: solo se descarga del propio Document Server, por
        # CUALQUIERA de los dominios con los que puede anunciarse.
        url_final = oo_urls.a_url_interna(url, bases_publicas_ds(), url_interna_ds())
        if not url_final:
            # Con la ruta: sin ella no hay forma de saber QUE archivo se
            # quedo sin guardar (paso del 24 al 31/08/2026, 192 veces).
            log.error('OnlyOffice callback: URL de documento no permitida: %s'
                      ' (ruta=%s usuario=%s)', url, ruta, usuario)
            return jsonify({'error': 1})
        try:
            respuesta = requests.get(url_final, timeout=120)
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
        # Vinculos de datos: si este archivo es ORIGEN de algun vinculo,
        # refrescar los destinos (valores) automaticamente. Best-effort.
        try:
            from api_vinculos import refrescar_por_origen
            refrescar_por_origen(usuario, ruta)
        except Exception as _exc_vinc:
            log.warning('vinculos refresco auto %s: %s', ruta, _exc_vinc)
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


def _share_por_token(token: str):
    """Share vigente por token (o None). Valida expiración; la clave la valida
    quien llama (viaja en el query `clave=`)."""
    filas = consultar("""
        SELECT id, propietario_id, ruta, token, puede_editar, permite_descarga,
               clave_hash, expira_en, email, requiere_otp
        FROM compartidos WHERE token = %s
    """, (token,))
    if not filas:
        return None
    comp = dict(filas[0])
    if comp['expira_en'] is not None:
        from datetime import datetime, timezone
        if comp['expira_en'] < datetime.now(timezone.utc):
            return None
    return comp


def _clave_ok(comp) -> bool:
    if not comp.get('clave_hash'):
        return True
    clave = request.args.get('clave', '')
    return hashlib.sha256(clave.encode()).hexdigest() == comp['clave_hash']


@bp_onlyoffice.route('/onlyoffice/config-public', methods=['GET'])
def onlyoffice_config_public():
    """GET /onlyoffice/config-public?token=<share>&clave= — configuración del
    editor para un ENLACE COMPARTIDO, sin sesión. La credencial es el token del
    share (+ su clave si tiene). Usa la MISMA key de sala que los usuarios
    internos → un invitado coedita en la misma sala. El DS descarga y guarda
    con los tokens firmados de siempre (u = propietario del archivo)."""
    if not (secreto_ds() and url_publica_ds()):
        return error('La edición online aún no está configurada', 503)
    comp = _share_por_token(request.args.get('token', ''))
    if not comp:
        return error('Enlace inválido o expirado', 404)
    # Enlace restringido (12/08/2026): tampoco se edita en línea sin sesión.
    if (comp.get('modo') or '') == 'restringido':
        return error('Este enlace ya no es público. Inicia sesión en el Drive '
                     'o pide acceso a los administradores de la unidad.', 403)
    if not _clave_ok(comp):
        return error('Clave incorrecta', 401)
    # Fase C: OTP por correo (si el enlace lo exige) + auditoria del acceso
    from api_acceso_externo import otp_ok, registrar_acceso, _mascara
    if not otp_ok(comp['token'], comp):
        return jsonify({'success': False, 'otp_requerido': True,
                        'email_mascara': _mascara(comp.get('email') or '')}), 428
    registrar_acceso(comp['id'], comp['token'],
                     'edito' if comp.get('puede_editar') else 'abrio',
                     comp.get('email') or '')
    try:
        from almacen_bd import ejecutar as _ej
        _ej('UPDATE compartidos SET accesos = accesos + 1 WHERE id = %s', (comp['id'],))
    except Exception:
        pass

    propietario, ruta = comp['propietario_id'], comp['ruta']

    # ── P-13b: archivo DENTRO de un enlace de CARPETA ───────────────────────
    # El enlace apunta a una carpeta y `sub` dice qué archivo de dentro se
    # quiere abrir. La contención (que `sub` no se escape del enlace) y el
    # ajuste «limitar el acceso» los resuelve _fisica_dentro, el MISMO helper
    # que ya usa la vista pública: así hay una sola regla de seguridad y no dos
    # que se puedan desincronizar. Import diferido para no crear un ciclo con
    # integracion_faro, que a su vez importa este módulo.
    sub = (request.args.get('sub') or '').strip('/')
    if sub:
        from integracion_faro import _fisica_dentro
        from seguridad_rutas import normalizar_ruta_virtual, RutaInvalida
        _base, _destino = _fisica_dentro(comp, sub)
        if not _destino or not os.path.isfile(_destino):
            return error('No encontramos ese archivo en el enlace', 404)
        try:
            ruta = normalizar_ruta_virtual(comp['ruta'] + '/' + sub)
        except RutaInvalida:
            return error('Ruta inválida', 400)

    nombre = ruta.rsplit('/', 1)[-1]
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    tipo_documento = TIPOS_DOCUMENTO.get(extension)
    if not tipo_documento:
        return error(f'Este tipo de archivo no se abre en línea: {extension}', 400)
    try:
        fisica = ruta_fisica(propietario, ruta)
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    if not os.path.isfile(fisica):
        return error('El archivo ya no existe', 404)

    puede_editar = bool(comp['puede_editar']) and extension in EXTENSIONES_EDITABLES

    # Política de macros: un archivo con macros se puede LEER y EDITAR en línea
    # (OnlyOffice no ejecuta VBA, así que aquí la macro nunca corre), pero no se
    # deja descargar ni imprimir desde el editor — descargarlo sacaría el
    # original con la macro dentro, que es justo lo que no debe salir. Quien
    # necesite el contenido tiene el botón de descarga del enlace, que entrega
    # la copia limpia.
    import compartir_macros
    descargable = (bool(comp['permite_descarga'])
                   and not compartir_macros.con_macros(fisica, nombre))

    # MISMA sala que los internos: misma base de documento y versión de sesión
    doc_base = _base_documento(propietario, ruta)
    version = _version_sesion(doc_base)
    doc_key = hashlib.sha1(f'{doc_base}:v{version}'.encode()).hexdigest()[:20]

    exp = int(time.time()) + DIAS_TOKEN * 86400
    token_descarga = firmar_jwt({'u': propietario, 'r': ruta, 'uso': 'descarga', 'exp': exp})
    token_callback = firmar_jwt({'u': propietario, 'r': ruta, 'uso': 'callback',
                                 'b': doc_base, 'w': puede_editar, 'exp': exp})

    invitado = comp.get('email') or 'Invitado'
    config = {
        'document': {
            'fileType': extension,
            'key': doc_key,
            'title': nombre,
            'url': f'{URL_PUBLICA}/api/almacen/onlyoffice/download?t={token_descarga}',
            'referenceData': {'fileKey': f'{propietario}|{ruta}', 'instanceId': URL_PUBLICA},
            'permissions': {
                'chat': True,
                'comment': puede_editar,
                'download': descargable,
                'edit': puede_editar,
                'print': descargable,
                'review': puede_editar,
            },
        },
        'documentType': tipo_documento,
        'editorConfig': {
            'callbackUrl': f'{URL_PUBLICA}/api/almacen/onlyoffice/callback?t={token_callback}',
            'coEditing': {'mode': 'fast', 'change': False},
            'lang': 'es',
            'mode': 'edit' if puede_editar else 'view',
            'user': {'id': f'invitado-{comp["id"]}', 'name': f'{invitado} (invitado)'},
            'region': 'es-EC',
            'customization': {
                'autosave': True,
                'comments': puede_editar,
                'compactHeader': True,
                'feedback': False,
                'forcesave': True,
                'help': False,
                'spellcheck': True,
                'uiTheme': _tema_editor(),
                # Coherencia de marca: el enlace público no llevaba logo.
                'logo': _logo_editor(publico=True),
                'zoom': 100,
            },
        },
        'height': '100%',
        'width': '100%',
        'type': 'desktop',
    }
    config['token'] = firmar_jwt(config)
    respuesta = jsonify({
        'success': True,
        'config': config,
        'api_js_url': f'{base_ds_publica(not puede_editar)}/web-apps/apps/api/documents/api.js',
        'puede_editar': puede_editar,
        'nombre': nombre,
    })
    respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    respuesta.headers['Pragma'] = 'no-cache'
    return respuesta


# ── página del editor (web) ──────────────────────────────────────────────
@bp_onlyoffice_web.route('/archivos-almacen/editar')
def editor_almacen():
    """Página del editor embebido del Almacén. La ruta del archivo viaja en
    ?ruta= y el JavaScript de la página pide la configuración a
    /api/almacen/onlyoffice/config. El candado maestro de /archivos-almacen*
    (integracion_faro) protege el acceso durante la fase de pruebas."""
    # Si la ruta apunta a una CARPETA (p. ej. una carpeta con puntos en el
    # nombre cuyo enlace se armó como si fuera archivo), NO abrir el editor
    # —daría "Tipo de archivo no soportado"—: llevar a la carpeta. Si no hay
    # sesión, el candado ya redirigió al login antes de llegar aquí.
    try:
        from flask import redirect as _redir
        from urllib.parse import quote as _q
        _ruta_raw = request.args.get('ruta', '')
        _ruta = normalizar_ruta_virtual(_ruta_raw)
        _fis = ruta_fisica(usuario_actual(), _ruta)
        if os.path.isdir(_fis):
            return _redir('/archivos-almacen' + _q(_ruta), 302)
    except Exception:
        pass
    return _pagina_editor('editor_onlyoffice.html')


@bp_onlyoffice_web.route('/archivos-almacen/editar-publico')
def editor_almacen_publico():
    """Página del editor para un ENLACE COMPARTIDO (invitado SIN sesión FARO).
    El token del share viaja en ?t= (y la clave opcional en ?clave=); el
    JavaScript pide la configuración a /api/almacen/onlyoffice/config-public.
    Esta ruta está exenta del candado maestro (ver integracion_faro): su
    seguridad es el token del enlace + la clave/expiración del share."""
    return _pagina_editor('editor_publico.html')
