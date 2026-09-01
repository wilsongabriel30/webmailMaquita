# -*- coding: utf-8 -*-
"""
API REST Principal - PDF Editor.

Blueprint con todos los endpoints del editor PDF.
"""

import os
import logging
from flask import Blueprint, request, jsonify, send_file, g, current_app
from functools import wraps

logger = logging.getLogger(__name__)

bp_pdf_api = Blueprint('pdf_api', __name__)


def obtener_servicio_pdf():
    """Obtiene o crea el servicio PDF para la solicitud actual."""
    if 'servicio_pdf' not in g:
        from ...aplicacion.servicios.servicio_pdf import ServicioPDF
        from ...infraestructura.persistencia.repositorio_documento_postgresql import RepositorioDocumentoPostgreSQL
        from ...infraestructura.externos.cliente_pymupdf import ClientePyMuPDF
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # Obtener sesión de base de datos herramientas
        try:
            from config import Config
            engine = create_engine(Config.HERRAMIENTAS_DATABASE_URI, pool_pre_ping=True)
            Session = sessionmaker(bind=engine)
            db_session = Session()
        except Exception as e:
            logger.error(f"Error conectando a BD herramientas: {e}")
            db_session = None

        repositorio = RepositorioDocumentoPostgreSQL(db_session) if db_session else None

        try:
            cliente_pdf = ClientePyMuPDF()
        except ImportError:
            cliente_pdf = None
            logger.warning("PyMuPDF no disponible, funcionalidad limitada")

        g.servicio_pdf = ServicioPDF(
            repositorio_documento=repositorio,
            cliente_pdf=cliente_pdf,
            ruta_uploads='/home/sistemas/Maquita/uploads/pdf_editor'
        )
        g.db_session = db_session

    return g.servicio_pdf


@bp_pdf_api.teardown_request
def cerrar_sesion_db(exception=None):
    """Cierra la sesión de BD al finalizar la solicitud."""
    db_session = g.pop('db_session', None)
    if db_session is not None:
        db_session.close()


def requiere_autenticacion(f):
    """Decorador que requiere usuario autenticado."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask_login import current_user
        if not current_user.is_authenticated:
            return jsonify({
                'exito': False,
                'mensaje': 'Autenticación requerida',
                'codigo': 'NO_AUTENTICADO'
            }), 401
        return f(*args, **kwargs)
    return decorated


def obtener_usuario_id():
    """Obtiene el ID del usuario actual."""
    from flask_login import current_user
    if current_user.is_authenticated:
        return current_user.id
    return None


# =============================================================================
# Almacenamiento de certificados de firma (.p12) POR USUARIO
# Se guardan en el servidor (fuera de rutas web, permisos restringidos) para que
# estén disponibles desde cualquier dispositivo. La contraseña NUNCA se guarda.
# Los endpoints de alta/baja/lista viven en firma_certificados_api.py.
# =============================================================================
_DIR_CERTS_FIRMA = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', '..', 'data', 'firmas_p12'))


# =============================================================================
# ENDPOINTS DE DOCUMENTOS
# =============================================================================

@bp_pdf_api.route('/documentos', methods=['POST'])
@requiere_autenticacion
def subir_documento():
    """
    Sube un nuevo documento PDF.

    POST /api/pdf/documentos
    Body: multipart/form-data con campo 'archivo'

    Returns:
        JSON con datos del documento creado
    """
    if 'archivo' not in request.files:
        return jsonify({
            'exito': False,
            'mensaje': 'No se proporcionó archivo',
            'codigo': 'ARCHIVO_REQUERIDO'
        }), 400

    archivo = request.files['archivo']

    if archivo.filename == '':
        return jsonify({
            'exito': False,
            'mensaje': 'Nombre de archivo vacío',
            'codigo': 'NOMBRE_VACIO'
        }), 400

    try:
        servicio = obtener_servicio_pdf()
        documento = servicio.subir_documento(
            archivo=archivo,
            usuario_id=obtener_usuario_id(),
            nombre_original=archivo.filename
        )

        return jsonify({
            'exito': True,
            'mensaje': 'Documento subido correctamente',
            'datos': documento.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error subiendo documento: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e),
            'codigo': 'ERROR_SUBIDA'
        }), 400


@bp_pdf_api.route('/documentos', methods=['GET'])
@requiere_autenticacion
def listar_documentos():
    """
    Lista los documentos del usuario.

    GET /api/pdf/documentos?pagina=1&por_pagina=20

    Returns:
        JSON con lista paginada de documentos
    """
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = request.args.get('por_pagina', 20, type=int)

    try:
        servicio = obtener_servicio_pdf()
        resultado = servicio.listar_documentos(
            usuario_id=obtener_usuario_id(),
            pagina=pagina,
            por_pagina=por_pagina
        )

        return jsonify({
            'exito': True,
            'datos': resultado.to_dict()
        })

    except Exception as e:
        logger.error(f"Error listando documentos: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 500


@bp_pdf_api.route('/documentos/<int:id>', methods=['GET'])
@requiere_autenticacion
def obtener_documento(id):
    """
    Obtiene un documento por ID.

    GET /api/pdf/documentos/<id>

    Returns:
        JSON con datos del documento
    """
    try:
        servicio = obtener_servicio_pdf()
        documento = servicio.obtener_documento(
            documento_id=id,
            usuario_id=obtener_usuario_id()
        )

        return jsonify({
            'exito': True,
            'datos': documento.to_dict()
        })

    except Exception as e:
        logger.error(f"Error obteniendo documento {id}: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 404


@bp_pdf_api.route('/documentos/<int:id>', methods=['DELETE'])
@requiere_autenticacion
def eliminar_documento(id):
    """
    Elimina un documento.

    DELETE /api/pdf/documentos/<id>?permanente=false

    Returns:
        JSON con resultado
    """
    permanente = request.args.get('permanente', 'false').lower() == 'true'

    try:
        servicio = obtener_servicio_pdf()
        resultado = servicio.eliminar_documento(
            documento_id=id,
            usuario_id=obtener_usuario_id(),
            permanente=permanente
        )

        return jsonify({
            'exito': resultado,
            'mensaje': 'Documento eliminado' if resultado else 'No se pudo eliminar'
        })

    except Exception as e:
        logger.error(f"Error eliminando documento {id}: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


@bp_pdf_api.route('/documentos/<int:id>/render/<int:pagina>', methods=['GET'])
@requiere_autenticacion
def renderizar_pagina(id, pagina):
    """
    Renderiza una página a imagen.

    GET /api/pdf/documentos/<id>/render/<pagina>?zoom=1.0&formato=png

    Returns:
        Imagen PNG/JPEG
    """
    zoom = request.args.get('zoom', 1.0, type=float)
    formato = request.args.get('formato', 'png')

    try:
        servicio = obtener_servicio_pdf()
        imagen = servicio.renderizar_pagina(
            documento_id=id,
            pagina=pagina,
            usuario_id=obtener_usuario_id(),
            zoom=zoom,
            formato=formato
        )

        mimetype = 'image/png' if formato == 'png' else 'image/jpeg'
        from io import BytesIO
        return send_file(
            BytesIO(imagen),
            mimetype=mimetype,
            as_attachment=False
        )

    except Exception as e:
        logger.error(f"Error renderizando página {pagina} de doc {id}: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


@bp_pdf_api.route('/documentos/<int:id>/thumbnail/<int:pagina>', methods=['GET'])
@requiere_autenticacion
def obtener_thumbnail(id, pagina):
    """
    Obtiene miniatura de una página.

    GET /api/pdf/documentos/<id>/thumbnail/<pagina>?ancho=150

    Returns:
        Imagen PNG
    """
    ancho = request.args.get('ancho', 150, type=int)

    try:
        servicio = obtener_servicio_pdf()
        imagen = servicio.obtener_thumbnail(
            documento_id=id,
            pagina=pagina,
            usuario_id=obtener_usuario_id(),
            ancho=ancho
        )

        from io import BytesIO
        return send_file(
            BytesIO(imagen),
            mimetype='image/png',
            as_attachment=False
        )

    except Exception as e:
        logger.error(f"Error generando thumbnail: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


@bp_pdf_api.route('/documentos/<int:id>/descargar', methods=['GET'])
@requiere_autenticacion
def descargar_documento(id):
    """
    Descarga el archivo PDF original.

    GET /api/pdf/documentos/<id>/descargar

    Returns:
        Archivo PDF
    """
    try:
        servicio = obtener_servicio_pdf()
        documento = servicio.obtener_documento(
            documento_id=id,
            usuario_id=obtener_usuario_id()
        )

        # Obtener ruta del archivo
        from ...infraestructura.persistencia.repositorio_documento_postgresql import RepositorioDocumentoPostgreSQL
        entidad = servicio.repositorio_documento.obtener_por_id(id)

        if not entidad or not os.path.exists(entidad.ruta_archivo):
            return jsonify({
                'exito': False,
                'mensaje': 'Archivo no encontrado'
            }), 404

        return send_file(
            entidad.ruta_archivo,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=documento.nombre_original
        )

    except Exception as e:
        logger.error(f"Error descargando documento {id}: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


# =============================================================================
# ENDPOINTS DE PÁGINAS
# =============================================================================

@bp_pdf_api.route('/documentos/<int:id>/paginas', methods=['GET'])
@requiere_autenticacion
def obtener_paginas(id):
    """
    Obtiene información de todas las páginas.

    GET /api/pdf/documentos/<id>/paginas

    Returns:
        JSON con lista de páginas
    """
    try:
        servicio = obtener_servicio_pdf()
        paginas = servicio.obtener_paginas(
            documento_id=id,
            usuario_id=obtener_usuario_id()
        )

        return jsonify({
            'exito': True,
            'datos': [p.to_dict() for p in paginas]
        })

    except Exception as e:
        logger.error(f"Error obteniendo páginas: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


@bp_pdf_api.route('/documentos/<int:id>/paginas/<int:pagina>/rotar', methods=['POST'])
@requiere_autenticacion
def rotar_pagina(id, pagina):
    """
    Rota una página.

    POST /api/pdf/documentos/<id>/paginas/<pagina>/rotar
    Body: {"grados": 90}

    Returns:
        JSON con documento actualizado
    """
    datos = request.get_json() or {}
    grados = datos.get('grados', 90)

    try:
        servicio = obtener_servicio_pdf()
        documento = servicio.rotar_pagina(
            documento_id=id,
            pagina=pagina,
            grados=grados,
            usuario_id=obtener_usuario_id()
        )

        return jsonify({
            'exito': True,
            'mensaje': f'Página {pagina} rotada {grados}°',
            'datos': documento.to_dict()
        })

    except Exception as e:
        logger.error(f"Error rotando página: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


@bp_pdf_api.route('/documentos/<int:id>/paginas/<int:pagina>', methods=['DELETE'])
@requiere_autenticacion
def eliminar_pagina(id, pagina):
    """
    Elimina una página.

    DELETE /api/pdf/documentos/<id>/paginas/<pagina>

    Returns:
        JSON con documento actualizado
    """
    try:
        servicio = obtener_servicio_pdf()
        documento = servicio.eliminar_pagina(
            documento_id=id,
            pagina=pagina,
            usuario_id=obtener_usuario_id()
        )

        return jsonify({
            'exito': True,
            'mensaje': f'Página {pagina} eliminada',
            'datos': documento.to_dict()
        })

    except Exception as e:
        logger.error(f"Error eliminando página: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


@bp_pdf_api.route('/documentos/<int:id>/paginas/reordenar', methods=['POST'])
@requiere_autenticacion
def reordenar_paginas(id):
    """
    Reordena las páginas.

    POST /api/pdf/documentos/<id>/paginas/reordenar
    Body: {"orden": [3, 1, 2]}

    Returns:
        JSON con documento actualizado
    """
    datos = request.get_json() or {}
    orden = datos.get('orden', [])

    if not orden:
        return jsonify({
            'exito': False,
            'mensaje': 'Se requiere el nuevo orden'
        }), 400

    try:
        servicio = obtener_servicio_pdf()
        documento = servicio.reordenar_paginas(
            documento_id=id,
            orden_nuevo=orden,
            usuario_id=obtener_usuario_id()
        )

        return jsonify({
            'exito': True,
            'mensaje': 'Páginas reordenadas',
            'datos': documento.to_dict()
        })

    except Exception as e:
        logger.error(f"Error reordenando páginas: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


# =============================================================================
# ENDPOINTS DE BÚSQUEDA
# =============================================================================

@bp_pdf_api.route('/buscar', methods=['GET'])
@requiere_autenticacion
def buscar_en_biblioteca():
    """
    Busca en todos los documentos del usuario.

    GET /api/pdf/buscar?q=<termino>

    Returns:
        JSON con documentos que coinciden
    """
    termino = request.args.get('q', '')

    if len(termino) < 2:
        return jsonify({
            'exito': False,
            'mensaje': 'El término de búsqueda debe tener al menos 2 caracteres'
        }), 400

    try:
        servicio = obtener_servicio_pdf()
        documentos = servicio.buscar_documentos(
            usuario_id=obtener_usuario_id(),
            termino=termino
        )

        return jsonify({
            'exito': True,
            'datos': [d.to_dict() for d in documentos]
        })

    except Exception as e:
        logger.error(f"Error buscando: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 500


@bp_pdf_api.route('/documentos/<int:id>/buscar', methods=['GET'])
@requiere_autenticacion
def buscar_en_documento(id):
    """
    Busca texto dentro de un documento.

    GET /api/pdf/documentos/<id>/buscar?q=<termino>

    Returns:
        JSON con posiciones encontradas
    """
    termino = request.args.get('q', '')

    if not termino:
        return jsonify({
            'exito': False,
            'mensaje': 'Se requiere término de búsqueda'
        }), 400

    try:
        servicio = obtener_servicio_pdf()

        # Verificar acceso
        servicio.obtener_documento(id, obtener_usuario_id())

        # Buscar usando cliente PDF
        if servicio.cliente_pdf:
            entidad = servicio.repositorio_documento.obtener_por_id(id)
            resultados = servicio.cliente_pdf.buscar_texto(
                entidad.ruta_archivo, termino
            )
        else:
            resultados = []

        return jsonify({
            'exito': True,
            'datos': resultados
        })

    except Exception as e:
        logger.error(f"Error buscando en documento: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 400


# =============================================================================
# ENDPOINTS DE ESTADÍSTICAS
# =============================================================================

@bp_pdf_api.route('/estadisticas', methods=['GET'])
@requiere_autenticacion
def obtener_estadisticas():
    """
    Obtiene estadísticas del usuario.

    GET /api/pdf/estadisticas

    Returns:
        JSON con estadísticas
    """
    try:
        servicio = obtener_servicio_pdf()
        stats = servicio.obtener_estadisticas(obtener_usuario_id())

        return jsonify({
            'exito': True,
            'datos': stats.to_dict()
        })

    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e)
        }), 500


# =============================================================================
# ENDPOINTS DE COMBINACIÓN
# =============================================================================

@bp_pdf_api.route('/combinar', methods=['POST'])
@requiere_autenticacion
def combinar_documentos():
    """
    Combina múltiples archivos PDF en uno solo.

    POST /api/pdf/combinar
    Body: multipart/form-data con campo 'archivos' (múltiples)

    Returns:
        Archivo PDF combinado para descarga
    """
    archivos = request.files.getlist('archivos')

    if len(archivos) < 2:
        return jsonify({
            'exito': False,
            'mensaje': 'Se requieren al menos 2 archivos PDF',
            'codigo': 'ARCHIVOS_INSUFICIENTES'
        }), 400

    import tempfile
    rutas_temp = []

    try:
        # Guardar archivos temporales
        for archivo in archivos:
            if not archivo.filename.lower().endswith('.pdf'):
                # Limpiar temporales ya creados
                for r in rutas_temp:
                    if os.path.exists(r):
                        os.remove(r)
                return jsonify({
                    'exito': False,
                    'mensaje': f'El archivo "{archivo.filename}" no es un PDF',
                    'codigo': 'FORMATO_INVALIDO'
                }), 400

            fd, ruta_temp = tempfile.mkstemp(suffix='.pdf')
            os.close(fd)
            archivo.save(ruta_temp)
            rutas_temp.append(ruta_temp)

        # Combinar usando PyMuPDF
        servicio = obtener_servicio_pdf()
        if not servicio.cliente_pdf:
            return jsonify({
                'exito': False,
                'mensaje': 'Servicio PDF no disponible',
                'codigo': 'SERVICIO_NO_DISPONIBLE'
            }), 503

        pdf_combinado = servicio.cliente_pdf.combinar_pdfs(rutas_temp)

        # Enviar resultado
        from io import BytesIO
        return send_file(
            BytesIO(pdf_combinado),
            mimetype='application/pdf',
            as_attachment=True,
            download_name='combinado.pdf'
        )

    except Exception as e:
        logger.error(f"Error combinando PDFs: {e}")
        return jsonify({
            'exito': False,
            'mensaje': str(e),
            'codigo': 'ERROR_COMBINACION'
        }), 400

    finally:
        # Limpiar archivos temporales
        for ruta in rutas_temp:
            if os.path.exists(ruta):
                os.remove(ruta)


# =============================================================================
# ENDPOINTS DE OPERACIONES DIRECTAS (reciben el PDF como upload, no usan BD)
# =============================================================================

# =============================================================================
# FIRMA DIGITAL CON CERTIFICADOS .P12
# =============================================================================



# =============================================================================
# MANEJADORES DE ERROR
# =============================================================================

@bp_pdf_api.errorhandler(Exception)
def manejar_error(error):
    """Manejador global de errores."""
    logger.error(f"Error no manejado: {error}")
    return jsonify({
        'exito': False,
        'mensaje': 'Error interno del servidor',
        'codigo': 'ERROR_INTERNO'
    }), 500


# ── Lo que se separó de aquí ────────────────────────────────────────────────
# Estos dos módulos cuelgan sus rutas del MISMO blueprint de arriba, así que hay
# que importarlos para que queden registradas. Va al final del archivo, y no
# arriba, porque ellos necesitan el blueprint ya creado.
from . import firma_p12  # noqa: E402,F401
from . import pdf_operaciones_api  # noqa: E402,F401

# Y se vuelven a publicar desde aquí las ayudas de la firma, porque
#  se las pide a este módulo desde siempre y no tiene por
# qué enterarse de que han cambiado de sitio.
from .firma_p12 import (  # noqa: E402,F401
    _cargar_p12_robusto, _fernet_firma, _generar_apariencia_firmaec,
    _ruta_clave_maestra, cifrar_password_firma, descifrar_password_firma,
    dir_certificados_usuario, firmar_pdf_una, password_guardado,
    ruta_p12_guardado,
)
from .pdf_operaciones_api import _leer_pdf_upload  # noqa: E402,F401
