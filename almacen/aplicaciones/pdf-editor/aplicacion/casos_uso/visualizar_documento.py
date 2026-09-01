# -*- coding: utf-8 -*-
"""
Caso de Uso: Visualizar Documento PDF.
"""

from dataclasses import dataclass
from typing import Optional, List

from ..dtos.documento_dto import DocumentoDTO
from ..dtos.pagina_dto import PaginaDTO, ThumbnailDTO
from ...dominio.excepciones import DocumentoNoEncontrado, PermisoInsuficiente


@dataclass
class SolicitudVisualizacion:
    """Solicitud para visualizar un documento."""
    documento_id: int
    usuario_id: int
    pagina_inicial: int = 1


@dataclass
class ResultadoVisualizacion:
    """Resultado de la visualización."""
    documento: DocumentoDTO
    paginas: List[PaginaDTO]
    pagina_actual: int
    total_paginas: int


class CasoUsoVisualizarDocumento:
    """
    Caso de uso para visualizar un documento PDF.

    Coordina la carga de un documento con sus páginas
    y prepara los datos necesarios para el visor.
    """

    def __init__(self, servicio_pdf):
        """
        Inicializa el caso de uso.

        Args:
            servicio_pdf: Instancia de ServicioPDF
        """
        self.servicio_pdf = servicio_pdf

    def ejecutar(self, solicitud: SolicitudVisualizacion) -> ResultadoVisualizacion:
        """
        Ejecuta el caso de uso.

        Args:
            solicitud: Datos de la solicitud

        Returns:
            Resultado con documento y páginas

        Raises:
            DocumentoNoEncontrado: Si el documento no existe
            PermisoInsuficiente: Si no tiene acceso
        """
        # Obtener documento
        documento = self.servicio_pdf.obtener_documento(
            documento_id=solicitud.documento_id,
            usuario_id=solicitud.usuario_id
        )

        # Obtener información de páginas
        paginas = self.servicio_pdf.obtener_paginas(
            documento_id=solicitud.documento_id,
            usuario_id=solicitud.usuario_id
        )

        # Validar página inicial
        pagina_actual = solicitud.pagina_inicial
        if pagina_actual < 1:
            pagina_actual = 1
        elif pagina_actual > documento.num_paginas:
            pagina_actual = documento.num_paginas

        return ResultadoVisualizacion(
            documento=documento,
            paginas=paginas,
            pagina_actual=pagina_actual,
            total_paginas=documento.num_paginas
        )

    def obtener_pagina_renderizada(
        self,
        documento_id: int,
        usuario_id: int,
        pagina: int,
        zoom: float = 1.0
    ) -> bytes:
        """
        Obtiene una página renderizada.

        Args:
            documento_id: ID del documento
            usuario_id: ID del usuario
            pagina: Número de página
            zoom: Nivel de zoom

        Returns:
            Bytes de la imagen
        """
        return self.servicio_pdf.renderizar_pagina(
            documento_id=documento_id,
            pagina=pagina,
            usuario_id=usuario_id,
            zoom=zoom
        )

    def obtener_miniaturas(
        self,
        documento_id: int,
        usuario_id: int,
        paginas: List[int] = None
    ) -> List[ThumbnailDTO]:
        """
        Obtiene miniaturas de las páginas.

        Args:
            documento_id: ID del documento
            usuario_id: ID del usuario
            paginas: Lista de páginas (None = todas)

        Returns:
            Lista de miniaturas
        """
        documento = self.servicio_pdf.obtener_documento(documento_id, usuario_id)

        if paginas is None:
            paginas = list(range(1, documento.num_paginas + 1))

        thumbnails = []
        for num_pagina in paginas:
            try:
                datos = self.servicio_pdf.obtener_thumbnail(
                    documento_id=documento_id,
                    pagina=num_pagina,
                    usuario_id=usuario_id
                )

                import base64
                thumbnails.append(ThumbnailDTO(
                    documento_id=documento_id,
                    pagina=num_pagina,
                    ancho=150,
                    alto=200,  # Aproximado
                    formato='png',
                    datos_base64=base64.b64encode(datos).decode('utf-8'),
                    url=f'/api/pdf/documentos/{documento_id}/thumbnail/{num_pagina}'
                ))
            except Exception:
                # Si falla una miniatura, continuar con las demás
                pass

        return thumbnails
