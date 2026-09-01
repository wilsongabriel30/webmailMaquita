# -*- coding: utf-8 -*-
"""
Controlador Web - PDF Editor.

Blueprint para las vistas web del editor PDF.
Estructura 1:1 con Adobe Acrobat:
- HOME: Pantalla principal con herramientas y recientes
- EDITOR: Solo se abre con documento cargado
"""

import os
import logging
import threading
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

# Obtener ruta absoluta de templates
_current_dir = os.path.dirname(os.path.abspath(__file__))
_template_folder = os.path.join(_current_dir, 'plantillas')

bp_pdf_web = Blueprint(
    'pdf_editor_web',
    __name__,
    template_folder=_template_folder
)


def obtener_servicio_pdf():
    """Obtiene el servicio PDF."""
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

        g.servicio_pdf = ServicioPDF(
            repositorio_documento=repositorio,
            cliente_pdf=cliente_pdf,
            ruta_uploads='/home/sistemas/Maquita/uploads/pdf_editor'
        )
        g.db_session = db_session

    return g.servicio_pdf


@bp_pdf_web.teardown_request
def cerrar_sesion_db(exception=None):
    """Cierra la sesión de BD al finalizar la solicitud."""
    db_session = g.pop('db_session', None)
    if db_session is not None:
        db_session.close()


# ============================================================
# HOME PDF - Pantalla principal (como Acrobat Reader)
# ============================================================
@bp_pdf_web.route('/')
@login_required
def index():
    """
    HOME PDF - Pantalla principal estilo Acrobat.

    Muestra:
    - Herramientas recomendadas
    - Documentos recientes
    - Acciones rapidas

    NO muestra editor, canvas ni paginas.
    """
    # Obtener documentos recientes (mock por ahora)
    recientes = []

    return render_template(
        'pdf_editor/home.html',
        titulo='PDF - FARO Maquita',
        recientes=recientes
    )


# ============================================================
# EDITOR PDF - Solo con documento
# ============================================================
@bp_pdf_web.after_request
def add_no_cache_headers(response):
    if 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


def _calentar_ayudantes():
    """Deja listos los procesos que harán el trabajo con el PDF.

    Levantarlos cuesta unos segundos, y quien los pagaría es el primer usuario
    que guarde algo. Como abrir el editor siempre va antes que editar, se
    aprovecha ese momento y se hace aparte, sin que la página espere.
    """
    def trabajo():
        try:
            from ...infraestructura.externos import pool_pdf
            pool_pdf.preparar()
        except Exception:
            logger.debug('no se pudieron preparar los ayudantes de PDF',
                         exc_info=True)
    try:
        threading.Thread(target=trabajo, daemon=True).start()
    except Exception:
        pass


@bp_pdf_web.route('/editor/nuevo')
@login_required
def editor_nuevo():
    """
    Editor PDF para documento nuevo.

    El documento se carga desde sessionStorage (cliente).
    Si no hay documento pendiente, redirige a HOME.
    """
    _calentar_ayudantes()
    return render_template(
        'pdf_editor/index.html',
        titulo='Editor PDF',
        modo='nuevo'
    )


@bp_pdf_web.route('/editor/<int:id>')
@login_required
def editor(id):
    """
    Editor de PDF con documento existente.

    Carga documento desde BD y lo muestra en el editor.
    """
    try:
        servicio = obtener_servicio_pdf()
        documento = servicio.obtener_documento(id, current_user.id)

        return render_template(
            'pdf_editor/index.html',
            documento=documento,
            titulo=f'Editor - {documento.nombre_original}',
            modo='editar'
        )

    except Exception as e:
        logger.error(f"Error abriendo editor: {e}")
        flash(str(e), 'error')
        return redirect(url_for('pdf_editor_web.index'))


# ============================================================
# EDITOR PDF SOBRE UN ARCHIVO DEL DRIVE (Almacen Maquita)
# ============================================================
# El PDF no se sube desde el equipo ni vive en la BD del editor: es un archivo
# que ya esta en el Drive. La pagina solo recibe SU RUTA; el navegador lo baja
# de /api/almacen/archivos/descargar y, al guardar, lo devuelve a
# POST /api/almacen/archivos, que versiona el anterior y escribe el nuevo. Asi
# el cambio queda en el Drive sin que nadie descargue y vuelva a subir a mano.
#
# Aqui NO se comprueba el permiso sobre el archivo: el dueno de los archivos es
# el motor del Almacen, y es el quien lo valida en cada peticion (bajar y
# guardar). Duplicar la comprobacion aqui solo daria dos verdades que se pueden
# desincronizar.
@bp_pdf_web.route('/editor/drive')
@login_required
def editor_drive():
    """Editor PDF trabajando directamente sobre un archivo del Drive."""
    ruta = (request.args.get('ruta') or '').strip()
    if not ruta.lower().endswith('.pdf'):
        flash('El editor PDF solo abre archivos .pdf', 'error')
        return redirect(url_for('pdf_editor_web.index'))

    _calentar_ayudantes()
    nombre = ruta.rsplit('/', 1)[-1]
    return render_template(
        'pdf_editor/index.html',
        titulo='Editor PDF - %s' % nombre,
        modo='drive',
        drive_ruta=ruta
    )


# ============================================================
# VISOR PDF - Solo lectura
# ============================================================
@bp_pdf_web.route('/visor/<int:id>')
@login_required
def visor(id):
    """
    Visor de PDF.
    Vista de solo lectura.
    """
    try:
        servicio = obtener_servicio_pdf()
        documento = servicio.obtener_documento(id, current_user.id)

        return render_template(
            'pdf_editor/visor.html',
            documento=documento,
            titulo=f'Visor - {documento.nombre_original}'
        )

    except Exception as e:
        logger.error(f"Error abriendo visor: {e}")
        flash(str(e), 'error')
        return redirect(url_for('pdf_editor_web.index'))
