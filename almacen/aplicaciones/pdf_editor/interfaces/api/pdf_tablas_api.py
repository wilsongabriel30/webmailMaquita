# -*- coding: utf-8 -*-
"""
API de COLUMNAS DE TABLAS dentro del propio PDF.
=================================================
«no necesito que me transformes a word sino que ahí mismo me permitas hacer
esos cambios» — el usuario, 27-jul-2026. Esto es ese "ahí mismo": el editor
reconoce las tablas de la página y deja agregar o quitar columnas sin sacar el
documento del PDF ni convertirlo en nada.

  POST /api/pdf/tablas/detectar   ¿qué tablas hay en esta página y dónde?
  POST /api/pdf/tablas/columna    inserta o elimina una columna → PDF nuevo
  POST /api/pdf/tablas/fila       inserta o elimina una fila → PDF nuevo
  POST /api/pdf/tablas/celda      escribe el texto de una celda → PDF nuevo
  POST /api/pdf/tablas/mover      lleva una fila o columna a otro sitio
  POST /api/pdf/tablas/medida     ancho de columna / alto de fila (arrastrar la raya)
  POST /api/pdf/parrafo/en        el párrafo que hay bajo un punto
  POST /api/pdf/parrafo/reemplazar  lo sustituye entero, recompuesto

El trabajo fino (reconocer la tabla, leer la tipografía, borrar la zona y
volver a dibujarla conservando la letra) está en
`infraestructura/externos/tablas_pdf.py`.

Va en un blueprint aparte para no engordar `pdf_editor_api.py`, que ya es
grande. La autenticación se reutiliza de allí.

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import io
import logging
import os

from flask import Blueprint, jsonify, request, send_file

from . import cabeceras
from .pdf_editor_api import requiere_autenticacion
from ...infraestructura.externos import (adelanto_tablas, parrafos_pdf,
                                         pool_pdf, sesion_pdf, tablas_medidas,
                                         tablas_pdf)

logger = logging.getLogger(__name__)

bp_pdf_tablas = Blueprint('pdf_tablas', __name__)


# Lo más grande que se acepta dejar en el servidor. Los documentos en edición
# viven en memoria compartida, que es memoria de TODA la máquina (la comparten
# FARO, PostgreSQL y nginx): sin este tope, unas pocas subidas enormes seguidas
# la llenan y el sistema se queda sin memoria. 50 MB cubre de sobra cualquier
# documento de la fundación, incluidos los escaneados largos.
# (Auditoría del 29-jul-2026.)
TAMANO_MAXIMO = 50 * 1024 * 1024


def _error(mensaje, codigo=400):
    return jsonify({'exito': False, 'mensaje': mensaje}), codigo


def _ocupado(excepcion):
    """El servidor atiende todo lo que puede y esta petición no cabe.

    Se responde 503 y con `Retry-After`, que es lo que corresponde: no es un
    fallo del documento ni culpa del usuario, es que hay que esperar un momento.
    El editor lo distingue del resto de errores y lo reintenta solo.
    """
    respuesta = jsonify({'exito': False, 'ocupado': True,
                         'mensaje': str(excepcion)})
    respuesta.headers['Retry-After'] = '5'
    return respuesta, 503


def _fallo(nombre, excepcion, mensaje):
    """El error de una operación, ya clasificado.

    Se separa lo que el usuario puede entender y corregir (un aviso con sentido)
    de lo que es un problema del servidor, y de cuando simplemente está lleno.
    """
    if isinstance(excepcion, pool_pdf.PdfOcupado):
        return _ocupado(excepcion)
    if isinstance(excepcion, ValueError):
        return _error(str(excepcion))
    logger.exception(nombre)
    return _error('%s: %s' % (mensaje, excepcion), 500)


def _usuario():
    from flask_login import current_user
    return getattr(current_user, 'id', None) or 'anonimo'


def _documento_de_la_peticion():
    """De qué documento habla esta petición.

    Dos formas, y las dos valen:

    · `doc`: el documento ya está en el servidor (lo normal desde hoy). No viaja
      nada por la red y se trabaja sobre el propio archivo.
    · `archivo`: el PDF entero, como se hacía siempre. Se conserva para que a
      quien tenga el editor viejo en la caché del navegador le siga funcionando
      todo, y para las herramientas que no abren sesión.

    Devuelve `(identificador, contenido)`; solo uno de los dos tiene valor.
    """
    identificador = (request.form.get('doc') or '').strip()
    if identificador:
        ruta = sesion_pdf.ruta_de(identificador, _usuario())   # y que es suyo
        # El navegador dice cuánto mide SU copia. Si no coincide con la del
        # servidor, las dos se han separado —una respuesta que se perdió, dos
        # pestañas sobre el mismo documento, un cambio hecho por otro camino— y
        # seguir sería mezclar versiones. Se dice que la sesión se perdió y el
        # editor la rehace con lo que él tiene, sin que el usuario note nada.
        base = request.form.get('base')
        if base is not None:
            try:
                if int(base) != os.path.getsize(ruta):
                    raise sesion_pdf.SesionInvalida(
                        'El documento cambió por otro lado. Se vuelve a enviar.')
            except (TypeError, ValueError):
                pass
        return identificador, None
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return None, None
    return None, (archivo.read() or None)


def _pdf_del_formulario():
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return None
    return archivo.read() or None


def _adelantar_deteccion(pdf, pagina):
    """Reconoce las tablas del PDF nuevo en segundo plano, SIN sesión.

    Es el camino de siempre, para cuando el documento viaja entero en cada
    petición. Con sesión se usa `adelanto_tablas.desde_sesion`, que toma la
    huella del archivo del servidor —la misma con la que se va a preguntar—.
    (Optimización pedida el 28-jul-2026: «que no se demore mucho al editar».)
    """
    if not pdf or len(pdf) > 40 * 1024 * 1024:
        return
    adelanto_tablas.adelantar(pdf, (pagina,))


@bp_pdf_tablas.errorhandler(sesion_pdf.SesionInvalida)
def _sesion_invalida(excepcion):
    """El documento no existe, caducó o no es de quien lo pide.

    Se responde 409 —no es un fallo del servidor— con una marca que el editor
    reconoce para volver a subir el documento y seguir sin molestar al usuario.
    """
    return jsonify({'exito': False, 'sesion_perdida': True,
                    'mensaje': str(excepcion)}), 409


def _referencia(identificador, contenido):
    """Cómo se le nombra el documento al ayudante para las consultas.

    Si hay sesión, por su ruta —no hace falta mover el archivo—; si no, el
    contenido, como siempre.
    """
    if identificador is None:
        return contenido
    from ...infraestructura.externos.guardado_pdf import PdfEnRuta
    return PdfEnRuta(sesion_pdf.ruta_de(identificador, _usuario()))


def _desaparecio(excepcion, ruta):
    """¿El ayudante falló porque el archivo de la sesión ya no estaba?"""
    texto = str(excepcion)
    return 'FileNotFoundError' in texto and os.path.basename(ruta) in texto


def _respuesta_de_operacion(identificador, contenido, tarea, *argumentos, **nombrados):
    """Hace la operación y responde, con o sin sesión, según cómo llegó.

    Con sesión, el ayudante trabaja sobre el propio archivo y devuelve solo el
    trozo añadido: son decenas de kB en vez de los megas que pesa el documento.
    """
    if identificador is None:
        pdf, aviso = pool_pdf.ejecutar(tarea, contenido, *argumentos, **nombrados)
        return _pdf_con_aviso(pdf, aviso, nombrados.get('pagina') or
                              (argumentos[0] if argumentos else None))

    ruta = sesion_pdf.ruta_de(identificador, _usuario())
    try:
        trozo, desde, aviso = pool_pdf.ejecutar('en_sesion', tarea, ruta,
                                                *argumentos, **nombrados)
    except pool_pdf.ErrorDeTarea as excepcion:
        # El documento existía al comprobar la sesión y ya no al operar (el
        # barrido se lo llevó en medio, o se cerró desde otra pestaña). No es
        # un fallo del servidor: es sesión perdida, y el editor la repone solo.
        if _desaparecio(excepcion, ruta):
            raise sesion_pdf.SesionInvalida(
                'El documento en edición ya no está en el servidor. Vuelve a abrirlo.')
        raise
    # El documento acaba de cambiar y el editor, en cuanto lo recargue, va a
    # volver a pedir las tablas de esta misma página. Se reconocen ya, en
    # segundo plano y sobre el archivo tal como ha quedado: cuando pregunte,
    # está hecho. Sin esto se pagaban 0,2-0,4 s de espera después de CADA
    # cambio. (18-ago-2026.)
    pagina_tocada = nombrados.get('pagina') or (argumentos[0] if argumentos else None)
    if pagina_tocada:
        adelanto_tablas.desde_sesion(ruta, (pagina_tocada,))
    respuesta = send_file(io.BytesIO(trozo), mimetype='application/pdf',
                          as_attachment=False, download_name='documento.pdf')
    respuesta.headers['X-Pdf-Desde'] = str(desde)
    respuesta.headers['Access-Control-Expose-Headers'] = 'X-Pdf-Desde'
    cabeceras.poner(respuesta, 'X-Aviso-Tabla', aviso)
    return respuesta


def _pdf_con_aviso(pdf, aviso, pagina=None):
    """El PDF de vuelta; el aviso viaja en una cabecera para no partir la respuesta."""
    if pagina:
        _adelantar_deteccion(pdf, pagina)
    respuesta = send_file(io.BytesIO(pdf), mimetype='application/pdf',
                          as_attachment=False, download_name='documento.pdf')
    cabeceras.poner(respuesta, 'X-Aviso-Tabla', aviso)
    return respuesta


@bp_pdf_tablas.route('/tablas/detectar', methods=['POST'])
@requiere_autenticacion
def detectar():
    """Tablas de una página, con sus columnas, para que el editor las señale."""
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
    except ValueError:
        return _error('Página inválida.')
    try:
        tablas = pool_pdf.ejecutar('detectar', _referencia(identificador,
                                                            contenido), pagina)
    except Exception as excepcion:
        return _fallo('tablas/detectar', excepcion, 'No se pudieron reconocer las tablas')
    return jsonify({'exito': True, 'pagina': pagina, 'tablas': tablas})


@bp_pdf_tablas.route('/tablas/adelantar', methods=['POST'])
@requiere_autenticacion
def adelantar():
    """«Ve reconociendo esta página, que es la que estoy mirando».

    El editor la llama al cambiar de página y no espera la respuesta. Así,
    cuando el usuario active la edición, el trabajo ya está hecho. Responde al
    instante: aquí no se reconoce nada, solo se encarga.
    """
    identificador = (request.form.get('doc') or '').strip()
    if not identificador:
        return jsonify({'exito': True, 'encargado': False})
    try:
        pagina = int(request.form.get('pagina') or 1)
    except ValueError:
        return jsonify({'exito': True, 'encargado': False})
    try:
        ruta = sesion_pdf.ruta_de(identificador, _usuario())
    except sesion_pdf.SesionInvalida:
        # No es un fallo: la sesión se rehará sola en la primera consulta.
        return jsonify({'exito': True, 'encargado': False})
    # La de al lado también: al pasar de página se sigue casi siempre hacia
    # adelante, y adelantarla cuesta lo mismo estando el usuario parado.
    adelanto_tablas.desde_sesion(ruta, (pagina, pagina + 1))
    return jsonify({'exito': True, 'encargado': True})


@bp_pdf_tablas.route('/tablas/columna', methods=['POST'])
@requiere_autenticacion
def columna():
    """Inserta o elimina una columna y devuelve el PDF ya redibujado."""
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
        indice_tabla = int(request.form.get('tabla') or 0)
        posicion = int(request.form.get('posicion') or 0)
    except ValueError:
        return _error('Los datos de la tabla llegaron mal.')
    accion = (request.form.get('accion') or '').strip()
    titulo = (request.form.get('titulo') or '').strip()[:60]

    try:
        return _respuesta_de_operacion(identificador, contenido,
                                       'cambiar_columna', pagina, indice_tabla,
                                       accion, posicion, titulo)
    except Exception as excepcion:
        return _fallo('tablas/columna', excepcion, 'No se pudo cambiar la columna')



@bp_pdf_tablas.route('/tablas/fila', methods=['POST'])
@requiere_autenticacion
def fila():
    """Agrega o quita una fila y devuelve el PDF ya redibujado."""
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
        indice_tabla = int(request.form.get('tabla') or 0)
        posicion = int(request.form.get('posicion') or 0)
    except ValueError:
        return _error('Los datos de la tabla llegaron mal.')
    accion = (request.form.get('accion') or '').strip()

    try:
        # `empujar`: baja lo que hay bajo la tabla en ESA página para hacer
        # sitio, y lo que se salga pasa a una página nueva. Lo pide el editor
        # cuando el usuario elige "desplazar" en vez de "solo aquí".
        empujar = (request.form.get('empujar') or '') in ('1', 'true', 'si')
        return _respuesta_de_operacion(identificador, contenido,
                                       'cambiar_fila', pagina, indice_tabla,
                                       accion, posicion, empujar=empujar)
    except Exception as excepcion:
        return _fallo('tablas/fila', excepcion, 'No se pudo cambiar la fila')


@bp_pdf_tablas.route('/tablas/celda', methods=['POST'])
@requiere_autenticacion
def celda():
    """Escribe (o cambia) el texto de una celda. Es lo que rellena las filas y
    columnas recién agregadas, que nacen vacías."""
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
        indice_tabla = int(request.form.get('tabla') or 0)
        fila_indice = int(request.form.get('fila'))
        columna_indice = int(request.form.get('columna'))
    except (ValueError, TypeError):
        return _error('Los datos de la celda llegaron mal.')
    texto = (request.form.get('texto') or '')[:400]

    try:
        return _respuesta_de_operacion(identificador, contenido,
                                       'escribir_celda', pagina, indice_tabla,
                                       fila_indice, columna_indice, texto)
    except Exception as excepcion:
        return _fallo('tablas/celda', excepcion, 'No se pudo escribir en la celda')


@bp_pdf_tablas.route('/tablas/mover', methods=['POST'])
@requiere_autenticacion
def mover():
    """Lleva una fila o una columna a otra posición."""
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
        indice_tabla = int(request.form.get('tabla') or 0)
        desde = int(request.form.get('desde'))
        hasta = int(request.form.get('hasta'))
    except (ValueError, TypeError):
        return _error('Los datos del movimiento llegaron mal.')
    que = (request.form.get('que') or '').strip()
    if que not in ('fila', 'columna'):
        return _error('Solo se pueden mover filas o columnas.')

    try:
        if que == 'columna':
            return _respuesta_de_operacion(identificador, contenido,
                                           'mover_columna', pagina,
                                           indice_tabla, desde, hasta)
        else:
            return _respuesta_de_operacion(identificador, contenido,
                                           'mover_fila', pagina, indice_tabla,
                                           desde, hasta)
    except Exception as excepcion:
        return _fallo('tablas/mover', excepcion, 'No se pudo mover')


@bp_pdf_tablas.route('/tablas/mover-tabla', methods=['POST'])
@requiere_autenticacion
def mover_tabla():
    """Lleva la tabla entera a otro sitio de la página, arrastrándola.

    «yo quiero… mover tablas… que funcione como un tipo Word» — el usuario,
    29-jul-2026. Mover una fila o una columna ya se podía; esto mueve el
    conjunto.
    """
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
        indice_tabla = int(request.form.get('tabla') or 0)
        dx = float(request.form.get('dx') or 0)
        dy = float(request.form.get('dy') or 0)
    except (ValueError, TypeError):
        return _error('Los datos del movimiento llegaron mal.')

    try:
        return _respuesta_de_operacion(identificador, contenido, 'mover_tabla',
                                       pagina, indice_tabla, dx, dy)
    except Exception as excepcion:
        return _fallo('tablas/mover-tabla', excepcion, 'No se pudo mover la tabla')


@bp_pdf_tablas.route('/tablas/medida', methods=['POST'])
@requiere_autenticacion
def medida():
    """Cambia el ancho de una columna o el alto de una fila arrastrando su raya.

    «unas barritas deslizantes ... yo poder ponerle al tamaño que yo quiero»
    — el usuario, 28-jul-2026. El editor manda qué raya se movió y cuánto, en
    puntos PDF; el recorte para que nada quede ilegible ni se salga de la hoja
    lo hace `tablas_medidas`.
    """
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
        indice_tabla = int(request.form.get('tabla') or 0)
        borde = int(request.form.get('borde'))
        delta = float(request.form.get('delta'))
    except (ValueError, TypeError):
        return _error('Los datos del ajuste llegaron mal.')
    que = (request.form.get('que') or '').strip()

    try:
        return _respuesta_de_operacion(identificador, contenido,
                                       'redimensionar', pagina, indice_tabla,
                                       que, borde, delta)
    except Exception as excepcion:
        return _fallo('tablas/medida', excepcion, 'No se pudo cambiar la medida')


# ============================================================
# EDICIÓN POR PÁRRAFO (no por palabra)
# ============================================================
@bp_pdf_tablas.route('/parrafo/en', methods=['POST'])
@requiere_autenticacion
def parrafo_en():
    """El párrafo que hay bajo un punto de la página, para abrirlo entero."""
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
        x = float(request.form.get('x'))
        y = float(request.form.get('y'))
    except (ValueError, TypeError):
        return _error('El punto llegó mal.')
    try:
        parrafo = pool_pdf.ejecutar('parrafo_en', _referencia(identificador,
                                                                 contenido),
                                    pagina, x, y)
    except Exception as excepcion:
        return _fallo('parrafo/en', excepcion, 'No se pudo leer el párrafo')
    if not parrafo:
        return jsonify({'exito': True, 'parrafo': None})
    return jsonify({'exito': True, 'parrafo': parrafo})


@bp_pdf_tablas.route('/parrafo/reemplazar', methods=['POST'])
@requiere_autenticacion
def parrafo_reemplazar():
    """Sustituye el párrafo entero por el texto nuevo, recomponiéndolo."""
    identificador, contenido = _documento_de_la_peticion()
    if identificador is None and not contenido:
        return _error('Falta el archivo PDF.')
    try:
        pagina = int(request.form.get('pagina') or 1)
        bbox = [float(v) for v in (request.form.get('bbox') or '').split(',')]
        if len(bbox) != 4:
            raise ValueError
    except (ValueError, TypeError):
        return _error('Los datos del párrafo llegaron mal.')
    texto = (request.form.get('texto') or '')[:6000]

    try:
        return _respuesta_de_operacion(identificador, contenido,
                                       'reemplazar_parrafo', pagina, bbox,
                                       texto)
    except Exception as excepcion:
        return _fallo('parrafo/reemplazar', excepcion, 'No se pudo cambiar el párrafo')


# ============================================================
# EL DOCUMENTO EN EL SERVIDOR MIENTRAS SE EDITA
# ============================================================
@bp_pdf_tablas.route('/sesion', methods=['POST'])
@requiere_autenticacion
def abrir_sesion():
    """Deja el documento en el servidor y devuelve su identificador.

    A partir de aquí, cada cambio manda solo ese identificador en vez del PDF
    entero: se ahorran los megas de subida y de bajada de cada clic.
    """
    # El tamaño se mira ANTES de leer el cuerpo: si no, ya se habría tragado en
    # memoria el archivo entero, que es justo lo que se quiere evitar.
    declarado = request.content_length or 0
    if declarado > TAMANO_MAXIMO:
        return _error('El documento pesa demasiado para editarlo en línea '
                      '(%d MB); el máximo son %d MB.'
                      % (declarado // (1024 * 1024), TAMANO_MAXIMO // (1024 * 1024)),
                      413)

    huella = (request.headers.get('X-Pdf-Huella') or '').strip().lower()

    # Camino nuevo (18-ago-2026): el documento viaja tal cual, sin envoltorio de
    # formulario, y se va escribiendo según llega. Antes, el formulario
    # multiparte lo dejaba de paso en un archivo temporal EN DISCO y luego lo
    # cargaba entero en memoria para volver a escribirlo: tres viajes para lo
    # mismo. El editor manda así desde esta fecha; el formulario se sigue
    # aceptando porque hay pestañas abiertas con el editor de antes.
    if (request.mimetype or '').lower() == 'application/pdf':
        cabecera = request.stream.read(5)
        if cabecera != b'%PDF-':
            return _error('Eso no es un archivo PDF.')
        try:
            identificador, pesaba = sesion_pdf.crear_desde_flujo(
                _con_cabecera(cabecera, request.stream), _usuario(),
                TAMANO_MAXIMO, huella=huella)
        except Exception as excepcion:
            logger.exception('sesion/abrir (en crudo)')
            return _error('No se pudo preparar el documento: %s' % excepcion, 500)
        if identificador is None:
            return _error('El documento pesa demasiado para editarlo en línea.', 413)
        _adelantar_al_abrir(identificador)
        return jsonify({'exito': True, 'doc': identificador, 'tamano': pesaba})

    contenido = _pdf_del_formulario()
    if not contenido:
        return _error('Falta el archivo PDF.')
    if len(contenido) > TAMANO_MAXIMO:
        return _error('El documento pesa demasiado para editarlo en línea.', 413)
    if not contenido.startswith(b'%PDF-'):
        return _error('Eso no es un archivo PDF.')
    try:
        identificador = sesion_pdf.crear(contenido, _usuario(), huella=huella)
    except Exception as excepcion:
        logger.exception('sesion/abrir')
        return _error('No se pudo preparar el documento: %s' % excepcion, 500)

    _adelantar_al_abrir(identificador)

    return jsonify({'exito': True, 'doc': identificador,
                    'tamano': len(contenido)})


def _con_cabecera(cabecera, resto):
    """El flujo entero otra vez, con los primeros bytes que ya se miraron."""
    return io.BufferedReader(_Pegado(cabecera, resto))


class _Pegado(io.RawIOBase):
    """Los bytes ya leídos, y después lo que quede por llegar."""

    def __init__(self, principio, resto):
        self._principio = principio
        self._resto = resto

    def readable(self):
        return True

    def readinto(self, hueco):
        if self._principio:
            cuantos = min(len(hueco), len(self._principio))
            hueco[:cuantos] = self._principio[:cuantos]
            self._principio = self._principio[cuantos:]
            return cuantos
        datos = self._resto.read(len(hueco))
        if not datos:
            return 0
        hueco[:len(datos)] = datos
        return len(datos)


@bp_pdf_tablas.route('/sesion/huella', methods=['POST'])
@requiere_autenticacion
def sesion_por_huella():
    """«¿Ya tienes este documento?». Se responde con 64 letras, no con megas.

    El navegador manda la huella del archivo antes de subirlo. Si el mismo
    documento de esta misma persona ya está en el servidor —recargó la página,
    lo abrió en otra pestaña, volvió a él más tarde— se sigue con el que hay y
    la subida entera se ahorra. Si no está, se responde que no y el navegador
    lo sube como siempre.
    """
    huella = (request.form.get('huella') or '').strip().lower()
    try:
        tamano = int(request.form.get('tamano') or 0)
    except ValueError:
        tamano = 0
    if not huella or tamano <= 0:
        return jsonify({'exito': True, 'doc': None})
    try:
        identificador = sesion_pdf.buscar_por_huella(huella, tamano, _usuario())
    except Exception:
        logger.debug('no se pudo buscar por huella', exc_info=True)
        identificador = None
    if identificador:
        _adelantar_al_abrir(identificador)
    return jsonify({'exito': True, 'doc': identificador, 'tamano': tamano})


def _adelantar_al_abrir(identificador):
    """Reconocer ya las tablas de las primeras páginas, en segundo plano.

    Cuando el usuario active la edición —que siempre es después— el trabajo ya
    está hecho y la tabla aparece marcada al instante, en vez de dejarlo
    esperando («no le reconoce rápidamente lo que es la tabla, se demora
    bastante», vídeo del usuario, 29-jul-2026).

    Se adelanta SOBRE LA SESIÓN, no sobre el contenido: el editor va a
    preguntar por la sesión, y hasta el 18-ago-2026 esto se hacía con el
    contenido, cuya huella es otra. El trabajo se hacía y no se encontraba: la
    primera consulta seguía costando 0,405 s.
    """
    try:
        adelanto_tablas.desde_sesion(
            sesion_pdf.ruta_de(identificador, _usuario()),
            adelanto_tablas.PAGINAS_AL_ABRIR)
    except Exception:
        logger.debug('no se pudo adelantar al abrir', exc_info=True)


@bp_pdf_tablas.route('/sesion/<path:identificador>', methods=['DELETE'])
@requiere_autenticacion
def cerrar_sesion(identificador):
    """Borra el documento del servidor. Lo llama el editor al cerrarse."""
    return jsonify({'exito': sesion_pdf.cerrar(identificador, _usuario())})


@bp_pdf_tablas.route('/sesion/<path:identificador>', methods=['GET'])
@requiere_autenticacion
def bajar_sesion(identificador):
    """El documento entero, tal como está ahora en el servidor.

    Es la red de seguridad: si al navegador se le descuadra su copia (por
    ejemplo porque una respuesta se perdió), lo pide entero y sigue trabajando.
    """
    try:
        contenido = sesion_pdf.leer(identificador, _usuario())
    except sesion_pdf.SesionInvalida as excepcion:
        return _error(str(excepcion), 404)
    return send_file(io.BytesIO(contenido), mimetype='application/pdf',
                     as_attachment=False, download_name='documento.pdf')
