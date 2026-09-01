# -*- coding: utf-8 -*-
"""
Caso de Uso: Gestionar Páginas PDF.
"""

from dataclasses import dataclass
from typing import List, Optional

from ..dtos.documento_dto import DocumentoDTO
from ..dtos.pagina_dto import ExtraerPaginasDTO
from ...dominio.excepciones import DocumentoInvalido, PaginaNoEncontrada


@dataclass
class ResultadoOperacionPaginas:
    """Resultado de una operación sobre páginas."""
    exito: bool
    documento: Optional[DocumentoDTO] = None
    mensaje: str = ''
    documento_nuevo_id: Optional[int] = None


class CasoUsoGestionarPaginas:
    """
    Caso de uso para operaciones sobre páginas.

    Incluye rotar, eliminar, reordenar, extraer y combinar páginas.
    """

    def __init__(self, servicio_pdf):
        """
        Inicializa el caso de uso.

        Args:
            servicio_pdf: Instancia de ServicioPDF
        """
        self.servicio_pdf = servicio_pdf

    def rotar_pagina(
        self,
        documento_id: int,
        pagina: int,
        grados: int,
        usuario_id: int
    ) -> ResultadoOperacionPaginas:
        """
        Rota una página.

        Args:
            documento_id: ID del documento
            pagina: Número de página
            grados: Grados a rotar (90, 180, 270, -90)
            usuario_id: ID del usuario

        Returns:
            Resultado de la operación
        """
        # Normalizar grados
        grados = grados % 360
        if grados not in (0, 90, 180, 270):
            return ResultadoOperacionPaginas(
                exito=False,
                mensaje="Los grados deben ser múltiplo de 90"
            )

        if grados == 0:
            return ResultadoOperacionPaginas(
                exito=True,
                mensaje="Sin rotación aplicada"
            )

        try:
            documento = self.servicio_pdf.rotar_pagina(
                documento_id=documento_id,
                pagina=pagina,
                grados=grados,
                usuario_id=usuario_id
            )

            return ResultadoOperacionPaginas(
                exito=True,
                documento=documento,
                mensaje=f"Página {pagina} rotada {grados}°"
            )
        except Exception as e:
            return ResultadoOperacionPaginas(
                exito=False,
                mensaje=str(e)
            )

    def eliminar_pagina(
        self,
        documento_id: int,
        pagina: int,
        usuario_id: int
    ) -> ResultadoOperacionPaginas:
        """
        Elimina una página.

        Args:
            documento_id: ID del documento
            pagina: Número de página a eliminar
            usuario_id: ID del usuario

        Returns:
            Resultado de la operación
        """
        try:
            documento = self.servicio_pdf.eliminar_pagina(
                documento_id=documento_id,
                pagina=pagina,
                usuario_id=usuario_id
            )

            return ResultadoOperacionPaginas(
                exito=True,
                documento=documento,
                mensaje=f"Página {pagina} eliminada"
            )
        except DocumentoInvalido as e:
            return ResultadoOperacionPaginas(
                exito=False,
                mensaje=str(e)
            )
        except Exception as e:
            return ResultadoOperacionPaginas(
                exito=False,
                mensaje=str(e)
            )

    def reordenar_paginas(
        self,
        documento_id: int,
        orden_nuevo: List[int],
        usuario_id: int
    ) -> ResultadoOperacionPaginas:
        """
        Reordena las páginas.

        Args:
            documento_id: ID del documento
            orden_nuevo: Nuevo orden de páginas
            usuario_id: ID del usuario

        Returns:
            Resultado de la operación
        """
        try:
            documento = self.servicio_pdf.reordenar_paginas(
                documento_id=documento_id,
                orden_nuevo=orden_nuevo,
                usuario_id=usuario_id
            )

            return ResultadoOperacionPaginas(
                exito=True,
                documento=documento,
                mensaje="Páginas reordenadas correctamente"
            )
        except Exception as e:
            return ResultadoOperacionPaginas(
                exito=False,
                mensaje=str(e)
            )

    def extraer_paginas(
        self,
        dto: ExtraerPaginasDTO,
        usuario_id: int
    ) -> ResultadoOperacionPaginas:
        """
        Extrae páginas a un nuevo documento.

        Args:
            dto: Datos de extracción
            usuario_id: ID del usuario

        Returns:
            Resultado con ID del nuevo documento
        """
        try:
            # Verificar acceso al documento original
            documento_original = self.servicio_pdf.obtener_documento(
                dto.documento_id, usuario_id
            )

            # Validar páginas
            for p in dto.paginas:
                if p < 1 or p > documento_original.num_paginas:
                    raise PaginaNoEncontrada(
                        dto.documento_id, p, documento_original.num_paginas
                    )

            # Extraer páginas usando el cliente PDF
            if not self.servicio_pdf.cliente_pdf:
                raise DocumentoInvalido("Cliente PDF no configurado")

            # El cliente PDF debe implementar extract_pages
            # que retorna bytes del nuevo PDF
            nuevo_pdf_bytes = self.servicio_pdf.cliente_pdf.extraer_paginas(
                ruta_pdf=f"{self.servicio_pdf.ruta_uploads}/documentos/{usuario_id}/{documento_original.nombre_archivo}",
                paginas=dto.paginas
            )

            # Crear nuevo documento
            from io import BytesIO
            archivo = BytesIO(nuevo_pdf_bytes)

            nombre_nuevo = dto.nombre_nuevo or f"{documento_original.nombre_original}_extracto.pdf"

            nuevo_doc = self.servicio_pdf.subir_documento(
                archivo=archivo,
                usuario_id=usuario_id,
                nombre_original=nombre_nuevo
            )

            return ResultadoOperacionPaginas(
                exito=True,
                documento=nuevo_doc,
                documento_nuevo_id=nuevo_doc.id,
                mensaje=f"Extraídas {len(dto.paginas)} páginas a nuevo documento"
            )

        except Exception as e:
            return ResultadoOperacionPaginas(
                exito=False,
                mensaje=str(e)
            )

    def combinar_documentos(
        self,
        documento_ids: List[int],
        usuario_id: int,
        nombre_nuevo: str = None
    ) -> ResultadoOperacionPaginas:
        """
        Combina múltiples documentos en uno.

        Args:
            documento_ids: IDs de documentos a combinar
            usuario_id: ID del usuario
            nombre_nuevo: Nombre del documento combinado

        Returns:
            Resultado con ID del nuevo documento
        """
        try:
            if len(documento_ids) < 2:
                return ResultadoOperacionPaginas(
                    exito=False,
                    mensaje="Se necesitan al menos 2 documentos para combinar"
                )

            # Verificar acceso a todos los documentos
            rutas = []
            for doc_id in documento_ids:
                doc = self.servicio_pdf.obtener_documento(doc_id, usuario_id)
                ruta = f"{self.servicio_pdf.ruta_uploads}/documentos/{usuario_id}/{doc.nombre_archivo}"
                rutas.append(ruta)

            # Combinar usando el cliente PDF
            if not self.servicio_pdf.cliente_pdf:
                raise DocumentoInvalido("Cliente PDF no configurado")

            pdf_combinado = self.servicio_pdf.cliente_pdf.combinar_pdfs(rutas)

            # Crear nuevo documento
            from io import BytesIO
            archivo = BytesIO(pdf_combinado)

            nombre = nombre_nuevo or "documento_combinado.pdf"

            nuevo_doc = self.servicio_pdf.subir_documento(
                archivo=archivo,
                usuario_id=usuario_id,
                nombre_original=nombre
            )

            return ResultadoOperacionPaginas(
                exito=True,
                documento=nuevo_doc,
                documento_nuevo_id=nuevo_doc.id,
                mensaje=f"Combinados {len(documento_ids)} documentos"
            )

        except Exception as e:
            return ResultadoOperacionPaginas(
                exito=False,
                mensaje=str(e)
            )
