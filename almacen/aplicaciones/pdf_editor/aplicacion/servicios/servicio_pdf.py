# -*- coding: utf-8 -*-
"""
Servicio de Aplicación: Orquestador principal del Editor PDF.

Coordina todas las operaciones del editor PDF, delegando
la lógica de negocio al dominio y la persistencia a la infraestructura.
"""

import os
import logging
from typing import Optional, List, Dict, Any, BinaryIO
from datetime import datetime

from ..dtos.documento_dto import DocumentoDTO, DocumentoResumenDTO, SubirDocumentoDTO
from ..dtos.pagina_dto import PaginaDTO, ThumbnailDTO, RenderPaginaDTO
from ..dtos.respuesta_dto import RespuestaAPI, PaginacionDTO, RespuestaPaginada, EstadisticasDTO
from ...dominio.entidades.documento_pdf import DocumentoPDF
from ...dominio.entidades.pagina import Pagina
from ...dominio.excepciones import (
    DocumentoNoEncontrado,
    DocumentoInvalido,
    PaginaNoEncontrada,
    PermisoInsuficiente,
    ArchivoMuyGrande,
    FormatoNoSoportado
)
from ...dominio.value_objects.tipos_pdf import (
    EstadoDocumento,
    MAX_TAMANO_ARCHIVO_MB,
    EXTENSIONES_PDF
)


logger = logging.getLogger(__name__)


class ServicioPDF:
    """
    Servicio principal del Editor PDF.

    Orquesta todas las operaciones, coordinando entre:
    - Repositorios de persistencia
    - Adaptadores externos (PyMuPDF, etc.)
    - Almacenamiento de archivos
    """

    def __init__(
        self,
        repositorio_documento,
        repositorio_anotacion=None,
        repositorio_version=None,
        cliente_pdf=None,
        almacenamiento=None,
        ruta_uploads: str = None
    ):
        """
        Inicializa el servicio.

        Args:
            repositorio_documento: Implementación de IRepositorioDocumento
            repositorio_anotacion: Implementación de IRepositorioAnotacion
            repositorio_version: Implementación de IRepositorioVersion
            cliente_pdf: Adaptador de librería PDF (PyMuPDF, etc.)
            almacenamiento: Servicio de almacenamiento de archivos
            ruta_uploads: Ruta base para subidas
        """
        self.repositorio_documento = repositorio_documento
        self.repositorio_anotacion = repositorio_anotacion
        self.repositorio_version = repositorio_version
        self.cliente_pdf = cliente_pdf
        self.almacenamiento = almacenamiento
        self.ruta_uploads = ruta_uploads or '/home/sistemas/Maquita/uploads/pdf_editor'

    # =========================================================================
    # OPERACIONES DE DOCUMENTO
    # =========================================================================

    def subir_documento(
        self,
        archivo: BinaryIO,
        usuario_id: int,
        nombre_original: str = None
    ) -> DocumentoDTO:
        """
        Sube un nuevo documento PDF.

        Args:
            archivo: Archivo PDF (file-like object)
            usuario_id: ID del usuario que sube
            nombre_original: Nombre original del archivo

        Returns:
            DTO del documento creado

        Raises:
            ArchivoMuyGrande: Si excede el tamaño máximo
            FormatoNoSoportado: Si no es PDF
            DocumentoInvalido: Si el PDF está corrupto
        """
        # Obtener nombre si no se proporcionó
        if not nombre_original and hasattr(archivo, 'filename'):
            nombre_original = archivo.filename

        # Validar extensión
        extension = os.path.splitext(nombre_original or '')[1].lower()
        if extension not in EXTENSIONES_PDF:
            raise FormatoNoSoportado(extension, list(EXTENSIONES_PDF))

        # Leer contenido para validar tamaño
        contenido = archivo.read()
        tamano_mb = len(contenido) / (1024 * 1024)

        if tamano_mb > MAX_TAMANO_ARCHIVO_MB:
            raise ArchivoMuyGrande(tamano_mb, MAX_TAMANO_ARCHIVO_MB)

        # Crear directorio del usuario si no existe
        ruta_usuario = os.path.join(self.ruta_uploads, 'documentos', str(usuario_id))
        os.makedirs(ruta_usuario, exist_ok=True)

        # Crear entidad de documento
        documento = DocumentoPDF.crear_nuevo(
            usuario_id=usuario_id,
            nombre_original=nombre_original,
            ruta_base=os.path.join(self.ruta_uploads, 'documentos'),
            tamano_bytes=len(contenido)
        )

        # Guardar archivo
        ruta_completa = os.path.join(ruta_usuario, documento.nombre_archivo)
        with open(ruta_completa, 'wb') as f:
            f.write(contenido)

        documento.ruta_archivo = ruta_completa

        # Validar PDF y extraer metadata
        try:
            if self.cliente_pdf:
                info = self.cliente_pdf.obtener_info(ruta_completa)
                documento.establecer_num_paginas(info.get('num_paginas', 1))
                documento.actualizar_metadata(info.get('metadata', {}))
        except Exception as e:
            # Limpiar archivo si falla
            if os.path.exists(ruta_completa):
                os.remove(ruta_completa)
            raise DocumentoInvalido(str(e), razon=str(e))

        # Persistir en base de datos
        documento = self.repositorio_documento.guardar(documento)

        logger.info(f"Documento subido: {documento.id} por usuario {usuario_id}")

        return DocumentoDTO.desde_entidad(documento, usuario_id)

    def obtener_documento(
        self,
        documento_id: int,
        usuario_id: int
    ) -> DocumentoDTO:
        """
        Obtiene un documento por ID.

        Args:
            documento_id: ID del documento
            usuario_id: ID del usuario que solicita

        Returns:
            DTO del documento

        Raises:
            DocumentoNoEncontrado: Si no existe
            PermisoInsuficiente: Si no tiene acceso
        """
        documento = self.repositorio_documento.obtener_por_id(documento_id)

        if not documento:
            raise DocumentoNoEncontrado(documento_id)

        if not documento.es_accesible_por(usuario_id):
            raise PermisoInsuficiente('ver', documento_id, usuario_id)

        return DocumentoDTO.desde_entidad(documento, usuario_id)

    def listar_documentos(
        self,
        usuario_id: int,
        pagina: int = 1,
        por_pagina: int = 20,
        incluir_eliminados: bool = False
    ) -> RespuestaPaginada:
        """
        Lista los documentos de un usuario con paginación.

        Args:
            usuario_id: ID del usuario
            pagina: Número de página
            por_pagina: Documentos por página
            incluir_eliminados: Si incluir eliminados

        Returns:
            Respuesta paginada con documentos
        """
        offset = (pagina - 1) * por_pagina

        documentos = self.repositorio_documento.obtener_por_usuario(
            usuario_id=usuario_id,
            incluir_eliminados=incluir_eliminados,
            limite=por_pagina,
            offset=offset
        )

        total = self.repositorio_documento.contar_por_usuario(usuario_id)
        paginacion = PaginacionDTO.calcular(total, pagina, por_pagina)

        items = [DocumentoResumenDTO.desde_entidad(d) for d in documentos]

        return RespuestaPaginada(items=items, paginacion=paginacion)

    def buscar_documentos(
        self,
        usuario_id: int,
        termino: str,
        limite: int = 50
    ) -> List[DocumentoResumenDTO]:
        """
        Busca documentos por texto.

        Args:
            usuario_id: ID del usuario
            termino: Término de búsqueda
            limite: Máximo de resultados

        Returns:
            Lista de documentos que coinciden
        """
        documentos = self.repositorio_documento.buscar(
            usuario_id=usuario_id,
            termino=termino,
            limite=limite
        )

        return [DocumentoResumenDTO.desde_entidad(d) for d in documentos]

    def eliminar_documento(
        self,
        documento_id: int,
        usuario_id: int,
        permanente: bool = False
    ) -> bool:
        """
        Elimina un documento.

        Args:
            documento_id: ID del documento
            usuario_id: ID del usuario
            permanente: Si eliminar permanentemente

        Returns:
            True si se eliminó

        Raises:
            DocumentoNoEncontrado: Si no existe
            PermisoInsuficiente: Si no es propietario
        """
        documento = self.repositorio_documento.obtener_por_id(documento_id)

        if not documento:
            raise DocumentoNoEncontrado(documento_id)

        if documento.usuario_id != usuario_id:
            raise PermisoInsuficiente('eliminar', documento_id, usuario_id)

        if permanente:
            # Eliminar archivo físico
            if os.path.exists(documento.ruta_archivo):
                os.remove(documento.ruta_archivo)

            # Eliminar caché de renderizado
            ruta_cache = os.path.join(
                self.ruta_uploads, 'render_cache', str(documento_id)
            )
            if os.path.exists(ruta_cache):
                import shutil
                shutil.rmtree(ruta_cache)

            return self.repositorio_documento.eliminar_permanente(documento_id)
        else:
            return self.repositorio_documento.eliminar(documento_id)

    # =========================================================================
    # OPERACIONES DE PÁGINA
    # =========================================================================

    def obtener_paginas(
        self,
        documento_id: int,
        usuario_id: int
    ) -> List[PaginaDTO]:
        """
        Obtiene información de todas las páginas.

        Args:
            documento_id: ID del documento
            usuario_id: ID del usuario

        Returns:
            Lista de DTOs de páginas
        """
        documento = self._verificar_acceso(documento_id, usuario_id)

        if not self.cliente_pdf:
            return []

        paginas = self.cliente_pdf.obtener_paginas(documento.ruta_archivo)
        return [PaginaDTO.desde_entidad(p) for p in paginas]

    def renderizar_pagina(
        self,
        documento_id: int,
        pagina: int,
        usuario_id: int,
        zoom: float = 1.0,
        formato: str = 'png'
    ) -> bytes:
        """
        Renderiza una página a imagen.

        Args:
            documento_id: ID del documento
            pagina: Número de página (1-indexed)
            usuario_id: ID del usuario
            zoom: Nivel de zoom (1.0 = 100%)
            formato: Formato de salida (png, jpeg)

        Returns:
            Bytes de la imagen

        Raises:
            PaginaNoEncontrada: Si la página no existe
        """
        documento = self._verificar_acceso(documento_id, usuario_id)

        if not self.cliente_pdf:
            raise DocumentoInvalido("Cliente PDF no configurado")

        # Verificar que la página existe
        if pagina < 1 or (documento.num_paginas and pagina > documento.num_paginas):
            raise PaginaNoEncontrada(documento_id, pagina, documento.num_paginas)

        # Renderizar
        return self.cliente_pdf.renderizar_pagina(
            ruta_pdf=documento.ruta_archivo,
            pagina=pagina,
            zoom=zoom,
            formato=formato
        )

    def obtener_thumbnail(
        self,
        documento_id: int,
        pagina: int,
        usuario_id: int,
        ancho: int = 150
    ) -> bytes:
        """
        Obtiene la miniatura de una página.

        Args:
            documento_id: ID del documento
            pagina: Número de página
            usuario_id: ID del usuario
            ancho: Ancho de la miniatura en pixels

        Returns:
            Bytes de la imagen miniatura
        """
        documento = self._verificar_acceso(documento_id, usuario_id)

        # Verificar caché
        ruta_cache = os.path.join(
            self.ruta_uploads,
            'render_cache',
            str(documento_id),
            f'thumb_{pagina:03d}_{ancho}.png'
        )

        if os.path.exists(ruta_cache):
            with open(ruta_cache, 'rb') as f:
                return f.read()

        # Generar miniatura
        if not self.cliente_pdf:
            raise DocumentoInvalido("Cliente PDF no configurado")

        imagen = self.cliente_pdf.generar_thumbnail(
            ruta_pdf=documento.ruta_archivo,
            pagina=pagina,
            ancho=ancho
        )

        # Guardar en caché
        os.makedirs(os.path.dirname(ruta_cache), exist_ok=True)
        with open(ruta_cache, 'wb') as f:
            f.write(imagen)

        return imagen

    def rotar_pagina(
        self,
        documento_id: int,
        pagina: int,
        grados: int,
        usuario_id: int
    ) -> DocumentoDTO:
        """
        Rota una página del documento.

        Args:
            documento_id: ID del documento
            pagina: Número de página
            grados: Grados a rotar (90, 180, 270)
            usuario_id: ID del usuario

        Returns:
            DTO del documento actualizado
        """
        documento = self._verificar_propietario(documento_id, usuario_id)

        if not self.cliente_pdf:
            raise DocumentoInvalido("Cliente PDF no configurado")

        # Rotar y guardar
        self.cliente_pdf.rotar_pagina(
            ruta_pdf=documento.ruta_archivo,
            pagina=pagina,
            grados=grados
        )

        # Limpiar caché de esa página
        self._limpiar_cache_pagina(documento_id, pagina)

        # Crear versión si está habilitado
        if self.repositorio_version:
            self._crear_version(documento, f"Rotar página {pagina} ({grados}°)", usuario_id)

        return DocumentoDTO.desde_entidad(documento, usuario_id)

    def eliminar_pagina(
        self,
        documento_id: int,
        pagina: int,
        usuario_id: int
    ) -> DocumentoDTO:
        """
        Elimina una página del documento.

        Args:
            documento_id: ID del documento
            pagina: Número de página a eliminar
            usuario_id: ID del usuario

        Returns:
            DTO del documento actualizado
        """
        documento = self._verificar_propietario(documento_id, usuario_id)

        if documento.num_paginas <= 1:
            raise DocumentoInvalido("No se puede eliminar la única página")

        if not self.cliente_pdf:
            raise DocumentoInvalido("Cliente PDF no configurado")

        # Eliminar página
        self.cliente_pdf.eliminar_pagina(
            ruta_pdf=documento.ruta_archivo,
            pagina=pagina
        )

        # Actualizar número de páginas
        documento.establecer_num_paginas(documento.num_paginas - 1)
        documento = self.repositorio_documento.guardar(documento)

        # Limpiar toda la caché (las páginas se renumeran)
        self._limpiar_cache_documento(documento_id)

        return DocumentoDTO.desde_entidad(documento, usuario_id)

    def reordenar_paginas(
        self,
        documento_id: int,
        orden_nuevo: List[int],
        usuario_id: int
    ) -> DocumentoDTO:
        """
        Reordena las páginas del documento.

        Args:
            documento_id: ID del documento
            orden_nuevo: Lista con el nuevo orden (ej: [3, 1, 2])
            usuario_id: ID del usuario

        Returns:
            DTO del documento actualizado
        """
        documento = self._verificar_propietario(documento_id, usuario_id)

        if not self.cliente_pdf:
            raise DocumentoInvalido("Cliente PDF no configurado")

        # Validar orden
        if len(orden_nuevo) != documento.num_paginas:
            raise DocumentoInvalido(
                f"El orden debe tener {documento.num_paginas} páginas"
            )

        self.cliente_pdf.reordenar_paginas(
            ruta_pdf=documento.ruta_archivo,
            orden=orden_nuevo
        )

        # Limpiar caché
        self._limpiar_cache_documento(documento_id)

        return DocumentoDTO.desde_entidad(documento, usuario_id)

    # =========================================================================
    # ESTADÍSTICAS
    # =========================================================================

    def obtener_estadisticas(self, usuario_id: int) -> EstadisticasDTO:
        """
        Obtiene estadísticas del usuario.

        Args:
            usuario_id: ID del usuario

        Returns:
            DTO con estadísticas
        """
        stats = self.repositorio_documento.obtener_estadisticas(usuario_id)

        return EstadisticasDTO(
            total_documentos=stats.get('total_documentos', 0),
            total_paginas=stats.get('total_paginas', 0),
            espacio_usado_bytes=stats.get('espacio_usado_bytes', 0),
            documentos_con_ocr=stats.get('documentos_con_ocr', 0),
            total_anotaciones=stats.get('total_anotaciones', 0),
            total_formularios=stats.get('total_formularios', 0)
        )

    # =========================================================================
    # MÉTODOS AUXILIARES
    # =========================================================================

    def _verificar_acceso(self, documento_id: int, usuario_id: int) -> DocumentoPDF:
        """Verifica acceso de lectura a un documento."""
        documento = self.repositorio_documento.obtener_por_id(documento_id)

        if not documento:
            raise DocumentoNoEncontrado(documento_id)

        if not documento.es_accesible_por(usuario_id):
            raise PermisoInsuficiente('ver', documento_id, usuario_id)

        return documento

    def _verificar_propietario(self, documento_id: int, usuario_id: int) -> DocumentoPDF:
        """Verifica que el usuario sea propietario."""
        documento = self.repositorio_documento.obtener_por_id(documento_id)

        if not documento:
            raise DocumentoNoEncontrado(documento_id)

        if documento.usuario_id != usuario_id:
            raise PermisoInsuficiente('editar', documento_id, usuario_id)

        return documento

    def _limpiar_cache_pagina(self, documento_id: int, pagina: int) -> None:
        """Limpia la caché de una página específica."""
        import glob

        patron = os.path.join(
            self.ruta_uploads,
            'render_cache',
            str(documento_id),
            f'*_{pagina:03d}_*'
        )

        for archivo in glob.glob(patron):
            try:
                os.remove(archivo)
            except Exception:
                pass

    def _limpiar_cache_documento(self, documento_id: int) -> None:
        """Limpia toda la caché de un documento."""
        import shutil

        ruta_cache = os.path.join(
            self.ruta_uploads,
            'render_cache',
            str(documento_id)
        )

        if os.path.exists(ruta_cache):
            shutil.rmtree(ruta_cache)

    def _crear_version(
        self,
        documento: DocumentoPDF,
        descripcion: str,
        usuario_id: int
    ) -> None:
        """Crea una versión del documento."""
        if not self.repositorio_version:
            return

        from ...dominio.entidades.version import VersionDocumento
        import shutil

        # Obtener siguiente número de versión
        num_version = self.repositorio_version.obtener_numero_siguiente(documento.id)

        # Copiar archivo
        ruta_version = os.path.join(
            self.ruta_uploads,
            'versiones',
            str(documento.id),
            f'v{num_version}.pdf'
        )
        os.makedirs(os.path.dirname(ruta_version), exist_ok=True)
        shutil.copy2(documento.ruta_archivo, ruta_version)

        # Crear registro
        version = VersionDocumento(
            documento_id=documento.id,
            numero_version=num_version,
            ruta_archivo=ruta_version,
            usuario_id=usuario_id,
            descripcion=descripcion
        )

        self.repositorio_version.guardar(version)
